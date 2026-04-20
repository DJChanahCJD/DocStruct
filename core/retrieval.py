import json
import logging
import os
import re
import sqlite3
from difflib import SequenceMatcher
from typing import Optional

import numpy as np

from core.chunker import split_markdown_into_chunks
from core.config import get_settings
from core.text_models import build_chat_completion_kwargs, get_openai_client, resolve_text_model
from schemas.models import ChunkRecord, DocumentRecord

try:
    import faiss
except Exception:  # pragma: no cover
    faiss = None

logger = logging.getLogger(__name__)
settings = get_settings()

EMBED_MODEL = settings.embedding_model
raw_client = get_openai_client()

VECTOR_DIR = settings.vector_dir
INDEX_PATH = os.path.join(VECTOR_DIR, "faiss.index")
META_PATH = os.path.join(VECTOR_DIR, "faiss_ids.json")
DB_PATH = settings.db_path
REQUIRED_CHUNK_COLUMNS: dict[str, str] = {
    "title_path": "TEXT",
    "section_title": "TEXT",
    "chunk_type": "TEXT",
    "order_index": "INTEGER",
    "embed_text": "TEXT",
    "display_text": "TEXT",
}
ENGLISH_STOPWORDS = {
    "what", "which", "when", "where", "who", "whom", "whose", "why", "how",
    "the", "a", "an", "is", "are", "was", "were", "do", "does", "did",
    "to", "for", "of", "in", "on", "at", "and", "or", "with", "from",
    "this", "that", "these", "those", "can", "could", "shall", "should",
    "would", "about", "into", "after", "before", "include", "includes",
}


def _ensure_vector_dir() -> None:
    os.makedirs(VECTOR_DIR, exist_ok=True)


def _ensure_chunk_record_schema() -> None:
    if not os.path.exists(DB_PATH):
        return

    conn = sqlite3.connect(DB_PATH)
    try:
        cursor = conn.execute("PRAGMA table_info(chunk_records)")
        existing_columns = {row[1] for row in cursor.fetchall()}
        if not existing_columns:
            return

        for column_name, column_type in REQUIRED_CHUNK_COLUMNS.items():
            if column_name in existing_columns:
                continue
            conn.execute(f"ALTER TABLE chunk_records ADD COLUMN {column_name} {column_type}")

        conn.commit()
    finally:
        conn.close()


def _embed_texts(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []

    vectors: list[list[float]] = []
    batch_size = settings.embedding_batch_size
    for i in range(0, len(texts), batch_size):
        batch = texts[i:i + batch_size]
        resp = raw_client.embeddings.create(model=EMBED_MODEL, input=batch)
        vectors.extend([item.embedding for item in resp.data])
    return vectors


def _extract_query_terms(question: str) -> list[str]:
    terms: list[str] = []
    seen: set[str] = set()

    for token in re.findall(r"[\u4e00-\u9fff]{2,}|[A-Za-z][A-Za-z0-9_/-]{2,}", question.lower()):
        if token in ENGLISH_STOPWORDS:
            continue
        if token in seen:
            continue
        seen.add(token)
        terms.append(token)

    return terms


def _compose_display_text(title_path: str | None, display_text: str) -> str:
    parts = []
    if title_path:
        parts.append(f"标题路径: {title_path}")
    if display_text:
        parts.append(display_text)
    return "\n\n".join(parts).strip()


def _normalize_title_path(title_path: str | None) -> str:
    if not title_path:
        return ""

    cleaned = re.sub(r"[*_`#]+", "", title_path)
    cleaned = re.sub(r"\bStructured Data\s*>\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*>\s*", " > ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip(" >")


def _normalize_snippet_line(line: str) -> str:
    cleaned = line.strip()
    if not cleaned:
        return ""

    cleaned = re.sub(r"^\s*标题路径:\s*", "", cleaned)
    cleaned = re.sub(r"[*_`#]+", "", cleaned)
    cleaned = re.sub(r"\[(.*?)\]\((.*?)\)", r"\1", cleaned)
    cleaned = re.sub(r"(?m)(^|\s)\d+(?=[{\[\"'])", r"\1", cleaned)
    cleaned = re.sub(r"\bAPI endpoint:\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\bMethod:\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\bPath:\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\bSummary:\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\bDescription:\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\bBug ID:\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*\|\s*", " | ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip(" -|")


def _normalize_snippet_text(display_text: str, chunk_type: str | None) -> str:
    """
    规范化 snippet 文本，仅处理 display_text 内容。
    title_path 由调用方单独传递，不再混入 snippet。
    """
    lines = [line for line in (display_text or "").splitlines() if line.strip()]
    normalized_lines = [_normalize_snippet_line(line) for line in lines]
    normalized_lines = [line for line in normalized_lines if line]

    if chunk_type == "table":
        normalized_lines = [line for line in normalized_lines if "---" not in line]

    return "\n".join(normalized_lines).strip()


def _select_snippet_source(content: str, question: str) -> str:
    lines = [line.strip() for line in content.splitlines() if line.strip()]
    if not lines:
        return ""

    terms = _extract_query_terms(question)
    if not terms:
        return "\n".join(lines[:3])

    matched_lines = [
        line for line in lines
        if any(term in line.lower() for term in terms)
    ]
    if matched_lines:
        return "\n".join(matched_lines[:3])

    return "\n".join(lines[:3])


def _build_snippet(content: str, question: str, max_chars: int = 220) -> str:
    source = _select_snippet_source(content, question)
    compact = re.sub(r"\s+", " ", source).strip()
    if len(compact) <= max_chars:
        return compact

    terms = _extract_query_terms(question)
    lower_content = compact.lower()
    match_pos = min(
        (lower_content.find(term) for term in terms if lower_content.find(term) >= 0),
        default=-1,
    )

    if match_pos < 0:
        return compact[:max_chars].rstrip()

    start = max(0, match_pos - max_chars // 3)
    end = min(len(compact), start + max_chars)
    if end - start < max_chars:
        start = max(0, end - max_chars)

    snippet = compact[start:end].strip()
    if start > 0:
        snippet = f"...{snippet}"
    if end < len(compact):
        snippet = f"{snippet}..."
    return snippet


def _normalize_for_compare(text: str) -> str:
    cleaned = text.lower().strip()
    cleaned = re.sub(r"[`*_#>\-\|]+", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned


def _content_density(item: dict) -> tuple[int, int]:
    display_text = item.get("display_text") or ""
    chunk_type = item.get("chunk_type") or ""
    lower_text = display_text.lower()
    fact_hits = sum(
        token in lower_text
        for token in ("failed", "error", "pass", "passed", "bug #", "bug id", "/api/", "method:", "path:", "tc", "req-")
    )
    type_weight = {
        "table": 4,
        "list": 3,
        "structured": 3,
        "code": 2,
        "paragraph": 1,
    }.get(chunk_type, 0)
    return type_weight + fact_hits, len(display_text)


def _prefer_candidate(candidate: dict, chosen: dict) -> bool:
    candidate_density = _content_density(candidate)
    chosen_density = _content_density(chosen)
    if candidate_density != chosen_density:
        return candidate_density > chosen_density
    return candidate["score"] > chosen["score"]


def _title_paths_related(candidate_path: str, chosen_path: str) -> bool:
    if not candidate_path or not chosen_path:
        return False
    if candidate_path == chosen_path:
        return True
    return candidate_path.startswith(f"{chosen_path} > ") or chosen_path.startswith(f"{candidate_path} > ")


def _rank_item(item: dict) -> tuple[float, tuple[int, int]]:
    return item["score"], _content_density(item)


def _select_primary_doc_results(results: list[dict], top_k: int) -> list[dict]:
    if len(results) <= 1:
        return results

    doc_scores: dict[int, list[float]] = {}
    for item in results:
        doc_scores.setdefault(item["doc_id"], []).append(item["score"])

    ranked_docs = sorted(
        doc_scores.items(),
        key=lambda item: (len(item[1]), max(item[1])),
        reverse=True,
    )
    primary_doc, primary_scores = ranked_docs[0]
    primary_results = [item for item in results if item["doc_id"] == primary_doc]
    if len(primary_results) < 2:
        return results[:top_k]

    best_primary = max(primary_scores)
    best_other = max(
        (item["score"] for item in results if item["doc_id"] != primary_doc),
        default=-1.0,
    )
    if best_other >= best_primary * 0.8:
        return results[:top_k]

    filtered = [item for item in results if item["doc_id"] == primary_doc]
    return filtered[:top_k]


def _is_duplicate_candidate(candidate: dict, chosen: dict) -> bool:
    if candidate["doc_id"] != chosen["doc_id"]:
        return False

    candidate_path = candidate.get("title_path") or ""
    chosen_path = chosen.get("title_path") or ""
    candidate_section = candidate.get("section_title") or ""
    chosen_section = chosen.get("section_title") or ""
    candidate_order = candidate.get("order_index")
    chosen_order = chosen.get("order_index")
    if (
        candidate_path
        and candidate_path == chosen_path
        and candidate_order is not None
        and chosen_order is not None
        and abs(candidate_order - chosen_order) <= 1
    ):
        return True

    if (
        _title_paths_related(candidate_path, chosen_path)
        and candidate_order is not None
        and chosen_order is not None
        and abs(candidate_order - chosen_order) <= 3
    ):
        return True

    if (
        candidate_section
        and chosen_section
        and candidate_section == chosen_section
        and candidate_order is not None
        and chosen_order is not None
        and abs(candidate_order - chosen_order) <= 2
    ):
        candidate_type = candidate.get("chunk_type")
        chosen_type = chosen.get("chunk_type")
        if {candidate_type, chosen_type} & {"table", "list", "structured", "code"}:
            return True

    candidate_text = _normalize_for_compare(candidate["display_text"])
    chosen_text = _normalize_for_compare(chosen["display_text"])
    if not candidate_text or not chosen_text:
        return False

    shorter, longer = sorted((candidate_text, chosen_text), key=len)
    if len(shorter) >= 80 and shorter in longer:
        return True

    return SequenceMatcher(None, candidate_text[:500], chosen_text[:500]).ratio() >= 0.88


def _merge_ranked_candidates(candidates: list[dict]) -> list[dict]:
    clusters: list[dict] = []
    for item in candidates:
        duplicate_index = next(
            (idx for idx, existing in enumerate(clusters) if _is_duplicate_candidate(item, existing)),
            None,
        )
        if duplicate_index is None:
            clusters.append(item)
            continue
        if _prefer_candidate(item, clusters[duplicate_index]):
            clusters[duplicate_index] = item

    clusters.sort(key=_rank_item, reverse=True)
    return clusters


async def _rebuild_index_from_db() -> None:
    if faiss is None:
        raise RuntimeError("FAISS 不可用，请安装 faiss-cpu。")

    _ensure_chunk_record_schema()
    _ensure_vector_dir()
    chunks = await ChunkRecord.all().order_by("id")
    if not chunks:
        if os.path.exists(INDEX_PATH):
            os.remove(INDEX_PATH)
        if os.path.exists(META_PATH):
            os.remove(META_PATH)
        return

    vectors = np.array([chunk.vector for chunk in chunks], dtype="float32")
    dimension = vectors.shape[1]
    index = faiss.IndexFlatIP(dimension)
    faiss.normalize_L2(vectors)
    index.add(vectors)
    faiss.write_index(index, INDEX_PATH)

    with open(META_PATH, "w", encoding="utf-8") as f:
        json.dump([chunk.id for chunk in chunks], f, ensure_ascii=False)


def _load_index_and_ids() -> tuple[Optional["faiss.Index"], list[int]]:
    if faiss is None:
        raise RuntimeError("FAISS 不可用，请安装 faiss-cpu。")

    if not (os.path.exists(INDEX_PATH) and os.path.exists(META_PATH)):
        return None, []

    index = faiss.read_index(INDEX_PATH)
    with open(META_PATH, "r", encoding="utf-8") as f:
        chunk_ids = json.load(f)
    return index, chunk_ids


async def build_retrieval_corpus(record_id: int) -> None:
    """
    为单个文档构建分块并写入向量缓存，然后重建全局 FAISS 索引。
    """
    _ensure_chunk_record_schema()
    doc = await DocumentRecord.get_or_none(id=record_id)
    if not doc or (not doc.parsed_content and not doc.extracted_data):
        logger.warning("Skip retrieval build: record not found or empty content. record_id=%s", record_id)
        return

    chunks = split_markdown_into_chunks(
        doc.parsed_content or "",
        max_chars=settings.retrieval_chunk_max_chars,
        overlap_chars=settings.retrieval_chunk_overlap_chars,
        min_chars=settings.retrieval_chunk_min_chars,
        doc_type=doc.doc_type,
        extracted_data=doc.extracted_data,
    )
    if not chunks:
        logger.warning("Skip retrieval build: no chunks generated. record_id=%s", record_id)
        return

    vectors = _embed_texts([chunk.embed_text for chunk in chunks])

    await ChunkRecord.filter(doc_id=record_id).delete()
    items = []
    for idx, chunk in enumerate(chunks):
        title_path = " > ".join(chunk.title_path) if chunk.title_path else None
        items.append(
            ChunkRecord(
                doc_id=record_id,
                chunk_index=idx,
                heading_path=title_path,
                title_path=title_path,
                section_title=chunk.section_title,
                chunk_type=chunk.chunk_type,
                order_index=chunk.order_index,
                content=chunk.display_text,
                embed_text=chunk.embed_text,
                display_text=chunk.display_text,
                vector=vectors[idx],
            )
        )
    await ChunkRecord.bulk_create(items)
    await _rebuild_index_from_db()
    logger.info("Retrieval index built for doc_id=%s, chunk_count=%s", record_id, len(items))


async def search_similar_chunks(
    question: str,
    doc_ids: Optional[list[int]] = None,
    top_k: int = 5,
) -> list[dict]:
    """
    在全局向量索引中检索相似 chunk，并在返回前做轻量去重。
    """
    _ensure_chunk_record_schema()
    doc_id_set = set(doc_ids or [])
    index, chunk_ids = _load_index_and_ids()
    if index is None or not chunk_ids:
        return []

    query_vec = np.array(_embed_texts([question]), dtype="float32")
    faiss.normalize_L2(query_vec)

    search_k = min(max(top_k * 10, top_k), len(chunk_ids))
    scores, indices = index.search(query_vec, search_k)

    candidates = []
    for score, idx in zip(scores[0], indices[0]):
        if idx < 0 or idx >= len(chunk_ids):
            continue
        candidates.append((float(score), chunk_ids[idx]))

    if not candidates:
        return []

    records = await ChunkRecord.filter(id__in=[item[1] for item in candidates]).prefetch_related("doc")
    record_map = {rec.id: rec for rec in records}

    ranked_candidates: list[dict] = []
    for score, chunk_id in candidates:
        rec = record_map.get(chunk_id)
        if not rec:
            continue
        if doc_id_set and rec.doc_id not in doc_id_set:
            continue

        title_path = rec.title_path or rec.heading_path
        display_text = rec.display_text or rec.content
        content = _compose_display_text(title_path=title_path, display_text=display_text)
        snippet_source = _normalize_snippet_text(
            display_text=display_text,
            chunk_type=rec.chunk_type,
        )
        item = {
            "doc_id": rec.doc_id,
            "chunk_id": rec.id,
            "score": round(score, 6),
            "title_path": _normalize_title_path(title_path) or None,
            "section_title": rec.section_title,
            "chunk_type": rec.chunk_type,
            "order_index": rec.order_index if rec.order_index is not None else rec.chunk_index,
            "snippet": _build_snippet(snippet_source, question=question),
            "display_text": display_text,
            "content": content,
        }

        ranked_candidates.append(item)

    result = _merge_ranked_candidates(ranked_candidates)

    if not doc_id_set:
        return _select_primary_doc_results(result, top_k=top_k)
    return result[:top_k]


async def answer_question(
    question: str,
    doc_ids: Optional[list[int]] = None,
    top_k: int = 5,
    llm_model: str | None = None,
) -> dict[str, object]:
    """基于检索片段生成答案，并按请求使用活动文本模型。"""
    model_spec = resolve_text_model(llm_model)
    retrieved = await search_similar_chunks(question=question, doc_ids=doc_ids, top_k=top_k)
    if not retrieved:
        return {
            "answer": "未找到足够依据，无法给出可靠答案。请尝试更具体的问题或先上传相关文档。",
            "citations": [],
        }

    context_blocks = []
    for idx, item in enumerate(retrieved, start=1):
        context_blocks.append(
            f"[{idx}] doc_id={item['doc_id']} chunk_id={item['chunk_id']}\n{item['content']}"
        )
    context = "\n\n".join(context_blocks)

    prompt = (
        "基于给定上下文回答问题。"
        "若上下文依据不足，必须明确说明“依据不足”。"
        "回答尽量简洁，并优先引用上下文中的事实。\n\n"
        f"问题: {question}\n\n上下文:\n{context}"
    )

    logger.info("Answer question using text model: %s", model_spec.id)
    resp = raw_client.chat.completions.create(
        **build_chat_completion_kwargs(
            llm_model=model_spec.id,
            messages=[
                {"role": "system", "content": "你是文档问答助手，必须基于检索片段作答，不可编造。"},
                {"role": "user", "content": prompt},
            ],
            temperature=0.1,
        )
    )
    answer = (resp.choices[0].message.content or "").strip()

    citations = [
        {
            "doc_id": item["doc_id"],
            "chunk_id": item["chunk_id"],
            "score": item["score"],
            "snippet": item["snippet"],
            "title_path": item.get("title_path"),
        }
        for item in retrieved
    ]
    return {"answer": answer, "citations": citations}

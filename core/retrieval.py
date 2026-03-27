import json
import logging
import os
from typing import Optional

import numpy as np
from dotenv import load_dotenv
from openai import OpenAI

from core.chunker import split_markdown_into_chunks
from schemas.models import ChunkRecord, DocumentRecord

try:
    import faiss
except Exception:  # pragma: no cover
    faiss = None


load_dotenv()
logger = logging.getLogger(__name__)

API_KEY = os.getenv("LLM_API_KEY")
BASE_URL = os.getenv("LLM_BASE_URL")
CHAT_MODEL = os.getenv("LLM_MODEL", "qwen2.5-7b-instruct-1m")
EMBED_MODEL = os.getenv("EMBEDDING_MODEL") or os.getenv("LLM_EMBED_MODEL") or "text-embedding-v4"

raw_client = OpenAI(api_key=API_KEY, base_url=BASE_URL)

VECTOR_DIR = os.path.join("db", "vector")
INDEX_PATH = os.path.join(VECTOR_DIR, "faiss.index")
META_PATH = os.path.join(VECTOR_DIR, "faiss_ids.json")


def _ensure_vector_dir() -> None:
    os.makedirs(VECTOR_DIR, exist_ok=True)


def _embed_texts(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []

    vectors: list[list[float]] = []
    batch_size = 32
    for i in range(0, len(texts), batch_size):
        batch = texts[i:i + batch_size]
        resp = raw_client.embeddings.create(model=EMBED_MODEL, input=batch)
        vectors.extend([item.embedding for item in resp.data])
    return vectors


async def _rebuild_index_from_db() -> None:
    if faiss is None:
        raise RuntimeError("FAISS 不可用，请安装 faiss-cpu。")

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
    doc = await DocumentRecord.get_or_none(id=record_id)
    if not doc or not doc.parsed_content:
        logger.warning("Skip retrieval build: record not found or empty content. record_id=%s", record_id)
        return

    chunks = split_markdown_into_chunks(doc.parsed_content, max_chars=1000, overlap_chars=100)
    if not chunks:
        logger.warning("Skip retrieval build: no chunks generated. record_id=%s", record_id)
        return

    texts = [chunk.text for chunk in chunks]
    vectors = _embed_texts(texts)

    await ChunkRecord.filter(doc_id=record_id).delete()
    items = []
    for idx, chunk in enumerate(chunks):
        heading_path = " > ".join(chunk.heading_path) if chunk.heading_path else None
        items.append(
            ChunkRecord(
                doc_id=record_id,
                chunk_index=idx,
                heading_path=heading_path,
                content=chunk.text,
                vector=vectors[idx],
            )
        )
    await ChunkRecord.bulk_create(items)
    await _rebuild_index_from_db()
    logger.info("Retrieval index built for doc_id=%s, chunk_count=%s", record_id, len(items))


async def search_similar_chunks(question: str, doc_id: Optional[int] = None, top_k: int = 5) -> list[dict]:
    """
    在全局向量索引中检索相似 chunk，并可按 doc_id 过滤。
    """
    index, chunk_ids = _load_index_and_ids()
    if index is None or not chunk_ids:
        return []

    query_vec = np.array(_embed_texts([question]), dtype="float32")
    faiss.normalize_L2(query_vec)

    search_k = min(max(top_k * 8, top_k), len(chunk_ids))
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

    result = []
    for score, chunk_id in candidates:
        rec = record_map.get(chunk_id)
        if not rec:
            continue
        if doc_id is not None and rec.doc_id != doc_id:
            continue
        result.append(
            {
                "doc_id": rec.doc_id,
                "chunk_id": rec.id,
                "score": round(score, 6),
                "snippet": rec.content[:220],
                "content": rec.content,
            }
        )
        if len(result) >= top_k:
            break

    return result


async def answer_question(question: str, doc_id: Optional[int] = None, top_k: int = 5) -> dict:
    retrieved = await search_similar_chunks(question=question, doc_id=doc_id, top_k=top_k)
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

    resp = raw_client.chat.completions.create(
        model=CHAT_MODEL,
        messages=[
            {"role": "system", "content": "你是文档问答助手，必须基于检索片段作答，不可编造。"},
            {"role": "user", "content": prompt},
        ],
        temperature=0.1,
    )
    answer = resp.choices[0].message.content.strip()

    citations = [
        {
            "doc_id": item["doc_id"],
            "chunk_id": item["chunk_id"],
            "score": item["score"],
            "snippet": item["snippet"],
        }
        for item in retrieved
    ]
    return {"answer": answer, "citations": citations}

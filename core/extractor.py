from __future__ import annotations

import asyncio
import json
import logging

from pydantic import BaseModel, ValidationError

from core.chunker import get_metadata_window, split_markdown_into_chunks
from core.config import get_settings
from core.constants import EXTRACT_PROMPT_TEMPLATE, JSON_FORMAT_INSTRUCTION
from core.llm import build_chat_completion_kwargs, get_openai_client
from core.utils import clean_and_parse_json, finalize_merged_result, merge_extraction_results, normalize_extracted_data
from schemas.models import DocumentMetadata, StructuredChunk


logger = logging.getLogger(__name__)
settings = get_settings()
raw_client = get_openai_client()
METADATA_FIELDS = {"doc_type", "language", "source_document_id", "schema_version", "extraction_version", "extra"}


def _infer_doc_type(response_model: type[BaseModel]) -> str | None:
    doc_type_field = getattr(response_model, "model_fields", {}).get("doc_type")
    default = getattr(doc_type_field, "default", None)
    return default if isinstance(default, str) and default.strip() else None


def _has_meaningful_schema_fields(data: dict[str, object], response_model: type[BaseModel]) -> bool:
    model_fields = getattr(response_model, "model_fields", {})
    for key, value in data.items():
        if key not in model_fields or key in METADATA_FIELDS:
            continue
        if value not in (None, "", [], {}):
            return True
    return False


def _json_schema_text(model: type[BaseModel]) -> str:
    return json.dumps(model.model_json_schema(), ensure_ascii=False, indent=2)


def _render_prompt(template: str, **kwargs: str) -> str:
    rendered = template
    for key, value in kwargs.items():
        rendered = rendered.replace(f"{{{key}}}", value)
    return rendered


def _create_text_completion(
    messages: list[dict[str, str]],
    *,
    temperature: float,
    model_name: str | None = None,
) -> str:
    response = raw_client.chat.completions.create(
        **build_chat_completion_kwargs(
            messages=messages,
            temperature=temperature,
            model_name=model_name,
        )
    )
    return response.choices[0].message.content or ""


def _extract_once(
    content: str,
    response_model: type[BaseModel],
    *,
    context_note: str | None = None,
    prompt_template: str | None = None,
    model_name: str | None = None,
) -> dict[str, object]:
    prompt_content = content
    if context_note:
        prompt_content = f"[Context]\n{context_note}\n\n[Document Chunk]\n{content}"

    template = prompt_template or EXTRACT_PROMPT_TEMPLATE
    prompt = _render_prompt(
        template,
        content=prompt_content,
        schema=_json_schema_text(response_model),
        json_instruction=JSON_FORMAT_INSTRUCTION,
        extra_instruction=JSON_FORMAT_INSTRUCTION,
    )
    response_text = _create_text_completion(
        messages=[
            {"role": "system", "content": "你是一个严谨的文档提取专家，只输出符合 Schema 的 JSON 数据。"},
            {"role": "user", "content": prompt},
        ],
        temperature=0.0,
        model_name=model_name,
    )
    data = clean_and_parse_json(response_text)
    return normalize_extracted_data(data)


async def _extract_chunk(
    semaphore: asyncio.Semaphore,
    chunk_text: str,
    response_model: type[BaseModel],
    *,
    context_note: str | None = None,
    prompt_template: str | None = None,
    model_name: str | None = None,
) -> dict[str, object]:
    async with semaphore:
        return await asyncio.to_thread(
            _extract_once,
            chunk_text,
            response_model,
            context_note=context_note,
            prompt_template=prompt_template,
            model_name=model_name,
        )


async def extract_structure_with_meta(
    markdown_content: str,
    response_model: type[BaseModel],
    *,
    prompt_template: str | None = None,
    model_name: str | None = None,
) -> tuple[BaseModel, dict[str, object]]:
    logger.info("Extracting structure for %s", response_model.__name__)
    content_length = len(markdown_content)

    if content_length > settings.extraction_max_chars:
        raise ValueError(
            f"文档长度为 {content_length} 字符，超过系统上限 {settings.extraction_max_chars}。"
            "当前系统仅面向中短文档。"
        )

    # 阶段 A：Metadata 抽取
    metadata_window = get_metadata_window(markdown_content)
    metadata_prompt_note = "请仅抽取文档级元信息，禁止从局部章节标题推测。无明确信息则留空。"
    
    metadata_dict = await asyncio.to_thread(
        _extract_once,
        metadata_window,
        DocumentMetadata,
        context_note=metadata_prompt_note,
        prompt_template=prompt_template,
        model_name=model_name,
    )
    
    doc_type = _infer_doc_type(response_model) or metadata_dict.get("doc_type")
    if doc_type:
        metadata_dict["doc_type"] = doc_type

    # 阶段 B：Chunk 内容抽取
    chunks = split_markdown_into_chunks(
        markdown_text=markdown_content,
        max_chars=settings.extraction_chunk_max_chars,
        overlap_chars=settings.extraction_chunk_overlap_chars,
        doc_type=doc_type,
    )
    if not chunks:
        raise ValueError("文档分块失败，无法继续提取")

    semaphore = asyncio.Semaphore(max(1, settings.extraction_concurrency))
    
    doc_title = metadata_dict.get("title") or "(Unknown Title)"
    doc_summary = metadata_dict.get("summary") or ""
    base_context = f"Document Title: {doc_title}"
    if doc_summary:
        base_context += f"\nDocument Summary: {doc_summary}"
        
    chunk_prompt_note = "请仅抽取当前 Chunk 中出现的对象列表。忽略文档级字段（如 title/version/summary）。"

    tasks = [
        _extract_chunk(
            semaphore,
            chunk.text,
            StructuredChunk,
            context_note=f"{base_context}\nLocal Path: {' > '.join(chunk.title_path) if chunk.title_path else '(no-heading)'}\n{chunk_prompt_note}",
            prompt_template=prompt_template,
            model_name=model_name,
        )
        for chunk in chunks
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    partial_results: list[dict[str, object]] = []
    failed_chunk_indexes: list[int] = []
    for index, result in enumerate(results):
        if isinstance(result, Exception):
            failed_chunk_indexes.append(index)
            logger.warning("Chunk extraction failed: %s", result)
            continue
        if not isinstance(result, dict) or not _has_meaningful_schema_fields(result, StructuredChunk):
            failed_chunk_indexes.append(index)
            logger.warning("Chunk returned no meaningful schema fields at index %s", index)
            continue
        try:
            validated_chunk = StructuredChunk.model_validate(result)
        except ValidationError as exc:
            failed_chunk_indexes.append(index)
            logger.warning("Chunk validation failed at index %s: %s", index, exc)
            continue
        partial_results.append(validated_chunk.model_dump(mode="python", exclude_none=True))

    if not partial_results:
        raise RuntimeError(f"分块提取失败，失败块数: {len(failed_chunk_indexes)}/{len(chunks)}")

    # 阶段 C：Finalize 清洗合并
    merged_data = finalize_merged_result(metadata_dict, partial_results)
    
    validated = response_model.model_validate(merged_data)
    failed_chunks = len(failed_chunk_indexes)
    return validated, {
        "mode": "three-stage",
        "chunk_count": len(chunks),
        "failed_chunks": failed_chunks,
        "failed_chunk_indexes": failed_chunk_indexes,
        "partial": failed_chunks > 0,
    }


def extract_structure(markdown_content: str, response_model: type[BaseModel]) -> BaseModel:
    extracted, _ = asyncio.run(extract_structure_with_meta(markdown_content, response_model))
    return extracted

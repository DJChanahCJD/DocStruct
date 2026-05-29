from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from pydantic import BaseModel, ValidationError

from core.chunker import split_ir_into_chunks, summarize_chunk
from core.config import get_settings
from core.constants import (
    JSON_FORMAT_INSTRUCTION,
)
from core.ir import build_basic_ir_from_markdown, document_ir_from_payload
from core.llm import build_chat_completion_kwargs, get_openai_client
from core.metadata import apply_document_metadata, extract_document_metadata
from core.reducer import discover_document_fields, discover_slots, reduce_extraction_results
from core.schema_registry import normalize_doc_type
from core.utils import clean_and_parse_json, normalize_extracted_data
from core.prompting import (
    create_prompt_messages,
    render_chunk_context,
    render_finalize_prompt,
    render_finalizer_input,
    render_map_prompt,
    render_summary_prompt,
)
from schemas.extraction import ExtractionContract, ExtractionMeta
from schemas.models import (
    DocType,
    DocumentChunk,
    DocumentIR,
)


logger = logging.getLogger(__name__)
settings = get_settings()
raw_client = get_openai_client()
RESPONSE_PREVIEW_CHARS = 500
SUMMARY_INPUT_MAX_CHARS = 12000


def build_extraction_contract(
    doc_type: str | DocType | None,
    response_model: type[BaseModel],
) -> ExtractionContract:
    """根据 typed response model 构造当前文档的抽取契约。"""
    normalized = normalize_doc_type(doc_type)
    common_rules = [
        "只抽取当前输入中明确出现的对象。不要编造或推断原文没有的内容。",
        "保持原文的聚合粒度。不要将同一编号、同一标题或同一表格行下的多个指标拆分为独立对象，也不要把多个独立条目合并为一个。",
        "evidence_element_ids 只使用 [ELEMENT: ...] 标记中的元素 ID。",
        "evidence_element_ids 只保留能直接支撑对象存在、定义或关键约束的高价值元素。",
        "只返回目标对象槽位；未出现的对象槽返回空列表。",
    ]
    target_slots = discover_slots(response_model)
    document_fields = discover_document_fields(response_model)
    return ExtractionContract(
        doc_type=normalized,
        document_fields=document_fields,
        target_slots=target_slots,
        rules=common_rules,
        ignore_sections=["术语表", "术语定义", "参考资料", "参考文献", "附录", "references", "glossary"],
    )


def _infer_doc_type(response_model: type[BaseModel]) -> str | None:
    doc_type_field = getattr(response_model, "model_fields", {}).get("doc_type")
    default = getattr(doc_type_field, "default", None)
    return default if isinstance(default, str) and default.strip() else None


def _has_meaningful_schema_fields(data: dict[str, object], response_model: type[BaseModel]) -> bool:
    model_fields = getattr(response_model, "model_fields", {})
    for key, value in data.items():
        if key not in model_fields:
            continue
        if value not in (None, "", [], {}):
            return True
    return False


def _json_schema_text(model: type[BaseModel]) -> str:
    return json.dumps(model.model_json_schema(), ensure_ascii=False, indent=2)


def _preview_text(text: str, limit: int = RESPONSE_PREVIEW_CHARS) -> str:
    """
    返回适合日志记录的单行短文本预览。
    """
    normalized = " ".join((text or "").split())
    if len(normalized) <= limit:
        return normalized
    return f"{normalized[:limit]}..."


def _compact_text(text: str) -> str:
    """返回压缩空白后的文本，用于摘要输入裁剪。"""
    return " ".join((text or "").split())


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


def generate_document_summary(
    markdown_content: str,
    document_ir: dict[str, Any] | DocumentIR,
    *,
    model_name: str | None = None,
) -> str:
    """基于全文和 IR 大纲生成用于抽取上下文的文档摘要。"""
    ir = document_ir_from_payload(document_ir)
    compact_content = _compact_text(markdown_content)
    content = compact_content[:SUMMARY_INPUT_MAX_CHARS]
    outline = ir.outline.model_dump_json(indent=2)
    prompt = render_summary_prompt(outline=outline, content=content)
    summary = _create_text_completion(
        messages=create_prompt_messages(prompt=prompt),
        temperature=0.0,
        model_name=model_name,
    )
    return _compact_text(summary)


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
        prompt_content = f"{context_note}\n\n[Current Chunk]\n{content}"

    if prompt_template:
        prompt = prompt_template.format(
            content=prompt_content,
            schema=_json_schema_text(response_model),
        )
    else:
        prompt = render_map_prompt(content=prompt_content, response_model=response_model)
    response_text = _create_text_completion(
        messages=create_prompt_messages(prompt=prompt),
        temperature=0.0,
        model_name=model_name,
    )
    try:
        data = clean_and_parse_json(response_text)
    except ValueError as exc:
        logger.warning(
            "LLM JSON parse failed: prompt_chars=%s response_chars=%s response_preview=%s",
            len(prompt),
            len(response_text),
            _preview_text(response_text),
        )
        raise ValueError(
            f"LLM JSON parse failed: prompt_chars={len(prompt)}, response_chars={len(response_text)}"
        ) from exc
    return normalize_extracted_data(data)


async def _extract_chunk(
    semaphore: asyncio.Semaphore,
    chunk: DocumentChunk,
    *,
    document_ir: DocumentIR,
    contract: ExtractionContract,
    response_model: type[BaseModel],
    document_summary: str | None = None,
    prompt_template: str | None = None,
    model_name: str | None = None,
) -> dict[str, object]:
    async with semaphore:
        try:
            return await asyncio.to_thread(
                _extract_once,
                chunk.markdown,
                response_model,
                context_note=render_chunk_context(
                    document_ir=document_ir,
                    contract=contract,
                    chunk=chunk,
                    document_summary=document_summary,
                ),
                prompt_template=prompt_template,
                model_name=model_name,
            )
        except Exception as exc:
            summary = summarize_chunk(chunk)
            raise RuntimeError(f"Chunk extraction failed: {summary}") from exc


async def extract_structure_with_meta(
    markdown_content: str,
    response_model: type[BaseModel],
    *,
    document_ir: dict[str, Any] | DocumentIR | None = None,
    document_summary: str | None = None,
    prompt_template: str | None = None,
    model_name: str | None = None,
) -> tuple[BaseModel, dict[str, object]]:
    logger.info("Extracting structure for %s", response_model.__name__)
    doc_type = _infer_doc_type(response_model) or DocType.UNKNOWN.value
    normalized_doc_type = normalize_doc_type(doc_type)

    ir = _prepare_document_ir(
        markdown_content=markdown_content,
        document_ir=document_ir,
        doc_type=normalized_doc_type,
    )
    content_length = sum(len(element.markdown or element.text or "") for element in ir.elements)
    logger.info(
        "Extraction input prepared: doc_type=%s content_chars=%s element_count=%s section_count=%s",
        normalized_doc_type.value,
        content_length,
        len(ir.elements),
        len(ir.outline.sections),
    )
    if content_length > settings.extraction_max_chars:
        raise ValueError(
            f"文档长度为 {content_length} 字符，超过系统上限 {settings.extraction_max_chars}。"
            "当前系统仅面向中短文档。"
        )

    contract = build_extraction_contract(normalized_doc_type, response_model=response_model)

    chunk_model = _typed_extraction_model(response_model)

    # Unified chunk path — small docs = 1 chunk
    chunk_max = settings.extraction_chunk_max_chars
    chunk_overlap = settings.extraction_chunk_overlap_chars
    chunks = split_ir_into_chunks(
        ir,
        max_chars=chunk_max,
        ignore_sections=contract.ignore_sections,
        overlap_chars=chunk_overlap,
    )
    if not chunks:
        raise ValueError("文档 IR 分块失败，无法继续提取")

    chunk_summaries = [summarize_chunk(chunk) for chunk in chunks]
    logger.info(
        "Extraction chunks prepared: chunk_count=%s chunk_max_chars=%s overlap=%s concurrency=%s chunks=%s",
        len(chunks),
        chunk_max,
        chunk_overlap,
        settings.extraction_concurrency,
        chunk_summaries,
    )

    semaphore = asyncio.Semaphore(max(1, settings.extraction_concurrency))
    tasks = [
        _extract_chunk(
            semaphore,
            chunk,
            document_ir=ir,
            contract=contract,
            response_model=chunk_model,
            document_summary=document_summary,
            prompt_template=prompt_template,
            model_name=model_name,
        )
        for chunk in chunks
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    partial_results: list[dict[str, Any]] = []
    failed_chunk_indexes: list[int] = []
    failed_chunk_details: list[dict[str, object]] = []
    for index, result in enumerate(results):
        chunk_summary = summarize_chunk(chunks[index])
        if isinstance(result, Exception):
            failed_chunk_indexes.append(index)
            failed_chunk_details.append({**chunk_summary, "index": index, "error": str(result)})
            logger.warning("Chunk extraction failed: index=%s summary=%s error=%s", index, chunk_summary, result)
            continue
        if not isinstance(result, dict) or not _has_meaningful_schema_fields(result, chunk_model):
            failed_chunk_indexes.append(index)
            failed_chunk_details.append({**chunk_summary, "index": index, "error": "no_meaningful_schema_fields"})
            logger.warning("Chunk returned no meaningful schema fields: index=%s summary=%s", index, chunk_summary)
            continue
        try:
            chunk_model.model_validate(result)
        except ValidationError as exc:
            failed_chunk_indexes.append(index)
            failed_chunk_details.append({**chunk_summary, "index": index, "error": str(exc)})
            logger.warning("Chunk validation failed: index=%s summary=%s error=%s", index, chunk_summary, exc)
            continue
        partial_results.append(result)

    if not partial_results:
        raise RuntimeError(f"分块提取失败，失败块数: {len(failed_chunk_indexes)}/{len(chunks)}")

    finalizer_failed = False
    try:
        finalized_data = await asyncio.to_thread(
            _finalize_extraction_once,
            document_ir=ir,
            contract=contract,
            chunk_results=partial_results,
            response_model=chunk_model,
            document_summary=document_summary,
            model_name=model_name,
        )
        chunk_results_for_reduce = [finalized_data]
    except Exception as exc:
        finalizer_failed = True
        logger.warning(
            "Finalizer failed, falling back to direct reducer: candidates=%s error=%s",
            len(partial_results), exc,
        )
        chunk_results_for_reduce = partial_results

    reduced_data, evidence_meta = reduce_extraction_results(
        doc_type=normalized_doc_type.value,
        title=ir.title,
        chunk_results=chunk_results_for_reduce,
        document_ir=ir,
        response_model=response_model,
    )
    apply_document_metadata(
        reduced_data,
        extract_document_metadata(markdown_content, ir),
    )
    validated = response_model.model_validate(reduced_data)
    failed_chunks = len(failed_chunk_indexes)
    return validated, ExtractionMeta(
        llm_model=model_name or settings.llm_model,
        confidence=round(evidence_meta.get("evidence_coverage", 0.0), 4),
        chunk_count=len(chunks),
        failed_chunks=failed_chunks,
        element_count=len(ir.elements),
        section_count=len(ir.outline.sections),
    ).model_dump(mode="json")


def extract_structure(markdown_content: str, response_model: type[BaseModel]) -> BaseModel:
    extracted, _ = asyncio.run(extract_structure_with_meta(markdown_content, response_model))
    return extracted


def _prepare_document_ir(
    *,
    markdown_content: str,
    document_ir: dict[str, Any] | DocumentIR | None,
    doc_type: DocType,
) -> DocumentIR:
    if document_ir is None:
        ir = build_basic_ir_from_markdown(markdown_content, doc_type=doc_type)
    else:
        ir = document_ir_from_payload(document_ir)

    ir.doc_type = doc_type
    ir.outline.doc_type = doc_type
    if not ir.title:
        ir.title = ir.outline.title
    if not ir.outline.title:
        ir.outline.title = ir.title
    return ir


def _finalize_extraction_once(
    *,
    document_ir: DocumentIR,
    contract: ExtractionContract,
    chunk_results: list[dict[str, Any]],
    response_model: type[BaseModel],
    document_summary: str | None = None,
    model_name: str | None = None,
) -> dict[str, object]:
    """
    Use the LLM to merge chunk candidates into one global structured document.
    """
    prompt = render_finalize_prompt(
        content=render_finalizer_input(
            document_ir=document_ir,
            contract=contract,
            chunk_results=chunk_results,
            document_summary=document_summary,
        ),
        response_model=response_model,
    )
    response_text = _create_text_completion(
        messages=create_prompt_messages(prompt=prompt),
        temperature=0.0,
        model_name=model_name,
    )
    try:
        data = clean_and_parse_json(response_text)
    except ValueError as exc:
        logger.warning(
            "LLM finalizer JSON parse failed: prompt_chars=%s response_chars=%s response_preview=%s",
            len(prompt),
            len(response_text),
            _preview_text(response_text),
        )
        raise ValueError(
            f"LLM finalizer JSON parse failed: prompt_chars={len(prompt)}, response_chars={len(response_text)}"
        ) from exc
    return normalize_extracted_data(data)


def _typed_extraction_model(response_model: type[BaseModel]) -> type[BaseModel]:
    """从文档模型提取对应的抽取容器（去除 evidence/doc_type 等包装字段）。"""
    from schemas.models import (
        ApiExtractedDocument, DBDDExtractedDocument, HLDExtractedDocument,
        SrsExtractedDocument, TestCaseExtractedDocument,
        ApiExtraction, DBDDExtraction, HLDExtraction,
        SrsExtraction, TestCaseExtraction,
    )
    mapping: dict[type[BaseModel], type[BaseModel]] = {
        SrsExtractedDocument: SrsExtraction,
        ApiExtractedDocument: ApiExtraction,
        HLDExtractedDocument: HLDExtraction,
        TestCaseExtractedDocument: TestCaseExtraction,
        DBDDExtractedDocument: DBDDExtraction,
    }
    if response_model not in mapping:
        raise ValueError(f"不支持的 typed response model: {response_model.__name__}")
    return mapping[response_model]



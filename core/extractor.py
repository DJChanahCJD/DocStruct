from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from pydantic import BaseModel, ValidationError

from core.chunker import split_ir_into_chunks
from core.config import get_settings
from core.constants import EXTRACT_PROMPT_TEMPLATE, JSON_FORMAT_INSTRUCTION
from core.ir import build_basic_ir_from_markdown, document_ir_from_payload
from core.llm import build_chat_completion_kwargs, get_openai_client
from core.reducer import OBJECT_SLOTS, reduce_extraction_results
from core.utils import clean_and_parse_json, normalize_extracted_data
from schemas.models import DocType, DocumentChunk, DocumentIR, ExtractionContract, StructuredChunk


logger = logging.getLogger(__name__)
settings = get_settings()
raw_client = get_openai_client()


SLOT_DESCRIPTIONS = {
    "entities": "Actors, modules, systems, services, components, or data objects explicitly present in the chunk.",
    "processes": "Business, workflow, operation, or test processes with ordered steps explicitly present in the chunk.",
    "requirements": "Functional, non-functional, business-rule, constraint, or acceptance requirements explicitly present in the chunk.",
    "interfaces": "HTTP, RPC, message, database, file, external system, hardware, or UI interfaces explicitly present in the chunk.",
    "artifacts": "Document artifacts such as endpoints, design modules, test cases, manual sections, issues, decisions, or tables.",
}


def build_extraction_contract(doc_type: str | DocType | None) -> ExtractionContract:
    normalized = _normalize_doc_type(doc_type)
    common_rules = [
        "Only extract objects that are explicitly present in the current chunk.",
        "Every object should include evidence_element_ids using only IDs shown in [ELEMENT: ...] markers.",
        "Do not output relations or metrics as top-level slots.",
        "Put quantified values on the relevant requirement.metric or artifact.extra field.",
        "Use extra only for small document-specific details; do not copy source sections into extra.",
    ]
    doc_rules = {
        DocType.SRS: [
            "Content with requirement IDs or shall/must/support language should be requirements.",
            "Functional points under one numbered requirement should stay in details.",
            "Acceptance criteria belong in acceptance_criteria, not separate requirements.",
        ],
        DocType.API: [
            "Endpoint paths and methods should become interfaces.",
            "Request, response, and operation metadata should become api_endpoint artifacts.",
        ],
        DocType.TEST: [
            "Test cases and reports should become artifacts; ordered execution flows should become processes.",
        ],
        DocType.ISSUE: [
            "Issue descriptions should become issue artifacts; reproduction steps should become processes.",
        ],
    }
    return ExtractionContract(
        doc_type=normalized,
        target_slots=list(OBJECT_SLOTS),
        slot_descriptions=dict(SLOT_DESCRIPTIONS),
        rules=common_rules + doc_rules.get(normalized, []),
        ignore_sections=["术语表", "参考资料", "references", "glossary"],
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
        prompt_content = f"{context_note}\n\n[Current Chunk]\n{content}"

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
            {"role": "system", "content": "You are a precise software-engineering document extractor. Return JSON only."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.0,
        model_name=model_name,
    )
    data = clean_and_parse_json(response_text)
    return normalize_extracted_data(data)


async def _extract_chunk(
    semaphore: asyncio.Semaphore,
    chunk: DocumentChunk,
    *,
    document_ir: DocumentIR,
    contract: ExtractionContract,
    prompt_template: str | None = None,
    model_name: str | None = None,
) -> dict[str, object]:
    async with semaphore:
        return await asyncio.to_thread(
            _extract_once,
            chunk.markdown,
            StructuredChunk,
            context_note=_render_chunk_context(document_ir=document_ir, contract=contract, chunk=chunk),
            prompt_template=prompt_template,
            model_name=model_name,
        )


async def extract_structure_with_meta(
    markdown_content: str,
    response_model: type[BaseModel],
    *,
    document_ir: dict[str, Any] | DocumentIR | None = None,
    prompt_template: str | None = None,
    model_name: str | None = None,
) -> tuple[BaseModel, dict[str, object]]:
    logger.info("Extracting structure for %s", response_model.__name__)
    doc_type = _infer_doc_type(response_model) or DocType.UNKNOWN.value
    normalized_doc_type = _normalize_doc_type(doc_type)

    ir = _prepare_document_ir(
        markdown_content=markdown_content,
        document_ir=document_ir,
        doc_type=normalized_doc_type,
    )
    content_length = sum(len(element.markdown or element.text or "") for element in ir.elements)
    if content_length > settings.extraction_max_chars:
        raise ValueError(
            f"文档长度为 {content_length} 字符，超过系统上限 {settings.extraction_max_chars}。"
            "当前系统仅面向中短文档。"
        )

    contract = build_extraction_contract(normalized_doc_type)
    chunks = split_ir_into_chunks(
        ir,
        max_chars=settings.extraction_chunk_max_chars,
        ignore_sections=contract.ignore_sections,
    )
    if not chunks:
        raise ValueError("文档 IR 分块失败，无法继续提取")

    semaphore = asyncio.Semaphore(max(1, settings.extraction_concurrency))
    tasks = [
        _extract_chunk(
            semaphore,
            chunk,
            document_ir=ir,
            contract=contract,
            prompt_template=prompt_template,
            model_name=model_name,
        )
        for chunk in chunks
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    partial_results: list[dict[str, Any]] = []
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
        partial_results.append(validated_chunk.model_dump(mode="json", exclude_none=True))

    if not partial_results:
        raise RuntimeError(f"分块提取失败，失败块数: {len(failed_chunk_indexes)}/{len(chunks)}")

    reduced_data, evidence_meta = reduce_extraction_results(
        doc_type=normalized_doc_type.value,
        title=ir.title,
        chunk_results=partial_results,
        document_ir=ir,
    )
    validated = response_model.model_validate(reduced_data)
    failed_chunks = len(failed_chunk_indexes)
    return validated, {
        "mode": "ir-map-reduce",
        "chunk_count": len(chunks),
        "failed_chunks": failed_chunks,
        "failed_chunk_indexes": failed_chunk_indexes,
        "partial": failed_chunks > 0,
        "element_count": len(ir.elements),
        "section_count": len(ir.outline.sections),
        **evidence_meta,
    }


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


def _render_chunk_context(
    *,
    document_ir: DocumentIR,
    contract: ExtractionContract,
    chunk: DocumentChunk,
) -> str:
    return "\n\n".join(
        [
            "[Document Outline]",
            document_ir.outline.model_dump_json(indent=2),
            "[Extraction Contract]",
            contract.model_dump_json(indent=2),
            "[Chunk Metadata]",
            json.dumps(
                {
                    "chunk_id": chunk.chunk_id,
                    "section_path": chunk.section_path,
                    "page_start": chunk.page_start,
                    "page_end": chunk.page_end,
                    "allowed_evidence_element_ids": [element.element_id for element in chunk.elements],
                },
                ensure_ascii=False,
                indent=2,
            ),
            (
                "Return only the five target slots. Use evidence_element_ids from "
                "allowed_evidence_element_ids. Leave a list empty when the chunk has no object for that slot."
            ),
        ]
    )


def _normalize_doc_type(doc_type: str | DocType | None) -> DocType:
    if isinstance(doc_type, DocType):
        return doc_type
    if doc_type is None or not str(doc_type).strip():
        return DocType.UNKNOWN
    try:
        return DocType(str(doc_type).strip())
    except ValueError:
        return DocType.UNKNOWN

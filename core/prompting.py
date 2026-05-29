from __future__ import annotations

import json

from core.constants import (
    CHUNK_EXTRACTION_INSTRUCTIONS,
    FINALIZE_USER_PROMPT_TEMPLATE,
    JSON_FORMAT_INSTRUCTION,
    MAP_USER_PROMPT_TEMPLATE,
    SUMMARY_USER_PROMPT_TEMPLATE,
    SYSTEM_PROMPT,
)
from schemas.extraction import ExtractionContract
from schemas.models import DocumentChunk, DocumentIR


def _json_schema_text(model: type) -> str:
    """序列化 Pydantic schema，供 prompt 填充使用。"""
    return json.dumps(model.model_json_schema(), ensure_ascii=False, indent=2)


def render_summary_prompt(*, outline: str, content: str) -> str:
    """渲染摘要生成 prompt。"""
    return SUMMARY_USER_PROMPT_TEMPLATE.format(outline=outline, content=content)


def render_chunk_context(
    *,
    document_ir: DocumentIR,
    contract: ExtractionContract,
    chunk: DocumentChunk,
    document_summary: str | None = None,
) -> str:
    """渲染分块抽取上下文。"""
    parts = [
        "[Document Outline]",
        document_ir.outline.model_dump_json(indent=2),
    ]
    if document_summary and document_summary.strip():
        parts.extend([
            "[Document Summary]",
            document_summary.strip(),
        ])
    parts.extend([
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
        CHUNK_EXTRACTION_INSTRUCTIONS,
    ])
    return "\n\n".join(parts)


def render_finalizer_input(
    *,
    document_ir: DocumentIR,
    contract: ExtractionContract,
    chunk_results: list[dict[str, object]],
    document_summary: str | None = None,
) -> str:
    """渲染 finalizer 输入。"""
    parts = [
        "[Document Outline]",
        document_ir.outline.model_dump_json(indent=2),
    ]
    if document_summary and document_summary.strip():
        parts.extend([
            "[Document Summary]",
            document_summary.strip(),
        ])
    parts.extend([
        "[Extraction Contract]",
        contract.model_dump_json(indent=2),
        "[Chunk Candidates]",
        json.dumps(chunk_results, ensure_ascii=False, indent=2),
    ])
    return "\n\n".join(parts)


def create_prompt_messages(*, prompt: str) -> list[dict[str, str]]:
    """创建统一的 system/user 消息。"""
    return [
        {"role": "system", "content": SYSTEM_PROMPT.strip()},
        {"role": "user", "content": prompt},
    ]


def render_map_prompt(*, content: str, response_model: type) -> str:
    """渲染分块抽取 prompt。"""
    return MAP_USER_PROMPT_TEMPLATE.format(
        content=content,
        schema=_json_schema_text(response_model),
    )


def render_finalize_prompt(*, content: str, response_model: type) -> str:
    """渲染 finalizer prompt。"""
    return FINALIZE_USER_PROMPT_TEMPLATE.format(
        content=content,
        schema=_json_schema_text(response_model),
    )

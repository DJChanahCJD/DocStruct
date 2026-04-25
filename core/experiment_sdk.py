from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from core.config import get_settings
from core.extractor import extract_structure_with_meta
from core.ir import document_ir_to_payload, parse_result_to_ir
from core.parser import ParserFactory
from core.schema_registry import get_response_model, normalize_doc_type


def parse_document(file_path: str | Path, doc_type: str | None = None) -> tuple[str, dict[str, Any]]:
    resolved_path = Path(file_path)
    parser = ParserFactory.get_parser(str(resolved_path))
    parse_result = parser.parse_to_result(str(resolved_path))
    document_ir = parse_result_to_ir(parse_result, doc_type=doc_type)
    return parse_result.markdown, {
        "parser_name": parser.__class__.__name__,
        "file_path": str(resolved_path).replace("\\", "/"),
        "title": parse_result.title,
        "block_count": len(parse_result.blocks),
        "element_count": len(document_ir.elements),
        "document_ir": document_ir_to_payload(document_ir),
        **parse_result.metadata,
    }


async def extract_document(
    markdown_content: str,
    doc_type: str,
    *,
    document_ir: dict[str, Any] | None = None,
    prompt_template: str | None = None,
    model_name: str | None = None,
) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    response_model = get_response_model(doc_type)
    normalized_doc_type = normalize_doc_type(doc_type)
    if response_model is None:
        return None, {
            "doc_type": normalized_doc_type.value,
            "model_name": model_name or get_settings().llm_model,
            "supported": False,
            "error_message": f"doc_type={normalized_doc_type.value} 不支持结构化抽取",
        }

    extracted, extraction_meta = await extract_structure_with_meta(
        markdown_content=markdown_content,
        response_model=response_model,
        document_ir=document_ir,
        prompt_template=prompt_template,
        model_name=model_name,
    )
    return extracted.model_dump(mode="json"), {
        **extraction_meta,
        "doc_type": normalized_doc_type.value,
        "model_name": model_name or get_settings().llm_model,
        "supported": True,
    }


async def run_sample(
    file_path: str | Path,
    doc_type: str,
    *,
    prompt_template: str | None = None,
    model_name: str | None = None,
) -> dict[str, Any]:
    markdown, parse_meta = await asyncio.to_thread(parse_document, file_path, doc_type)
    extracted_data, extraction_meta = await extract_document(
        markdown,
        doc_type,
        document_ir=parse_meta.get("document_ir") if isinstance(parse_meta.get("document_ir"), dict) else None,
        prompt_template=prompt_template,
        model_name=model_name,
    )
    return {
        "markdown_content": markdown,
        "parse_meta": parse_meta,
        "extracted_data": extracted_data,
        "extraction_meta": extraction_meta,
    }


def summarize_sample_result(result: dict[str, Any]) -> dict[str, Any]:
    parse_meta = result.get("parse_meta") if isinstance(result.get("parse_meta"), dict) else {}
    extraction_meta = result.get("extraction_meta") if isinstance(result.get("extraction_meta"), dict) else {}
    return {
        "file_path": parse_meta.get("file_path"),
        "parser_name": parse_meta.get("parser_name"),
        "title": parse_meta.get("title"),
        "block_count": parse_meta.get("block_count"),
        "element_count": parse_meta.get("element_count"),
        "doc_type": extraction_meta.get("doc_type"),
        "model_name": extraction_meta.get("model_name"),
        "supported": extraction_meta.get("supported"),
        "error_message": extraction_meta.get("error_message"),
    }


def write_json(data: dict[str, Any], output_path: str | Path) -> Path:
    resolved_path = Path(output_path)
    resolved_path.parent.mkdir(parents=True, exist_ok=True)
    resolved_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return resolved_path

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from core.config import get_settings
from core.extractor import extract_structure_with_meta
from core.parser import ParserFactory
from core.schema_registry import get_response_model, normalize_doc_type


def parse_document(file_path: str | Path) -> tuple[str, dict[str, Any]]:
    resolved_path = Path(file_path)
    parser = ParserFactory.get_parser(str(resolved_path))
    markdown = parser.parse(str(resolved_path))
    return markdown, {"parser_name": parser.__class__.__name__, "file_path": str(resolved_path).replace("\\", "/")}


async def extract_document(
    markdown_content: str,
    doc_type: str,
    *,
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
    markdown, parse_meta = await asyncio.to_thread(parse_document, file_path)
    extracted_data, extraction_meta = await extract_document(
        markdown,
        doc_type,
        prompt_template=prompt_template,
        model_name=model_name,
    )
    return {
        "markdown_content": markdown,
        "parse_meta": parse_meta,
        "extracted_data": extracted_data,
        "extraction_meta": extraction_meta,
    }

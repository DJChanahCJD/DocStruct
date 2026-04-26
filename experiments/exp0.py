from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from core.experiment_sdk import (
    extract_document,
    parse_document,
    summarize_sample_result,
    write_json,
)


DOC_TYPE = "srs"
INPUT_FILE = ROOT_DIR / "experiments" / "assets" / "srs_mini.pdf"
RESULT_DIR = ROOT_DIR / "experiments" / "results"
MARKDOWN_OUTPUT = RESULT_DIR / "exp0_parsed.md"
JSON_OUTPUT = RESULT_DIR / "exp0_latest.json"


def build_output_result(
    parse_meta: dict[str, Any],
    extracted_data: dict[str, Any] | None,
    extraction_meta: dict[str, Any],
) -> dict[str, Any]:
    compact_parse_meta = {key: value for key, value in parse_meta.items() if key != "document_ir"}

    return {
        "parsed_markdown_path": str(MARKDOWN_OUTPUT.relative_to(ROOT_DIR)).replace("\\", "/"),
        "parse_meta": compact_parse_meta,
        "extracted_data": extracted_data,
        "extraction_meta": extraction_meta,
    }


def print_summary(result: dict[str, Any]) -> None:
    summary = summarize_sample_result(result)
    print("Experiment 0 quick check")
    print(f"- file: {summary.get('file_path')}")
    print(f"- parser: {summary.get('parser_name')}")
    print(f"- title: {summary.get('title')}")
    print(f"- blocks/elements: {summary.get('block_count')}/{summary.get('element_count')}")
    print(f"- doc_type: {summary.get('doc_type')}")
    print(f"- model: {summary.get('model_name')}")
    print(f"- supported: {summary.get('supported')}")
    if summary.get("error_message"):
        print(f"- error: {summary.get('error_message')}")
    print(f"- markdown: {MARKDOWN_OUTPUT}")
    print(f"- json: {JSON_OUTPUT}")


async def main() -> None:
    markdown, parse_meta = parse_document(INPUT_FILE, DOC_TYPE)
    extracted_data, extraction_meta = await extract_document(
        markdown,
        DOC_TYPE,
        document_ir=parse_meta.get("document_ir") if isinstance(parse_meta.get("document_ir"), dict) else None,
    )

    output_result = build_output_result(parse_meta, extracted_data, extraction_meta)
    write_json(output_result, JSON_OUTPUT)
    print_summary(output_result)


if __name__ == "__main__":
    asyncio.run(main())

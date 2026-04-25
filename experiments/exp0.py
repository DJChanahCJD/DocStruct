from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from core.experiment_sdk import parse_document, run_sample, summarize_sample_result, write_json


DEFAULT_FILE = ROOT_DIR / "experiments" / "assets" / "srs_mini.md"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="实验0：单文档快速验证 DocStruct 核心链路")
    parser.add_argument("--file", default=str(DEFAULT_FILE), help="测试文档路径")
    parser.add_argument("--doc-type", default="srs", help="文档类型，默认 srs")
    parser.add_argument("--output", help="可选：写入完整 JSON 结果的路径")
    parser.add_argument("--model", dest="model_name", help="可选：覆盖 LLM 模型名")
    parser.add_argument("--parse-only", action="store_true", help="只验证解析和 IR，不调用 LLM")
    return parser


def print_summary(summary: dict[str, Any]) -> None:
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


async def main() -> None:
    args = build_parser().parse_args()
    if args.parse_only:
        markdown, parse_meta = parse_document(args.file, args.doc_type)
        result = {
            "markdown_content": markdown,
            "parse_meta": parse_meta,
            "extracted_data": None,
            "extraction_meta": {
                "doc_type": args.doc_type,
                "model_name": args.model_name,
                "supported": None,
                "parse_only": True,
            },
        }
    else:
        result = await run_sample(args.file, args.doc_type, model_name=args.model_name)
    summary = summarize_sample_result(result)

    print_summary(summary)
    if args.output:
        output_path = write_json(result, args.output)
        print(f"- output: {output_path}")
    else:
        print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())

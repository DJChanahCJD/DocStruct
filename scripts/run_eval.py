import argparse
import asyncio
import json
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from core.config import get_settings
from core.extractor import extract_structure_with_meta
from core.parser import ParserFactory
from schemas.models import ApiDocument, DesignDocument, DocType, IssueDocument, ManualDocument, SrsDocument, TestDocument


TYPE_MODEL_MAP = {
    DocType.SRS: SrsDocument,
    DocType.API: ApiDocument,
    DocType.DESIGN: DesignDocument,
    DocType.TEST: TestDocument,
    DocType.MANUAL: ManualDocument,
    DocType.ISSUE: IssueDocument,
}


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="运行 DocStruct 结构化抽取评测。")
    parser.add_argument("--manifest", default="experiments/datasets/baseline_manifest.json")
    parser.add_argument("--output-dir", default="experiments/results")
    parser.add_argument("--prompt-version", default="baseline-v1")
    return parser.parse_args()


def _load_manifest(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _is_empty_value(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return value.strip() == ""
    if isinstance(value, (list, dict)):
        return len(value) == 0
    return False


def _count_fields(value: Any) -> tuple[int, int]:
    if isinstance(value, dict):
        total = 0
        filled = 0
        for key, item in value.items():
            if key == "doc_type":
                continue
            child_total, child_filled = _count_fields(item)
            if child_total == 0:
                total += 1
                if not _is_empty_value(item):
                    filled += 1
                continue
            total += child_total
            filled += child_filled
        return total, filled
    if isinstance(value, list):
        if not value:
            return 1, 0
        total = 0
        filled = 0
        for item in value:
            child_total, child_filled = _count_fields(item)
            if child_total == 0:
                total += 1
                if not _is_empty_value(item):
                    filled += 1
                continue
            total += child_total
            filled += child_filled
        return total, filled
    return 0, 0


def _compute_completeness(extracted: dict[str, Any] | None) -> float | None:
    if not extracted:
        return None
    total, filled = _count_fields(extracted)
    if total == 0:
        return None
    return round(filled / total, 4)


def _resolve_target_doc_type(expected_doc_type: str) -> DocType | None:
    try:
        return DocType(expected_doc_type)
    except ValueError:
        return None


async def _evaluate_sample(sample: dict[str, Any]) -> dict[str, Any]:
    sample_id = sample["sample_id"]
    file_path = Path(sample["file_path"])
    expected_doc_type = sample["expected_doc_type"]

    parse_start = time.perf_counter()
    parser = ParserFactory.get_parser(str(file_path))
    markdown = parser.parse(str(file_path))
    parse_ms = round((time.perf_counter() - parse_start) * 1000, 2)

    extraction_model = _resolve_target_doc_type(expected_doc_type=expected_doc_type)
    extracted_data = None
    extraction_meta = None
    extraction_error = None
    extraction_ms = None

    if extraction_model and extraction_model in TYPE_MODEL_MAP:
        extract_start = time.perf_counter()
        try:
            extracted, extraction_meta = await extract_structure_with_meta(
                markdown_content=markdown,
                response_model=TYPE_MODEL_MAP[extraction_model],
            )
            extracted_data = extracted.model_dump(mode="json")
        except Exception as exc:
            extraction_error = str(exc)
        extraction_ms = round((time.perf_counter() - extract_start) * 1000, 2)
    else:
        extraction_error = f"无法确定抽取模型: type={expected_doc_type}"

    completeness = _compute_completeness(extracted_data)
    total_ms = round(parse_ms + (extraction_ms or 0), 2)
    return {
        "sample_id": sample_id,
        "file_path": str(file_path).replace("\\", "/"),
        "expected_doc_type": expected_doc_type,
        "prompt_version": sample.get("prompt_version"),
        "model_name": get_settings().llm_model,
        "parse_latency_ms": parse_ms,
        "extraction_latency_ms": extraction_ms,
        "total_latency_ms": total_ms,
        "content_length": len(markdown),
        "used_chunking": bool(extraction_meta and extraction_meta.get("mode") == "chunked"),
        "extraction_success": extraction_error is None and extracted_data is not None,
        "completeness_score": completeness,
        "extraction_meta": extraction_meta,
        "error_message": extraction_error,
        "extracted_data": extracted_data,
        "notes": sample.get("notes"),
    }


def _build_summary(results: list[dict[str, Any]], prompt_version: str, settings) -> dict[str, Any]:
    total = len(results)
    extraction_success = sum(1 for item in results if item["extraction_success"])
    chunked = sum(1 for item in results if item["used_chunking"])
    completeness_scores = [item["completeness_score"] for item in results if item["completeness_score"] is not None]
    avg_latency_ms = round(sum(item["total_latency_ms"] for item in results) / total, 2) if total else 0.0
    avg_completeness = round(sum(completeness_scores) / len(completeness_scores), 4) if completeness_scores else None
    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "prompt_version": prompt_version,
        "model_name": settings.llm_model,
        "sample_count": total,
        "extraction_success_rate": round(extraction_success / total, 4) if total else 0.0,
        "chunked_sample_rate": round(chunked / total, 4) if total else 0.0,
        "avg_total_latency_ms": avg_latency_ms,
        "avg_total_latency_s": round(avg_latency_ms / 1000, 3),
        "avg_completeness_score": avg_completeness,
    }


def _build_markdown_report(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    rows = [
        "| sample_id | doc_type | extract_ok | completeness | total_time | mode |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for item in payload["results"]:
        mode = (item.get("extraction_meta") or {}).get("mode", "-")
        completeness = item["completeness_score"]
        completeness_text = "-" if completeness is None else str(completeness)
        total_time_s = round(item["total_latency_ms"] / 1000, 3)
        rows.append(
            f"| {item['sample_id']} | {item['expected_doc_type']} | "
            f"{'Y' if item['extraction_success'] else 'N'} | {completeness_text} | "
            f"{total_time_s}s | {mode} |"
        )
    lines = [
        "# DocStruct 评测报告",
        "",
        f"- 生成时间：`{summary['generated_at']}`",
        f"- 模型：`{summary['model_name']}`",
        f"- Prompt 版本：`{summary['prompt_version']}`",
        f"- 样本数：`{summary['sample_count']}`",
        f"- 抽取成功率：`{summary['extraction_success_rate']}`",
        f"- 平均耗时：`{summary['avg_total_latency_s']}s`",
        f"- 平均完整率：`{summary['avg_completeness_score']}`",
        "",
        "## 明细",
        "",
        *rows,
    ]
    return "\n".join(lines) + "\n"


async def _main_async() -> None:
    args = _parse_args()
    settings = get_settings()
    manifest = _load_manifest(Path(args.manifest))
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    samples = manifest.get("samples", [])
    results = [await _evaluate_sample(sample) for sample in samples]
    payload = {
        "summary": _build_summary(results, args.prompt_version, settings),
        "results": results,
    }

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    json_path = output_dir / f"eval-{timestamp}.json"
    md_path = output_dir / f"eval-{timestamp}.md"

    with json_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
    with md_path.open("w", encoding="utf-8") as handle:
        handle.write(_build_markdown_report(payload))

    print(f"评测完成: {json_path}")
    print(f"报告完成: {md_path}")


def main() -> None:
    asyncio.run(_main_async())


if __name__ == "__main__":
    main()

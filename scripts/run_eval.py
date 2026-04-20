import argparse
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
from core.extractor import classify_document, extract_structure_with_meta
from core.parser import ParserFactory
from core.url_parser import parse_url_to_markdown
from schemas.models import (
    ApiDocument,
    DesignDocument,
    DocType,
    IssueDocument,
    ManualDocument,
    SrsDocument,
    TestDocument,
)


TYPE_MODEL_MAP = {
    DocType.SRS: SrsDocument,
    DocType.API: ApiDocument,
    DocType.DESIGN: DesignDocument,
    DocType.TEST: TestDocument,
    DocType.MANUAL: ManualDocument,
    DocType.ISSUE: IssueDocument,
}


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="运行 DocStruct 最小评测基线。")
    parser.add_argument(
        "--manifest",
        default="experiments/datasets/baseline_manifest.json",
        help="评测清单 JSON 路径",
    )
    parser.add_argument(
        "--output-dir",
        default="experiments/results",
        help="结果输出目录",
    )
    parser.add_argument(
        "--prompt-version",
        default="baseline-v1",
        help="本次实验使用的 Prompt 版本标识",
    )
    parser.add_argument(
        "--extraction-model-source",
        choices=["expected", "predicted"],
        default="expected",
        help="抽取时使用期望文类还是分类预测文类",
    )
    return parser.parse_args()


def _load_manifest(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


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


def _resolve_target_doc_type(
    expected_doc_type: str,
    predicted_doc_type: str,
    source: str,
) -> DocType | None:
    target = expected_doc_type if source == "expected" else predicted_doc_type
    try:
        return DocType(target)
    except ValueError:
        return None


def _evaluate_sample(sample: dict[str, Any], args: argparse.Namespace, settings) -> dict[str, Any]:
    sample_id = sample["sample_id"]
    source_type = sample.get("source_type", "file")
    expected_doc_type = sample["expected_doc_type"]

    parse_start = time.perf_counter()
    if source_type == "url":
        source_url = sample["url"]
        _, markdown = parse_url_to_markdown(source_url)
        source_ref = source_url
    else:
        file_path = Path(sample["file_path"])
        parser = ParserFactory.get_parser(str(file_path))
        markdown = parser.parse(str(file_path))
        source_ref = str(file_path).replace("\\", "/")
    parse_ms = round((time.perf_counter() - parse_start) * 1000, 2)

    classify_start = time.perf_counter()
    classification = classify_document(markdown)
    classify_ms = round((time.perf_counter() - classify_start) * 1000, 2)

    predicted_doc_type = classification.doc_type.value
    classification_correct = predicted_doc_type == expected_doc_type

    extraction_model = _resolve_target_doc_type(
        expected_doc_type=expected_doc_type,
        predicted_doc_type=predicted_doc_type,
        source=args.extraction_model_source,
    )

    extracted_data = None
    extraction_meta = None
    extraction_error = None
    extraction_ms = None

    if extraction_model and extraction_model in TYPE_MODEL_MAP:
        extract_start = time.perf_counter()
        try:
            extracted, extraction_meta = extract_structure_with_meta(
                markdown_content=markdown,
                response_model=TYPE_MODEL_MAP[extraction_model],
            )
            extracted_data = extracted.model_dump(mode="json")
        except Exception as exc:
            extraction_error = str(exc)
        extraction_ms = round((time.perf_counter() - extract_start) * 1000, 2)
    else:
        extraction_error = f"无法确定抽取模型: source={args.extraction_model_source}"

    completeness = _compute_completeness(extracted_data)
    total_ms = round(parse_ms + classify_ms + (extraction_ms or 0), 2)

    return {
        "sample_id": sample_id,
        "source_type": source_type,
        "file_path": source_ref,
        "expected_doc_type": expected_doc_type,
        "predicted_doc_type": predicted_doc_type,
        "classification_correct": classification_correct,
        "classification_confidence": classification.confidence,
        "classification_reasoning": classification.reasoning,
        "prompt_version": args.prompt_version,
        "model_name": settings.llm_model,
        "extraction_model_source": args.extraction_model_source,
        "extraction_target_doc_type": extraction_model.value if extraction_model else None,
        "parse_latency_ms": parse_ms,
        "classification_latency_ms": classify_ms,
        "extraction_latency_ms": extraction_ms,
        "total_latency_ms": total_ms,
        "content_length": len(markdown),
        "used_chunking": bool(extraction_meta and extraction_meta.get("mode") in {"chunked", "single_fallback"}),
        "extraction_success": extraction_error is None and extracted_data is not None,
        "completeness_score": completeness,
        "extraction_meta": extraction_meta,
        "error_message": extraction_error,
        "extracted_data": extracted_data,
        "notes": sample.get("notes"),
    }


def _build_summary(results: list[dict[str, Any]], args: argparse.Namespace, settings) -> dict[str, Any]:
    total = len(results)
    classified_correct = sum(1 for item in results if item["classification_correct"])
    extraction_success = sum(1 for item in results if item["extraction_success"])
    chunked = sum(1 for item in results if item["used_chunking"])
    completeness_scores = [
        item["completeness_score"]
        for item in results
        if item["completeness_score"] is not None
    ]
    avg_latency_ms = round(
        sum(item["total_latency_ms"] for item in results) / total,
        2,
    ) if total else 0.0
    avg_completeness = round(sum(completeness_scores) / len(completeness_scores), 4) if completeness_scores else None

    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "prompt_version": args.prompt_version,
        "model_name": settings.llm_model,
        "embedding_model": settings.embedding_model,
        "sample_count": total,
        "classification_accuracy": round(classified_correct / total, 4) if total else 0.0,
        "extraction_success_rate": round(extraction_success / total, 4) if total else 0.0,
        "chunked_sample_rate": round(chunked / total, 4) if total else 0.0,
        "avg_total_latency_ms": avg_latency_ms,
        "avg_total_latency_s": round(avg_latency_ms / 1000, 3),
        "avg_completeness_score": avg_completeness,
        "extraction_model_source": args.extraction_model_source,
    }


def _build_markdown_report(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    rows = [
        "| sample_id | expected | predicted | class_ok | extract_ok | completeness | total_time | mode |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]

    for item in payload["results"]:
        mode = (item.get("extraction_meta") or {}).get("mode", "-")
        completeness = item["completeness_score"]
        completeness_text = "-" if completeness is None else str(completeness)
        total_time_s = round(item['total_latency_ms'] / 1000, 3)
        rows.append(
            f"| {item['sample_id']} | {item['expected_doc_type']} | {item['predicted_doc_type']} | "
            f"{'Y' if item['classification_correct'] else 'N'} | "
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
        f"- 文类识别准确率：`{summary['classification_accuracy']}`",
        f"- 抽取成功率：`{summary['extraction_success_rate']}`",
        f"- 平均耗时：`{summary['avg_total_latency_s']}s`",
        f"- 平均完整率：`{summary['avg_completeness_score']}`",
        "",
        "## 明细",
        "",
        *rows,
    ]
    return "\n".join(lines) + "\n"


def main() -> None:
    args = _parse_args()
    settings = get_settings()
    manifest_path = Path(args.manifest)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    manifest = _load_manifest(manifest_path)
    samples = manifest.get("samples", [])
    results = [_evaluate_sample(sample, args, settings) for sample in samples]
    payload = {
        "summary": _build_summary(results, args, settings),
        "results": results,
    }

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    json_path = output_dir / f"eval-{timestamp}.json"
    md_path = output_dir / f"eval-{timestamp}.md"

    with json_path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    with md_path.open("w", encoding="utf-8") as f:
        f.write(_build_markdown_report(payload))

    print(f"评测完成: {json_path}")
    print(f"报告完成: {md_path}")


if __name__ == "__main__":
    main()

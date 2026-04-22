from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from core.config import get_settings
from core.experiment_sdk import extract_document, parse_document
from core.llm_judge import judge_extraction
from core.schema_registry import normalize_doc_type


DEFAULT_CONFIGS = {
    "exp1": "experiments/configs/exp1.json",
    "exp2": "experiments/configs/exp2.json",
    "exp3": "experiments/configs/exp3.json",
}


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="运行 DocStruct 离线实验。")
    parser.add_argument("--experiment", choices=sorted(DEFAULT_CONFIGS.keys()), default="exp1")
    parser.add_argument("--config", help="实验配置文件路径，默认使用 experiments/configs 下的预置配置。")
    parser.add_argument("--manifest", help="覆盖配置中的样本清单路径。")
    parser.add_argument("--output-dir", default="experiments/results")
    parser.add_argument("--enable-llm-judge", action="store_true", help="开启基于标准答案与生成答案的 LLM 整体评审。")
    return parser.parse_args()


def _resolve_path(path_text: str | None, *, base_dir: Path) -> Path | None:
    if not path_text:
        return None
    path = Path(path_text)
    if path.is_absolute():
        return path
    return (base_dir / path).resolve()


def _load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _load_text(path: Path | None) -> str | None:
    if path is None:
        return None
    return path.read_text(encoding="utf-8")


def _judge_enabled(config: dict[str, Any], cli_enabled: bool) -> bool:
    judge_config = config.get("judge") or {}
    return cli_enabled and judge_config.get("enabled", True)


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


def _flatten_json(value: Any, prefix: str = "") -> dict[str, Any]:
    if isinstance(value, dict):
        if not value:
            return {prefix or "$": {}}
        flattened: dict[str, Any] = {}
        for key, item in value.items():
            child_prefix = f"{prefix}.{key}" if prefix else key
            flattened.update(_flatten_json(item, child_prefix))
        return flattened
    if isinstance(value, list):
        if not value:
            return {prefix or "$": []}
        flattened: dict[str, Any] = {}
        for index, item in enumerate(value):
            child_prefix = f"{prefix}[{index}]" if prefix else f"[{index}]"
            flattened.update(_flatten_json(item, child_prefix))
        return flattened
    return {prefix or "$": value}


def _compute_field_level_score(extracted: dict[str, Any] | None, golden: dict[str, Any] | None) -> float | None:
    if not extracted or not golden:
        return None
    golden_flat = _flatten_json(golden)
    extracted_flat = _flatten_json(extracted)
    if not golden_flat:
        return None

    matched = 0
    for key, expected in golden_flat.items():
        actual = extracted_flat.get(key)
        if actual == expected:
            matched += 1
    return round(matched / len(golden_flat), 4)


def _matches_filters(sample: dict[str, Any], filters: dict[str, Any] | None) -> bool:
    if not filters:
        return True

    sample_doc_type = sample.get("doc_type")
    allowed_doc_types = filters.get("doc_types") or []
    if allowed_doc_types and sample_doc_type not in allowed_doc_types:
        return False

    sample_tags = set(sample.get("tags") or [])
    required_tags = set(filters.get("required_tags") or [])
    if required_tags and not required_tags.issubset(sample_tags):
        return False

    excluded_tags = set(filters.get("excluded_tags") or [])
    if excluded_tags and sample_tags.intersection(excluded_tags):
        return False

    return True


def _aggregate_bucket(items: list[dict[str, Any]]) -> dict[str, Any]:
    success_count = sum(1 for item in items if item["success"])
    completeness_values = [item["completeness_score"] for item in items if item["completeness_score"] is not None]
    field_scores = [item["field_level_score"] for item in items if item["field_level_score"] is not None]
    judge_scores = [item["llm_judge_score"] for item in items if item["llm_judge_score"] is not None]
    judge_completed = sum(1 for item in items if item["llm_judge_status"] == "completed")
    latency_values = [item["total_latency_ms"] for item in items]
    return {
        "sample_count": len(items),
        "success_rate": round(success_count / len(items), 4) if items else 0.0,
        "avg_total_latency_ms": round(sum(latency_values) / len(latency_values), 2) if latency_values else 0.0,
        "avg_completeness_score": round(sum(completeness_values) / len(completeness_values), 4) if completeness_values else None,
        "avg_field_level_score": round(sum(field_scores) / len(field_scores), 4) if field_scores else None,
        "avg_llm_judge_score": round(sum(judge_scores) / len(judge_scores), 2) if judge_scores else None,
        "judge_coverage_rate": round(judge_completed / len(items), 4) if items else 0.0,
    }


def _build_grouped_summary(results: list[dict[str, Any]], group_key: str) -> dict[str, Any]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in results:
        values = item.get(group_key)
        if isinstance(values, list):
            for value in values:
                grouped[str(value)].append(item)
            continue
        grouped[str(values)].append(item)
    return {key: _aggregate_bucket(items) for key, items in sorted(grouped.items(), key=lambda pair: pair[0])}


def _build_summary(
    *,
    experiment_id: str,
    config_path: Path,
    manifest_path: Path,
    results: list[dict[str, Any]],
    llm_judge_enabled: bool,
) -> dict[str, Any]:
    settings = get_settings()
    overall = _aggregate_bucket(results)
    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "experiment_id": experiment_id,
        "config_path": str(config_path).replace("\\", "/"),
        "manifest_path": str(manifest_path).replace("\\", "/"),
        "model_name": settings.llm_model,
        "sample_count": overall["sample_count"],
        "success_rate": overall["success_rate"],
        "avg_total_latency_ms": overall["avg_total_latency_ms"],
        "avg_total_latency_s": round(overall["avg_total_latency_ms"] / 1000, 3),
        "avg_completeness_score": overall["avg_completeness_score"],
        "avg_field_level_score": overall["avg_field_level_score"],
        "avg_llm_judge_score": overall["avg_llm_judge_score"],
        "judge_coverage_rate": overall["judge_coverage_rate"],
        "llm_judge_status": "enabled" if llm_judge_enabled else "disabled",
        "by_variant": _build_grouped_summary(results, "variant_id"),
        "by_doc_type": _build_grouped_summary(results, "doc_type"),
        "by_tag": _build_grouped_summary(results, "tags"),
    }


def _build_markdown_report(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    rows = [
        "| variant | sample_id | doc_type | success | completeness | field_score | judge_score | judge_decision | total_time | mode |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for item in payload["results"]:
        extraction_meta = item.get("extraction_meta") or {}
        rows.append(
            f"| {item['variant_id']} | {item['sample_id']} | {item['doc_type']} | "
            f"{'Y' if item['success'] else 'N'} | {item['completeness_score'] if item['completeness_score'] is not None else '-'} | "
            f"{item['field_level_score'] if item['field_level_score'] is not None else '-'} | "
            f"{item['llm_judge_score'] if item['llm_judge_score'] is not None else '-'} | "
            f"{item['llm_judge_decision'] if item['llm_judge_decision'] is not None else item['llm_judge_status']} | "
            f"{round(item['total_latency_ms'] / 1000, 3)}s | {extraction_meta.get('mode', '-')} |"
        )

    lines = [
        "# DocStruct 实验报告",
        "",
        f"- 实验：`{summary['experiment_id']}`",
        f"- 生成时间：`{summary['generated_at']}`",
        f"- 配置：`{summary['config_path']}`",
        f"- 数据集：`{summary['manifest_path']}`",
        f"- 默认模型：`{summary['model_name']}`",
        f"- 样本数：`{summary['sample_count']}`",
        f"- 成功率：`{summary['success_rate']}`",
        f"- 平均耗时：`{summary['avg_total_latency_s']}s`",
        f"- 平均完整率：`{summary['avg_completeness_score']}`",
        f"- 平均字段分：`{summary['avg_field_level_score']}`",
        f"- 平均 Judge 分：`{summary['avg_llm_judge_score']}`",
        f"- Judge 覆盖率：`{summary['judge_coverage_rate']}`",
        f"- LLM 评审：`{summary['llm_judge_status']}`",
        "",
        "## 明细",
        "",
        *rows,
        "",
        "## Judge Summary",
        "",
    ]
    for item in payload["results"]:
        if not item.get("llm_judge_summary"):
            continue
        lines.append(
            f"- `{item['variant_id']} / {item['sample_id']}` "
            f"[{item['llm_judge_score']}] {item['llm_judge_summary']}"
        )
    return "\n".join(lines) + "\n"


def _resolve_judge_settings(config: dict[str, Any], variant: dict[str, Any], config_dir: Path) -> dict[str, Any]:
    judge_config = dict(config.get("judge") or {})
    variant_judge_config = variant.get("judge") or {}
    judge_config.update(variant_judge_config)
    prompt_path = _resolve_path(judge_config.get("prompt_template"), base_dir=config_dir)
    return {
        "model_name": judge_config.get("model_name"),
        "temperature": float(judge_config.get("temperature", 0.0)),
        "prompt_template": _load_text(prompt_path),
    }


async def _evaluate_variant_sample(
    sample: dict[str, Any],
    *,
    config: dict[str, Any],
    llm_judge_enabled: bool,
    variant: dict[str, Any],
    config_dir: Path,
) -> dict[str, Any]:
    sample_file = _resolve_path(sample["file_path"], base_dir=ROOT_DIR)
    if sample_file is None or not sample_file.exists():
        raise FileNotFoundError(f"样本文件不存在: {sample.get('file_path')}")

    doc_type = normalize_doc_type(sample["doc_type"]).value
    prompt_path = _resolve_path(variant.get("prompt_template"), base_dir=config_dir)
    prompt_template = _load_text(prompt_path)
    golden_path = _resolve_path(sample.get("golden_path"), base_dir=ROOT_DIR)
    golden_payload = _load_json(golden_path) if golden_path and golden_path.exists() else None

    error_message = None
    extracted_data = None
    extraction_meta = None
    parse_meta = None
    markdown_content = None
    parse_latency_ms = None
    extraction_latency_ms = None
    llm_judge_status = "disabled"
    llm_judge_score = None
    llm_judge_decision = None
    llm_judge_summary = None
    llm_judge_issues: list[str] = []
    llm_judge_model_name = None
    llm_judge_latency_ms = None
    llm_judge_error = None

    try:
        parse_start = time.perf_counter()
        markdown_content, parse_meta = await asyncio.to_thread(parse_document, sample_file)
        parse_latency_ms = round((time.perf_counter() - parse_start) * 1000, 2)

        extract_start = time.perf_counter()
        extracted_data, extraction_meta = await extract_document(
            markdown_content,
            doc_type,
            prompt_template=prompt_template,
            model_name=variant.get("model_name"),
        )
        extraction_latency_ms = round((time.perf_counter() - extract_start) * 1000, 2)
        error_message = extraction_meta.get("error_message")
    except Exception as exc:
        error_message = str(exc)

    total_latency_ms = round((parse_latency_ms or 0) + (extraction_latency_ms or 0), 2)
    success = error_message is None and extracted_data is not None
    completeness_score = _compute_completeness(extracted_data)
    field_level_score = _compute_field_level_score(extracted_data, golden_payload)
    used_model = None
    if extraction_meta:
        used_model = extraction_meta.get("model_name")

    if llm_judge_enabled:
        if golden_payload is None:
            llm_judge_status = "missing_golden"
        elif not success or extracted_data is None or markdown_content is None:
            llm_judge_status = "generation_failed"
        else:
            judge_settings = _resolve_judge_settings(config, variant, config_dir)
            llm_judge_model_name = judge_settings["model_name"] or get_settings().llm_model
            judge_start = time.perf_counter()
            try:
                judge_result = await asyncio.to_thread(
                    judge_extraction,
                    doc_type=doc_type,
                    markdown_content=markdown_content,
                    golden_payload=golden_payload,
                    predicted_payload=extracted_data,
                    model_name=judge_settings["model_name"],
                    prompt_template=judge_settings["prompt_template"],
                    temperature=judge_settings["temperature"],
                )
                llm_judge_latency_ms = round((time.perf_counter() - judge_start) * 1000, 2)
                llm_judge_status = "completed"
                llm_judge_score = round(float(judge_result.score), 2)
                llm_judge_decision = judge_result.decision
                llm_judge_summary = judge_result.summary.strip()
                llm_judge_issues = [issue.strip() for issue in judge_result.issues if issue and issue.strip()]
            except Exception as exc:
                llm_judge_latency_ms = round((time.perf_counter() - judge_start) * 1000, 2)
                llm_judge_status = "judge_error"
                llm_judge_error = str(exc)

    return {
        "experiment_id": variant.get("experiment_id"),
        "variant_id": variant["variant_id"],
        "variant_label": variant.get("label"),
        "sample_id": sample["sample_id"],
        "file_path": str(sample_file).replace("\\", "/"),
        "doc_type": doc_type,
        "tags": sample.get("tags", []),
        "notes": sample.get("notes"),
        "prompt_template_path": str(prompt_path).replace("\\", "/") if prompt_path else None,
        "requested_model_name": variant.get("model_name"),
        "used_model_name": used_model,
        "parse_latency_ms": parse_latency_ms,
        "extraction_latency_ms": extraction_latency_ms,
        "total_latency_ms": total_latency_ms,
        "content_length": len(markdown_content) if markdown_content else None,
        "success": success,
        "doc_type_match": bool(extracted_data and extracted_data.get("doc_type") == doc_type),
        "completeness_score": completeness_score,
        "field_level_score": field_level_score,
        "golden_available": golden_payload is not None,
        "llm_judge_status": llm_judge_status,
        "llm_judge_score": llm_judge_score,
        "llm_judge_decision": llm_judge_decision,
        "llm_judge_summary": llm_judge_summary,
        "llm_judge_issues": llm_judge_issues,
        "llm_judge_model_name": llm_judge_model_name,
        "llm_judge_latency_ms": llm_judge_latency_ms,
        "llm_judge_error": llm_judge_error,
        "parse_meta": parse_meta,
        "extraction_meta": extraction_meta,
        "error_message": error_message,
        "extracted_data": extracted_data,
    }


async def _main_async() -> None:
    args = _parse_args()
    config_path = _resolve_path(args.config or DEFAULT_CONFIGS[args.experiment], base_dir=ROOT_DIR)
    if config_path is None or not config_path.exists():
        raise FileNotFoundError(f"实验配置不存在: {args.config or DEFAULT_CONFIGS[args.experiment]}")

    config = _load_json(config_path)
    config_dir = config_path.parent
    manifest_path = _resolve_path(args.manifest or config.get("manifest"), base_dir=config_dir)
    if manifest_path is None or not manifest_path.exists():
        raise FileNotFoundError(f"样本清单不存在: {args.manifest or config.get('manifest')}")

    manifest = _load_json(manifest_path)
    filters = config.get("sample_filters")
    samples = [sample for sample in manifest.get("samples", []) if _matches_filters(sample, filters)]
    if not samples:
        raise ValueError("过滤后没有可用样本")

    variants = config.get("variants") or [{"variant_id": "default"}]
    output_dir = _resolve_path(args.output_dir, base_dir=ROOT_DIR)
    assert output_dir is not None
    output_dir.mkdir(parents=True, exist_ok=True)
    llm_judge_enabled = _judge_enabled(config, args.enable_llm_judge)

    results: list[dict[str, Any]] = []
    for variant in variants:
        variant_payload = dict(variant)
        variant_payload["experiment_id"] = config.get("experiment_id", args.experiment)
        for sample in samples:
            results.append(
                await _evaluate_variant_sample(
                    sample,
                    config=config,
                    llm_judge_enabled=llm_judge_enabled,
                    variant=variant_payload,
                    config_dir=config_dir,
                )
            )

    payload = {
        "summary": _build_summary(
            experiment_id=config.get("experiment_id", args.experiment),
            config_path=config_path,
            manifest_path=manifest_path,
            results=results,
            llm_judge_enabled=llm_judge_enabled,
        ),
        "config": config,
        "results": results,
    }

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    experiment_id = config.get("experiment_id", args.experiment)
    json_path = output_dir / f"{experiment_id}-{timestamp}.json"
    md_path = output_dir / f"{experiment_id}-{timestamp}.md"

    with json_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
    with md_path.open("w", encoding="utf-8") as handle:
        handle.write(_build_markdown_report(payload))

    print(f"实验完成: {json_path}")
    print(f"报告完成: {md_path}")


def main() -> None:
    asyncio.run(_main_async())


if __name__ == "__main__":
    main()

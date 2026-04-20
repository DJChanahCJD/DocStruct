"""
矩阵评测脚本：5 模型 × 4 Prompt 版本 = 20 组实验

用法：
    python scripts/run_matrix_eval.py
    python scripts/run_matrix_eval.py --manifest experiments/datasets/baseline_manifest.json
    python scripts/run_matrix_eval.py --models qwen-doc-turbo deepseek-v3.2
    python scripts/run_matrix_eval.py --prompts en-concise zh-detailed
    python scripts/run_matrix_eval.py --samples srs-md-001 req-analysis-pdf-001

输出：
    experiments/results/matrix-eval-{timestamp}.json  # 完整数据
    experiments/results/matrix-eval-{timestamp}.md    # 对比摘要报告
"""

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

# 所有可用模型及其单价（元/百万 Token）
MODEL_PRICING: dict[str, dict[str, float]] = {
    "qwen-doc-turbo": {"input": 0.6, "output": 1.0},
    "deepseek-v3.2":  {"input": 2.0, "output": 3.0},
    "kimi-k2.5":      {"input": 4.0, "output": 21.0},
    "glm-4.7":        {"input": 3.0, "output": 14.0},
    "MiniMax-M2.5":   {"input": 2.1, "output": 8.4},
}

DEFAULT_MODELS = list(MODEL_PRICING.keys())

# Prompt 版本与文件的映射（相对于 PROMPTS_DIR）
DEFAULT_PROMPTS = ["en-concise", "en-detailed", "zh-concise", "zh-detailed"]
PROMPTS_DIR = ROOT_DIR / "experiments" / "prompts"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="DocStruct 矩阵评测：多模型 × 多 Prompt 对比")
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
        "--models",
        nargs="+",
        default=DEFAULT_MODELS,
        help="参与对比的模型 ID 列表",
    )
    parser.add_argument(
        "--prompts",
        nargs="+",
        default=DEFAULT_PROMPTS,
        help="参与对比的 Prompt 版本标识列表",
    )
    parser.add_argument(
        "--extraction-model-source",
        choices=["expected", "predicted"],
        default="expected",
        help="抽取时使用期望文类还是预测文类",
    )
    parser.add_argument(
        "--samples",
        nargs="+",
        default=None,
        help="只跑指定 sample_id，不填则跑全部",
    )
    return parser.parse_args()


def _load_manifest(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _load_prompt_template(prompt_version: str) -> str:
    """从 experiments/prompts/{version}.txt 加载 Prompt 模板。"""
    prompt_file = PROMPTS_DIR / f"{prompt_version}.txt"
    if not prompt_file.exists():
        raise FileNotFoundError(f"Prompt 文件不存在: {prompt_file}")
    return prompt_file.read_text(encoding="utf-8")


def _is_empty_value(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return value.strip() == ""
    if isinstance(value, (list, dict)):
        return len(value) == 0
    return False


def _count_fields(value: Any) -> tuple[int, int]:
    """递归统计字段总数与已填充数。"""
    if isinstance(value, dict):
        total, filled = 0, 0
        for key, item in value.items():
            if key == "doc_type":
                continue
            child_total, child_filled = _count_fields(item)
            if child_total == 0:
                total += 1
                if not _is_empty_value(item):
                    filled += 1
            else:
                total += child_total
                filled += child_filled
        return total, filled

    if isinstance(value, list):
        if not value:
            return 1, 0
        total, filled = 0, 0
        for item in value:
            child_total, child_filled = _count_fields(item)
            if child_total == 0:
                total += 1
                if not _is_empty_value(item):
                    filled += 1
            else:
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


def _estimate_cost_cny(model_id: str, input_tokens: int, output_tokens: int) -> float | None:
    """按官方单价估算费用（元），Token 数从 LLM 响应获取时使用，否则返回 None。"""
    pricing = MODEL_PRICING.get(model_id)
    if not pricing:
        return None
    cost = (input_tokens * pricing["input"] + output_tokens * pricing["output"]) / 1_000_000
    return round(cost, 6)


def _parse_document(sample: dict[str, Any]) -> tuple[str, str]:
    """解析文档并返回 (markdown, source_ref)。"""
    source_type = sample.get("source_type", "file")
    if source_type == "url":
        source_url = sample["url"]
        _, markdown = parse_url_to_markdown(source_url)
        return markdown, source_url
    file_path = Path(sample["file_path"])
    parser = ParserFactory.get_parser(str(file_path))
    markdown = parser.parse(str(file_path))
    return markdown, str(file_path).replace("\\", "/")


def _run_single_cell(
    markdown: str,
    sample: dict[str, Any],
    model_id: str,
    prompt_version: str,
    prompt_template: str,
    extraction_model_source: str,
) -> dict[str, Any]:
    """运行单个实验格（一个模型 × 一个 Prompt 版本）。"""
    expected_doc_type = sample["expected_doc_type"]

    # 分类（固定使用 qwen-doc-turbo，不受模型参数影响）
    classify_start = time.perf_counter()
    classification = classify_document(markdown)
    classify_ms = round((time.perf_counter() - classify_start) * 1000, 2)

    predicted_doc_type = classification.doc_type.value
    classification_correct = predicted_doc_type == expected_doc_type

    # 确定用于抽取的文类
    target_type_str = expected_doc_type if extraction_model_source == "expected" else predicted_doc_type
    try:
        target_doc_type = DocType(target_type_str)
    except ValueError:
        target_doc_type = None

    extracted_data = None
    extraction_meta = None
    extraction_error = None
    extraction_ms = None
    input_tokens = 0
    output_tokens = 0

    if target_doc_type and target_doc_type in TYPE_MODEL_MAP:
        extract_start = time.perf_counter()
        try:
            extracted, extraction_meta = extract_structure_with_meta(
                markdown_content=markdown,
                response_model=TYPE_MODEL_MAP[target_doc_type],
                llm_model=model_id,
                prompt_override=prompt_template,
            )
            extracted_data = extracted.model_dump(mode="json")
        except Exception as exc:
            extraction_error = str(exc)
        extraction_ms = round((time.perf_counter() - extract_start) * 1000, 2)
    else:
        extraction_error = f"无法确定抽取文类: source={extraction_model_source}, type={target_type_str}"

    completeness = _compute_completeness(extracted_data)
    total_ms = round(classify_ms + (extraction_ms or 0), 2)
    estimated_cost = _estimate_cost_cny(model_id, input_tokens, output_tokens) if input_tokens else None

    return {
        "model_id": model_id,
        "prompt_version": prompt_version,
        "sample_id": sample["sample_id"],
        "expected_doc_type": expected_doc_type,
        "predicted_doc_type": predicted_doc_type,
        "classification_correct": classification_correct,
        "classification_confidence": classification.confidence,
        "extraction_success": extraction_error is None and extracted_data is not None,
        "completeness_score": completeness,
        "classification_latency_ms": classify_ms,
        "extraction_latency_ms": extraction_ms,
        "total_latency_ms": total_ms,
        "used_chunking": bool(extraction_meta and extraction_meta.get("mode") in {"chunked", "single_fallback"}),
        "extraction_meta": extraction_meta,
        "error_message": extraction_error,
        "extracted_data": extracted_data,
        "estimated_cost_cny": estimated_cost,
    }


def _build_matrix_summary(
    cells: list[dict[str, Any]],
    models: list[str],
    prompts: list[str],
) -> dict[str, Any]:
    """构建按模型和 Prompt 分组的聚合摘要。"""

    def _agg(group: list[dict]) -> dict[str, Any]:
        total = len(group)
        if total == 0:
            return {}
        success = sum(1 for c in group if c["extraction_success"])
        scores = [c["completeness_score"] for c in group if c["completeness_score"] is not None]
        latencies = [c["total_latency_ms"] for c in group]
        return {
            "sample_count": total,
            "extraction_success_rate": round(success / total, 4),
            "avg_completeness_score": round(sum(scores) / len(scores), 4) if scores else None,
            "avg_total_latency_ms": round(sum(latencies) / total, 2),
        }

    by_model: dict[str, Any] = {}
    for model_id in models:
        group = [c for c in cells if c["model_id"] == model_id]
        by_model[model_id] = _agg(group)

    by_prompt: dict[str, Any] = {}
    for pv in prompts:
        group = [c for c in cells if c["prompt_version"] == pv]
        by_prompt[pv] = _agg(group)

    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "total_cells": len(cells),
        "models_tested": models,
        "prompts_tested": prompts,
        "by_model": by_model,
        "by_prompt": by_prompt,
    }


def _build_markdown_report(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    cells = payload["cells"]
    models = summary["models_tested"]
    prompts = summary["prompts_tested"]

    lines = [
        "# DocStruct 矩阵评测报告",
        "",
        f"- 生成时间：`{summary['generated_at']}`",
        f"- 实验组数：`{summary['total_cells']}`",
        f"- 模型：`{', '.join(models)}`",
        f"- Prompt 版本：`{', '.join(prompts)}`",
        "",
        "---",
        "",
        "## 按模型聚合",
        "",
        "| 模型 | 抽取成功率 | 平均完整率 | 平均耗时(ms) | 输入价(元/M) | 输出价(元/M) |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for model_id in models:
        agg = summary["by_model"].get(model_id, {})
        pricing = MODEL_PRICING.get(model_id, {})
        lines.append(
            f"| {model_id} "
            f"| {agg.get('extraction_success_rate', '-')} "
            f"| {agg.get('avg_completeness_score', '-')} "
            f"| {agg.get('avg_total_latency_ms', '-')} "
            f"| {pricing.get('input', '-')} "
            f"| {pricing.get('output', '-')} |"
        )

    lines += [
        "",
        "## 按 Prompt 版本聚合",
        "",
        "| Prompt 版本 | 抽取成功率 | 平均完整率 | 平均耗时(ms) |",
        "| --- | --- | --- | --- |",
    ]
    for pv in prompts:
        agg = summary["by_prompt"].get(pv, {})
        lines.append(
            f"| {pv} "
            f"| {agg.get('extraction_success_rate', '-')} "
            f"| {agg.get('avg_completeness_score', '-')} "
            f"| {agg.get('avg_total_latency_ms', '-')} |"
        )

    lines += [
        "",
        "---",
        "",
        "## 完整明细（模型 × Prompt × 样本）",
        "",
        "| 模型 | Prompt | 样本 | 抽取成功 | 完整率 | 耗时(ms) | 模式 |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for cell in cells:
        mode = (cell.get("extraction_meta") or {}).get("mode", "-")
        completeness = cell["completeness_score"]
        lines.append(
            f"| {cell['model_id']} "
            f"| {cell['prompt_version']} "
            f"| {cell['sample_id']} "
            f"| {'Y' if cell['extraction_success'] else 'N'} "
            f"| {completeness if completeness is not None else '-'} "
            f"| {cell['total_latency_ms']} "
            f"| {mode} |"
        )

    return "\n".join(lines) + "\n"


def main() -> None:
    args = _parse_args()
    manifest_path = Path(args.manifest)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    manifest = _load_manifest(manifest_path)
    samples = manifest.get("samples", [])
    if args.samples:
        samples = [s for s in samples if s["sample_id"] in args.samples]

    # 预加载所有 Prompt 模板
    prompt_templates: dict[str, str] = {}
    for pv in args.prompts:
        prompt_templates[pv] = _load_prompt_template(pv)

    # 预解析所有文档（避免重复 parse）
    parsed_docs: dict[str, tuple[str, str]] = {}
    for sample in samples:
        sid = sample["sample_id"]
        print(f"  解析文档: {sid} ...", flush=True)
        parsed_docs[sid] = _parse_document(sample)
        print(f"  解析完成: {sid}", flush=True)

    total = len(args.models) * len(args.prompts) * len(samples)
    done = 0
    cells: list[dict[str, Any]] = []

    for model_id in args.models:
        for prompt_version in args.prompts:
            prompt_template = prompt_templates[prompt_version]
            for sample in samples:
                sid = sample["sample_id"]
                done += 1
                print(f"[{done}/{total}] 模型={model_id}  prompt={prompt_version}  样本={sid}", flush=True)
                markdown, source_ref = parsed_docs[sid]
                cell = _run_single_cell(
                    markdown=markdown,
                    sample=sample,
                    model_id=model_id,
                    prompt_version=prompt_version,
                    prompt_template=prompt_template,
                    extraction_model_source=args.extraction_model_source,
                )
                cell["source_ref"] = source_ref
                cells.append(cell)

    summary = _build_matrix_summary(cells, args.models, args.prompts)
    payload = {"summary": summary, "cells": cells}

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    json_path = output_dir / f"matrix-eval-{timestamp}.json"
    md_path = output_dir / f"matrix-eval-{timestamp}.md"

    with json_path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    with md_path.open("w", encoding="utf-8") as f:
        f.write(_build_markdown_report(payload))

    print(f"\n评测完成 ({total} 组)", flush=True)
    print(f"  JSON: {json_path}", flush=True)
    print(f"  报告: {md_path}", flush=True)

    # 打印快速摘要
    print("\n=== 模型对比 ===", flush=True)
    for model_id in args.models:
        agg = summary["by_model"].get(model_id, {})
        print(
            f"  {model_id:<20} 成功率={agg.get('extraction_success_rate', '-')}"
            f"  完整率={agg.get('avg_completeness_score', '-')}"
            f"  耗时={agg.get('avg_total_latency_ms', '-')}ms",
            flush=True,
        )

    print("\n=== Prompt 对比 ===", flush=True)
    for pv in args.prompts:
        agg = summary["by_prompt"].get(pv, {})
        print(
            f"  {pv:<16} 成功率={agg.get('extraction_success_rate', '-')}"
            f"  完整率={agg.get('avg_completeness_score', '-')}"
            f"  耗时={agg.get('avg_total_latency_ms', '-')}ms",
            flush=True,
        )


if __name__ == "__main__":
    main()

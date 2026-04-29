"""
离线评测脚本：对比系统抽取结果与人工标注 ground truth，计算 P/R/F1。

用法：
    # 离线模式（读取已缓存的抽取结果）
    python scripts/evaluate.py

    # 在线模式（实时调用 LLM 抽取）
    python scripts/evaluate.py --live

    # 指定输出目录
    python scripts/evaluate.py --output experiments/results/v1
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from datetime import datetime
from typing import Any


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

DEFAULT_MANIFEST = os.path.join(PROJECT_ROOT, "experiments", "manifest.json")
DEFAULT_CACHE_DIR = os.path.join(PROJECT_ROOT, "experiments", "results", "cached")
DEFAULT_OUTPUT_DIR = os.path.join(
    PROJECT_ROOT, "experiments", "results", datetime.now().strftime("%Y%m%d_%H%M%S")
)

SLOTS = ("entities", "requirements", "interfaces")
TYPE_FIELDS = {
    "entities": "entity_type",
    "requirements": "requirement_type",
    "interfaces": "interface_type",
}


# ── file helpers ──────────────────────────────────────────────


def load_json(path: str) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def save_json(data: Any, path: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)


def read_text(path: str) -> str:
    with open(path, "r", encoding="utf-8") as fh:
        return fh.read()


# ── matching logic ────────────────────────────────────────────


def jaccard(a: str, b: str) -> float:
    """字符级 Jaccard 相似度。"""
    set_a = set(a)
    set_b = set(b)
    if not set_a and not set_b:
        return 1.0
    union = set_a | set_b
    return len(set_a & set_b) / len(union) if union else 0.0


def _clean_name(name: str) -> str:
    """去除名称尾部的编号后缀，如"用户注册（SRS-USER-001）"→"用户注册"。"""
    import re
    cleaned = re.sub(r"\s*[（(][A-Za-z0-9\-_]+[）)]\s*$", "", name.strip())
    return cleaned.strip()


def _is_substring_match(a: str, b: str) -> bool:
    """短名称是否为长名称的子串（用于名称包含关系的快速匹配）。"""
    if len(a) >= 3 and len(b) >= 3:
        return a in b or b in a
    return False


def _get_name(item: dict[str, Any]) -> str:
    return _clean_name(item.get("name") or "")


def _get_raw_name(item: dict[str, Any]) -> str:
    return (item.get("name") or "").strip()


def _get_type(item: dict[str, Any], type_field: str) -> str:
    return str(item.get(type_field) or "").strip().lower()


def match_objects(
    preds: list[dict[str, Any]],
    gts: list[dict[str, Any]],
    type_field: str,
    threshold: float = 0.5,
) -> tuple[int, int, int, list[dict[str, Any]]]:
    """贪心匹配。先检查子串包含，再检查 Jaccard 相似度。"""
    matched_pairs: list[dict[str, Any]] = []
    used_pred: set[int] = set()
    used_gt: set[int] = set()

    # 按相似度降序排列所有候选对
    candidates: list[tuple[float, int, int]] = []
    for pi, pred in enumerate(preds):
        pred_clean = _get_name(pred)
        pred_raw = _get_raw_name(pred)
        pred_type = _get_type(pred, type_field)
        for gi, gt in enumerate(gts):
            gt_clean = _get_name(gt)
            gt_raw = _get_raw_name(gt)
            gt_type = _get_type(gt, type_field)
            if pred_type != gt_type:
                continue

            # 子串包含直接高分
            if _is_substring_match(pred_clean, gt_clean) or _is_substring_match(pred_raw, gt_raw):
                candidates.append((0.95, pi, gi))
                continue

            sim = jaccard(pred_clean, gt_clean)
            if sim >= threshold:
                candidates.append((sim, pi, gi))

    candidates.sort(key=lambda x: x[0], reverse=True)

    for sim, pi, gi in candidates:
        if pi not in used_pred and gi not in used_gt:
            used_pred.add(pi)
            used_gt.add(gi)
            matched_pairs.append({
                "pred_name": _get_raw_name(preds[pi]),
                "gt_name": _get_raw_name(gts[gi]),
                "similarity": round(sim, 4),
            })

    tp = len(matched_pairs)
    fp = len(preds) - tp
    fn = len(gts) - tp
    return tp, fp, fn, matched_pairs


# ── metrics ───────────────────────────────────────────────────


def compute_f1(tp: int, fp: int, fn: int) -> dict[str, float]:
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
    return {"precision": round(precision, 4), "recall": round(recall, 4), "f1": round(f1, 4)}


def evaluate_slot(
    pred: dict[str, Any],
    gt: dict[str, Any],
    slot: str,
) -> dict[str, Any]:
    pred_items = pred.get(slot) or []
    gt_items = gt.get(slot) or []
    type_field = TYPE_FIELDS[slot]
    tp, fp, fn, pairs = match_objects(pred_items, gt_items, type_field)
    metrics = compute_f1(tp, fp, fn)
    return {
        "slot": slot,
        "gt_count": len(gt_items),
        "pred_count": len(pred_items),
        "tp": tp,
        "fp": fp,
        "fn": fn,
        **metrics,
        "matched_pairs": pairs,
    }


# ── extraction helper ──────────────────────────────────────────


def _run_extraction(markdown: str, doc_type: Any) -> dict[str, Any]:
    """同步包装器：调用 LLM 抽取并返回 dict。"""
    from core.schema_registry import get_response_model

    response_model = get_response_model(doc_type)
    if response_model is None:
        return {"doc_type": str(doc_type), "entities": [], "processes": [], "requirements": [], "interfaces": [], "artifacts": []}

    from core.extractor import extract_structure_with_meta

    async def _run() -> dict[str, Any]:
        extracted, _meta = await extract_structure_with_meta(markdown, response_model)
        return extracted.model_dump(mode="json", exclude_none=True)

    return asyncio.run(_run())


# ── per-document evaluation ───────────────────────────────────


def evaluate_document(
    doc_path: str,
    gt_path: str,
    *,
    live: bool = False,
    cache_dir: str = DEFAULT_CACHE_DIR,
) -> dict[str, Any]:
    """评估单篇文档，返回指标字典。"""
    doc_abs = os.path.join(PROJECT_ROOT, doc_path)
    gt_abs = os.path.join(PROJECT_ROOT, gt_path)

    gt = load_json(gt_abs)
    doc_id = os.path.splitext(os.path.basename(doc_path))[0]

    # 获取抽取结果
    cache_path = os.path.join(cache_dir, f"{doc_id}.json")
    if not live:
        if os.path.exists(cache_path):
            pred = load_json(cache_path)
            mode = "cached"
        else:
            print(f"SKIP (no cache, use --live)")
            return None
    else:
        # 延迟导入，避免模块级 OpenAI 客户端初始化依赖代理配置
        from core.schema_registry import normalize_doc_type

        # MD/TXT 文件直接读取，PDF/DOCX 使用解析器
        ext = os.path.splitext(doc_abs)[1].lower()
        if ext in (".md", ".txt", ".markdown"):
            markdown = read_text(doc_abs)
        else:
            from core.parser import ParserFactory

            parser = ParserFactory.get_parser(doc_abs)
            if hasattr(parser, "parse_to_result"):
                markdown = parser.parse_to_result(doc_abs).markdown
            else:
                markdown = parser.parse(doc_abs)

        doc_type = normalize_doc_type(gt.get("doc_type"))

        extracted_data = _run_extraction(markdown, doc_type)
        pred = extracted_data
        mode = "live"
        save_json(pred, cache_path)

    # 按槽位评估
    slot_results = {}
    for slot in SLOTS:
        slot_results[slot] = evaluate_slot(pred, gt, slot)

    # 汇总
    all_tp = sum(r["tp"] for r in slot_results.values())
    all_fp = sum(r["fp"] for r in slot_results.values())
    all_fn = sum(r["fn"] for r in slot_results.values())
    summary = compute_f1(all_tp, all_fp, all_fn)

    return {
        "doc_id": doc_id,
        "doc_path": doc_path,
        "doc_type": gt.get("doc_type"),
        "mode": mode,
        "slots": slot_results,
        "summary": {"tp": all_tp, "fp": all_fp, "fn": all_fn, **summary},
    }


# ── batch evaluation ──────────────────────────────────────────


def evaluate_all(
    manifest_path: str = DEFAULT_MANIFEST,
    *,
    live: bool = False,
    cache_dir: str = DEFAULT_CACHE_DIR,
) -> dict[str, Any]:
    manifest = load_json(manifest_path)
    results = {}
    all_tp = all_fp = all_fn = 0

    for doc_path, gt_path in manifest.items():
        print(f"Evaluating: {doc_path} ...", end=" ", flush=True)
        result = evaluate_document(doc_path, gt_path, live=live, cache_dir=cache_dir)
        if result is None:
            continue
        results[doc_path] = result
        s = result["summary"]
        all_tp += s["tp"]
        all_fp += s["fp"]
        all_fn += s["fn"]
        print(f"F1={s['f1']:.3f} (P={s['precision']:.3f} R={s['recall']:.3f}) [{result['mode']}]")

    overall = compute_f1(all_tp, all_fp, all_fn)
    print(f"\nOverall: P={overall['precision']:.3f} R={overall['recall']:.3f} F1={overall['f1']:.3f}")

    return {
        "generated_at": datetime.now().isoformat(),
        "manifest": manifest_path,
        "mode": "live" if live else "cached",
        "overall": {"tp": all_tp, "fp": all_fp, "fn": all_fn, **overall},
        "documents": results,
    }


# ── reporting ─────────────────────────────────────────────────


def print_markdown_report(results: dict[str, Any]) -> None:
    """打印 Markdown 格式的评测报告。"""
    print("\n# 评测报告\n")
    print(f"生成时间：{results['generated_at']}")
    print(f"模式：{results['mode']}")
    overall = results["overall"]
    print(f"\n## 总体指标\n")
    print(f"| 指标 | 值 |")
    print(f"|---|---|")
    print(f"| Precision | {overall['precision']:.4f} |")
    print(f"| Recall | {overall['recall']:.4f} |")
    print(f"| F1 | {overall['f1']:.4f} |")
    print(f"| TP / FP / FN | {overall['tp']} / {overall['fp']} / {overall['fn']} |")

    print(f"\n## 按文档\n")
    print(f"| 文档 | 类型 | P | R | F1 | TP/FP/FN |")
    print(f"|---|---|---|---|---|---|")
    for doc in results["documents"].values():
        s = doc["summary"]
        print(f"| {doc['doc_id']} | {doc['doc_type']} | {s['precision']:.3f} | {s['recall']:.3f} | {s['f1']:.3f} | {s['tp']}/{s['fp']}/{s['fn']} |")

    print(f"\n## 按槽位\n")
    for slot in SLOTS:
        print(f"\n### {slot}\n")
        print(f"| 文档 | GT | Pred | TP | FP | FN | P | R | F1 |")
        print(f"|---|---|---|---|---|---|---|---|---|")
        for doc in results["documents"].values():
            r = doc["slots"][slot]
            print(f"| {doc['doc_id']} | {r['gt_count']} | {r['pred_count']} | {r['tp']} | {r['fp']} | {r['fn']} | {r['precision']:.3f} | {r['recall']:.3f} | {r['f1']:.3f} |")


def save_report(results: dict[str, Any], output_dir: str) -> str:
    """保存评测结果为 JSON 文件，返回输出路径。"""
    os.makedirs(output_dir, exist_ok=True)
    summary_path = os.path.join(output_dir, "summary.json")
    save_json(results, summary_path)

    # 保存 Markdown 报告
    md_path = os.path.join(output_dir, "report.md")
    with open(md_path, "w", encoding="utf-8") as fh:
        from io import StringIO
        import contextlib
        buf = StringIO()
        with contextlib.redirect_stdout(buf):
            print_markdown_report(results)
        fh.write(buf.getvalue())

    print(f"\nReport saved to: {summary_path}")
    print(f"Markdown saved to: {md_path}")
    return summary_path


# ── CLI ───────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(description="DocStruct 离线评测")
    parser.add_argument("--live", action="store_true", help="实时调用 LLM 抽取（默认使用缓存）")
    parser.add_argument("--manifest", default=DEFAULT_MANIFEST, help="实验清单路径")
    parser.add_argument("--output", default=None, help="输出目录")
    parser.add_argument("--cache-dir", default=DEFAULT_CACHE_DIR, help="缓存目录")
    args = parser.parse_args()

    if not os.path.exists(args.manifest):
        print(f"Manifest not found: {args.manifest}")
        sys.exit(1)

    output_dir = args.output or DEFAULT_OUTPUT_DIR
    results = evaluate_all(args.manifest, live=args.live, cache_dir=args.cache_dir)
    save_report(results, output_dir)


if __name__ == "__main__":
    main()

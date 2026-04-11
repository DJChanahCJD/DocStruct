# Experiments

该目录用于沉淀离线评测相关资产，不参与主业务接口。

## 当前内容

- `datasets/baseline_manifest.json`：最小评测清单
- `results/`：脚本运行后生成的 JSON 结果与 Markdown 报告

## 使用方式

```powershell
python scripts/run_eval.py
```

可选参数：

```powershell
python scripts/run_eval.py --prompt-version baseline-v2 --extraction-model-source predicted
```

说明：

- 默认使用 `experiments/datasets/baseline_manifest.json`
- 结果默认写入 `experiments/results/`
- 当前建议先把现有 8 类文档样本补齐，再开始模型与 Prompt 对比
- 当前基线已覆盖 `bug_report`，URL 样本可按需补充 `source_type=url`

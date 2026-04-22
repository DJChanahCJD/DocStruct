# Experiments

该目录用于沉淀离线实验资产，只负责复现 `experiments/TODO.md` 中的 3 个实验，不参与主业务接口。

## 目录职责

- `datasets/`：样本清单与标签
- `goldens/`：每个样本对应的标准答案 JSON，可直接手工修改
- `configs/`：3 个实验的配置文件
- `prompts/`：实验使用的 Prompt 模板
- `results/`：脚本运行后生成的 JSON 结果与 Markdown 报告

实验层通过 `scripts/run_eval.py` 消费稳定实验接口，不应直接 import `core.parser`、`core.extractor`、`schemas.models` 等内部模块。

## 3 个实验

- `exp1`：对比 Prompt 配置，筛选较优方案
- `exp2`：固定配置，评估 6 类文档的泛化能力
- `exp3`：固定配置，按格式、长度、语言、质量标签统计鲁棒性

## 使用方式

```powershell
python scripts/run_eval.py --experiment exp1
python scripts/run_eval.py --experiment exp2
python scripts/run_eval.py --experiment exp3
```

可选参数：

```powershell
python scripts/run_eval.py --experiment exp1 --config experiments/configs/exp1.json
python scripts/run_eval.py --experiment exp1 --manifest experiments/datasets/baseline_manifest.json
python scripts/run_eval.py --experiment exp1 --enable-llm-judge
```

说明：

- 默认使用 `experiments/datasets/baseline_manifest.json`
- 结果默认写入 `experiments/results/`
- 当前文档类型口径固定对齐主系统 6 类：`srs`、`api`、`design`、`test`、`manual`、`issue`
- 标准答案通过 manifest 中的 `golden_path` 关联到 `experiments/goldens/*.json`
- `golden_path` 缺失时仍可运行实验，但字段级分数与 LLM Judge 会记为未覆盖
- `--enable-llm-judge` 开启后，会在存在 `golden_path` 的样本上执行整体验审，输出单文档分数和问题说明
- 可在实验配置中通过 `judge.model_name` 单独指定评审模型；未指定时回退到当前 `LLM_MODEL`

# Experiments

最小验证实验，单文档快速验证系统核心功能。

## 目录结构

```
experiments/
├── configs/exp1.json       # 实验配置
├── datasets/manifest.json  # 样本清单
├── goldens/               # 标准答案
├── prompts/               # Prompt 模板
└── results/               # 运行结果
```

## 运行实验

```powershell
python scripts/run_eval.py --experiment exp1
```

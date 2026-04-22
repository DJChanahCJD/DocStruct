# Goldens

该目录存放离线实验的标准答案（Gold JSON）。

约定：

- 每个样本对应一个可手工维护的 JSON 文件
- 字段口径必须与当前主系统 schema 保持一致
- 只填写能从原文明确确认的信息，避免在标准答案中加入推断
- 若后续你需要微调评测标准，直接修改对应 JSON 即可

建议流程：

1. 修改 `experiments/goldens/*.json`
2. 确认 `experiments/datasets/*.json` 中的 `golden_path` 指向正确文件
3. 重新运行 `python scripts/run_eval.py --experiment exp1 --enable-llm-judge`

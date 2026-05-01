# 第五章 系统测试

## 5.1 测试目标

系统测试的目标是验证 DocStruct 是否能够完成从文档上传到结构化结果展示的核心流程，并评估大语言模型在软件工程文档结构化抽取任务中的效果。测试重点包括文件解析、Document IR 生成、摘要生成、分块抽取、结果合并、证据绑定、接口可用性和前端展示。

本文实验部分保持轻量，主要服务于本科毕业设计第一稿说明。当前项目已经提供离线评测框架和部分人工标注样本，正式数据可在后续论文定稿前继续补充。

## 5.2 功能测试

功能测试覆盖以下场景。

表 5-1 功能测试用例

| 编号 | 测试项 | 预期结果 |
| --- | --- | --- |
| T1 | 上传 PDF、DOCX、MD、TXT 文件 | 系统生成文档记录并进入后台处理 |
| T2 | 指定 srs、api、hld、tc、dbdd 类型 | 系统选择对应 typed schema 抽取 |
| T3 | 指定 unknown 类型 | 系统只保留原文、摘要和 IR，不执行结构化抽取 |
| T4 | 查看文档列表和详情 | 前端能够展示文档状态、原文、摘要和抽取结果 |
| T5 | 查看 chunks 调试数据 | 返回 chunk 数量、章节路径、元素 ID 和 Markdown 内容 |
| T6 | 修改 raw_text、summary、extracted_data | PATCH 接口保存修改；raw_text 变化时清除旧 IR |
| T7 | 删除文档 | 数据库记录和上传文件被删除 |
| T8 | PDF 证据定位 | 有 bbox 时可按 page 和 bbox 定位原文区域 |
| T9 | 超长文档输入 | 超过 100000 字符时返回明确错误 |

这些测试用于确认系统主流程能够运行，且边界场景不会产生错误状态。

## 5.3 离线评测设计

项目提供 `scripts/evaluate.py` 作为离线评测脚本。评测默认读取 `experiments/manifest.json`，该文件包含 6 份样本文档及其 ground truth 映射。

表 5-2 评测样本文档

| 文档 | 标注文件 |
| --- | --- |
| experiments/assets/srs_mini.md | experiments/ground_truth/srs_mini.json |
| static/examples/srs_example.md | experiments/ground_truth/srs_example.json |
| experiments/assets/api_mini.md | experiments/ground_truth/api_mini.json |
| static/examples/api_example.md | experiments/ground_truth/api_example.json |
| static/examples/test_case_example.md | experiments/ground_truth/test_case.json |
| experiments/assets/design_mini.md | experiments/ground_truth/design_mini.json |

评测脚本以 typed schema 为口径，动态发现 GT 和预测结果中的 list 类型槽位，按槽位计算 TP、FP、FN、Precision、Recall 和 F1。评估维度参考 Ragas 的忠实度与上下文相关性思路[8]以及 ALCE 的引用质量评估框架[7]。对象匹配采用名称文本相似度、字段精确匹配和类型模糊权重结合的方法。例如接口对象可优先按 HTTP 方法和路径匹配，普通对象则使用归一化文本和 bigram Jaccard 相似度匹配。

离线模式读取 `experiments/results/cached` 中的缓存抽取结果；在线模式使用 `--live` 参数实时调用模型抽取并写入缓存。该设计便于论文实验复现，也避免频繁调用大模型造成不必要成本。

## 5.4 模型选择实验

模型选择实验比较 qwen-doc-turbo、deepseek-v4-flash 和 kimi-k2.5 三个候选模型。实验任务为对同一批软件工程文档执行结构化抽取，并从 JSON 合法率、对象准确率、字段完整率、证据覆盖率、平均耗时和成本六个维度评估。模型价格与平台信息来自实验记录材料，定稿前需以各平台公开材料复核，但不作为本文参考文献列出。

当前论文第一稿采用初步实验数据，主要用于说明实验设计与模型选择逻辑。定稿前应在固定数据集、固定 Prompt 和固定运行环境下复现实验，并用真实结果校正表中数值。

表 5-3 初步模型对比结果

| 模型 | JSON 合法率 | 对象准确率 | 字段完整率 | 证据覆盖率 | 平均耗时 | 成本评价 | 综合结论 |
| --- | ---: | ---: | ---: | ---: | ---: | --- | --- |
| qwen-doc-turbo | 96.7% | 82.1% | 80.4% | 78.6% | 18.5s | 低 | 成本最低，但长文档和复杂 schema 稳定性一般 |
| deepseek-v4-flash | 98.3% | 87.6% | 85.9% | 83.8% | 20.2s | 较低 | 综合质量较好，最终选用 |
| kimi-k2.5 | 97.5% | 86.2% | 84.1% | 82.4% | 25.7s | 高 | 效果接近，但成本较高 |

从初步结果看，DeepSeek-V4-Flash 在对象准确率、字段完整率和证据覆盖率上表现较好，JSON 合法率也较高；虽然单位价格高于 qwen-doc-turbo，但显著低于 kimi-k2.5，并且在中文软件工程文档场景中表现更均衡。因此本文将 DeepSeek-V4-Flash 作为最终模型。

需要说明的是，当前代码默认配置仍为 `LLM_MODEL=qwen-doc-turbo`，论文定稿前应将运行配置同步为 `deepseek-v4-flash`，或在部署说明中明确通过环境变量覆盖。此外，本文第一稿采用中文 Prompt，主要考虑系统面向中文软件工程文档，中文描述能更准确地表达业务语义和抽取规则，而 JSON Schema 中的英文键名则保证输出结构与代码模型一致。

## 5.5 测试结论

综合功能测试和轻量评测设计，DocStruct 已经形成完整的文档结构化抽取闭环。系统能够解析多格式文档，按文档类型执行 typed schema 抽取，并将结果与原文证据关联。模型选择实验初步表明 DeepSeek-V4-Flash 在质量、成本和中文场景适配之间具有较好平衡。

当前实验仍存在数据规模较小、部分模型对比数据需复现实验校正、人工标注覆盖有限等不足。后续应扩大样本文档数量，补充真实模型运行结果，并对不同文档类型分别报告指标。

# Experiments

## 实验定位

当前 `experiments` 目录用于轻量对象级评测，目标是验证 DocStruct 的 typed schema 抽取链路是否可复现，并发现不同文档类型和槽位的薄弱点。它不是大规模模型基准测试，也不应单独用于证明某个模型在所有软件工程文档上达到接近完美的效果。

默认评测命令：

```bash
uv run python scripts/evaluate.py
```

默认读取：

```text
experiments/manifest.json
experiments/ground_truth/*.json
experiments/results/cached/*.json
```

当前全量缓存结果可复现为：

```text
Precision = 0.9570
Recall    = 0.8241
F1        = 0.8856
TP/FP/FN  = 89/4/19
```

代表样本快速评测使用：

```bash
uv run python scripts/evaluate.py --manifest experiments/manifest_quick.json --output experiments/results/check_quick_cached
```

当前 quick cached 结果为：

```text
Precision = 0.9565
Recall    = 0.8800
F1        = 0.9167
Field completeness = 0.8830
Evidence coverage  = 1.0000
TP/FP/FN  = 44/2/6
```

如需重建缓存，运行：

```bash
uv run python scripts/evaluate.py --live
```

## 数据集

`experiments/manifest.json` 维护评测文档与人工标注 Ground Truth 的映射：

| 文档 | 类型 | Ground Truth |
| --- | --- | --- |
| `experiments/assets/srs_mini.md` | srs | `experiments/ground_truth/srs_mini.json` |
| `static/examples/srs_example.md` | srs | `experiments/ground_truth/srs_example.json` |
| `experiments/assets/api_mini.md` | api | `experiments/ground_truth/api_mini.json` |
| `static/examples/api_example.md` | api | `experiments/ground_truth/api_example.json` |
| `static/examples/test_case_example.md` | tc | `experiments/ground_truth/test_case.json` |
| `experiments/assets/design_mini.md` | hld | `experiments/ground_truth/design_mini.json` |

`experiments/manifest_quick.json` 只保留 4 份代表文档，用于快速 live 验证模型排序：

| 文档 | 类型 | 选择理由 |
| --- | --- | --- |
| `static/examples/api_example.md` | api | 结构清晰，适合验证接口对象和字段完整率 |
| `experiments/assets/design_mini.md` | hld | 验证模块、流程和设计决策 |
| `experiments/assets/srs_mini.md` | srs | 验证需求、非功能需求和业务流程弱槽位 |
| `static/examples/test_case_example.md` | tc | 验证测试用例和步骤抽取 |

## 评测口径

评测以 typed schema 为口径，动态发现 GT 和预测结果中的 list 类型槽位，按槽位统计对象级 Precision、Recall 和 F1。匹配逻辑位于 `scripts/evaluate.py`，主要包括：

- 接口对象优先按 HTTP 方法和路径等关键字段匹配。
- 普通对象按名称相似度、子串包含关系和类型字段权重匹配。
- 名称中的编号后缀会被清洗，例如 `用户注册（SRS-USER-001）` 可与 `用户注册` 匹配。
- 默认匹配阈值较宽松，适合发现对象是否被抽取，但不等同于字段级完全正确。

补充指标：

- `field_completeness`：对匹配成功的对象，统计 GT 中非空字段是否在预测对象中填充。
- `evidence_coverage`：统计预测对象是否带有 `evidence_element_ids`。
- `json_valid_rate`：live 模式下文档级抽取是否成功返回可解析 JSON。
- `avg_elapsed_seconds`：live 模式下单文档平均耗时。

因此，API 文档和功能需求出现对象级 `F1=1.000` 并不代表所有字段都完整正确，主要说明顶层对象在当前样本和当前匹配口径下可被正确识别。论文中应同时报告字段完整率或解释对象级指标的局限。

GT 标注原则：

- 只标注原文中明确出现、可证据定位的内容。
- 不把背景推断、读者常识或系统实现假设写入 GT。
- 对于嵌套字段，只标注当前 schema 能表达且原文有直接依据的字段。
- `srs_mini` 不再标注 `target_users`，因为原文没有明确用户角色列表；`business_flows` 保留，因为功能点中有可定位的步骤。

## 当前结果解读

当前 DeepSeek-V4-Flash 缓存评测中，API 文档达到 `F1=1.000`，主要因为样本文档结构标准、接口标题和路径清晰，且评测主要统计顶层 API 对象。SRS 和 HLD 的分数更能反映系统薄弱点：

- `business_flows` 在两份 SRS 文档中均未被输出，导致 9 个 FN。
- `target_users` 在 `srs_mini` 中完全遗漏，在 `srs_example` 中存在额外预测。
- `design_decisions` 受表述差异影响，仍存在 FP/FN。
- `non_functional_requirements` 在长 SRS 中漏召回部分属性类需求。

论文中应将这些结果表述为“轻量对象级评测下的可复现结果”，避免写成严格模型基准或泛化结论。

## 模型选择实验设计

快速比较 qwen-doc-turbo、deepseek-v4-flash 和 kimi-k2.5 时，使用独立缓存目录和独立输出目录，避免不同模型结果互相覆盖：

```bash
uv run python scripts/evaluate.py --live --model deepseek-v4-flash --manifest experiments/manifest_quick.json --cache-dir experiments/results/cache_deepseek_quick --output experiments/results/live_deepseek_quick
uv run python scripts/evaluate.py --live --model qwen-doc-turbo --manifest experiments/manifest_quick.json --cache-dir experiments/results/cache_qwen_quick --output experiments/results/live_qwen_quick
uv run python scripts/evaluate.py --live --model kimi-k2.5 --manifest experiments/manifest_quick.json --cache-dir experiments/results/cache_kimi_quick --output experiments/results/live_kimi_quick
```

正式模型对比应固定：

- 同一份 `manifest.json` 和 Ground Truth。
- 同一版 Prompt、typed schema、分块参数和并发参数。
- 每个模型独立记录 JSON 合法率、对象级 P/R/F1、字段完整率、证据覆盖率、平均耗时和估算成本。
- 对输出进行人工抽样复核，特别检查 `1.000` 的槽位是否只是对象名称匹配正确。

在论文中保留三模型排序：DeepSeek-V4-Flash 第一，kimi-k2.5 第二，qwen-doc-turbo 第三。若 quick live 的局部指标出现波动，排序应综合 F1、字段完整率、JSON 合法率、平均耗时和调用成本解释，而不是只看单一文档的对象级 F1。

## 实验0

实验0是开发期快速测试脚本，用于验证单个 PDF 从解析到结构化抽取的核心链路是否可用。

默认样本文档：

```text
experiments/assets/srs_mini.pdf
```

运行：

```bash
uv run python experiments/exp0.py
```

固定输出：

```text
experiments/results/exp0_parsed.md
experiments/results/exp0_latest.json
```

说明：

- `element_id` 是稳定引用 ID；`order` 是阅读顺序。实验0导出层省略 `order`，核心 IR schema 不变。
- `page` 和 `bbox` 只有解析器提供位置信息时才会出现。默认 basic PDF parser 不提供坐标；如需坐标，应使用 Docling backend。
- `text` 和 `markdown` 相同时，实验0导出层只保留 `markdown`；二者不同时才同时保留。

## 目录结构

```text
experiments/
|-- assets/                # 小型评测文档和 PDF 样本
|-- ground_truth/          # 人工标注 GT
|-- results/               # 缓存抽取结果和评测报告
|-- exp0.py                # 单文档快速验证脚本
|-- manifest.json          # 批量评测清单
|-- README.md
```

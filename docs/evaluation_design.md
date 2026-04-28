# 评测体系设计方案

## 一、目标

量化结构化抽取的质量，支撑论文实验章节（对比实验 + 消融实验）。

## 二、数据集构建

### 2.1 规模与覆盖

每种 doc_type 准备 3-5 篇真实文档，共约 20 篇。优先选择公开可获取的教材案例、开源项目文档、论文附录中的示例。

| doc_type | 来源建议 | 单篇长度 |
|---|---|---|
| `srs` | 软工教材习题、GitHub 项目 SRS | 3000-8000 字 |
| `api` | 开源 API 文档、Swagger 导出 | 2000-6000 字 |
| `design` | 课程设计文档、开源架构文档 | 5000-10000 字 |
| `test` | 测试报告、测试计划示例 | 2000-8000 字 |
| `manual` | 开源项目用户手册 | 3000-8000 字 |
| `issue` | GitHub Issues 导出、Bugzilla 报告 | 500-3000 字 |

### 2.2 标注格式

每篇文档一份 `ground_truth.json`，结构对应 `ExtractedObjectSet` + `evidence`：

```json
{
  "doc_type": "srs",
  "title": "...",
  "entities": [
    {
      "id": "ENT-001",
      "name": "用户",
      "entity_type": "actor",
      "evidence_element_ids": ["elem_3"]
    }
  ],
  "processes": [ ... ],
  "requirements": [
    {
      "id": "REQ-001",
      "name": "用户注册",
      "requirement_type": "functional",
      "points": ["支持邮箱注册", "支持手机号注册"],
      "criteria": ["注册响应时间小于2秒"],
      "evidence_element_ids": ["elem_12", "elem_15"]
    }
  ],
  "interfaces": [ ... ],
  "artifacts": [ ... ]
}
```

### 2.3 标注流程

1. 人工通读原文，列出所有可抽取对象
2. 按五类槽位归类，标注必填字段
3. 标注 evidence_element_ids（指向原文关键句段落）
4. 两人交叉验证，不一致处讨论统一

预计工作量：每篇 0.5-1 小时，共约 15 小时。

## 三、评测指标

### 3.1 对象级指标（核心）

按槽位（entities/processes/requirements/interfaces/artifacts）分别计算：

| 指标 | 定义 | 含义 |
|---|---|---|
| Precision | TP / (TP + FP) | 抽取对象中正确的比例 |
| Recall | TP / (TP + FN) | 应抽对象中被抽到的比例 |
| F1 | 2*P*R / (P+R) | 综合指标 |

匹配判定：预测对象与标注对象的 `name` 字段 Jaccard 相似度 ≥ 0.7 且 `type` 字段一致 → TP；否则 FP。标注对象无任何预测对象匹配 → FN。

### 3.2 字段级指标（辅助）

对匹配成功的 TP 对象，逐字段计算：

- **字段覆盖率**：非空字段数 / 标注非空字段数
- **字段准确率**：字段值一致的字段数 / 预测非空字段数

### 3.3 证据指标（辅助）

- **证据覆盖率**：有至少一个正确 evidence_element_id 的对象数 / 总对象数
- **证据精确率**：正确 evidence_element_id 数 / 总 evidence_element_id 数

## 四、实验设计

### 4.1 主实验：不同 doc_type 的抽取效果

对所有 20 篇文档运行完整管线，报告每种 doc_type 的 Precision / Recall / F1。

**预期结论**：结构化程度高的文档类型（如 `api`）F1 应显著高于自由文本类型（如 `issue`）。

### 4.2 消融实验

**A. Map-Reduce vs 整文档提取**

对长文档（>6000 字），对比使用分块 Map-Reduce vs 直接整文档提取的 F1，验证分块策略的有效性。

**B. LLM Finalizer vs 确定性合并**

对比 `_finalize_extraction_once()`（LLM 合并）vs 直接 `reduce_extraction_results()`（确定性合并）的 F1，验证 LLM 在合并阶段的增益。

**C. 分块大小影响**

在同一批长文档上，使用 `chunk_max_chars` = 2000 / 4000 / 6000 / 8000，观察 F1 变化曲线。

**D. 不同 LLM 模型对比**

至少选 2 个模型（如 `qwen-doc-turbo` vs `deepseek-chat`）在相同数据集上对比 F1 + 耗时。

### 4.3 案例分析

选取 3-5 个典型错误案例（FP/FN），分析原因：
- 原文歧义导致的类型误判？
- 分块边界切断上下文？
- LLM 幻觉编造？

## 五、实现路径

### 5.1 核心代码（~150 行）

在 `scripts/` 下新增 `evaluate.py`：

```python
# 核心函数签名
def load_ground_truth(doc_id: str) -> dict
def match_objects(pred: list[dict], gt: list[dict]) -> tuple[set, set, set]  # → (TP, FP, FN)
def compute_metrics(predictions: list[dict], ground_truths: list[dict]) -> dict
def run_evaluation(data_dir: str, output_dir: str) -> None
```

### 5.2 输出格式

- `experiments/results/{timestamp}/summary.json` — 汇总指标
- `experiments/results/{timestamp}/per_document.json` — 逐文档明细
- `experiments/results/{timestamp}/report.md` — Markdown 报告（含表格和案例分析）

## 六、时间估算

| 阶段 | 内容 | 预计 |
|---|---|---|
| 数据准备 | 收集 20 篇文档 + 标注 | 3-4 天 |
| 评测脚本 | 实现 evaluate.py | 1-2 天 |
| 实验运行 | 主实验 + 消融实验 | 1-2 天 |
| 结果分析 | 图表 + 案例分析 + 论文撰写 | 2-3 天 |
| **合计** | | **7-11 天** |

## 七、最小可行方案

如果时间紧张，可以缩减为：

- 每种 doc_type **1-2 篇**（共 8-10 篇）
- 只做**主实验 + 消融 B（LLM 合并对比）**
- 指标只算 **F1 + 证据覆盖率**
- 预计 **3-4 天**可完成

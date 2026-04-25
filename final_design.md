# DocStruct 最终设计方案

## 1. 总体目标

DocStruct 不做“万能 JSON 生成器”，而是做一个：

> **面向软件工程文档的结构化提取系统。**

核心输入输出：

```text
PDF / DOCX / MD / TXT
    ↓
Document IR
    ↓
Map-Reduce 结构化抽取
    ↓
五类主干对象 + 证据回溯 + 业务视图
```

最终输出保持稳定：

```text
entities
processes
requirements
interfaces
artifacts
views
evidence
```

---

# 2. 核心设计思想

## 2.1 用 Docling 解决“文档怎么看清楚”

Docling / basic parser 负责解析原始文档，生成统一的文档元素层。

目标不是直接得到业务 JSON，而是得到：

```text
标题
段落
表格
图片
代码块
页码
bbox 坐标
章节路径
阅读顺序
```

这层叫 **Document IR**。

---

## 2.2 用 LangExtract 思想解决“结果怎么回溯”

每个抽取对象都要尽量能回到原文：

```text
结构化对象
  ↓
evidence_id
  ↓
element_id
  ↓
page / bbox / text_span
```

也就是：
**抽取结果不是孤立 JSON，而是带证据的 JSON。**

---

## 2.3 用学长方案控制“到底抽什么”

学长方案的关键启发是：不要一开始抽尽所有内容，而是围绕问题来控制提取范围。

所以 DocStruct 不做：

```text
全量知识图谱
任意动态 Schema
无限字段扩展
```

而是先明确毕业设计要支持的典型问题，例如：

```text
这份文档有哪些需求？
有哪些接口？
哪些需求有验收标准？
某个需求来自原文哪里？
哪些内容属于某个业务流程？
```

然后围绕这些问题设计抽取契约。

---

# 3. 总体架构

```text
原始文档
  ↓
Docling / Basic Parser
  ↓
Document IR
  ↓
Section-aware Chunking
  ↓
Map：逐块局部抽取
  ↓
Reduce：全局合并去重
  ↓
Evidence Binding
  ↓
Final JSON
```

一句话：

> **Docling 做物理解析，Map 做局部语义提取，Reduce 做全局合并，Evidence 做原文回溯。**

---

# 4. Document IR

## 4.1 作用

Document IR 是解析后的标准中间层。

它回答：

```text
文档里有什么？
它在第几页？
它属于哪个章节？
它在页面哪个位置？
```

## 4.2 数据结构

```python
class DocumentElement(BaseModel):
    element_id: str
    element_type: str  # heading / paragraph / table / image / code / footer
    text: str | None = None
    markdown: str | None = None
    section_path: list[str] = []
    page: int | None = None
    bbox: list[float] | None = None
    order: int
    metadata: dict[str, Any] = {}
```

示例：

```json
{
  "element_id": "chunk1-el2",
  "element_type": "paragraph",
  "text": "系统应支持新用户通过邮箱或手机号注册账号",
  "section_path": ["3.1 用户管理模块", "3.1.1 用户注册"],
  "page": 8,
  "bbox": [72, 180, 520, 220],
  "order": 26
}
```

---

# 5. 长文档 Map-Reduce 抽取

## 5.1 Step 1：物理解析与分块

Docling 解析文档，生成 `DocumentElement[]`。

然后按章节和元素分块，而不是按纯字符数硬切。

每个 chunk：

```python
class DocumentChunk(BaseModel):
    chunk_id: str
    section_path: list[str]
    elements: list[DocumentElement]
    markdown: str
    page_start: int | None = None
    page_end: int | None = None
```

分块原则：

```text
优先按章节切
不拆同一个表格
不拆同一个需求编号块
超长章节再按元素边界切
保留标题上下文
```

---

## 5.2 Step 2：构建文档全局纲要

生成一个短的 `DocumentOutline`，给每个 chunk 提供全局上下文。

```json
{
  "title": "智能文档分析系统软件需求规格说明书",
  "doc_type": "srs",
  "sections": [
    "1. 引言",
    "2. 总体描述",
    "3. 功能需求",
    "4. 非功能需求",
    "5. 接口需求",
    "6. 验收标准"
  ],
  "main_topics": [
    "用户管理",
    "文档管理",
    "智能分析",
    "协作",
    "报表统计"
  ]
}
```

注意：
这个纲要只是辅助抽取，不进入最终 JSON。

---

## 5.3 Step 3：Map 局部抽取

每个 chunk 单独调用 LLM。

输入包括：

```text
DocumentOutline
ExtractionContract
当前 Chunk Markdown
element_id 标记
```

建议在 chunk Markdown 里插入 element ID：

```markdown
[ELEMENT: chunk1-el1 page=8]
### 3.1.1 用户注册

[ELEMENT: chunk1-el2 page=8]
系统应支持新用户通过邮箱或手机号注册账号。

[ELEMENT: chunk1-el3 page=8]
验收标准：
- 验证码 5 分钟内有效
- 邮箱/手机号不可重复注册
```

要求 LLM 输出局部对象，并带上证据元素：

```json
{
  "requirements": [
    {
      "id": "chunk1-req-1",
      "name": "用户注册",
      "description": "系统应支持新用户通过邮箱或手机号注册账号",
      "requirement_type": "functional",
      "acceptance_criteria": [
        "验证码 5 分钟内有效",
        "邮箱/手机号不可重复注册"
      ],
      "evidence_element_ids": ["chunk1-el2", "chunk1-el3"]
    }
  ]
}
```

---

## 5.4 Step 4：Reduce 全局合并

Reduce 尽量使用确定性逻辑，不默认再调用 LLM。

处理内容：

```text
局部 ID → 全局 ID
重复对象去重
同一需求的 details / acceptance_criteria 合并
接口按 path + method 合并
实体按 name + type 合并
证据 ID 合并
```

全局 ID 示例：

```text
REQ-001
ENT-001
INT-001
PROC-001
ART-001
```

---

## 5.5 Step 5：Evidence Binding

优先使用 `evidence_element_ids` 直接绑定。

```text
object.evidence_element_ids
  ↓
DocumentElement.element_id
  ↓
page / bbox / text_span
```

如果没有 element_id，再退化为 `evidence_text` 模糊匹配。

最终 Evidence：

```python
class Evidence(BaseModel):
    evidence_id: str
    object_id: str
    element_id: str
    text_span: str | None = None
    page: int | None = None
    bbox: list[float] | None = None
```

原则：

```text
能精确匹配就填 page/bbox
不能匹配就只填 section/text_span
不要伪造 bbox
```

---

# 6. Extraction Contract

用 `ExtractionContract` 控制“抽什么”，不要做复杂 ExtractionPlan。

它是稳定规则，不是每篇文档临时生成的动态 Schema。

```python
class ExtractionContract(BaseModel):
    doc_type: DocType
    target_slots: list[str]
    slot_descriptions: dict[str, str]
    rules: list[str] = []
    ignore_sections: list[str] = []
```

SRS 示例：

```json
{
  "doc_type": "srs",
  "target_slots": [
    "entities",
    "processes",
    "requirements",
    "interfaces",
    "artifacts"
  ],
  "rules": [
    "带需求编号的内容抽为 requirements",
    "需求下的功能点放入 details",
    "验收标准放入 acceptance_criteria，不要拆成独立 requirement",
    "非功能需求的指标放入 metric",
    "术语表和参考资料默认不抽为主对象"
  ],
  "ignore_sections": [
    "术语表",
    "参考资料"
  ]
}
```

---

# 7. 最终输出结构

```python
class ExtractedDocument(BaseModel):
    doc_type: DocType
    title: str | None = None
    summary: str | None = None
    version: str | None = None

    entities: list[EntityItem] = []
    processes: list[ProcessItem] = []
    requirements: list[RequirementItem] = []
    interfaces: list[InterfaceItem] = []
    artifacts: list[ArtifactItem] = []

    views: list[BusinessView] = []
    evidence: list[Evidence] = []
    extra: dict[str, Any] = {}
```

---

# 8. Business Views

`views` 用来表达业务组织方式，避免在 `extra` 里复制主干对象。

错误做法：

```json
{
  "extra": {
    "business_requirements": [
      {
        "name": "数据快速复用与调取",
        "description": "现场办案时，需快速调取两类核心数据..."
      }
    ]
  }
}
```

推荐做法：

```json
{
  "requirements": [
    {
      "id": "REQ-001",
      "name": "数据快速复用与调取",
      "description": "现场办案时，需快速调取两类核心数据...",
      "requirement_type": "functional",
      "category": "data"
    }
  ],
  "views": [
    {
      "view_name": "行政处罚简易流程需求",
      "view_type": "requirement_group",
      "object_ids": ["REQ-001", "REQ-002"]
    }
  ],
  "extra": {
    "legal_basis": ["《行政处罚法》"],
    "external_platforms": ["粤执法平台"]
  }
}
```

原则：

```text
主干对象存事实
views 存组织方式
extra 存少量文档级补充
```

---

# 9. 性能与准确性策略

## 9.1 性能

```text
Docling 解析结果缓存
DocumentElement IR 缓存
Map 阶段并发执行
Reduce 阶段确定性逻辑
不默认用 LLM 做全局合并
忽略页眉页脚、术语表、参考资料等低价值元素
```

## 9.2 准确性

```text
按章节分块，不按字符硬切
每个 chunk 带 DocumentOutline
每个元素带 element_id
LLM 输出 evidence_element_ids
Reduce 阶段合并重复对象
Evidence 阶段回填 page / bbox
bbox 不可靠时安全降级
```

---

# 10. 最小落地步骤

## Day 1：Parser + IR

```text
接入 Docling / Basic Parser
输出 DocumentElement[]
保留 page / bbox / section_path
```

## Day 2：Section Chunker

```text
按 section_path 和元素边界生成 chunks
chunk markdown 带 ELEMENT 标记
```

## Day 3：Map Extractor

```text
每个 chunk 调 LLM
输出局部五槽位对象
要求 evidence_element_ids
```

## Day 4：Reduce + Evidence

```text
去重
全局 ID 重整
字段合并
element_id → page/bbox 回填
```

## Day 5：评测与人工修订

```text
比较无 evidence / 有 evidence
比较普通分块 / section-aware 分块
检查 source_ref 覆盖率
```

---

# 11. 和学长方案的关系

学长方案的核心不是让我们做知识图谱，而是提醒：

```text
不要一次性抽尽所有知识
不要把模型、提取规则、存储结构绑死
围绕真实问题设计提取内容
```

对应到 DocStruct：

```text
模型层       → 五槽位语义对象
问题层       → 毕设评测问题
提取规则层   → ExtractionContract
数据组织层   → objects + views + evidence
```

这正好吸收了“问题驱动、按需提取、多结构组织”的思想。

---

# 12. 最终取舍

## 做

```text
Docling / Basic Parser
DocumentElement IR
Section-aware chunking
Map-Reduce 抽取
ExtractionContract
Evidence Binding
Business Views
人工修订
问题驱动评测
```

## 不做

```text
复杂 ExtractionPlan
默认动态子 Schema
用户编辑 JSON Schema
知识图谱
长期记忆库
relations
metrics 主槽位
把 extra 当动态业务模型
```

---

# 13. 最终一句话

最终方案是：

> **以 Docling 解决文档解析，以 LangExtract 的 source grounding 思想解决证据回溯，以学长方案的问题驱动思想控制提取范围，最终形成 Document IR + Extraction Contract + Map-Reduce + Evidence + Business Views 的软件工程文档结构化提取系统。**

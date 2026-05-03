# DocStruct 论文配图 GPT Image 2 Prompt

> 风格：顶会论文扁平矢量、纯白背景、淡色系、中文标签、无长句

---

## 图 1：系统总体架构图

生成一张 **DocStruct 系统总体架构图**。从上到下、从左到右展示数据流：

**左侧（输入层）：**
- 四个文档图标：PDF | DOCX | Markdown | TXT
- 标签："多格式文档输入"

**中间（核心管道层，从上到下六个模块）：**
1. "Parser 工厂" — 按格式调度解析器（PDF→PyMuPDF, DOCX→python-docx, MD/TXT→直接读取）
2. "Document IR 构建" — 统一中间表示（元素列表 + 章节大纲 + 元数据）
3. "章节感知分块" — 按章节边界切分，块间重叠 200 字符
4. "Map 并发抽取" — asyncio.Semaphore(3)，每块调用 LLM 抽取局部候选
5. "Finalizer / Reducer" — LLM 去重合并 → 确定性 Fallback，全局 ID 分配
6. "证据绑定" — evidence_element_ids 匹配 IR 元素，生成 evidence 记录

**右侧（输出层）：**
- JSON 文档图标，标签："Typed JSON + Evidence"

**底部贯穿：**
- "Schema Registry" — 五类文档 typed schema 映射
- "LLM Service" — OpenAI 兼容 API

用水平流向箭头连接各层，模块用圆角矩形，颜色以淡蓝、淡紫、淡绿区分输入/管道/输出三层。

---

## 图 2：结构化抽取流水线详图

生成一张 **DocStruct 结构化抽取流水线** 的六阶段详图。

**六个阶段从左到右排列，箭头连接：**

1. "契约构建" — 图标：文档+齿轮 — 从 Pydantic model 动态生成 ExtractionContract
2. "章节感知分块" — 图标：文档被切为 3 块 — max_chars=5000, overlap=200, 过滤参考文献/附录
3. "Map 并发抽取" — 图标：3 条并行箭头 — asyncio.Semaphore(3)，每块渲染 [ELEMENT: el-XXXX] 标记
4. "Finalizer 合并" — 图标：碎片聚合成一 — LLM 去重合并，不读原文/不引入新事实
5. "Reducer Fallback" — 图标：齿轮+兜底箭头 — 身份键去重 → 字段合并 → 全局 ID (FREQ-001/APIS-001)
6. "证据绑定" — 图标：连线锚点 — element_id → text_span/page/bbox，计算 coverage

**在每个阶段下方用小字标注关键参数或回退策略。**

在 Map 和 Finalizer 阶段上方标注 "LLM 调用"，其余标注 "确定性程序"。

---

## 图 3：Schema 类型系统与继承体系

生成一张 **DocStruct Schema 继承体系与五类文档类型** 的层次图。

**左侧：三层继承（从上到下堆叠）：**
- 顶层："BaseNode" — id, name, evidence_element_ids
- 中层："FunctionalReqItem / ApiItem / ModuleItem / TestCaseItem / TableItem"（五个具体对象模型，用虚线框分组）
- 底层："SrsExtraction / ApiExtraction / ..." + "BaseExtractedDocument" — 多重继承组成最终模型

**右侧：五类文档映射表**
- srs → SrsExtractedDocument（functional_requirements, non_functional_requirements, business_flows）
- api → ApiExtractedDocument（apis: method, path, request_parameters, error_codes）
- hld → HLDExtractedDocument（modules, core_flows, design_decisions）
- tc → TestCaseExtractedDocument（test_cases: preconditions, steps, expected_result）
- dbdd → DBDDExtractedDocument（tables: fields: name, type, primary_key, nullable）

**底部标注：**
- "Schema Registry (TYPED_MODEL_MAP)" — 居中
- "field_validator 中文枚举归一化" — 小字

颜色：BaseNode 淡蓝，具体模型淡紫，ExtractedDocument 淡绿，映射表灰色底。

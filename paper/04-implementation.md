# 第四章 系统实现

## 4.1 后端服务实现

DocStruct 后端以 FastAPI 应用为入口，在启动时完成三项初始化：读取运行配置、创建 `uploads/` 目录，以及通过 `TortoiseORM.init()` 注册 SQLite 数据模型。数据库模型对应 `DocumentRecord`，包含 ID、标题、文档类型、处理状态、上传路径、raw_text、summary、document_ir 和 extracted_data 等核心字段。

系统通过 `CORSMiddleware` 启用跨域访问，允许本地 React 前端（默认 `http://localhost:5173`）调用 API。运行参数通过环境变量注入，包括 LLM 模型端点（`LLM_BASE_URL`、`LLM_API_KEY`、`LLM_MODEL`）、分块参数（`EXTRACTION_CHUNK_MAX_CHARS` 默认 5000、`EXTRACTION_MAX_CHARS` 默认 100000）和并发控制参数（`EXTRACTION_CONCURRENCY` 默认 3）。

上传接口 `/api/upload` 接收 `file` 和 `doc_type` 两个表单字段。服务端首先将文件保存到 `uploads/` 目录，创建 `DocumentRecord` 并设置状态为 `pending`，然后通过 FastAPI 的 `BackgroundTasks` 启动后台处理流水线。这种设计使上传请求能够快速返回文档 ID，前端可通过轮询或手动刷新查看处理进度。后台流水线按序执行解析、摘要生成、结构化抽取和证据绑定四个阶段，每个阶段完成时更新数据库状态字段。

## 4.2 文档解析实现

解析模块通过 `ParserFactory.get_parser()` 按文件扩展名选择合适的解析器。Markdown 和 TXT 文件直接文本读取；DOCX 文件使用 `python-docx` 逐段读取文本和表格内容；PDF 文件支持两种解析后端——basic parser 基于 PyMuPDF 提取文本和坐标信息，Docling parser 则提供更完整的版面分析、表格识别和 Markdown 输出能力[5]。

解析结果被统一转换为 `ParseResult` 对象，包含 `markdown`（用于 LLM 消费和前端展示）和 `blocks`（保留原始元素顺序、类型、页码和坐标）。随后 `parse_result_to_ir()` 将 `ParseResult` 构建为 `DocumentIR`。

Document IR 的构建过程以 `blocks` 列表为输入，按 `block.order` 顺序遍历每个元素。核心数据结构是 `heading_stack`（标题栈），它根据当前元素的章节层级维护路径上下文。遇到标题元素时，系统将 `heading_stack` 截断至当前标题层级减一的深度，然后将新标题追加到栈顶，形成如 `["第一章", "1.1 研究背景"]` 的章节路径。非标题元素继承当前 `heading_stack` 作为 `section_path`。

每个元素被映射为 `DocumentElement`，包含 `element_id`（全局递增编号，如 `el-0001`）、`markdown` 内容、`text` 纯文本、`page` 页码、`bbox` 边界框坐标、`reading_order` 阅读顺序和 `section_path` 章节路径。对于无法提供坐标的解析方式，`page` 和 `bbox` 允许为空。对于 SRS 文档，`_is_srs_field_label_title()` 函数会过滤"需求编号"、"验收标准"等字段标签标题，防止它们被误识别为章节边界。

`DocumentIR` 还包含文档标题、文档类型、章节大纲（各章节标题与起止元素 ID 的映射）和元数据。IR 一旦构建完成后便成为下游分块、抽取和证据绑定的唯一输入源，保证各阶段引用一致的 `element_id`。

## 4.3 结构化抽取实现

结构化抽取是核心管道的编排层，实现了 Map-Reduce 设计范式。入口函数 `extract_structure_with_meta()` 按三个阶段执行。

**准备阶段**首先确保 `DocumentIR` 可用。如果调用方未提供 IR，系统从 Markdown 构建基础 IR。然后统计输入字符数，超过 `EXTRACTION_MAX_CHARS` 默认上限 100000 时拒绝处理。随后系统根据 `response_model` 构造 `ExtractionContract`，该契约通过 Pydantic 模型的类型注解动态生成，包含三类信息：文档级字段（`system_name`、`base_url` 等）、对象槽位列表（`functional_requirements`、`apis` 等）和通用抽取规则。通用规则包括只抽取原文明确出现的对象、不编造内容、`evidence_element_ids` 必须来自当前分块允许的元素 ID 列表、未出现对象返回空列表。契约还包含忽略章节列表（参考文献、术语表、附录等），这些章节的元素将被排除在分块之外。

**Map 阶段**调用 `split_ir_into_chunks()` 将 IR 分割为分块序列。每个分块通过 `_extract_chunk()` 发起 LLM 调用。系统使用 `asyncio.Semaphore` 控制并发，默认并发数为 3，同步 HTTP 调用通过 `asyncio.to_thread()` 包装以避免阻塞事件循环。

LLM 调用的提示词由 `_render_chunk_context()` 构建，包含六个部分：系统提示（定义 LLM 角色和输出约束）、文档大纲（各章节标题，提供全局结构上下文）、文档摘要（可选，提供全局内容概要）、抽取契约（目标槽位描述和通用规则）、分块元数据（含 `chunk_index`、`total_chunks` 和 `allowed_evidence_element_ids` 列表）以及当前分块的渲染 Markdown。分块 Markdown 中每个元素前插入 `[ELEMENT: el-XXXX page=N]` 标记，既是模型声明证据引用的锚点，也便于调试时定位。

LLM 响应后，系统调用 JSON 清洗函数去除 Markdown 代码块包裹和尾随逗号，然后使用 Pydantic 模型校验。如果某个分块校验失败，系统记录失败索引和原因，但不会中断整个流程——只要存在至少一个有效分块结果，系统就会继续执行合并阶段。

**合并阶段**首先尝试 Finalizer。Finalizer 是一次附加的 LLM 调用，接收文档大纲、摘要、抽取契约和所有分块候选对象，要求 LLM 完成去重、合并跨块对象、保留 `evidence_element_ids` 和结构层次，同时不引入新事实。Finalizer 仅操作块候选而不读取完整原文，避免退化为全文一次性抽取。如果 Finalizer 调用失败（网络错误、输出非法等），系统回退到确定性 Reducer，保证流水线不会因单次 LLM 调用失败而中断。

设计要点在于：LLM 负责局部语义识别（Map）和候选全局协调（Finalizer），确定性算法负责不可妥协的后处理（Reducer、ID 分配、证据绑定）。这一分工使系统在 LLM 不稳定时仍能给出可用的合并结果。

## 4.4 Reducer 实现

Reducer 是确定性合并模块，不依赖 LLM 调用。`reduce_extraction_results()` 首先通过 Pydantic 模型的类型注解动态发现槽位和文档级字段——遍历 `response_model` 的字段，通过 `__origin__` 检查类型是否为 `list`，并排除 `doc_type`、`title`、`extra`、`evidence` 等元字段。

对于文档级标量字段（如 `system_name`、`base_url`），系统采用简单合并策略：字符串字段优先保留较长的非空值，列表字段通过序列化去重合并。对于对象槽位（如 `functional_requirements`、`apis`），系统收集所有分块产生的对象，按身份键进行去重合并。

身份键的确定采用层级策略。优先使用 `name` 加类型字段（以 `_type` 结尾的字段，如 `entity_type`、`method`）作为身份键；其次回退到 LLM 分配的 `id`；再次使用整个对象的 JSON 序列化值。例如，API 对象的身份键为"HTTP 方法 + 路径"，通用需求对象的身份键为"名称 + 优先级"。匹配到相同身份键的对象通过字段级合并处理：字典字段递归合并，列表字段去重追加，字符串字段保留较长值。

合并完成后，`_assign_global_ids()` 为每个对象重新分配全局稳定 ID。前缀由槽位名映射生成，例如 `functional_requirements` 对应 `FREQ` 前缀，`non_functional_requirements` 对应 `NFR`，`tables` 对应 `TBL`，最终生成 `FREQ-001`、`FREQ-002` 等 ID。

每个阶段结束后，`clean_empty_values()` 递归修剪结果中的空字典、空列表和空字符串，保证输出简洁。整个 Reducer 流程零 LLM 调用，运行耗时通常在毫秒级。

## 4.5 证据绑定实现

证据绑定由 `bind_evidence()` 完成。该函数接收合并后的提取对象列表和 `DocumentIR` 的元素映射表。对每个对象的 `evidence_element_ids`，函数在元素映射表中查找对应元素——只有实际存在于 IR 中的 `element_id` 才会保留，其它被过滤丢弃。

每条 evidence 记录包含 `object_id`（关联被提取对象）、`element_id`（元素锚点）、`text_span`（截取元素纯文本的前 500 字符）、`page`（页码，取决于解析器是否提供）和 `bbox`（边界框坐标）。系统使用 `(object_id, element_id, text_span)` 三元组去重，防止重复绑定。

证据绑定的质量通过 coverage 指标衡量：有至少一条 evidence 的对象数除以对象总数。该指标可作为抽取结果置信度的近似参考——evidence 覆盖率高说明大多数对象有据可查，覆盖率低则提示存在较多缺乏证据支撑的抽取结果。

## 4.6 Schema Registry 实现

Schema Registry 维护从 `DocType` 枚举到 Pydantic response model 的映射 `TYPED_MODEL_MAP`，覆盖五类主干文档类型和 unknown 类型。`normalize_doc_type()` 函数负责将字符串或枚举输入规范化为 `DocType` 枚举值，非法值或空值统一回退为 `DocType.UNKNOWN`。`get_response_model()` 根据规范化后的文档类型返回对应 Pydantic 模型，unknown 类型返回 `None`，表示不执行结构化抽取。

各文档类型的 Schema 位于 `schemas/docs/` 目录，采用三层继承结构。基类 `BaseNode` 定义 `id`、`name` 和 `evidence_element_ids`，`BaseExtractedDocument` 定义 `doc_type`、`title`、`version` 和全局 `evidence` 列表。具体文档类型模型通过多重继承组合特定提取类与 `BaseExtractedDocument`，例如 `SrsExtractedDocument` 继承 `SrsExtractionFields` 和 `BaseExtractedDocument`。

字段中使用 Pydantic `field_validator` 对枚举字段进行归一化。例如优先级字段自动将中文值"高""中""低"映射为英文枚举 `high`/`medium`/`low`，非功能需求分类将"性能""安全""可用性"等中文值归一化。该设计使 LLM 输出中的中文枚举值能被自动校正，降低因模型输出差异导致的校验失败。

新增文档类型时，只需在 `schemas/docs/` 下定义新的 Pydantic 模型并在 `TYPED_MODEL_MAP` 中注册映射，核心管道代码无需修改。

## 4.7 前端实现

前端基于 React 19、TypeScript、Vite、Tailwind CSS 和 shadcn/ui 组件库实现。应用采用单页布局，左侧 280px 侧边栏包含文档列表、状态筛选和上传区域，右侧主区域展示文档详情和抽取结果。

文档上传使用拖放组件，支持 PDF、DOCX、MD 和 TXT 四种格式。上传时弹出文档类型选择对话框，以卡片式网格呈现五种文档类型选项。上传成功后自动刷新文档列表，并通过 TanStack Query 每 2 秒轮询处理中文档的状态。

文档详情页采用双列布局。左侧为原文查看器，根据文件类型分发：PDF 使用 pdf.js 进行客户端渲染并支持证据边界框覆盖层，DOCX 通过 mammoth.js 转换为 HTML，Markdown 和纯文本使用对应的渲染组件。右侧为结构化结果面板，按文档类型槽位将提取对象分组展示为可折叠列表。点击对象时，左侧原文对应区域自动高亮，支持从结构化结果到原文证据的双向定位。

证据可视化的实现取决于来源文档类型。PDF 文档通过 `calculateHighlightRect()` 将证据 bbox 坐标映射为视口相对坐标，渲染为可点击的 `<button>` 覆盖层。对于无 bbox 的 DOCX、Markdown 和 TXT 文档，前端通过 `useTextEvidence` 钩子在 DOM 渲染后遍历文本节点，使用 `document.createRange` 和 `<mark>` 元素标记匹配的 `text_span`。

前端还提供修订接口，支持用户编辑 raw_text、summary 和 extracted_data。raw_text 变化时自动清除旧 IR，确保数据一致性。结构化 JSON 编辑使用基于 CodeMirror 的代码编辑器，提供语法高亮和格式校验。

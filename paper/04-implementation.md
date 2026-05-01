# 第四章 系统实现

## 4.1 后端服务实现

DocStruct 后端入口为 FastAPI 应用，启动时完成：读取环境变量配置、创建 `uploads/` 目录、通过 `TortoiseORM.init()` 注册 SQLite 数据模型。启用 CORS 允许本地 React 前端（`http://localhost:5173`）访问。运行参数通过环境变量注入——`LLM_BASE_URL`、`LLM_MODEL` 指定模型端点，`EXTRACTION_CHUNK_MAX_CHARS`（默认 5000）和 `EXTRACTION_CONCURRENCY`（默认 3）控制分块和并发。

上传接口 `/api/upload` 接收 file 和 doc_type 表单字段。服务端保存文件至 `uploads/`，创建状态为 pending 的 `DocumentRecord`，通过 FastAPI `BackgroundTasks` 启动后台流水线。流水线按序执行解析、摘要生成、结构化抽取和证据绑定，每阶段完成时更新数据库状态。上传请求快速返回文档 ID，前端可轮询或手动刷新查看进度。

## 4.2 文档解析实现

解析模块通过 `ParserFactory.get_parser()` 按文件扩展名调度。Markdown/TXT 直接文本读取；DOCX 使用 `python-docx` 解析段落和表格；PDF 支持两种后端——basic parser 基于 PyMuPDF 提取文本和坐标，Docling parser 提供版面分析、表格识别和 Markdown 输出[5]。

解析结果统一为 `ParseResult`（markdown + blocks），随后由 `parse_result_to_ir()` 构建 `DocumentIR`。构建过程按 `block.order` 遍历，维护 `heading_stack`（标题栈）：遇标题时截断栈至当前层级减一，追加新标题，形成 `["第一章", "1.1 研究背景"]` 的路径。非标题元素继承当前栈作为 section_path。每个元素映射为 `DocumentElement`，包含递增 element_id（如 `el-0001`）、markdown、text、page、bbox、reading_order 和 section_path。对于 SRS 文档，`_is_srs_field_label_title()` 过滤"需求编号"、"验收标准"等字段标签，防止误判为章节边界。

IR 构建完成后成为下游分块、抽取和证据绑定的唯一输入源。

## 4.3 结构化抽取实现

入口函数 `extract_structure_with_meta()` 分三阶段执行。

**准备阶段：** 确保 DocumentIR 可用（无 IR 则从 Markdown 构建），检查字符数（超 100000 拒绝处理），根据 response_model 构造 `ExtractionContract`。契约通过 Pydantic 类型注解动态生成——`__origin__` 检查区分文档级字段和 list 类型槽位。同时读取忽略章节列表，将参考文献、附录等排除出分块范围。

**Map 阶段：** 调用 `split_ir_into_chunks()` 分块后，为每个块创建异步任务 `_extract_chunk()`。`asyncio.Semaphore(3)` 控制并发，同步 HTTP 调用通过 `asyncio.to_thread()` 包装。提示词由 `_render_chunk_context()` 构建，含六部分：系统提示、文档大纲（全局章节结构）、文档摘要（可选）、抽取契约（目标槽位 + 规则）、分块元数据（chunk_index、total_chunks、allowed_evidence_element_ids）和渲染 Markdown（每元素前缀 `[ELEMENT: el-XXXX page=N]`）。LLM 响应后经 JSON 清洗（去 Markdown 代码块包裹、修复尾随逗号）和 Pydantic 校验。单块失败不中断流程——只要存在至少一个有效块，系统继续合并。

**合并阶段：** 先尝试 Finalizer（一次附加 LLM 调用，去重合并跨块候选，不读原文、不引入新事实），失败回退 Reducer。

## 4.4 Reducer 实现

Reducer 零 LLM 调用。`reduce_extraction_results()` 通过 response_model 类型注解动态发现槽位，排除 doc_type、title、extra、evidence 等元字段。文档级标量字段取长不取空，列表去重合并。对象槽位按身份键去重：name + 类型字段（`_type` 结尾）优先，LLM id 次之，JSON 序列化兜底。匹配对象按字段级合并——字典递归、列表去重追加、字符串取长。`_assign_global_ids()` 按槽位映射前缀（functional_requirements→FREQ，tables→TBL 等），分配 `FREQ-001` 格式的全局 ID。`clean_empty_values()` 递归修剪空值。

## 4.5 证据绑定实现

`bind_evidence()` 遍历每个对象的 evidence_element_ids，在 IR 元素映射表中查找对应元素——仅保留实际存在的 ID，其余丢弃。每条 evidence 含 object_id、element_id、text_span（截取前 500 字符）、page 和 bbox，通过 `(object_id, element_id, text_span)` 三元组去重。evidence coverage = 有证据对象数 / 总对象数。

## 4.6 Schema Registry 实现

`TYPED_MODEL_MAP` 维护 DocType 枚举到 Pydantic model 的映射，覆盖五类文档 + unknown。`normalize_doc_type()` 将输入规范化为枚举（非法值回退 unknown），`get_response_model()` 返回对应模型或 None。各文档 Schema 位于 `schemas/docs/`，采用 BaseNode → 具体类型 → BaseExtractedDocument 三层继承。字段级 `field_validator` 将中文枚举值（"高"/"中"/"低"）归一化为英文枚举。新增文档类型只需定义新模型并注册映射。

## 4.7 前端实现

前端基于 React 19、TypeScript、Vite、Tailwind CSS 和 shadcn/ui。单页布局：左侧 280px 侧边栏（文档列表 + 筛选 + 拖放上传区），右侧主区域（文档详情 + 抽取结果）。

上传使用拖放组件，支持 PDF/DOCX/MD/TXT。上传时弹出文档类型选择对话框（卡片网格展示五种类型）。TanStack Query 管理数据获取，处理中文档每 2 秒轮询状态。

详情页双列布局：左侧原文查看器按文件类型分发——PDF 用 pdf.js 渲染并叠加证据覆盖层，DOCX 用 mammoth.js 转 HTML，Markdown/纯文本用对应组件。右侧结构化结果面板按槽位分组展示可折叠对象列表。点击对象时左侧自动高亮对应原文区域。

证据可视化因文档类型而异：PDF 通过 `calculateHighlightRect()` 将 bbox 映射为视口坐标，渲染可点击覆盖层；无 bbox 文档通过 `useTextEvidence` 钩子遍历 DOM 文本节点，用 `<mark>` 标记匹配的 text_span。前端提供 raw_text/summary/extracted_data 修订功能，raw_text 变化时自动清除旧 IR。

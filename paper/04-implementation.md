# 第四章 系统实现

## 4.1 后端服务实现

DocStruct 后端入口为 FastAPI 应用。系统在启动时读取运行配置，创建上传目录，并通过 Tortoise ORM 注册 SQLite 数据库模型。后端启用 CORS，使本地 React 前端可以访问 API。

上传接口接收文件和 doc_type 表单字段，保存记录后通过 BackgroundTasks 启动后台处理流水线。系统通过环境变量配置模型端点、分块参数和并发数等运行参数。当前代码默认模型为 qwen-doc-turbo，论文实验最终选定 deepseek-v4-flash，后续应同步默认配置。

## 4.2 文档解析实现

解析模块按文件扩展名选择合适解析器。Markdown 和 TXT 文档可直接读取为文本；DOCX 文档需要读取段落和表格；PDF 文档可通过 basic parser 或 Docling parser 解析[5]。解析结果会被转换为统一的 Markdown 和 Document IR。

Document IR 构建时会为文档元素分配 element_id，并记录元素文本、Markdown、页码、bbox、章节路径和阅读顺序等信息。对于无法提供坐标的解析方式，page 和 bbox 可以为空，但元素 ID 和文本仍能支持基本证据回溯。

## 4.3 结构化抽取实现

抽取模块首先根据 response_model 构造 ExtractionContract，然后准备 Document IR。如果调用方没有提供 IR，系统会从 Markdown 构建基础 IR。系统会统计输入字符数，并在超过最大长度时拒绝处理，当前默认上限为 100000 字符。

分块完成后，系统使用 asyncio.Semaphore 控制并发，默认并发数为 3。每个 chunk 调用大语言模型完成局部抽取，与 LLM×MapReduce 的分块处理思路一致[6]。提示词包含系统提示、文档大纲、文档摘要、抽取契约、分块元数据、允许引用的 evidence_element_ids 和当前分块内容。模型输出后，系统调用 JSON 清洗和解析函数，并使用 Pydantic 模型校验结果。

如果某些 chunk 抽取失败，系统会记录失败索引和失败原因。只要存在有效分块结果，系统仍会尝试继续合并；如果所有分块都失败，则抛出错误并终止抽取。

## 4.4 Reducer 实现

Reducer 使用 response_model 动态发现对象槽位和文档级字段。对于文档级字段，系统选择非空值并按类型合并；对于对象槽位，系统收集所有分块候选，按槽位、名称和类型字段生成身份键进行合并。

合并策略保持简单。字典字段递归合并，列表字段去重合并，字符串字段保留更长的非空值。合并完成后，系统为对象重新分配全局 ID，避免不同分块中模型生成的 ID 冲突。

证据绑定由 bind_evidence 完成。该函数根据对象中的 evidence_element_ids 查找 Document IR 元素，过滤不存在的证据 ID，并生成 evidence 记录。证据覆盖率由带证据对象数除以对象总数得到，可作为结果质量的辅助指标。

## 4.5 Schema Registry 实现

Schema Registry 负责将 doc_type 映射到对应 Pydantic response model。系统支持的文档类型包括 srs、api、hld、tc、dbdd 和 unknown。unknown 类型不执行结构化抽取，只保留基础解析结果。

各文档类型的 Schema 位于 `schemas/docs` 目录。以 SRS 为例，系统定义了 FunctionalReqItem、NonFunctionalReqItem、BusinessFlowItem 和 SrsExtractedDocument。字段中使用枚举和 validator 归一化优先级、非功能需求类别等值，降低模型输出差异对校验的影响。

## 4.6 前端实现

前端基于 React、TypeScript、Vite、Tailwind CSS 和 shadcn/ui 实现。主要页面包括文档上传、文档列表、文档详情、结构化结果展示和原文对照视图。

前端读取后端返回的 extracted_data 和 evidence，将不同槽位的结构化对象展示为可读列表。对于 PDF 文档，如果 evidence 中包含 page 和 bbox，前端可以将结构化对象映射回 PDF 页面并进行高亮。对于没有 bbox 的文档，前端仍可展示 text_span 作为文本证据。

该设计使用户不仅能看到抽取结果，还能检查结果来源，减少大模型输出不可解释的问题。

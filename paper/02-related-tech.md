# 第二章 相关技术

## 2.1 大语言模型技术

### 2.1.1 大语言模型概述

大语言模型（Large Language Model, LLM）是基于 Transformer 架构的大规模预训练语言模型，通过在超大规模文本语料上进行自监督学习，获得了强大的自然语言理解与生成能力。以 GPT-4、Claude、Qwen、DeepSeek 为代表的主流 LLM 在文本摘要、信息抽取、代码生成、多轮对话等任务上展现出接近甚至超越人类水平的表现。

LLM 的核心能力之一是在零样本（Zero-Shot）或少样本（Few-Shot）条件下遵循指令完成任务。用户通过自然语言提示词（Prompt）描述任务要求，模型即可按照指定的格式输出结果。这种"指令遵循"能力使得 LLM 非常适合处理软件工程文档的信息提取任务：用户无需为每种文档类型训练专用模型，只需设计合适的提示词和输出模式，即可让 LLM 从非结构化文本中抽取需求、接口、测试用例等结构化信息。

### 2.1.2 OpenAI 兼容 API 与模型选择

当前主流 LLM 服务提供商（包括 OpenAI、阿里云 DashScope、DeepSeek、月之暗面 Moonshot 等）普遍采用与 OpenAI Chat Completions API 兼容的接口规范。该规范的核心参数包括：`model`（模型名称）、`messages`（对话消息列表，区分 system/user/assistant 角色）、`temperature`（生成随机性控制，取值范围 0~2）和 `max_tokens`（最大输出 token 数）。

在本系统中，LLM 的调用通过一个薄适配层（`core/llm.py`）封装，使用 OpenAI 官方 Python SDK 的 `OpenAI` 客户端实例，通过配置 `base_url` 和 `api_key` 实现对不同服务提供商的透明切换。模块提供了 `get_openai_client()` 函数（采用 LRU 缓存确保单例）和 `build_chat_completion_kwargs()` 函数（统一构建请求参数）。温度参数固定为 0.0，以最大化提取结果的确定性与可复现性。

### 2.1.3 提示词工程

提示词工程（Prompt Engineering）是 LLM 应用开发中的关键技术，指通过精心设计输入文本的结构、措辞和约束条件，引导模型生成符合预期的输出。在本系统中，提示词设计遵循以下原则：

**角色设定**。系统提示词（System Prompt）为模型设定"严谨的软件工程文档结构化专家"角色，明确其任务是将输入的文档内容按照指定模式提取为结构化数据。

**结构化输出约束**。提示词中包含严格的 JSON 格式指令（`JSON_FORMAT_INSTRUCTION`），要求模型"只返回合法 JSON，不要 Markdown，不要注释"。同时，通过将 Pydantic 模型转换为 JSON Schema 字符串嵌入提示词，使模型理解目标输出的字段名称、类型和嵌套结构。

**上下文注入**。Map 阶段的用户提示词模板（`MAP_USER_PROMPT_TEMPLATE`）包含四个占位符：`{doc_outline}`（文档大纲）、`{phase0_context}`（预扫描上下文）、`{contract}`（提取契约，定义目标槽位、规则和忽略章节）以及 `{content}`（分块后的文档文本，含元素标记）。这种层次化的上下文注入确保模型在理解全局结构的前提下进行局部精确提取。

## 2.2 文档解析技术

### 2.2.1 多格式解析与归一化

软件工程文档的格式呈现高度多样性，常见的存储格式包括 PDF、DOCX、Markdown 和纯文本。不同格式的解析方法存在显著差异：PDF 需要处理页面布局分析和文本提取；DOCX 需要解析 Open XML 文档结构；Markdown 和纯文本则需要统一的规范化处理。

本系统采用"解析器策略模式"（Parser Strategy Pattern）实现多格式统一处理。抽象基类 `BaseParser` 定义统一的 `parse_to_result(file_path) -> ParseResult` 接口，三种具体解析器分别实现：

- **PdfParser**：基于 `pymupdf4llm` 库，将 PDF 页面转换为 Markdown 格式。该解析器内置 OCR 需求智能检测机制：通过对首页、中间页和尾页进行分层抽样，统计文本字符数、平均每页字符数和空页面占比，当任一指标低于阈值时自动启用 OCR 模式。该设计避免了在文本型 PDF 上进行不必要的 OCR 处理，平衡了解析质量和处理速度。

- **DocxParser**：基于 `python-docx` 库，遍历 DOCX 文档的 XML 正文子元素。解析器通过 Word 样式映射识别标题级别、列表项、代码块和引用块，将相邻列表项聚合为统一的列表块，并将所有内容渲染为规范的 Markdown 输出。

- **PlainTextParser**：处理 `.md` 和 `.txt` 文件，通过 UTF-8（带 GBK 回退）编码读取后，送入 `MarkdownNormalizer` 进行规范化处理。

### 2.2.2 Markdown 规范化与中间表示

为实现不同格式输出的一致性，系统设计了"Markdown 规范化器"（`MarkdownNormalizer`），采用两遍（Two-Pass）处理策略。

第一遍（解析阶段）将输入文本按行解析为 `DocBlock` 列表，每个 `DocBlock` 包含类型（标题、段落、引用、代码、列表、表格）、文本内容、层级和元数据。解析通过正则表达式调度完成：持续匹配 Markdown 标题标记（`#` 开头）、编号标题（如"1.2.3 标题"）、代码围栏（` ``` `）、表格分隔行、列表项标记和引用标记，将普通文本行聚合为段落块。

第二遍（渲染阶段）通过 `MarkdownRenderer` 将 `DocBlock` 列表确定性渲染回 Markdown 文本。对于表格块，渲染器自动选择 Markdown 管道表格或 HTML `<table>` 标签：当单元格内容包含换行或管道符时，触发 HTML 渲染以保证格式稳定性。

规范化的 Markdown 输出随后被转换为**文档中间表示**（Document Intermediate Representation, Document IR）。Document IR 是后续所有操作（分块、LLM 提取、证据绑定）的基础数据结构，包含三个核心组件：

1. **元素列表**（`elements`）：将每个 `DocBlock` 映射为 `DocumentElement`，分配全局唯一的元素 ID（如 `el-0001`），记录元素类型、文本内容、Markdown 渲染、所属章节路径和页码。
2. **章节大纲**（`outline`）：通过维护标题栈构建层级化的章节路径（如 `["1 系统概述", "1.1 架构设计"]`），生成扁平的章节列表和主要主题摘要。
3. **元数据**（`metadata`）：包含文档标题、类型、版本等附加信息。

### 2.2.3 替代解析后端

除基本解析器外，系统还支持基于 IBM Docling 库的替代解析后端（`DoclingParser`）。Docling 在以下方面具有优势：更精确的表格结构识别、细粒度的页面边界框（Bounding Box）坐标提取、视觉行合并能力（将跨多行的碎片化文本合并为连贯段落）。系统通过 `ParserFactory` 工厂方法和 `PARSER_BACKEND` 环境变量实现解析后端的可插拔切换，用户可根据文档特征选择合适的解析策略。

## 2.3 分块策略

LLM 的核心限制之一是上下文窗口（Context Window）的有限性。尽管主流模型已支持数十万 token 的上下文，但输入长度与提取质量之间存在负相关关系：过长的输入会导致模型注意力分散，在文档中部或尾部区域出现信息遗漏或"幻觉"。此外，更长的输入意味着更高的 API 调用成本和延迟。

为应对这一挑战，系统采用**分节感知分块策略**（Section-Aware Chunking），将长文档拆分为多个大小可控的分块（Chunk），分别送入 LLM 进行局部提取。分块算法（`split_ir_into_chunks`）的核心设计要点如下：

**章节边界尊重**。分块以文档元素为最小单位，优先将属于同一章节路径的元素聚合到同一分块中。分块器仅在当前分块的累计字符数超过目标上限时才切分。当单个章节的元素字符数超过目标上限时，按元素边界进一步拆分为多个子分块，确保每个分块在语义上是自包含的。

**章节过滤**。默认忽略术语表（Glossary）、参考文献（References）和附录（Appendix）等非核心章节（支持中英文名称变体），减少无关信息对 LLM 提取的干扰。

**重叠窗口**。相邻分块之间保留可配置的重叠字符数（默认 200 字符），通过"尾部复制"（Tail Copy）机制将前一个分块的末尾元素注入当前分块的首部。这为 LLM 提供跨分块边界的上下文连续性，降低因切分而导致的信息断裂风险。

**证据标记注入**。在渲染每个分块的 Markdown 文本时，为每个元素插入位置标记（`[ELEMENT: el-0001 page=3]`），作为后续证据绑定的锚点。

## 2.4 相关框架与工具

### 2.4.1 FastAPI

FastAPI 是一个基于 Python 类型注解的现代 Web 框架，构建于 Starlette（异步 Web 框架）和 Pydantic（数据验证库）之上。其核心特点包括：自动生成 OpenAPI 文档、基于类型注解的请求验证、原生异步支持（`async/await`）以及高性能（性能对标 Node.js 和 Go 框架）。

本系统使用 FastAPI 构建 RESTful API 服务，提供文档上传、文档列表查询、详情获取、手动修订、分块调试、重新提取和文件下载等 8 个端点。后台提取任务通过 FastAPI 的 `BackgroundTasks` 机制异步执行，上传接口在完成文件接收和数据库记录创建后立即返回，后续的解析和提取在后台独立完成。

### 2.4.2 React 与 TypeScript

React 是 Meta 公司开源的声明式前端 UI 框架，采用组件化开发模式和虚拟 DOM 机制实现高效的视图更新。TypeScript 通过静态类型检查增强了 JavaScript 的可靠性和可维护性，尤其适合数据结构复杂的应用场景。

本系统的前端基于 React + Vite + TypeScript 构建，采用 TanStack Query（前身为 React Query）进行服务端状态管理和自动轮询。核心界面为三标签页的校对工作台：证据对照标签页使用 PDF.js 渲染原始 PDF 文档并叠加边界框高亮层，Markdown 校对标签页提供并排的原文查看和编辑区域，分块调试标签页展示管道的分块结果。

### 2.4.3 Pydantic 数据校验

Pydantic 是 Python 的数据验证库，通过类型注解定义数据模型，在运行时自动进行类型转换和校验。其 v2 版本基于 Rust 核心（pydantic-core），在性能上有显著提升。

在本系统中，Pydantic 承担三重角色：第一，作为 LLM 提取输出的校验层——所有提取结果在入库前必须通过对应文档类型的 Pydantic 模型验证，不合法的输出被拒绝并返回错误信息；第二，作为 Schema 生成源——通过 `model_json_schema()` 方法将模型转换为 JSON Schema 字符串，嵌入 LLM 提示词中指导结构化输出；第三，作为 ORM 数据模型——Tortoise ORM 的 `DocumentRecord` 同样定义为 Pydantic 模型，统一了数据校验和数据持久化的模型定义。

### 2.4.4 Tortoise ORM 与 aiosqlite

Tortoise ORM 是 Python 的异步对象关系映射库，灵感来源于 Django ORM，但专为 `asyncio` 生态设计。系统选用 SQLite（通过 `aiosqlite` 驱动）作为存储后端，其零配置、轻量级的特点适合单机部署场景。数据库仅存储文档记录（含解析内容和提取结果），不构建知识图谱或向量索引，保持了系统架构的简洁性。

# 第五章 系统实现

## 5.1 开发环境与技术选型

系统的技术选型遵循"成熟稳定、生态丰富、学习曲线平缓"的原则。后端采用 Python 3.11+ 作为主要开发语言，利用 `asyncio` 实现异步 I/O；前端采用 React 18 + TypeScript + Vite 构建。表 5-1 列出了各模块的核心技术栈。

**表5-1 技术栈选型**

| 层次 | 技术 | 版本 | 选型理由 |
|------|------|------|---------|
| 后端框架 | FastAPI | 0.115+ | 原生异步、自动 OpenAPI 文档、Pydantic 集成 |
| 异步 ORM | Tortoise ORM | 0.21+ | 类 Django 语法、完整 asyncio 支持 |
| 数据库 | SQLite (aiosqlite) | — | 零配置、单文件部署、事务支持 |
| LLM SDK | openai (Python) | 1.x | OpenAI 兼容协议，支持多提供商 |
| PDF 解析 | PyMuPDF (pymupdf4llm) | 1.24+ | Markdown 输出、OCR 检测 |
| DOCX 解析 | python-docx | 1.1+ | XML 段落级遍历、样式映射 |
| 前端框架 | React | 18 | 组件化、虚拟 DOM、生态丰富 |
| 前端构建 | Vite | 6 | 快速 HMR、ESBuild 打包 |
| 状态管理 | TanStack Query | 5 | 服务端状态缓存、自动轮询 |
| PDF 渲染 | PDF.js | 4.x | 高保真 PDF 渲染、页码导航 |
| 数据校验 | Pydantic | 2.x | Rust 核心、JSON Schema 生成 |

## 5.2 文档解析模块实现

### 5.2.1 解析器架构

解析器模块采用策略模式（Strategy Pattern）实现多格式支持。抽象基类 `BaseParser` 定义统一接口，三种具体解析器（`PdfParser`、`DocxParser`、`PlainTextParser`）分别实现。`ParserFactory` 工厂类根据文件扩展名（或用户指定的后端参数）选择合适的解析器实例。

```python
# core/parser.py — ParserFactory 核心逻辑
class ParserFactory:
    _EXT_MAP = {".pdf": "pdf", ".docx": "docx", ".txt": "text", ".md": "text"}

    @staticmethod
    def create(file_path, *, backend="basic"):
        ext = Path(file_path).suffix.lower()
        kind = ParserFactory._EXT_MAP.get(ext)
        if kind == "pdf":
            if backend == "docling":
                return DoclingParser()
            return PdfParser()
        if kind == "docx":
            return DocxParser()
        if kind == "text":
            return PlainTextParser()
        raise ValueError(f"Unsupported file type: {ext}")
```

### 5.2.2 PDF 解析与 OCR 智能检测

`PdfParser` 基于 `pymupdf4llm.to_markdown()` 将 PDF 页面转化为 Markdown 格式。其关键设计在于 OCR 需求智能检测机制——系统通过分层抽样判断是否需要启用 OCR，避免在文本型 PDF 上进行不必要的 OCR 处理。

检测算法（`_needs_ocr` 方法）统计采样页面的文本提取指标：总字符数、平均每页字符数和空页面占比。当任一指标低于预设阈值时，触发 OCR 模式。抽样采用分层策略（`_sample_page_indices`）：确保首页、中间页和尾页都被覆盖，以捕获扫描文档中典型的"封面扫描+正文文本"或"全文扫描"等不同分布模式。

### 5.2.3 Markdown 规范化器

`MarkdownNormalizer` 实现了两遍文本规范化处理。第一遍（`_parse_blocks`）将输入文本逐行解析为 `DocBlock` 列表，使用正则调度器按优先级匹配行类型：代码围栏标记、表格分隔行、Markdown 标题（`#` 开头）、编号标题（如"1.2.3 标题"）、列表项标记、引用标记和普通段落。

编号标题检测（`_parse_numbered_heading`）是一个专门的启发式算法：基于纯数字点号模式的识别和层级推断，同时利用上下文特征（前一行是否以冒号结尾、后续行是否延续简单数字序列）来减少误识别。该算法将"1.2.3 功能需求"自动转换为三级标题，保持了与 Markdown 标题一致的结构语义。

第二遍通过 `MarkdownRenderer` 将 `DocBlock` 列表确定性渲染回 Markdown。表格块的渲染采用自适应策略：当单元格内容包含换行符或管道符时，自动切换到 HTML `<table>` 渲染以保证格式稳定性；简单表格则使用标准 Markdown 管道表格格式。

## 5.3 结构化提取模块实现

### 5.3.1 提取管道编排

`extract_structure_with_meta` 函数是整个提取管道的总控入口。该函数按以下顺序编排各阶段：

**第一步：准备 Document IR。** 若调用方传入外部 IR（例如从数据库加载的已缓存 IR），则直接使用；否则从 Markdown 文本通过 `build_basic_ir_from_markdown` 构建新 IR，并同步 `doc_type` 和 `title` 到大纲中。

**第二步：构建 ExtractionContract。** 通过 `build_extraction_contract` 函数，从响应模型自省发现目标槽位（调用 `discover_slots`），组装提取规则和忽略章节列表，形成完整的提取契约对象。

**第三步：Phase 0 预扫描。** 当 `phase0_enabled=True` 时，调用 `run_phase0_prescan` 执行廉价预扫描。该函数采样文档头/中/尾部各约 2000 字符（总计 6000 字符预算内的三等分），向 LLM 发送轻量级分析请求，获取文档类型判断、关键实体和章节主题。

**第四步：分块。** 调用 `split_ir_into_chunks`，传入可配置的 `chunk_max_chars`、`overlap_chars` 和 `ignore_sections` 参数，将 Document IR 拆分为分块列表。

**第五步：Map 并发提取。** 使用 `asyncio.Semaphore` 控制并发数（默认 3），通过 `asyncio.gather` 并发发起 LLM 提取请求。每个分块调用 `_extract_chunk`，该函数先通过 `_render_chunk_context` 构建上下文注解（含文档大纲、Phase 0 上下文、提取契约和分块元数据），再调用 `_extract_once` 执行实际的 LLM 调用和 JSON 解析。

### 5.3.2 上下文注入机制

每个分块的 LLM 调用接收四个层次的上下文信息：

- **全局结构层**：文档完整大纲（所有章节标题及其层级关系），帮助 LLM 理解当前分块在整个文档中的位置。
- **预扫描层**：Phase 0 的分析结果（文档类型、关键实体、章节主题、提取提示），为 LLM 提供文档全局语义。
- **契约层**：提取契约（目标槽位列表、提取规则），明确要求 LLM 提取哪些类型的信息。
- **分块层**：当前分块元数据（chunk_id、section_path、页码范围、允许引用的元素 ID 白名单）。

分块的 Markdown 文本中包含 `[ELEMENT: el-NNNN page=N]` 格式的元素标记，LLM 被指示在每个提取对象的 `evidence_element_ids` 字段中引用这些标记，从而实现证据追踪。

### 5.3.3 健壮 JSON 解析

LLM 返回的自然语言响应可能不完全符合 JSON 格式规范。`clean_and_parse_json` 函数实现了多层次的容错解析策略：

1. **Markdown 代码块剥离**：尝试匹配并去除 ` ```json ` 或 ` ``` ` 包裹。
2. **截断修复**（`_repair_truncated_json`）：从后往前扫描，补齐缺失的 `}`、`]` 和 `"` 闭合符号。
3. **Python 字典转换**：尝试使用 `ast.literal_eval` 处理单引号风格的 Python 字典。
4. **标准 JSON 解析**：调用 `json.loads` 进行最终解析。

## 5.4 Reducer 与证据绑定实现

### 5.4.1 槽位发现

`discover_slots` 函数通过内省 Pydantic 模型的字段注解，筛选出类型为 `list[BaseNode 子类]` 的字段作为目标槽位。该函数维护一个排除列表（`doc_type`、`title`、`version`、`extra`、`evidence`、`base_url`、`test_stage`），确保文档级字段不会被误识别为提取槽位。这种自省式设计消除了 Reducer 对硬编码槽位列表的依赖。

### 5.4.2 身份去重算法

`_identity_for_item` 函数实现了槽位特定的身份匹配策略。核心逻辑如下：

- 接口对象：若 `http_method` 和 `endpoint` 字段均非空，以 `<interface_type>#<http_method>#<endpoint>` 为主身份；否则回退到 `<name>#<provider>#<consumer>`。
- 实体对象：以 `<entity_type>#<name>` 为身份。
- 需求对象：优先使用原始文档 ID（如 `FUNC-REQ-001`），缺失时以 `<requirement_type>#<name>#<text[:80]>` 为身份。

同一去重组内的候选对象被合并：取最长名称、最长文本字段，合并所有唯一证据引用。冲突字段（如不一致的 `entity_type`）以首次出现为准并记录日志。

### 5.4.3 证据绑定

`bind_evidence` 函数将 LLM 引用的 `evidence_element_ids` 与 Document IR 中的实际元素进行交叉验证。函数首先构建 `{element_id: DocumentElement}` 的快速查找表，然后遍历所有提取对象，为每个有效的 `evidence_element_id` 创建 `Evidence` 记录（含对象 ID、元素 ID、文本片段、页码和边界框）。

证据绑定的核心价值在于"可验证性"——用户可以通过点击前端界面中的任意提取对象，导航到原始文档中对应的确切位置。对于 PDF 文档，系统利用边界框坐标在 PDF.js 渲染层上绘制高亮叠加层；对于 Markdown 和纯文本文档，系统高亮对应的文本段落。

## 5.5 前端界面实现

### 5.5.1 整体布局与导航

前端基于 React 18 + TypeScript 构建，入口组件 `App.tsx` 采用左侧边栏 + 右侧主面板的双栏布局。左侧边栏（`DocSidebar`）展示文档列表，支持按文件名搜索和按文档类型筛选。右侧主面板使用标签页（Tab）切换三种视图：证据对照、Markdown 校对和分块调试。

状态管理采用 TanStack Query（前身为 React Query），利用其自动轮询机制——对于状态为 `"uploaded"`、`"parsing"` 或 `"extracting"` 的文档，每 2 秒自动刷新一次状态，直到处理完成或失败。

### 5.5.2 证据对照标签页

证据对照标签页（`PdfEvidenceViewer` + `ExtractionResultPanel`）是系统的核心交互界面，采用对开（Split-Pane）布局：左侧渲染原始文档，右侧以分组列表展示结构化提取结果。

左侧原始文档渲染按文档格式自适应：PDF 文档使用 PDF.js 库渲染，支持页码导航和缩放；Markdown 文档使用 `rehype` + `remark` 渲染为 HTML；纯文本文档以预格式化文本显示。在 PDF 模式下，证据系统根据 `Evidence.bbox` 数据在每个证据对应的页面位置绘制半透明彩色矩形叠加层，当用户在右侧点击某个提取对象的"定位"按钮时，PDF 查看器自动跳转到对应页面并闪烁高亮边界框。

右侧提取结果面板按文档类型特定的槽位分组展示。例如，对 SRS 类型文档，面板依次显示"实体对象"、"功能需求"、"非功能需求"和"接口"四个分组。每个对象展示为一张可折叠的卡片，显示名称、类型和关键摘要字段。展开卡片后，用户可查看完整字段详情并逐字段进行内联编辑后保存。

### 5.5.3 Markdown 校对标签页

Markdown 校对标签页（`DocPreviewPanel`）提供标准化 Markdown 文本的查看与编辑功能。左右两栏并排显示：左栏为解析生成的标准化 Markdown（只读模式），右栏为可编辑的文本区域。用户可在右栏直接修改 Markdown 文本后点击"保存并重新提取"按钮，系统将更新后的文本发送到后端重跑提取管道。

### 5.5.4 分块调试标签页

分块调试标签页（`ChunkDebugPanel`）是面向开发者和高级用户的诊断工具。它通过 `/api/documents/{id}/chunks` 端点获取分块信息，以列表形式展示每个分块的元数据（chunk_id、section_path、页码范围、元素数量、字符数）及其包含的元素预览。用户可以直观地了解管道如何将文档切分为分块，帮助诊断分块策略导致的信息遗漏或重复问题。

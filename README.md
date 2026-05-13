# DocStruct

**基于大模型的软件工程文档结构化提取系统**

> 推荐使用 `.venv` 环境。

DocStruct 当前聚焦于软件工程文档的结构化提取与离线评测。系统不包含知识库问答、向量检索、URL 导入、模型切换和前端联动能力。

## 当前能力

- 支持 `PDF`、`DOCX`、`MD`、`TXT` 文件上传
- 支持 5 类主干软件工程文档：`srs`、`api`、`hld`、`tc`、`dbdd`
- `unknown` 类型只保留解析后的原文、摘要与 IR，不执行结构化抽取
- 解析结果同时保存 `raw_text`、`summary` 和 `document_ir`
- 抽取结果统一输出五类主干对象和证据回溯
- 前端支持 PDF/DOCX 原文与结构化结果左右对照，并可点击提取项定位 bbox 证据
- 支持从文档前部确定性提取版本号等元数据
- 提供离线评测脚本，便于论文实验复现

## 设计概要

DocStruct 不做通用 JSON 生成器，而是面向软件工程文档建立稳定抽取链路：

```text
PDF / DOCX / MD / TXT
    ↓
Parser → Document IR
    ↓
LLM Summary
    ↓
Section-aware Chunking
    ↓
Map：逐块局部抽取
    ↓
Finalize：LLM 合并分块候选（失败则降级跳过）
    ↓
Reduce：确定性合并、去重、全局 ID
    ↓
Evidence Binding
    ↓
Final JSON
```

核心思想：

- `Document IR` 保存标题、段落、表格、页码、bbox、章节路径和阅读顺序
- `summary` 在解析后由 LLM 基于文档内容和大纲生成，并作为分块抽取的全局上下文
- `ExtractionContract` 控制每类文档抽什么，不使用任意动态 Schema
- LLM 只负责 chunk 内局部语义抽取和候选合并，Reduce 尽量使用确定性逻辑
- Finalizer 在 Map 之后用一次额外 LLM 调用合并分块候选，失败时自动降级跳过
- 术语表、参考资料、附录等章节在分块时自动跳过
- finalizer 只合并分块候选，不再读取完整原文证据片段，避免退化为全文一次性抽取
- 每个对象通过 1-3 个 `evidence_element_ids` 锚点绑定到原文元素，最终生成 `evidence`
- 前端通过 `evidence.object_id/page/bbox` 将结构化对象映射回 PDF 页面证据
- Schema 只保留高价值事实字段，避免用派生分组或兜底字段稀释结果

## 边界说明

- 系统仅面向中短文档，默认上限为 `100000` 字符
- 超过上限的文档直接拒绝处理
- 当前后端只服务结构化提取主流程
- 知识库问答、向量库和跨文档长期记忆后续应作为独立模块设计

## 支持的文档类型

| 文档类型 | `doc_type` | 重点抽取内容 |
| --- | --- | --- |
| 软件需求规格说明书 | `srs` | 角色、模块、需求、接口；需求内包含验收标准 |
| API 接口文档 | `api` | 接口、endpoint 元数据、请求响应产物 |
| 概要设计说明书 | `hld` | 架构风格、技术栈、模块职责 |
| 测试用例文档 | `tc` | 测试范围、测试用例、测试步骤 |
| 数据库设计文档 | `dbdd` | 数据库、表、字段定义 |
| 未知类型 | `unknown` | 仅保留基础元信息、原文、摘要和 IR |

## Typed 输出结构

```python
class SrsExtractedDocument(SrsExtraction, BaseExtractedDocument):
    doc_type: Literal[“srs”] = Field(default=”srs”)
    system_name: str = Field(default=””)
    target_users: list[str] = Field(default_factory=list)
    functional_requirements: list[FunctionalReqItem] = Field(default_factory=list)
    non_functional_requirements: list[NonFunctionalReqItem] = Field(default_factory=list)
    business_flows: list[BusinessFlowItem] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)
```

- 每类文档使用独立 typed schema：SRS 使用 `functional_requirements` / `non_functional_requirements` / `business_flows`，API 使用 `apis`，HLD 使用 `modules` / `core_flows` / `design_decisions`，TC 使用 `test_cases`，DBDD 使用 `tables`
- `id` 是系统生成的稳定对象 ID，前缀映射如下：

| 槽位 | 前缀 | 示例 |
| --- | --- | --- |
| `functional_requirements` | `FREQ` | `FREQ-001` |
| `non_functional_requirements` | `NFR` | `NFR-001` |
| `business_flows` | `BFL` | `BFL-001` |
| `apis` | `APIS` | `APIS-001` |
| `modules` | `MOD` | `MOD-001` |
| `core_flows` | `CFL` | `CFL-001` |
| `design_decisions` | `DEC` | `DEC-001` |
| `test_cases` | `TC` | `TC-001` |
| `tables` | `TBL` | `TBL-001` |

- 原文编号可作为 `name` 后缀保留
- SRS 的验收标准不作为独立需求输出，局部验收条目写入对应功能需求的 `criteria`
- `evidence` 保存对象到 `DocumentElement` 的回溯信息
- `evidence_element_ids` 是少量定位锚点，不要求覆盖对象的每个字段或明细
- `evidence` 不包含独立编号或章节路径；定位依赖 `object_id`、`element_id`、`page`、`bbox`、`text_span`

## 快速开始

### 1. 安装依赖

```powershell
pip install -r requirements.txt
```

### 2. 配置环境变量

根目录创建 `.env`：

```env
LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
LLM_API_KEY=your_api_key
LLM_MODEL=deepseek-v4-flash
EXTRACTION_CHUNK_MAX_CHARS=5000
EXTRACTION_MAX_CHARS=100000
EXTRACTION_CONCURRENCY=3
PARSER_BACKEND=basic
DOCLING_ENABLE_OCR=false
DOCLING_ENABLE_TABLE_STRUCTURE=true
DOCLING_FORCE_BACKEND_TEXT=true
```

| 配置项 | 说明 | 默认值 |
| --- | --- | --- |
| `LLM_API_KEY` | 大模型调用鉴权（回退 `DASHSCOPE_API_KEY`） | 无 |
| `LLM_BASE_URL` | OpenAI-Compatible 接口地址 | 无 |
| `LLM_MODEL` | 结构化提取模型 | `deepseek-v4-flash` |
| `UPLOAD_DIR` | 上传文件目录 | `db/uploads` |
| `DB_PATH` | SQLite 路径 | `db/db.sqlite3` |
| `EXTRACTION_CHUNK_MAX_CHARS` | IR chunk 目标大小 | `5000` |
| `EXTRACTION_MAX_CHARS` | 文档最大字符数上限 | `100000` |
| `EXTRACTION_THRESHOLD` | 触发抽取的最小字符阈值 | `6000` |
| `EXTRACTION_CONCURRENCY` | 分块并发抽取数 | `3` |
| `PARSER_BACKEND` | 解析后端，当前默认 `basic` | `basic` |
| `DOCLING_ENABLE_OCR` | Docling OCR 开关 | `false` |
| `DOCLING_ENABLE_TABLE_STRUCTURE` | Docling 表格结构识别开关 | `true` |
| `DOCLING_FORCE_BACKEND_TEXT` | Docling 优先使用 PDF 原生文本层 | `true` |
| `EXTRACTION_CHUNK_OVERLAP_CHARS` | 相邻分块重叠字符数 | `200` |
| `LLM_MAX_TOKENS` | LLM 最大输出 token 数 | `16384` |
| `PHASE0_ENABLED` | Phase 0 预扫描开关 | `false` |
| `PHASE0_MAX_SAMPLE_CHARS` | Phase 0 采样字符数上限 | `6000` |

### 3. 启动后端

```powershell
python main.py
```

服务默认运行在 `http://127.0.0.1:8001`。

## 技术栈

| 层次 | 技术 |
| --- | --- |
| 后端 | `FastAPI` + `Tortoise-ORM` + `SQLite` |
| 文档解析 | `docling`、`pymupdf4llm`、`python-docx` |
| 结构化抽取 | OpenAI-Compatible API + `Pydantic` |
| 评测 | Python 脚本 + JSON / Markdown 报告 |
| 前端 | `React 19` + `TypeScript` + `Vite` + `Tailwind CSS v4` + `shadcn/ui` + `CodeMirror` + `pdfjs-dist` + `TanStack Query` |

## 项目结构

```text
DocStruct/
├── main.py
├── core/
│   ├── parser.py
│   ├── parsers/
│   │   ├── __init__.py
│   │   └── docling_parser.py
│   ├── ir.py
│   ├── chunker.py
│   ├── extractor.py
│   ├── reducer.py
│   ├── config.py
│   ├── constants.py
│   ├── utils.py
│   ├── metadata.py
│   ├── schema_registry.py
│   ├── experiment_sdk.py
│   ├── document_service.py
│   └── llm.py
├── schemas/
│   ├── models.py
│   ├── dto.py
│   ├── constants.py
│   ├── extraction.py
│   ├── ir.py
│   └── docs/
│       ├── __init__.py
│       ├── base.py
│       ├── srs.py
│       ├── api.py
│       ├── design.py
│       ├── test.py
│       └── dbdd.py
├── scripts/
│   ├── ci_test.py
│   ├── evaluate.py
│   └── hooks/
├── tests/
│   ├── test_reducer.py
│   ├── test_extractor_prompts.py
│   ├── test_dto.py
│   ├── test_metadata.py
│   └── test_docling_parser.py
├── frontend/         (React + TypeScript + Vite)
├── experiments/      (offline evaluation)
├── static/           (example documents)
└── paper/            (thesis chapters)
```

## 核心流程

```text
文档上传
    ↓
Parser 生成 Markdown 与 Document IR
    ↓
LLM 生成 summary
    ↓
用户指定 doc_type
    ↓
构建 DocumentOutline 与 ExtractionContract
    ↓
按章节和元素边界生成 chunk
    ↓
并发 Map 抽取
    ↓
Finalize：LLM 合并分块候选（失败则降级跳过）
    ↓
Reduce 确定性合并、去重、重排全局 ID
    ↓
Evidence Binding 回填 page / bbox / text_span
    ↓
保存 extracted_data
```

`raw_text` 用于人类预览和修订，`summary` 用作分块抽取的全局背景，`document_ir` 是分块与证据绑定的机器可读来源。`summary` 不作为 evidence 来源，不会进入 `allowed_evidence_element_ids`。finalizer 只处理分块候选及其已有证据 ID，不重新读取完整 `document_ir.elements`。

## API 接口

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `POST` | `/api/upload` | 上传文件并执行结构化抽取 |
| `GET` | `/api/documents` | 获取文档列表 |
| `GET` | `/api/documents/{doc_id}` | 获取文档详情 |
| `PATCH` | `/api/documents/{doc_id}` | 人工修订 `raw_text`、`summary` 或 `extracted_data` |
| `DELETE` | `/api/documents/{doc_id}` | 删除文档记录与原始文件 |
| `GET` | `/api/documents/{doc_id}/chunks` | 返回分块调试数据 |
| `POST` | `/api/documents/{doc_id}/retry-extraction` | 重新执行结构化抽取 |
| `GET` | `/api/documents/{doc_id}/file` | 下载原始上传文件 |

上传请求要求：

- 表单字段 `file`
- 表单字段 `doc_type`

## 运行数据目录

| 路径 | 用途 |
| --- | --- |
| `db/uploads/` | 上传的原始文件 |
| `db/db.sqlite3` | 主数据库 |
| `experiments/results/` | 评测输出结果 |

当前数据库模型使用 `title`、`created_at`、`raw_text`、`summary` 等字段，不兼容旧版 `filename`、`upload_time`、`parsed_content` 表结构。开发环境如保留旧 SQLite 文件，需要重建数据库或执行单独迁移。

## 手动验证

建议至少覆盖以下场景：

1. 上传 `PDF / DOCX / MD / TXT`，确认状态从 `uploaded` / `parsing` / `extracting` 变为 `completed` 或 `failed`
2. 检查 `raw_text` 是否正常生成
3. 检查 `summary` 是否生成，并确认摘要失败不会阻断结构化抽取
4. 检查 `document_ir` 是否包含 `elements`、`outline`、`section_path`
5. 检查 `extracted_data` 是否符合五类主干对象和 `evidence`
6. 对使用 Docling 解析的 PDF，点击前端提取项，确认 PDF 跳转到对应页并高亮 bbox
7. 对 basic parser 或非 PDF 文档，确认前端仍可展示文本证据且不会错误绘制 PDF 框
8. 上传 `unknown` 类型文档，确认只保留原文和 IR
9. 上传超长文档，确认返回明确错误
10. 修改 `raw_text`、`summary` 或 `extracted_data`，确认 `PATCH` 生效
11. 删除文档后确认数据库记录与上传文件一并清理

## CI Test

```bash
uv run python scripts/ci_test.py
uv run python scripts/ci_test.py --backend-only
uv run python scripts/ci_test.py --frontend-only
```

后端检查当前包含：

- Python 编译检查
- `main.py` 导入与应用实例化检查

## 参考资料

- https://github.com/docling-project/docling
- https://github.com/IBM/docling

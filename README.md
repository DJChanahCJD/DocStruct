# DocStruct

**基于大模型的软件工程文档结构化提取系统**

> 推荐使用 `.venv` 环境。

DocStruct 当前聚焦于软件工程文档的结构化提取与离线评测。系统不包含知识库问答、向量检索、URL 导入、模型切换和前端联动能力。

## 当前能力

- 支持 `PDF`、`DOCX`、`MD`、`TXT` 文件上传
- 支持 6 类主干软件工程文档：`srs`、`api`、`design`、`test`、`manual`、`issue`
- `unknown` 类型只保留解析后的原文与 IR，不执行结构化抽取
- 解析结果同时保存 `parsed_content` 和 `document_ir`
- 抽取结果统一输出五类主干对象和证据回溯
- 前端支持 PDF 原文与结构化结果左右对照，并可点击提取项定位 Docling bbox 证据
- 提供离线评测脚本，便于论文实验复现

## 设计概要

DocStruct 不做通用 JSON 生成器，而是面向软件工程文档建立稳定抽取链路：

```text
PDF / DOCX / MD / TXT
    ↓
Parser → Document IR
    ↓
Section-aware Chunking
    ↓
Map：逐块局部抽取
    ↓
Reduce：合并、去重、全局 ID
    ↓
Evidence Binding
    ↓
Final JSON
```

核心思想：

- `Document IR` 保存标题、段落、表格、页码、bbox、章节路径和阅读顺序
- `ExtractionContract` 控制每类文档抽什么，不使用任意动态 Schema
- LLM 只负责 chunk 内局部语义抽取，Reduce 尽量使用确定性逻辑
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
| 系统设计说明书 | `design` | 模块、服务、设计产物 |
| 测试文档 | `test` | 测试流程、测试用例、测试报告 |
| 用户手册 | `manual` | 操作流程、手册章节、相关实体 |
| 问题单 / 缺陷单 | `issue` | 问题描述、复现流程、期望结果 |
| 未知类型 | `unknown` | 仅保留基础元信息、原文和 IR |

## 统一输出结构

```python
class StructuredDocument(BaseExtractedDocument):
    entities: list[EntityItem] = Field(default_factory=list)
    processes: list[ProcessItem] = Field(default_factory=list)
    requirements: list[RequirementItem] = Field(default_factory=list)
    interfaces: list[InterfaceItem] = Field(default_factory=list)
    artifacts: list[ArtifactItem] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)
```

- 主干对象保存事实：实体、流程、需求、接口、文档产物
- `id` 是系统生成的稳定对象 ID，例如 `REQ-001`；原文编号可作为 `name` 后缀保留，例如 `用户注册（SRS-USER-001）`
- SRS 的验收标准不作为独立需求输出，局部验收条目写入对应需求的 `criteria`
- `entities` 只保存产品域或架构中可独立指称的角色、模块、系统、服务、组件、数据对象，不保存需求标题
- `requirements` 不再包含 `priority`、`category` 等容易诱导模型猜测的低置信字段
- `interfaces` 和 `artifacts` 的类型字段使用简洁字符串，不再用过细枚举强制分类
- `interfaces` 中 `method` 只保存动作，`path` 只保存可定位入口，`target` 只保存目标对象，避免自然语言说明混入结构字段
- `evidence` 保存对象到 `DocumentElement` 的回溯信息
- `evidence_element_ids` 是少量定位锚点，不要求覆盖对象的每个字段或明细
- `evidence` 不包含独立编号或章节路径；定位依赖 `object_id`、`element_id`、`page`、`bbox`、`text_span`
- 不再使用 `views`、`relations`、`metrics` 顶层槽位；量化指标写入相关对象字段

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
LLM_MODEL=qwen-doc-turbo
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
| `LLM_API_KEY` | 大模型调用鉴权，也可使用 `DASHSCOPE_API_KEY` | 无 |
| `LLM_BASE_URL` | OpenAI-Compatible 接口地址 | 无 |
| `LLM_MODEL` | 结构化提取模型 | `qwen-doc-turbo` |
| `UPLOAD_DIR` | 上传文件目录 | `db/uploads` |
| `DB_PATH` | SQLite 路径 | `db/db.sqlite3` |
| `EXTRACTION_CHUNK_MAX_CHARS` | IR chunk 目标大小 | `5000` |
| `EXTRACTION_MAX_CHARS` | 文档最大字符数上限 | `100000` |
| `EXTRACTION_CONCURRENCY` | 分块并发抽取数 | `3` |
| `PARSER_BACKEND` | 解析后端，当前默认 `basic` | `basic` |
| `DOCLING_ENABLE_OCR` | Docling OCR 开关 | `false` |
| `DOCLING_ENABLE_TABLE_STRUCTURE` | Docling 表格结构识别开关 | `true` |
| `DOCLING_FORCE_BACKEND_TEXT` | Docling 优先使用 PDF 原生文本层 | `true` |

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

## 项目结构

```text
DocStruct/
├── main.py
├── core/
│   ├── parser.py
│   ├── ir.py
│   ├── chunker.py
│   ├── extractor.py
│   ├── reducer.py
│   ├── experiment_sdk.py
│   ├── document_service.py
│   └── llm.py
├── schemas/
│   ├── models.py
│   └── dto.py
└── scripts/
    ├── ci_test.py
```

## 核心流程

```text
文档上传
    ↓
Parser 生成 Markdown 与 Document IR
    ↓
用户指定 doc_type
    ↓
构建 DocumentOutline 与 ExtractionContract
    ↓
按章节和元素边界生成 chunk
    ↓
并发 Map 抽取
    ↓
Reduce 合并、去重、重排全局 ID
    ↓
Evidence Binding 回填 page / bbox / text_span
    ↓
保存 extracted_data
```

`parsed_content` 用于人类预览和修订，`document_ir` 是分块与证据绑定的机器可读来源。

## API 接口

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `POST` | `/api/upload` | 上传文件并执行结构化抽取 |
| `GET` | `/api/documents` | 获取文档列表 |
| `GET` | `/api/documents/{doc_id}` | 获取文档详情 |
| `PATCH` | `/api/documents/{doc_id}` | 人工修订 `parsed_content` 或 `extracted_data` |
| `DELETE` | `/api/documents/{doc_id}` | 删除文档记录与原始文件 |

上传请求要求：

- 表单字段 `file`
- 表单字段 `doc_type`

## 运行数据目录

| 路径 | 用途 |
| --- | --- |
| `db/uploads/` | 上传的原始文件 |
| `db/db.sqlite3` | 主数据库 |
| `experiments/results/` | 评测输出结果 |

## 手动验证

建议至少覆盖以下场景：

1. 上传 `PDF / DOCX / MD / TXT`，确认状态从 `uploaded` / `parsing` / `extracting` 变为 `completed` 或 `failed`
2. 检查 `parsed_content` 是否正常生成
3. 检查 `document_ir` 是否包含 `elements`、`outline`、`section_path`
4. 检查 `extracted_data` 是否符合五类主干对象和 `evidence`
5. 对使用 Docling 解析的 PDF，点击前端提取项，确认 PDF 跳转到对应页并高亮 bbox
6. 对 basic parser 或非 PDF 文档，确认前端仍可展示文本证据且不会错误绘制 PDF 框
7. 上传 `unknown` 类型文档，确认只保留原文和 IR
8. 上传超长文档，确认返回明确错误
9. 修改 `parsed_content` 或 `extracted_data`，确认 `PATCH` 生效
10. 删除文档后确认数据库记录与上传文件一并清理

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

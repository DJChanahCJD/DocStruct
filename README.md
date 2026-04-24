# DocStruct

**基于大模型的软件工程文档结构化提取系统**

当前版本只保留后端最小抽取内核，目标聚焦于软件工程文档的结构化提取与评测，不包含知识库问答、向量检索、URL 导入、模型切换和前端联动能力。

## 当前能力

- 支持 `PDF`、`DOCX`、`MD`、`TXT` 文件上传
- 支持 6 类主干软件工程文档的结构化抽取：`srs`、`api`、`design`、`test`、`manual`、`issue`
- `unknown` 类型仅保留解析后的原文，不执行结构化抽取
- 文档统一解析为 Markdown，再按统一知识对象 `Pydantic Schema` 输出 JSON
- 保留文档查询、详情查看、人工修订 `parsed_content` / `extracted_data`
- 提供离线评测脚本，便于论文实验复现

## 边界说明

- 系统仅面向中短文档，默认上限为 `100000` 字符
- 超过上限的文档直接拒绝处理，不再尝试兜底
- 长文档统一走固定分块抽取，不再保留串行调用和单次全量回退策略
- 当前后端只服务结构化提取主流程，知识库问答与向量库后续如需接入，应作为独立扩展模块重新设计

## 支持的文档类型

| 文档类型 | `doc_type` | 抽取能力 |
| --- | --- | --- |
| 软件需求规格说明书 | `srs` | 优先抽取角色/模块等 `entities`、业务 `processes`、各类 `requirements`、接口与关系 |
| API 接口文档 | `api` | 优先抽取 `interfaces`、`artifacts`（如 endpoint 元数据）、相关 `relations` |
| 系统设计说明书 | `design` | 优先抽取模块/服务等 `entities`、设计产物 `artifacts`、依赖 `relations` |
| 测试文档 | `test` | 优先抽取测试流程 `processes`、测试产物 `artifacts`、验证关系 `relations`、测试指标 `metrics` |
| 用户手册 | `manual` | 优先抽取操作流程 `processes`、手册章节 `artifacts`、涉及实体 `entities` |
| 问题单 / 缺陷单 | `issue` | 优先抽取问题产物 `artifacts`、复现流程 `processes`、影响关系 `relations` |
| 未知类型 | `unknown` | 仅保留基础元信息 |

## 统一输出结构

```python
class BaseExtractedDocument(BaseModel):
    doc_type: DocType
    title: str | None = None
    summary: str | None = None
    version: str | None = None
    extra: dict[str, Any] = Field(default_factory=dict)


class StructuredDocument(BaseExtractedDocument):
    entities: list[EntityItem] = Field(default_factory=list)
    processes: list[ProcessItem] = Field(default_factory=list)
    requirements: list[RequirementItem] = Field(default_factory=list)
    interfaces: list[InterfaceItem] = Field(default_factory=list)
    artifacts: list[ArtifactItem] = Field(default_factory=list)
    relations: list[RelationItem] = Field(default_factory=list)
    metrics: list[MetricItem] = Field(default_factory=list)
```

- 统一输出以“对象槽位”组织，不再按文档类型维护彼此割裂的顶层字段
- 文档类型只决定哪些槽位更常见、哪些轻量特化字段可启用，例如 `ApiDocument.base_url`、`TestDocument.test_stage`
- 当前设计优先服务稳定抽取与跨文档融合，不追求完整重建原文章节结构

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
EXTRACTION_THRESHOLD=6000
EXTRACTION_CHUNK_MAX_CHARS=5000
EXTRACTION_CHUNK_OVERLAP_CHARS=200
EXTRACTION_MAX_CHARS=100000
EXTRACTION_CONCURRENCY=5
```

说明：

| 配置项 | 说明 | 默认值 |
| --- | --- | --- |
| `LLM_API_KEY` | 大模型调用鉴权 | 无 |
| `LLM_BASE_URL` | OpenAI-Compatible 接口地址 | 无 |
| `LLM_MODEL` | 固定使用的结构化提取模型 | `qwen-doc-turbo` |
| `UPLOAD_DIR` | 上传文件目录 | `db/uploads` |
| `DB_PATH` | SQLite 路径 | `db/db.sqlite3` |
| `EXTRACTION_THRESHOLD` | 超过该长度后进入分块抽取 | `6000` |
| `EXTRACTION_CHUNK_MAX_CHARS` | 固定分块大小 | `5000` |
| `EXTRACTION_CHUNK_OVERLAP_CHARS` | 分块重叠字符数 | `200` |
| `EXTRACTION_MAX_CHARS` | 文档最大字符数上限 | `100000` |
| `EXTRACTION_CONCURRENCY` | 分块并发抽取数 | `5` |

### 3. 启动后端

```powershell
python main.py
```

服务默认运行在 `http://127.0.0.1:8001`

## 技术栈

| 层次 | 技术 |
| --- | --- |
| 后端 | `FastAPI` + `Tortoise-ORM` + `SQLite` |
| 文档解析 | `pymupdf4llm`、`python-docx` |
| 结构化抽取 | OpenAI-Compatible API + `Pydantic` |
| 评测 | Python 脚本 + JSON / Markdown 报告 |

## 项目结构

```text
DocStruct/
├── main.py
├── core/
│   ├── parser.py
│   ├── extractor.py
│   ├── experiment_sdk.py
│   ├── chunker.py
│   ├── llm.py
│   ├── document_service.py
│   ├── constants.py
│   ├── schema_registry.py
│   └── utils.py
├── schemas/
│   ├── models.py
│   └── dto.py
├── experiments/
│   ├── datasets/
│   ├── configs/
│   ├── prompts/
│   └── results/
├── scripts/
│   ├── ci_test.py
│   └── run_eval.py
└── db/
```

## 核心流程

```text
文档上传
    ↓
Parser（PDF / DOCX / MD / TXT → Markdown）
    ↓
用户指定 doc_type
    ↓
Extractor（短文档单次抽取 / 长文档固定分块并发抽取）
    ↓
Pydantic 校验
    ↓
文档查询与人工修订
```

### 抽取策略

- 短文档：单次抽取
- 长文档：固定大小分块 + 并发 LLM 调用 + 合并校验
- 超长文档：直接拒绝

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

1. 上传 `PDF / DOCX / MD / TXT`，确认状态从 `processing` 变为 `completed` 或 `failed`
2. 检查 `parsed_content` 是否正常生成
3. 检查 `extracted_data` 是否符合统一主干槽位和指定 `doc_type`
4. 上传 `unknown` 类型文档，确认只保留原文不执行结构化抽取
5. 上传超长文档，确认返回明确错误
6. 修改 `parsed_content` 或 `extracted_data`，确认 `PATCH` 生效
7. 删除文档后确认数据库记录与上传文件一并清理

## CI Test

```bash
uv run python scripts/ci_test.py
uv run python scripts/ci_test.py --backend-only
uv run python scripts/ci_test.py --frontend-only
```

后端检查当前包含：

- Python 编译检查
- `main.py` 导入与应用实例化检查

## 离线评测

```powershell
python scripts/run_eval.py --experiment exp1
python scripts/run_eval.py --experiment exp2
python scripts/run_eval.py --experiment exp3
```

评测结果输出到 `experiments/results/`，记录实验配置、样本 ID、文档类型、Prompt 变体、成功率、耗时、完整率与字段级分数等指标。
具体实验说明见 [experiments/README.md](/C:/Users/DJCHAN/SE/1_CourseProject/DocStruct/experiments/README.md)。

## TODO

### High Priority

- [x] 重构精简系统
- [x] 移除 `source_type`、`source_url`、`llm_model`
- [x] 明确系统仅针对中短文档
- [x] 固定长文档分块提取方案
- [x] 异步 LLM 调用优化

### Medium Priority

- [ ] 引入 `pydantic-to-typescript`，方便前后端类型共享
- [ ] 继续完善统一对象模型与跨文档关系抽取质量
- [ ] 引入更真实的软件工程文档样本集
- [ ] 设计原文与 JSON 的对照修订能力
- [ ] 评估容器化部署方案
- [ ] 设计 JSON 节点到原文位置的映射机制

### Low Priority

- [ ] 格式化导出渠道（JSON / MD / CSV / YAML）
- [ ] 多语言支持扩展
- [ ] 轻量文档管理能力

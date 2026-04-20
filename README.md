# DocStruct

**基于大模型的软件工程文档内容结构化提取系统**

将非结构化软件工程文档（PDF / DOCX / MD / TXT / URL）自动转化为可存储、可检索、可问答的结构化数据。

---

## 功能特性

- **多格式输入**：支持 PDF、DOCX、MD、TXT 上传，以及公开 URL 抓取
- **6 类核心文档支持**：自动识别主干软件工程文档类型，按最小必要结构输出 JSON
- **长文档处理**：分块抽取 + 结果合并 + 三段降级容错机制
- **语义分块**：识别标题、段落、列表、表格、代码块，生成适合向量化的语义片段
- **RAG 知识问答**：FAISS 向量召回 + LLM 生成答案，返回带引用证据的回答
- **React 前端**：三栏布局（文档列表 / 问答区 / 原文预览），支持文档管理、结构化结果浏览、引用回溯
- **离线评测**：可复现的实验脚本，支持模型与 Prompt 多维对比

---

## 支持的文档类型

| 文档类型 | `doc_type` | 抽取能力 |
| --- | --- | --- |
| 软件需求规格说明书 | `srs` | 需求项列表 |
| API 接口文档 | `api` | 接口方法、路径、请求/响应摘要 |
| 系统设计说明书 | `design` | 架构摘要、模块列表 |
| 测试文档 | `test` | 测试项、步骤、预期/实际、状态 |
| 用户手册 | `manual` | 章节列表 |
| 问题单 / 缺陷单 | `issue` | 问题编号、状态、严重级别、复现步骤、期望/实际结果 |
| 未知类型 | `unknown` | 仅保留基础元信息 |

---

## 一、优化原则

1. 统一公共头，减少重复  
   所有文档统一保留 `doc_type`、`title`、`summary`、`version`、`items`、`extra` 这组公共字段。
2. 每类只保留最能代表文档价值的字段  
   SRS 关注需求项，API 关注接口，Design 关注模块，Test 关注测试项，Manual 关注章节，Issue 关注问题核心信息。
3. 非核心信息全部进入 `extra`  
   `environment`、`workaround`、`resources`、`strategy`、`database_design` 等增强字段不作为第一阶段核心结构。
4. 文档类型先收敛到主干工程场景  
   第一阶段仅保留 `srs`、`api`、`design`、`test`、`manual`、`issue`、`unknown` 七类。

## 二、统一输出结构

```python
class BaseExtractedDocument(BaseModel):
    doc_type: DocType
    title: str | None = None
    summary: str | None = None
    version: str | None = None
    extra: dict[str, Any] = Field(default_factory=dict)
```

- 大多数文类通过 `items` 承载核心条目列表。
- `issue` 保留顶层核心字段：`issue_id`、`status`、`severity`、`steps`、`expected`、`actual`。
- 该设计不追求重建完整原文，而是服务于稳定抽取、统一评测和低成本扩展。

## 快速开始

### 1. 安装依赖

```powershell
pip install -r requirements.txt
```

#### OCR 依赖（用于图片型 PDF）

系统默认会自动检测图片型 PDF 并启用 OCR。如需此功能，需安装 Tesseract：

**Windows**
1. 下载安装包：https://github.com/UB-Mannheim/tesseract/wiki
   - 推荐：`tesseract-ocr-w64-setup-5.5.0.20241111.exe`
2. 安装需要的语言包（如简体中文等）
3. 添加 Tesseract 到环境变量 PATH
4. 环境变量配置（如果 Tesseract 不在 PATH）：
TESSDATA_PREFIX=C:\Program Files\Tesseract-OCR\tessdata

**macOS**
```bash
brew install tesseract tesseract-lang
```

**Linux (Ubuntu/Debian)**
```bash
sudo apt-get install tesseract-ocr tesseract-ocr-chi-sim
```

> [!NOTE]
> 如不需要处理图片型 PDF，可跳过此步骤。纯文本 PDF 不受影响。

### 2. 配置环境变量

在根目录创建 `.env`：

```env
LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
LLM_API_KEY=your_api_key
LLM_MODEL=qwen-doc-turbo
EMBEDDING_MODEL=text-embedding-v4
```

> [!TIP]
> 若你的环境已经统一使用阿里云百炼命名，也可以只配置 `DASHSCOPE_API_KEY`；代码会自动回退读取该变量。


### 3. 启动后端

```powershell
python main.py
```

服务默认运行在 `http://127.0.0.1:8001`

### 4. 启动前端（开发模式）

```powershell
cd frontend
npm install
npm run dev
```

前端开发服务器默认运行在 `http://localhost:5173`，在生产使用中后端直接提供静态资源服务（`/` 路由）。

---

## 环境变量说明

| 配置项 | 说明 | 默认值 |
| --- | --- | --- |
| `LLM_API_KEY` | 大模型与 embedding 调用鉴权 | 无（必填） |
| `LLM_BASE_URL` | OpenAI-Compatible 接口地址 | 无（必填） |
| `LLM_MODEL` | 文类识别、抽取、问答所用模型 | `qwen2.5-7b-instruct-1m` |
| `EMBEDDING_MODEL` | 向量化模型 | `text-embedding-v4` |
| `LLM_EMBED_MODEL` | embedding 备用配置项 | 仅在 `EMBEDDING_MODEL` 缺失时生效 |

> [!NOTE]
> `EMBEDDING_MODEL` 优先级高于 `LLM_EMBED_MODEL`，建议显式配置避免模型不匹配。

---

## 技术栈

| 层次 | 技术 |
| --- | --- |
| 后端 | `FastAPI` + `Tortoise-ORM` + `SQLite` |
| 文档解析 | `pymupdf4llm`（PDF，含 OCR）、`python-docx`（DOCX）、原生读取（MD / TXT）|
| 结构化抽取 | OpenAI-Compatible API + `Pydantic` Schema 约束 |
| 向量检索 | `FAISS` + `NumPy` |
| 前端 | `React` + `TypeScript` + `Vite` + `shadcn/ui` |

---

## 项目结构

```text
DocStruct/
├── main.py                  # FastAPI 入口，路由、上传、编排与 ORM 注册
├── core/
│   ├── parser.py            # 文档解析器工厂，统一处理 PDF / DOCX / MD / TXT / URL
│   ├── extractor.py         # 文类识别与结构化抽取（含分块抽取与回退策略）
│   ├── chunker.py           # Markdown 语义分块
│   ├── retrieval.py         # 向量化、FAISS 索引、检索与问答
│   ├── constants.py         # Prompt 与常量
│   └── utils.py             # JSON 清洗、结果合并等辅助逻辑
├── schemas/
│   └── models.py            # DocType 枚举、ORM 模型、Pydantic 模型、API 契约
├── frontend/
│   └── src/
│       ├── App.tsx           # 三栏布局：文档侧边栏 + 问答区 + 预览面板
│       └── components/       # DocSidebar、QaPanel、DocPreviewPanel 等
├── static/
│   └── examples/            # 手动验证样例文档
├── experiments/
│   ├── datasets/            # 评测清单 baseline_manifest.json
│   └── results/             # 评测脚本输出（JSON + Markdown 报告）
├── scripts/
│   └── run_eval.py          # 离线评测脚本
├── db/                      # 运行数据（上传文件、SQLite、FAISS 索引，不纳入版本控制）
└── requirements.txt
```

---

## 核心流程

```
文档上传 / URL 导入
    ↓
Parser（PDF / DOCX / MD / TXT / HTML → Markdown）
    ↓
Extractor（文类识别 → 结构化抽取 → Pydantic 校验）
    ↓
Chunker（语义分块）+ Retrieval（向量化 → FAISS 索引）
    ↓
QA（向量召回 → LLM 生成答案 + 引用片段）
```

### 抽取策略

- 短文档（< 6000 字符）：单次抽取
- 长文档：分块抽取（块大小 5000 / 重叠 200）→ 结果合并校验 → 失败回退为单次抽取（截断至 30000 字符）

### 关键阈值

| 参数 | 当前值 | 位置 |
| --- | --- | --- |
| 长文档阈值 | 6000 字符 | `core/extractor.py` |
| 分块目标大小 | 700 字符 | `core/chunker.py` |
| 分块重叠 | 80 字符 | `core/chunker.py` |
| embedding 批大小 | 32 | `core/retrieval.py` |
| 抽取温度 | 0.0 | `core/extractor.py` |
| 问答温度 | 0.1 | `core/retrieval.py` |

---

## API 接口

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `GET` | `/` | 前端主页 |
| `POST` | `/api/upload` | 上传文件（PDF / DOCX / MD / TXT） |
| `POST` | `/api/upload-url` | 导入公开静态网页 URL |
| `GET` | `/api/documents` | 获取全部文档列表 |
| `GET` | `/api/documents/{doc_id}` | 获取文档详情（解析内容 + 结构化数据） |
| `DELETE` | `/api/documents/{doc_id}` | 删除文档记录与上传文件 |
| `POST` | `/api/reindex/{doc_id}` | 为指定文档重建向量索引 |
| `POST` | `/api/qa` | 向量召回 + LLM 问答 |

问答请求示例：

```json
{
  "question": "系统支持哪些上传格式？",
  "doc_id": 1,
  "top_k": 5
}
```

---

## 运行数据目录

| 路径 | 用途 |
| --- | --- |
| `db/uploads/` | 上传的原始文件 |
| `db/db.sqlite3` | 主数据库 |
| `db/vector/faiss.index` | FAISS 索引文件 |
| `db/vector/faiss_ids.json` | 索引与 chunk ID 映射 |
| `static/examples/` | 手动验证样例文档 |

> [!WARNING]
> `db/` 目录仅存放运行数据，不纳入版本控制。首次运行会自动创建。

---

## 手动验证

当前提供基础契约测试，同时仍推荐结合 `static/examples/` 做手动验证，至少覆盖：

1. 在顶栏切换不同文本模型后，上传新文档并确认状态从 `processing` 转为 `completed` 或 `failed`
2. 检查 `parsed_content` 是否生成
3. 检查 `extracted_data` 是否符合对应文类结构
4. 检查新文档的 `llm_model` 是否保存为当前选择的模型
5. 执行重建索引，确认正常返回
6. 对当前文档或全库发起问答，检查答案、引用片段与模型切换是否生效
7. 检查 `db/` 下 SQLite / 向量索引是否正常生成
8. 对 URL 导入文档，检查 `source_type`、`source_url` 与 `llm_model` 是否正确保存


---

## 离线评测

```powershell
# 使用默认基线清单
python scripts/run_eval.py

# 指定参数
python scripts/run_eval.py --prompt-version baseline-v2 --extraction-model-source predicted
```

评测结果输出到 `experiments/results/`，包含结构化 JSON 和 Markdown 报告，记录：样本 ID、期望 / 预测文类、抽取成功率、耗时、结构完整率等。

---

## Roadmap

| 阶段 | 目标 | 状态 |
| --- | --- | --- |
| Phase 0 | 基线收敛：文档、配置、接口与实现对齐 | ✅ 完成 |
| Phase 1 | 评测体系：建立可复现实验基线与评测脚本 | ✅ 完成 |
| Phase 2 | 稳定性优化：长文档成功率提升、异步化改造 | 🚧 进行中 |
| Phase 3 | 输入扩展：URL 导入与主干文类收敛 | ✅ 完成 |
| Phase 4 | 前端与检索增强：React 应用、结构化浏览、关系视图 | 🚧 进行中 |

---

## TODO

### 高优先级

- [ ] 明确该系统仅针对中短文档，10w字符以上的长文档不适合。

- [ ] 重构精简系统（Qwen-Doc-Turbo 纯文本仅 9K 输入 ，且肯定有注意力问题，还是要做分块抽取（但能否分块文档内容 + 大致上下文？）），是否对不同模型定制分块大小
1. 长文档处理慢：分块+串行调用导致耗时高，且合并块时存在信息丢失风险
2. 文档提取字段混乱且不够细化，暂时无法覆盖大多数工程场景
3. ✅ ~~图片型 PDF 文档暂时无法处理，需要引入 OCR~~（已支持，基于 Tesseract 自动检测）
4. 缺乏真实软件工程文档

- [ ] 期望能够参考immersive translate，对照修改原文、json。需要保留上传文档
- [ ] 评估当前方案能够容器化部署到云端？
- [ ] **异步化 LLM 调用**：将文类识别、结构化抽取、embedding 生成、索引构建改为异步，提升长文档处理性能与并发能力
- [ ] **配置集中化**：将散落在 `extractor.py` / `retrieval.py` / `chunker.py` 中的阈值与默认值抽离为统一配置模块
- [ ] **评测数据集扩充**：为每类文档补充长文档 / 结构混乱文档样本，支撑论文模型与 Prompt 对比实验

### 中优先级

- [ ] 有没有可能点击json特定区域，能够跳转到原文具体文档位置？
- [ ] **前端关系视图**：在 React 应用中增加需求项浏览、API 列表、测试结果汇总等结构化展示面板
- [ ] **检索质量优化**：降低重复引用，提升片段相关性，优化多文档检索排序
- [ ] **更多输入格式**：图片（OCR）、HTML、XML 等格式按需接入

### 低优先级

- [ ] 格式化导出渠道（JSON / MD / CSV / YAML）
- [ ] 多语言支持扩展
- [ ] 简易管理系统？ UUID

## 其他

### 可用数据集与参考文档
1. https://zenodo.org/records/10976097
2. SRS PDF： https://zenodo.org/records/7897601
3. https://github.com/yawar2518/Online-Examination-System-Software-Requirments-Specification-Document
3. https://www.pdfsdownload.com/download-pdf-for-free/srs-document
2. 韩文 http://dslab.konkuk.ac.kr/Class/2025/25GP/Projects/project1/srs2.pdf
3. API文档：https://apis.guru/
4. 测试报告参考: https://support.functionize.com/hc/en-us/articles/33002630144535-Test-Reports
5. bug数据集： https://github.com/rjust/defects4j

### 需求分类基础
软件需求分为两大类：
- **功能需求（FR）**：系统需实现的具体功能
- **非功能需求（NFR）**：性能、安全、易用性等质量属性

### 核心研究内容
1. **大模型对比实验**
    - 统一文档与 Prompt 环境，对比不同模型表现
    - 筛选当前场景下**性价比最优**的模型
2. **Prompt 工程优化**
    - 对比中英文 Prompt 效果
    - 对比简洁型与详细型 Prompt 效果

### 技术方案：大模型语义级信息抽取
#### 传统抽取方法
- 关键词匹配
- 正则表达式规则
- 常规 NLP 模型

#### 大模型优势
- 理解需求语义
- 自动完成需求分类
- 抽取复杂结构化信息

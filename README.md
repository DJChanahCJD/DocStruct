## DocStruct

DocStruct 是一个面向软件工程文档的结构化提取系统。项目目标是将非结构化文档转换为可存储、可检索、可问答的结构化数据，支持论文实验与工程演示两类场景。

当前项目已经完成 MVP 闭环，主链路为：

`文档上传 -> 文本解析 -> 文类识别 -> 结构化抽取 -> 向量索引 -> 检索问答`

## 当前支持能力

### 支持输入格式

- `PDF`
- `DOCX`
- `MD`
- `TXT`

### 支持文档类型

当前已支持 7 类软件工程文档：

| 文档类型 | `doc_type` | 当前能力 |
| --- | --- | --- |
| 软件需求规格说明书 | `srs` | 提取需求项、优先级、标题等结构 |
| API 接口文档 | `api` | 提取接口方法、路径、摘要、描述 |
| 系统设计说明书 | `design` | 提取架构摘要、模块信息、数据库设计 |
| 测试计划 | `test_plan` | 提取范围、资源、进度、策略、交付物 |
| 测试用例 | `test_case` | 提取测试用例标题、步骤、预期结果等 |
| 测试报告 | `test_report` | 提取执行摘要、统计信息、用例结果 |
| 用户手册 | `user_manual` | 提取章节内容与故障排除信息 |

### 当前前端能力

前端为单页 `static/index.html`，已支持：

- 文档上传
- 文档列表查看
- 文档删除
- 指定文档重建索引
- 全库或单文档问答
- 引用片段查看
- 原文与结构化 JSON 浏览

## 技术栈

- 后端：`FastAPI`
- ORM：`Tortoise-ORM + SQLite`
- 文档解析：
  - `pymupdf4llm` 解析 PDF
  - `python-docx` 解析 DOCX
  - 原生文本读取处理 `MD / TXT`
- 大模型调用：`OpenAI-Compatible API`
- 抽取约束：`Pydantic`
- 向量检索：`NumPy + FAISS`
- 前端：单页 `Vue 3 + Tailwind CSS`

说明：

- 当前 `core/extractor.py` 虽然保留了 `instructor` 依赖初始化，但主抽取过程实际通过 OpenAI Compatible 接口返回 JSON，再由 Pydantic 做校验。
- 当前主方案是“解析器 + Schema 约束抽取”，不是“模型原生直读文件”方案。

## 环境变量

推荐配置如下：

```env
LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
LLM_API_KEY=your_api_key
LLM_MODEL=qwen-doc-turbo
EMBEDDING_MODEL=text-embedding-v4
```

补充说明：

- `LLM_MODEL` 用于分类、抽取和问答。
- `EMBEDDING_MODEL` 用于向量索引与检索。
- 若未显式设置 `EMBEDDING_MODEL`，当前代码会回退到默认值，但建议显式配置，避免模型不匹配导致错误。

## 项目结构

```text
DocStruct/
├── main.py                 # FastAPI 入口，负责路由、上传、编排与 ORM 注册
├── core/
│   ├── parser.py           # 文档解析器工厂，统一处理 PDF / DOCX / MD / TXT
│   ├── extractor.py        # 文类识别与结构化抽取
│   ├── chunker.py          # Markdown 语义分块
│   ├── retrieval.py        # 向量化、FAISS 索引、检索与问答
│   ├── constants.py        # Prompt 与常量
│   └── utils.py            # JSON 清洗、结果合并等辅助逻辑
├── schemas/
│   └── models.py           # Pydantic 模型、ORM 模型、DocType 定义
├── static/
│   ├── index.html          # 单页前端
│   └── examples/           # 手动验证样例
├── db/                     # 运行数据目录，包含上传文件、SQLite、向量索引
├── SUMMARY.md              # 中期汇报与阶段 TODO
├── PLAN.md                 # 后续开发总计划
└── requirements.txt        # 依赖清单
```

## 核心流程

### 1. 上传与解析

- `POST /api/upload` 接收文件上传。
- 根据扩展名选择解析器。
- 输出统一 Markdown 文本，作为后续分类与抽取输入。

### 2. 文类识别

- 使用文档前部摘要进行快速分类。
- 输出 `DocClassification`，包含：
  - `doc_type`
  - `confidence`
  - `reasoning`

### 3. 结构化抽取

- 按识别结果匹配对应 Pydantic 模型。
- 短文档走单次抽取。
- 长文档走分块抽取、结果合并、失败回退。
- 最终结果统一通过 Pydantic 校验。

### 4. 存储与索引

- 文档元数据、解析结果、抽取 JSON 存入 `document_records`。
- 分块结果与向量存入 `chunk_records`。
- 完成后重建或更新 FAISS 索引。

### 5. 问答

- `/api/qa` 先做向量召回。
- 再将命中的上下文片段送入模型生成答案。
- 返回答案与引用片段，支持证据回溯。

## 当前接口

### 页面入口

- `GET /`

返回前端主页。

### 文档上传

- `POST /api/upload`

上传并处理文档，返回文档 ID、状态与识别结果。

### 文档列表

- `GET /api/documents`

返回全部文档记录。

### 文档详情

- `GET /api/documents/{doc_id}`

返回指定文档的解析内容、结构化数据和状态信息。

### 删除文档

- `DELETE /api/documents/{doc_id}`

删除指定记录，并尝试删除对应上传文件。

### 重建索引

- `POST /api/reindex/{doc_id}`

为指定文档重新生成向量索引。

### 问答

- `POST /api/qa`

示例请求：

```json
{
  "question": "系统支持哪些上传格式？",
  "doc_id": 1,
  "top_k": 5
}
```

## 安装与运行

### 1. 安装依赖

```powershell
pip install -r requirements.txt
```

### 2. 配置环境变量

在根目录创建 `.env`，至少包含：

```env
LLM_BASE_URL=...
LLM_API_KEY=...
LLM_MODEL=...
EMBEDDING_MODEL=...
```

### 3. 启动服务

```powershell
python main.py
```

默认启动在：

`http://127.0.0.1:8001`

## 手动验证

当前无自动化测试，必须手动验证。

推荐使用 `static/examples/` 中样例文件，至少覆盖以下检查：

1. 上传文档后，确认状态从 `processing` 正常转为 `completed` 或 `failed`。
2. 打开文档详情，检查 `parsed_content` 是否生成。
3. 检查 `extracted_data` 是否符合目标文类结构。
4. 执行一次 `重建索引`，确认接口正常返回。
5. 对当前文档或全库发起问答，检查答案与引用片段是否一致。
6. 检查日志与 `db/` 下 SQLite / 向量索引是否正常生成。

## 已知现状与后续方向

- 当前项目以轻量单体为主，不做复杂服务拆分。
- 当前重点问题是：
  - README 与实现对齐
  - 长文档稳定性
  - 模型与 Prompt 评测体系
  - URL 输入与新增文类扩展
- 后续开发总路线见根目录 [PLAN.md](C:\Users\DJCHAN\SE\1_CourseProject\DocStruct\PLAN.md)。

## 📝 本科生毕业设计项目文档：DocStruct

### 1. 项目定位

本系统是一个基于大语言模型（LLM）的**软件工程文档结构化提取系统**。旨在将非结构化的 PDF/DOCX/Markdown 文档转化为标准化的 JSON 结构，覆盖软件工程全生命周期。

### 2. 核心功能与支持

| 文档类型              | 状态    | 描述                |
| :---------------- | :---- | :---------------- |
| **软件需求规格 (SRS)**  | ✅ 已支持 | 提取功能需求、非功能需求、优先级  |
| **API 接口文档**      | ✅ 已支持 | 提取接口路径、方法、参数、响应   |
| **测试报告**          | ✅ 已支持 | 提取测试用例、执行结果、统计数据  |
| **系统设计说明书 (SDD)** | ✅ 已支持 | 提取架构设计、模块划分、数据库设计 |
| **用户手册**          | ✅ 已支持 | 提取操作指南、故障排除步骤     |

### 3. 技术栈 (Technical Stack)

- **后端**: FastAPI (Web 路由与静态托管) 。
- **解析**: Marker-PDF (将 PDF 转换为高质量 Markdown，保留表格结构)。
- **提取**: Instructor (基于 Pydantic 模型的强约束 LLM 提取) 。
- **模型**: Pydantic (定义字段、校验数据与 JSON 生成) 。
- **持久化**: SQLite + Tortoise-ORM (轻量级异步 ORM，零配置存储)。
- **检索问答**: NumPy + FAISS (向量索引) + OpenAI-Compatible Embedding + RAG 问答。
- **前端**: 单页 `index.html` (原生 JS Fetch + Tailwind CSS 极简展示)。

### 3.1 环境变量（DashScope/OpenAI-Compatible）

```env
LLM_PROVIDER=openai_compatible
LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
LLM_API_KEY=你的 Key
LLM_MODEL=qwen-doc-turbo
EMBEDDING_MODEL=text-embedding-v4
```

说明：
- `EMBEDDING_MODEL` 建议显式设置为 `text-embedding-v4`，避免出现 `text-embedding-3-small` 的 `404 model_not_found`。

### 4. 项目结构 (Project Structure)

```text
DocStruct/
├── main.py            # FastAPI 入口，集成 Tortoise-ORM 与静态文件挂载
├── core/
|   ├── prompts.py     # 定义 LLM 不同文档的格式化提示模板
│   ├── parser.py      # Marker 封装：PDF -> Markdown
│   └── extractor.py   # Instructor 封装：Markdown -> Pydantic Model
├── schemas/
│   └── models.py      # 数据模型：包含 Pydantic Schema 与 Tortoise ORM Model 
├── static/
│   └── index.html     # 极简前端上传与 JSON 展示页面 
├── db.sqlite3         # 运行时自动生成的数据库文件
└── requirements.txt   # 核心依赖清单
└── .env               # 环境变量配置文件（包含 LLM_PROVIDER、LLM_BASE_URL、LLM_MODEL、LLM_API_KEY） openai_compatible

```

### 5. 核心逻辑流程 (Pipeline)

1. **解析层**: 采用“Markdown 优先”策略。利用 Marker 还原 PDF 中的层级、标题与表格，为 LLM 提供语义清晰的输入。
2. **提取层**: 使用 `instructor.patch(client)`。定义 `SrsDocument`, `ApiDocument`, `TestReportDocument` 等 Pydantic 类 。
3. **持久化层**: 提取成功的 JSON 数据连同元数据（文件名、时间）存入 `document_records` 表。
4. **向量层**: 将解析文本切块后做 embedding，写入 `chunk_records` 并重建 FAISS 索引。
5. **问答层**: `/api/qa` 先向量召回，再把片段上下文送入 LLM 生成答案与引用。
6. **校验层**: 利用 Pydantic 的 `ValidationError` 捕获异常 。
5. 核心 Pydantic 约束示例

```python
class RequirementItem(BaseModel):
    id: str = Field(min_length=1)
    description: str = Field(min_length=1)
    priority: Literal["low", "medium", "high"] = "medium"

class SrsDocument(BaseModel):
    doc_type: Literal["srs"] = "srs"
    title: str
    requirements: list[RequirementItem]

```

### 6. 检索问答接口

- `POST /api/reindex/{doc_id}`：重建指定文档向量索引。
- `POST /api/qa`：基于向量召回做问答。

示例请求：

```json
{
  "question": "系统支持哪些上传格式？",
  "doc_id": 1,
  "top_k": 5
}
```


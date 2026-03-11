## 📝 项目文档：DocStruct

### 1. 项目定位

本系统是一个基于大语言模型（LLM）的**软件工程文档结构化提取系统**。旨在将非结构化的 PDF 文档（SRS、API、测试报告）通过 OCR 和 LLM 转化为标准化的 JSON 结构 。

### 2. 技术栈 (Technical Stack)

* **后端**: FastAPI (Web 路由与静态托管) 。


* **解析**: Marker-PDF (将 PDF 转换为高质量 Markdown，保留表格结构)。
* **提取**: Instructor (基于 Pydantic 模型的强约束 LLM 提取) 。
* **模型**: Pydantic (定义字段、校验数据与 JSON 生成) 。
* **持久化**: SQLite + Tortoise-ORM (轻量级异步 ORM，零配置存储)。
* **前端**: 单页 `index.html` (原生 JS Fetch + Tailwind CSS 极简展示)。

### 3. 项目结构 (Project Structure)

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

### 4. 核心逻辑流程

1. **解析层**: 采用“Markdown 优先”策略。利用 Marker 还原 PDF 中的层级、标题与表格，为 LLM 提供语义清晰的输入。
2. **提取层**: 使用 `instructor.patch(client)`。定义 `SrsDocument`, `ApiDocument`, `TestReportDocument` 等 Pydantic 类 。
3. **持久化层**: 提取成功的 JSON 数据连同元数据（文件名、时间）存入 `document_records` 表。
4. **校验层**: 利用 Pydantic 的 `ValidationError` 捕获异常 。



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
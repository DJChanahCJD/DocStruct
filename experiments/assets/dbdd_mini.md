# DocStruct 数据库设计

## 数据库信息

- 数据库名称：docstruct
- 数据库类型：SQLite（开发）/ PostgreSQL（生产）

## 表结构

### document — 文件记录表

存储文档的解析内容、结构化抽取结果和处理状态，是系统的核心数据表。

| 字段名 | 类型 | 主键 | 可为空 | 默认值 | 说明 |
|--------|------|------|--------|--------|------|
| id | IntField | 是 | 否 | 自增 | 自增主键 |
| title | CharField(255) | 否 | 否 | — | 文档标题，默认取文件名 |
| stored_path | CharField(512) | 否 | 否 | — | 文件存储路径 |
| created_at | DatetimeField | 否 | 否 | auto_now_add | 创建时间 |
| updated_at | DatetimeField | 否 | 是 | — | 最后修改时间 |
| doc_type | CharField(50) | 否 | 否 | UNKNOWN | 文档类型，可选值：srs/api/design/test_case/dbdd |
| raw_text | TextField | 否 | 是 | — | 解析后的原始文本 / Markdown 内容 |
| summary | TextField | 否 | 是 | — | 文档摘要，默认从原始文本中提取 |
| document_ir | JSONField | 否 | 是 | — | 文档元素 IR，用于分块与证据回溯 |
| extracted_data | JSONField | 否 | 是 | — | 结构化抽取结果 |
| extraction_meta | JSONField | 否 | 是 | — | 抽取元信息：模型名、置信度、分块统计等 |
| status | CharField(20) | 否 | 否 | PENDING | 处理状态：PENDING/PROCESSING/COMPLETED/FAILED |
| error_message | TextField | 否 | 是 | — | 失败原因，仅在 status=FAILED 时有值 |

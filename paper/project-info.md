# DocStruct 项目参考信息

> 本文档记录项目的基本架构、技术栈和数据流，供论文撰写参考。
> 最后更新：2026-05-01

## 1. 项目概述

DocStruct（Document Structure Extractor）是基于大语言模型的软件工程文档结构化提取系统。将 PDF/DOCX/MD/TXT 格式的软件工程文档自动解析并提取为带证据绑定的结构化 JSON。

- **定位**：单文档级结构化抽取（不含跨文档知识图谱）
- **语言**：后端 Python 3.11+，前端 TypeScript/React
- **许可**：学术研究项目（华南理工大学本科毕业设计）

## 2. 五层架构

| 层次 | 技术 | 说明 |
|------|------|------|
| 存储层 | SQLite (aiosqlite)、文件系统 (db/) | 单文件部署 |
| 数据层 | Pydantic v2、Schema Registry、Tortoise ORM | 类型校验 + 动态槽位发现 |
| 核心管道层 | Parser → IR Builder → Chunker → Extractor → Reducer → Evidence Binder | Map-Reduce 范式 |
| API 服务层 | FastAPI、Uvicorn | 8 个 RESTful 端点 |
| 表示层 | React 19 + TypeScript + Vite + Tailwind CSS + shadcn/ui | 单页应用 |

## 3. 支持的文档类型

| 代码 | 全称 | 核心对象槽位 | 关键文件 |
|------|------|------------|---------|
| `srs` | 需求规格说明书 | functional_requirements, non_functional_requirements, business_flows | `schemas/docs/srs.py` |
| `api` | 接口文档 | apis | `schemas/docs/api.py` |
| `hld` | 概要设计文档 | modules, core_flows, design_decisions | `schemas/docs/design.py` |
| `tc` | 测试用例文档 | test_cases | `schemas/docs/test.py` |
| `dbdd` | 数据库设计文档 | tables | `schemas/docs/dbdd.py` |
| `unknown` | 未知类型 | 仅解析，不提取 | — |

## 4. Map-Reduce 处理管道

```
上传 → 解析 → Document IR → 分块 → Map(并发LLM) → Finalizer(可选) → Reduce → 校验 → 入库
```

- **解析**：ParserFactory 按扩展名选择解析器（PdfParser/DocxParser/PlainTextParser）
- **IR**：`parse_result_to_ir()` 构建 DocumentIR（元素 + 大纲 + 元数据）
- **分块**：`split_ir_into_chunks()` 按章节边界分块，默认 5000 字符/块，200 字符重叠
- **Map**：`asyncio.Semaphore(3)` 控制并发，每个分块独立 LLM 调用
- **Reduce**：`reduce_extraction_results()` 确定性合并去重 + 全局 ID 分配
- **证据绑定**：element_id → page/bbox/text_span 解析

## 5. API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/upload` | 上传文件 + 指定 doc_type，触发后台处理 |
| GET | `/api/documents` | 文档列表（按 ID 降序） |
| GET | `/api/documents/{id}` | 文档详情 |
| PATCH | `/api/documents/{id}` | 修订 raw_text / extracted_data |
| DELETE | `/api/documents/{id}` | 删除记录 + 文件 |
| GET | `/api/documents/{id}/chunks` | 分块调试数据 |
| POST | `/api/documents/{id}/retry-extraction` | 重新提取 |
| GET | `/api/documents/{id}/file` | 下载原始文件 |

## 6. 关键技术决策

1. **LLM 处理局部语义，确定性算法处理全局协调** — Map 阶段用 LLM，Reduce 阶段用 Python 代码
2. **证据绑定是硬约束** — 每个提取对象必须有 `evidence_element_ids`，摘要不作为证据来源
3. **槽位动态发现** — `discover_slots()` 内省 Pydantic 模型字段，新增文档类型无需改管道代码
4. **理想耦合** — `ExtractionContract` 解耦"提取什么"和"如何提取"
5. **Finalizer 只操作块候选** — 不读取完整源文档，失败时回退到确定性 Reducer

## 7. 环境配置

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `LLM_MODEL` | qwen-doc-turbo | LLM 模型标识 |
| `EXTRACTION_CHUNK_MAX_CHARS` | 5000 | 分块最大字符数 |
| `EXTRACTION_CONCURRENCY` | 3 | LLM 调用并发数 |
| `EXTRACTION_MAX_CHARS` | 100000 | 文档长度硬限制 |
| `PARSER_BACKEND` | basic | basic (PyMuPDF) 或 docling |
| `DB_PATH` | db/db.sqlite3 | SQLite 数据库路径 |

## 8. 关键源文件

| 文件 | 说明 |
|------|------|
| `main.py` | FastAPI 应用入口 |
| `core/parser.py` | 多格式解析器（PDF/DOCX/TXT/MD） |
| `core/extractor.py` | Map-Reduce 提取管道 |
| `core/reducer.py` | 确定性合并/去重/ID 分配 |
| `core/chunker.py` | 章节感知分块 |
| `core/ir.py` | Document IR 构建 |
| `core/llm.py` | OpenAI 兼容 API 客户端 |
| `core/schema_registry.py` | 类型→模型分发 |
| `schemas/docs/*.py` | 各文档类型提取模型 |
| `scripts/evaluate.py` | 离线评估框架 |
| `frontend/src/App.tsx` | React 应用根组件 |

## 9. 评估框架

- **指标**：精确率/召回率/F1（槽位粒度）
- **匹配算法**：名称词级二元组 Jaccard 相似度 + 类型模糊权重 + 贪婪匹配
- **实验**：模型对比（Qwen/DeepSeek/Kimi）+ 消融（Phase 0/Finalizer/重叠窗口）
- **数据集**：6 份中文软件工程文档，人工标注 Ground Truth

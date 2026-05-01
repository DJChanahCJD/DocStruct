# 第二章 需求分析

## 2.1 系统目标

软件工程文档在实际项目中常以 PDF、DOCX、Markdown 或纯文本保存，格式不统一、结构不稳定，难以直接转换为可计算的结构化数据。DocStruct 面向单文档级结构化抽取，接收用户上传的文档，自动解析原文，调用大语言模型抽取关键对象，输出带证据回溯的 typed JSON。

系统覆盖五类主干文档：需求规格说明书（SRS）、API 接口文档、概要设计说明书（HLD）、测试用例文档（TC）和数据库设计文档（DBDD）。不涉及跨文档知识库、向量检索、问答机器人、URL 爬取和多模型在线切换。主要用户包括开发者（查询接口定义和模块划分）、测试人员（获取测试用例）、项目管理人员（了解文档结构）和论文实验人员（评测抽取质量）。

## 2.2 功能需求

### 2.2.1 文档上传与类型管理

用户可通过 Web 界面上传 PDF、DOCX、MD 和 TXT 文件，上传时指定文档类型（srs/api/hld/tc/dbdd/unknown）。系统生成文档列表，展示标题、类型、处理状态和创建时间，支持按类型和状态筛选。

### 2.2.2 文档解析与中间表示

解析模块按文件扩展名选择解析器：Markdown 和 TXT 直接读取，DOCX 解析段落和表格，PDF 支持 basic parser（PyMuPDF）和 Docling parser 两种后端。解析结果统一转换为 Document IR，包含元素 ID、文本、Markdown、章节路径、页码和边界框坐标。unknown 类型文档只保留原文和 IR，不执行后续抽取。

### 2.2.3 摘要生成

解析后调用 LLM 生成文档摘要（主题、主要章节和核心内容简述），作为分块抽取的全局上下文。摘要生成失败不阻断主流程。

### 2.2.4 结构化抽取

对五类主干文档，系统根据文档类型选择 typed schema，按章节感知策略分块，对每个分块并发调用 LLM 执行局部抽取（Map），通过 Finalizer 或 Reducer 将候选合并为全局结果（Reduce）。抽取结果须符合对应 Pydantic 模型的字段和类型约束。

### 2.2.5 证据回溯

每个抽取对象绑定 1 到多个 `evidence_element_ids`，系统在证据绑定阶段从 Document IR 查找对应元素，生成含 `object_id`、`element_id`、`text_span`、`page` 和 `bbox` 的 evidence 记录。前端点击对象时可查看原文证据，有 bbox 的 PDF 文档支持页面级高亮定位。

### 2.2.6 结果查看与修订

文档详情页展示原始文档、摘要、结构化抽取结果和证据。支持修订 raw_text、summary 和 extracted_data。修改 raw_text 时自动清除旧 IR。extracted_data 通过 JSON 编辑器修订。

### 2.2.7 调试与重试

分块调试接口返回各块的章节路径、元素 ID、允许的证据 ID 和渲染 Markdown。支持对已有文档重新执行结构化抽取。

## 2.3 非功能需求

**正确性：** 抽取结果须符合 typed schema。LLM 输出经 JSON 清洗（去 Markdown 包裹、修复尾随逗号）和 Pydantic 校验，失败分块被记录并跳过，不阻塞有效块的合并。

**可追溯性：** 保留 raw_text、summary、document_ir、extracted_data 和 evidence 完整链路，使结构化对象能逐级回溯到原始文档元素。

**可维护性：** 职责拆分到 Parser、IR Builder、Chunker、Extractor、Reducer、Evidence Binder、Schema Registry 和 API 服务等独立模块。新增文档类型通过新增 Pydantic Schema 并注册实现，不修改核心管道代码。运行参数通过环境变量注入。

**性能：** 面向中短文档（上限 100000 字符），分块并发数默认 3。文档解析和 Reducer 合并在毫秒级完成，整体耗时主要由 LLM 调用决定。

**易用性：** 前端上传流程简单直接。详情页同时展示原文和结构化结果，支持双向定位。PDF 证据高亮定位到对应页面区域。

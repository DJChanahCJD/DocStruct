# 后端精简重构计划

## 目标
将系统收敛为“软件工程文档结构化提取系统”，只保留后端核心能力，删除知识库问答、向量库、URL 导入、重抽取与审核链路，优先优化结构化提取主流程。

## 重构后保留的最小能力
1. 文件上传（PDF / DOCX / MD / TXT）
2. 文档解析为 Markdown
3. 按 `doc_type` 执行结构化提取
4. 长文档固定走分块提取 + 合并
5. 文档列表查询、详情查询、删除
6. SQLite 持久化文档原文与结构化结果

## 必删内容
### 数据模型
- 删除 `DocumentRecord` 中：`source_type`、`source_url`、`llm_model`
- 删除 `ChunkRecord`

### 后端接口
- 删除 URL 导入接口
- 删除 QA 接口
- 删除 reindex 接口
- 删除 review-model 相关接口
- 删除 re-extract 相关接口
- 删除 text-models 相关接口（如果仅保留单模型）

### 后端模块
- 删除 `core/retrieval.py`
- 删除 `core/review_model.py`
- 删除 `core/source_service.py`
- 删除与向量索引、问答、RAG、审核模型相关的辅助逻辑

### DTO / 配置 / 文档
- 删除 URL、QA、reindex、review-model、re-extract 对应 DTO
- 删除多模型选择配置，固定单一提取模型
- README 改为仅描述“结构化提取”后端能力

## 核心链路收敛
收敛为：

`上传文件 -> 解析 Markdown -> 结构化提取 -> 结果校验/合并 -> 保存数据库 -> 查询结果`

### 提取策略
- 中短文档：直接单次提取
- 长文档：固定分块提取，不再保留多套策略分支
- 明确系统不面向超长文档（如 10 万字符以上）

## 关键文件修改清单
- `main.py`：收缩路由，只保留上传、列表、详情、删除
- `core/document_service.py`：移除 URL、向量、模型透传、重抽相关逻辑
- `core/extractor.py`：保留并简化单次提取 / 分块提取 / 合并主流程
- `core/chunker.py`：仅保留服务于结构化提取的分块逻辑
- `core/config.py`：固定提取模型与分块参数
- `schemas/models.py`：删除冗余字段与 `ChunkRecord`
- `schemas/dto.py`：同步删除无关 DTO
- `README.md`：重写功能边界、接口说明、技术栈、TODO

## 推荐执行顺序
1. 先删数据模型冗余字段与 `ChunkRecord`
2. 再删路由层无关接口
3. 删除 `retrieval` / `review_model` / `source_service` 及引用
4. 收缩 `document_service`，只保留上传-解析-抽取-保存
5. 简化 `extractor` 与 `chunker`，固定长文档策略
6. 清理 DTO、配置、脚本与 README
7. 跑后端测试与最小手工验证

## 风险点
- 删除字段后需要同步处理数据库初始化/迁移逻辑
- `main.py` 与 `document_service.py` 可能存在较多级联引用，需要一次性清理干净
- `extractor.py` 可能仍隐式依赖已删除模块，需逐个断开
- README、测试脚本、接口说明必须同步收敛，否则实现与文档会再次脱节

## 最小验证范围
1. 上传 PDF / DOCX / MD / TXT 是否成功
2. 文档是否能正确解析为 Markdown
3. 每类 `doc_type` 是否能输出合法 JSON
4. 长文档是否稳定走固定分块提取
5. 超长文档是否明确拒绝或提示不适用
6. 文档列表、详情、删除是否正常
7. `uv run python scripts/ci_test.py --backend-only` 可通过

## 本次重构原则
- 只保留毕设当前真正需要的后端能力
- 不做兼容层，不保留废弃占位
- 优先降低复杂度与维护成本
- 后续新增 QA / 向量库时再单独设计接入
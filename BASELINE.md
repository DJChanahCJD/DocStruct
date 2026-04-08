# DocStruct 运行基线说明

本文档用于收敛当前项目的实际运行配置、默认值、关键阈值和目录约定，作为后续实验、调优和重构的统一参考。

## 1. 当前运行入口

- 启动文件：`main.py`
- 默认服务地址：`http://127.0.0.1:8001`
- Uvicorn 配置：
  - `host=0.0.0.0`
  - `port=8001`
  - `reload=False`

## 2. 当前环境变量

### 必要配置

| 配置项 | 作用 | 当前代码位置 | 默认值 |
| --- | --- | --- | --- |
| `LLM_API_KEY` | 大模型与 embedding 调用鉴权 | `core/extractor.py`、`core/retrieval.py` | 无 |
| `LLM_BASE_URL` | OpenAI-Compatible 接口地址 | `core/extractor.py`、`core/retrieval.py` | 无 |
| `LLM_MODEL` | 文类识别、结构化抽取、问答所用模型 | `core/extractor.py`、`core/retrieval.py` | `qwen2.5-7b-instruct-1m` |
| `EMBEDDING_MODEL` | 向量化模型 | `core/retrieval.py` | 优先读取该值 |
| `LLM_EMBED_MODEL` | embedding 备用配置项 | `core/retrieval.py` | 仅在 `EMBEDDING_MODEL` 缺失时生效 |

### 当前 embedding 选择优先级

`core/retrieval.py` 中当前优先级为：

1. `EMBEDDING_MODEL`
2. `LLM_EMBED_MODEL`
3. 默认值 `text-embedding-v4`

### 建议 `.env` 基线

```env
LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
LLM_API_KEY=your_api_key
LLM_MODEL=qwen-doc-turbo
EMBEDDING_MODEL=text-embedding-v4
```

## 3. 当前关键阈值与默认参数

### 3.1 上传与存储

| 项目 | 当前值 | 位置 |
| --- | --- | --- |
| 上传目录 | `db/uploads` | `main.py` |
| 支持扩展名 | `.pdf`、`.docx`、`.md`、`.txt` | `main.py` |
| SQLite 路径 | `db/db.sqlite3` | `main.py` |

### 3.2 抽取阶段

`core/extractor.py`

| 项目 | 当前值 | 说明 |
| --- | --- | --- |
| 长文档阈值 | `6000` 字符 | 超过后进入分块抽取 |
| 分块抽取 `max_chars` | `5000` | 长文档抽取单块最大字符数 |
| 分块抽取 `overlap_chars` | `200` | 长文档抽取分块重叠长度 |
| 单次抽取截断 | `30000` 字符 | 单次抽取或回退时仅取前 30000 字符 |
| 温度 | `0.0` | 分类与抽取均使用低温度，强调稳定性 |

当前抽取策略：

- 短文档：单次抽取
- 长文档：分块抽取 -> 合并校验
- 合并失败或分块无结果：回退为单次抽取

### 3.3 分块阶段

`core/chunker.py`

| 项目 | 当前值 | 说明 |
| --- | --- | --- |
| 默认目标块大小 | `700` | `DEFAULT_TARGET_SIZE` |
| 默认重叠长度 | `80` | `DEFAULT_OVERLAP` |
| 默认最小块长度 | `200` | `DEFAULT_MIN_SIZE` |

### 3.4 索引阶段

`core/retrieval.py`

| 项目 | 当前值 | 说明 |
| --- | --- | --- |
| 检索建库 `max_chars` | `700` | 构建检索块时的目标长度 |
| 检索建库 `overlap_chars` | `80` | 构建检索块时的重叠长度 |
| 检索建库 `min_chars` | `200` | 检索块最小长度 |
| embedding 批大小 | `32` | `_embed_texts` 中固定值 |
| QA 温度 | `0.1` | 问答阶段略高于抽取阶段 |

## 4. 当前目录与运行数据约定

| 目录或文件 | 用途 |
| --- | --- |
| `db/uploads` | 上传后的原始文件 |
| `db/db.sqlite3` | 主数据库 |
| `db/vector/faiss.index` | FAISS 索引文件 |
| `db/vector/faiss_ids.json` | 索引与 chunk ID 映射 |
| `static/examples/` | 手动验证样例文档 |

## 5. 当前主流程中的隐式约定

- 分类、抽取、问答当前共享 `LLM_MODEL`，尚未拆分成独立模型配置。
- embedding 模型与聊天模型配置是分离的，但尚未集中配置化。
- 抽取链与检索链都在模块导入时执行 `load_dotenv()`。
- `README.md`、`PLAN.md`、本文档三者目前共同构成项目基线说明。

## 6. 目录职责边界

### `main.py`

当前职责：

- FastAPI 应用初始化
- 静态资源挂载
- 上传入口与基础扩展名校验
- 调用 `core/` 中的解析、分类、抽取、索引、问答能力
- ORM 注册与接口返回

边界要求：

- 保持为“入口与编排层”，不要继续堆积抽取规则、检索策略、Prompt 细节。
- 允许保留少量装配性质配置，例如当前的 `TYPE_MODEL_MAP`。
- 若后续新增 URL 输入、实验接口或后台任务，仍应优先放在路由编排层，不将核心处理逻辑直接写在接口函数内部。

### `core/`

当前职责：

- `parser.py`：输入文档解析
- `extractor.py`：分类、抽取、回退策略
- `chunker.py`：Markdown 结构切分与语义分块
- `retrieval.py`：向量化、检索、问答
- `constants.py`：Prompt 与常量
- `utils.py`：抽取结果清洗、归一化与合并

边界要求：

- 所有核心业务规则、处理策略、阈值、回退逻辑都应优先放在 `core/`。
- 后续如果要做异步化、模型对比、长文档优化，也应以 `core/` 为主要承载位置。
- `core/` 内部允许继续拆模块，但不要把数据模型定义反向放回业务模块中。

### `schemas/models.py`

当前职责：

- `DocType` 文类枚举
- ORM 数据表模型
- Pydantic 分类模型
- 各类文档结构模型
- API 请求/响应模型

边界要求：

- 保持为统一模型层，不承载解析、抽取、检索逻辑。
- 新增文类时，必须在此文件内完成文类枚举和结构模型补充。
- 所有 API 契约结构优先集中维护在这里，避免散落到路由文件和业务模块。

### `static/`

当前职责：

- 单页前端展示
- `static/examples/` 手动验证样例

边界要求：

- 前端仅消费接口，不直接承担后端规则判断。
- 样例文档可持续扩充，但应继续服务“手动验证”和“论文演示”两类场景。

### `db/`

当前职责：

- 运行期数据库
- 上传文件
- FAISS 索引与映射文件

边界要求：

- 仅存放运行数据，不纳入版本控制。
- 后续若新增实验输出，应优先另建独立目录，不与运行期上传文件混放。

## 7. 当前主要风险点

- 阈值与默认值仍分散在 `extractor.py`、`retrieval.py`、`chunker.py` 中，不利于后续实验复现。
- 分类、抽取、问答共用一个 `LLM_MODEL`，后续模型对比时粒度不够细。
- 当前没有实验模式和生产模式的配置区分。
- 当前没有专门的配置模块，参数修改需要直接改代码。

## 8. Phase 0 收敛状态

以下内容已完成收敛：

- 当前环境变量清单
- 当前默认模型与 embedding 取值逻辑
- 当前抽取阈值与分块参数
- 当前存储路径与运行目录约定
- 当前手动验证样例入口
- 当前目录职责边界说明

后续建议：

- 下一步将这些参数抽离为统一配置模块或配置常量。
- 在进入 Phase 1 前，保持本文件与代码一致，作为实验基线。

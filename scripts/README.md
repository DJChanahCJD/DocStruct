# Scripts

这个目录放的是项目的开发辅助脚本，主要分为三类：`CI 回归`、`离线评测`、`接口/单元测试`。

## 快速开始

日常改动后，优先跑：

```bash
uv run python scripts/ci_test.py
```

如果只想跑后端：

```bash
uv run python scripts/ci_test.py --backend-only
```

## 脚本说明

### CI 回归

- `ci_test.py`
  - 统一 CI 入口。
  - 默认执行后端核心 unittest 和前端 `npm run build`。
  - 适合每次代码改动后快速确认主链路没有回归。

### 离线评测

- `run_eval.py`
  - 配置驱动的统一离线实验入口。
  - 支持 `exp1`、`exp2`、`exp3` 三个实验，通过配置切换样本过滤、Prompt 变体和结果聚合方式。
  - 适合做论文实验复现和 Prompt 对比。

### 接口契约测试

- `test_qa_contract.py`
  - 校验问答相关接口契约。
  - 包括 `text-models`、`qa`、基础文档接口、上传参数校验等。

- `test_re_extract_contract.py`
  - 校验 `re-extract` 接口契约。
  - 覆盖全量重提取、字段级重提取和错误分支。

- `test_review_model_contract.py`
  - 校验新的 `review-model` 接口契约。
  - 覆盖审核视图获取、节点级保存、保存后重建索引、节点级预览重提取。

### 单元测试

- `test_re_extract_unit.py`
  - 测 `re_extract_with_instruction` 的核心逻辑。
  - 关注 prompt 拼装、字段级提取、异常处理。

- `test_review_model_unit.py`
  - 测 review-model 的纯逻辑。
  - 关注 `extracted_data -> 审核视图` 映射、局部 patch、节点定位。

## 建议使用方式

- 改了前后端主流程：跑 `ci_test.py`
- 改了问答接口：至少跑 `test_qa_contract.py`
- 改了重提取逻辑：至少跑 `test_re_extract_contract.py` 和 `test_re_extract_unit.py`
- 改了审核/局部编辑逻辑：至少跑 `test_review_model_contract.py` 和 `test_review_model_unit.py`
- 改了抽取 prompt 或实验配置：再补跑 `run_eval.py`

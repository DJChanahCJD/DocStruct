# Experiments

## 实验设计

### 实验0：最小验证实验，单文档快速验证系统核心功能

实验0是开发期快速测试脚本，用于验证单个文档从解析到结构化抽取的核心链路是否可用。

默认样本文档：

```text
experiments/assets/srs_mini.md
```

运行：

```bash
uv run python experiments/exp0.py
```

只验证解析链路，不调用 LLM：

```bash
uv run python experiments/exp0.py --parse-only
```

写出完整结果：

```bash
uv run python experiments/exp0.py --output experiments/results/exp0_latest.json
```

可选参数：

```bash
uv run python experiments/exp0.py --file experiments/assets/srs_mini.md --doc-type srs
```

控制台会输出 parser、文档块数、IR 元素数、抽取模型和支持状态。完整 JSON 包含 `markdown_content`、`parse_meta`、`extracted_data`、`extraction_meta`。

### 实验一：选择最优 LLM

🚧 可等系统稳定后再做

### 实验二：选择最优 Prompt

🚧 可等系统稳定后再做。事实上，是否真的需要这个实验存疑，因为在开发过程中为了提高系统的性能和稳定性，已经对 Prompt 进行了优化。

### 实验三：泛化鲁棒性

🚧 可等系统稳定后再做

> 架构消融暂不考虑

## 目录结构

```
experiments/
|── assets/
|   ├── srs_mini.md            # 测试文档   
|── exp0.py                    # 单文档快速验证脚本
|── exp1/
    ├── configs/              # 实验配置
    └── results/              # 运行结果
    ├── exp1.py                 # 实验脚本
|── exp2/
...
```

## TODO

- [] 移除当前的旧实验框架，等系统稳定后再做实验,当前可以搭一个简易前端做轻量测试

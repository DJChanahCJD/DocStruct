# 本地执行约定

- 项目：DocStruct - 基于大模型的软件工程文档结构化提取系统
- 项目目标：通过设计简洁高效的 Prompt 将 软件工程文档结构化提取为 JSON
- 语言：中文
- 环境：Windows / PowerShell
- Python：优先使用项目内虚拟环境的显式解释器路径：

```powershell
.\.venv\Scripts\python.exe
```

- 运行测试示例：

```powershell
.\.venv\Scripts\python.exe -m unittest scripts.tests.test_srs_requirement_boundaries
```

- 运行编译检查示例：

```powershell
.\.venv\Scripts\python.exe -m compileall core schemas main.py
```

- 不要假设 `python` 一定指向当前项目 `.venv`；需要确认时执行：

```powershell
.\.venv\Scripts\python.exe -c "import sys; print(sys.executable)"
```

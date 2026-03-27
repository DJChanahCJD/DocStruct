# AGENTS

## 项目结构
- `main.py`：入口（路由 / 上传 / ORM）
- `core/`：核心逻辑（解析 / chunk / pipeline）
- `schemas/models.py`：数据模型
- `static/`：前端 + 示例文件
- `db/`：运行数据（禁止提交）

## 代码规则

* PEP8，4 空格
* `snake_case`（函数/变量），`PascalCase`（类）
* 路由保持轻量，逻辑必须在 `core/`
* 新增文档类型：必须同时更新 `DocType` + model + `TYPE_MODEL_MAP`

## 测试

* 无自动测试 → 必须手动验证：

  * 上传 `static/examples/`
  * 检查 JSON / 日志 / DB

## 提交

* Conventional Commits（feat/fix/refactor/docs）
* 一次提交只做一件事

## 安全

* 禁止提交：`.env` / `db/` / 上传文件

## 核心原则

1. 最简单方案优先
2. 不做无关重构
3. 不重复造轮子
4. 正确性优先
5. Breaking Change 必须确认

## 工作要求

* 中文输出，简洁明了
* 必须说明：修改内容 + 原因
* 修改前先读代码，禁止猜测
* 未要求不执行 Git 操作

## 环境

* Windows + PowerShell

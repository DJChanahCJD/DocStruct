
# 评测报告

生成时间：2026-04-29T18:45:25.722002
模式：cached

## 总体指标

| 指标 | 值 |
|---|---|
| Precision | 0.5638 |
| Recall | 0.7067 |
| F1 | 0.6272 |
| TP / FP / FN | 106 / 82 / 44 |

## 按文档

| 文档 | 类型 | P | R | F1 | TP/FP/FN |
|---|---|---|---|---|---|
| srs_mini | srs | 0.812 | 0.619 | 0.703 | 13/3/8 |
| srs_example | srs | 0.795 | 0.912 | 0.849 | 62/16/6 |
| api_mini | api | 1.000 | 0.667 | 0.800 | 4/0/2 |
| api_example | api | 0.545 | 0.750 | 0.632 | 12/10/4 |
| test_case_example | test | 0.121 | 0.292 | 0.171 | 7/51/17 |
| design_mini | design | 0.800 | 0.533 | 0.640 | 8/2/7 |

## 按槽位


### auth

| 文档 | GT | Pred | TP | FP | FN | P | R | F1 | 备注 |
|---|---|---|---|---|---|---|---|---|---|
| api_mini | 1 | 1 | 1 | 0 | 0 | 1.000 | 1.000 | 1.000 |  |
| api_example | 1 | 1 | 0 | 1 | 1 | 0.000 | 0.000 | 0.000 |  |

### decisions

| 文档 | GT | Pred | TP | FP | FN | P | R | F1 | 备注 |
|---|---|---|---|---|---|---|---|---|---|
| design_mini | 3 | 3 | 1 | 2 | 2 | 0.333 | 0.333 | 0.333 |  |

### defects

| 文档 | GT | Pred | TP | FP | FN | P | R | F1 | 备注 |
|---|---|---|---|---|---|---|---|---|---|
| test_case_example | 0 | 0 | 0 | 0 | 0 | 0.000 | 0.000 | 0.000 |  |

### endpoints

| 文档 | GT | Pred | TP | FP | FN | P | R | F1 | 备注 |
|---|---|---|---|---|---|---|---|---|---|
| api_mini | 3 | 3 | 3 | 0 | 0 | 1.000 | 1.000 | 1.000 |  |
| api_example | 12 | 17 | 12 | 5 | 0 | 0.706 | 1.000 | 0.828 |  |

### entities

| 文档 | GT | Pred | TP | FP | FN | P | R | F1 | 备注 |
|---|---|---|---|---|---|---|---|---|---|
| srs_mini | 6 | 1 | 1 | 0 | 5 | 1.000 | 0.167 | 0.286 |  |
| srs_example | 16 | 22 | 14 | 8 | 2 | 0.636 | 0.875 | 0.737 |  |
| api_mini | 2 | 0 | 0 | 0 | 2 | 0.000 | 0.000 | 0.000 |  |
| api_example | 3 | 4 | 0 | 4 | 3 | 0.000 | 0.000 | 0.000 |  |
| test_case_example | 4 | 0 | 0 | 0 | 4 | 0.000 | 0.000 | 0.000 |  |
| design_mini | 5 | 0 | 0 | 0 | 5 | 0.000 | 0.000 | 0.000 |  |

### functional_requirements

| 文档 | GT | Pred | TP | FP | FN | P | R | F1 | 备注 |
|---|---|---|---|---|---|---|---|---|---|
| srs_mini | 5 | 5 | 5 | 0 | 0 | 1.000 | 1.000 | 1.000 |  |
| srs_example | 12 | 12 | 12 | 0 | 0 | 1.000 | 1.000 | 1.000 |  |

### interfaces

| 文档 | GT | Pred | TP | FP | FN | P | R | F1 | 备注 |
|---|---|---|---|---|---|---|---|---|---|
| srs_mini | 4 | 4 | 1 | 3 | 3 | 0.250 | 0.250 | 0.250 |  |
| srs_example | 8 | 12 | 4 | 8 | 4 | 0.333 | 0.500 | 0.400 |  |
| design_mini | 3 | 3 | 3 | 0 | 0 | 1.000 | 1.000 | 1.000 |  |

### modules

| 文档 | GT | Pred | TP | FP | FN | P | R | F1 | 备注 |
|---|---|---|---|---|---|---|---|---|---|
| design_mini | 4 | 4 | 4 | 0 | 0 | 1.000 | 1.000 | 1.000 |  |

### non_functional_requirements

| 文档 | GT | Pred | TP | FP | FN | P | R | F1 | 备注 |
|---|---|---|---|---|---|---|---|---|---|
| srs_mini | 6 | 6 | 6 | 0 | 0 | 1.000 | 1.000 | 1.000 |  |
| srs_example | 32 | 32 | 32 | 0 | 0 | 1.000 | 1.000 | 1.000 |  |

### schemas

| 文档 | GT | Pred | TP | FP | FN | P | R | F1 | 备注 |
|---|---|---|---|---|---|---|---|---|---|
| api_mini | 0 | 3 | 0 | 0 | 0 | 0.000 | 0.000 | 0.000 | ignored |
| api_example | 0 | 30 | 0 | 0 | 0 | 0.000 | 0.000 | 0.000 | ignored |

### test_cases

| 文档 | GT | Pred | TP | FP | FN | P | R | F1 | 备注 |
|---|---|---|---|---|---|---|---|---|---|
| test_case_example | 6 | 10 | 2 | 8 | 4 | 0.200 | 0.333 | 0.250 |  |

### test_steps

| 文档 | GT | Pred | TP | FP | FN | P | R | F1 | 备注 |
|---|---|---|---|---|---|---|---|---|---|
| test_case_example | 14 | 48 | 5 | 43 | 9 | 0.104 | 0.357 | 0.161 |  |

## 诊断样例


### srs_mini

- `entities` FP: -
- `entities` FN: 用户；文档解析服务；搜索服务；企业微信；GitLab
- `interfaces` FP: 企业微信 API；GitLab API；文档解析服务
- `interfaces` FN: 企业微信消息推送API；GitLab代码仓库API；文档解析gRPC接口

### srs_example

- `entities` FP: 开发团队；测试团队；项目管理团队；协作模块；报表与统计模块
- `entities` FN: PostgreSQL数据库；Redis缓存
- `interfaces` FP: Web 界面；移动端适配；硬件接口；文档解析服务；搜索服务
- `interfaces` FN: 文档解析gRPC；Elasticsearch REST API；Redis缓存；RabbitMQ消息队列

### api_mini

- `entities` FP: -
- `entities` FN: 智能文档系统；用户
- `schemas`: ignored (3 predictions)

### api_example

- `auth` FP: 获取访问令牌 (2.1)
- `auth` FN: Bearer Token
- `endpoints` FP: 启动实验 (7.2)；暂停实验 (7.3)；终止实验 (7.4)；查询实验数据 (8.2)；查询分析结果 (9.2)
- `endpoints` FN: -
- `entities` FP: Device；Experiment；DataPoint；AnalysisJob
- `entities` FN: NebulaLab实验编排平台；研究者；传感器
- `schemas`: ignored (30 predictions)

### test_case_example

- `entities` FP: -
- `entities` FN: 用户；电商平台；短信验证码服务；支付宝
- `test_cases` FP: 验证用户使用有效手机号成功注册；验证已注册用户通过手机号密码登录；验证通过关键词搜索商品返回正确结果；验证用户可将商品加入购物车；验证连续输入错误密码后账号锁定
- `test_cases` FN: 用户注册功能（TC-USER-001）；用户登录功能（TC-USER-002）；商品搜索功能（TC-PROD-001）；添加商品到购物车（TC-CART-001）
- `test_steps` FP: 打开注册页面；输入未注册的手机号（如：13800138001）；点击"获取验证码"按钮；等待接收短信验证码；输入正确的6位验证码
- `test_steps` FN: 用户注册功能（TC-USER-001） 步骤 1；用户注册功能（TC-USER-001） 步骤 2；用户注册功能（TC-USER-001） 步骤 3；用户登录功能（TC-USER-002） 步骤 1；商品搜索功能（TC-PROD-001） 步骤 1

### design_mini

- `decisions` FP: 抽取结果统一映射到实体、流程、需求、接口和产物五类对象；解析失败时保留错误信息，避免覆盖原始文档记录
- `decisions` FN: 抽取结果统一映射到结构化对象；解析失败保留错误信息
- `entities` FP: -
- `entities` FN: Web前端；API服务；文档解析服务；数据库；用户


# 评测报告

生成时间：2026-04-29T20:31:18.230176
模式：cached

## 总体指标

| 指标 | 值 |
|---|---|
| Precision | 0.9076 |
| Recall | 0.9278 |
| F1 | 0.9176 |
| TP / FP / FN | 167 / 17 / 13 |

## 按文档

| 文档 | 类型 | P | R | F1 | TP/FP/FN |
|---|---|---|---|---|---|
| srs_mini | srs | 0.938 | 0.714 | 0.811 | 15/1/6 |
| srs_example | srs | 0.808 | 0.926 | 0.863 | 63/15/5 |
| api_mini | api | 1.000 | 1.000 | 1.000 | 4/0/0 |
| api_example | api | 0.944 | 0.944 | 0.944 | 17/1/1 |
| test_case_example | test | 1.000 | 0.983 | 0.992 | 58/0/1 |
| design_mini | design | 1.000 | 1.000 | 1.000 | 10/0/0 |

## 按槽位


### auth

| 文档 | GT | Pred | TP | FP | FN | P | R | F1 | 备注 |
|---|---|---|---|---|---|---|---|---|---|
| api_mini | 1 | 1 | 1 | 0 | 0 | 1.000 | 1.000 | 1.000 |  |
| api_example | 1 | 1 | 0 | 1 | 1 | 0.000 | 0.000 | 0.000 |  |

### decisions

| 文档 | GT | Pred | TP | FP | FN | P | R | F1 | 备注 |
|---|---|---|---|---|---|---|---|---|---|
| design_mini | 3 | 3 | 3 | 0 | 0 | 1.000 | 1.000 | 1.000 |  |

### defects

| 文档 | GT | Pred | TP | FP | FN | P | R | F1 | 备注 |
|---|---|---|---|---|---|---|---|---|---|
| test_case_example | 0 | 0 | 0 | 0 | 0 | 0.000 | 0.000 | 0.000 |  |

### endpoints

| 文档 | GT | Pred | TP | FP | FN | P | R | F1 | 备注 |
|---|---|---|---|---|---|---|---|---|---|
| api_mini | 3 | 3 | 3 | 0 | 0 | 1.000 | 1.000 | 1.000 |  |
| api_example | 17 | 17 | 17 | 0 | 0 | 1.000 | 1.000 | 1.000 |  |

### entities

| 文档 | GT | Pred | TP | FP | FN | P | R | F1 | 备注 |
|---|---|---|---|---|---|---|---|---|---|
| srs_mini | 6 | 1 | 1 | 0 | 5 | 1.000 | 0.167 | 0.286 |  |
| srs_example | 16 | 22 | 14 | 8 | 2 | 0.636 | 0.875 | 0.737 |  |
| api_mini | 2 | 0 | 0 | 0 | 0 | 0.000 | 0.000 | 0.000 | ignored |
| api_example | 3 | 4 | 0 | 0 | 0 | 0.000 | 0.000 | 0.000 | ignored |
| test_case_example | 4 | 0 | 0 | 0 | 0 | 0.000 | 0.000 | 0.000 | ignored |
| design_mini | 5 | 0 | 0 | 0 | 0 | 0.000 | 0.000 | 0.000 | ignored |

### functional_requirements

| 文档 | GT | Pred | TP | FP | FN | P | R | F1 | 备注 |
|---|---|---|---|---|---|---|---|---|---|
| srs_mini | 5 | 5 | 5 | 0 | 0 | 1.000 | 1.000 | 1.000 |  |
| srs_example | 12 | 12 | 12 | 0 | 0 | 1.000 | 1.000 | 1.000 |  |

### interfaces

| 文档 | GT | Pred | TP | FP | FN | P | R | F1 | 备注 |
|---|---|---|---|---|---|---|---|---|---|
| srs_mini | 4 | 4 | 3 | 1 | 1 | 0.750 | 0.750 | 0.750 |  |
| srs_example | 8 | 12 | 5 | 7 | 3 | 0.417 | 0.625 | 0.500 |  |
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
| test_case_example | 10 | 10 | 10 | 0 | 0 | 1.000 | 1.000 | 1.000 |  |

### test_steps

| 文档 | GT | Pred | TP | FP | FN | P | R | F1 | 备注 |
|---|---|---|---|---|---|---|---|---|---|
| test_case_example | 49 | 48 | 48 | 0 | 1 | 1.000 | 0.980 | 0.990 |  |

## 诊断样例


### srs_mini

- `entities` FP: -
- `entities` FN: 用户；文档解析服务；搜索服务；企业微信；GitLab
- `interfaces` FP: 文档解析服务
- `interfaces` FN: 文档解析gRPC接口

### srs_example

- `entities` FP: 开发团队；测试团队；项目管理团队；协作模块；报表与统计模块
- `entities` FN: PostgreSQL数据库；Redis缓存
- `interfaces` FP: Web 界面；移动端适配；硬件接口；搜索服务；缓存服务
- `interfaces` FN: Elasticsearch REST API；Redis缓存；RabbitMQ消息队列

### api_mini

- `entities`: ignored (0 predictions)
- `schemas`: ignored (3 predictions)

### api_example

- `auth` FP: 获取访问令牌 (2.1)
- `auth` FN: Bearer Token
- `entities`: ignored (4 predictions)
- `schemas`: ignored (30 predictions)

### test_case_example

- `entities`: ignored (0 predictions)

### design_mini

- `entities`: ignored (0 predictions)

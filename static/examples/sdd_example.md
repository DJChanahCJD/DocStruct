# 电商平台后端系统设计说明书 (SDD)

## 1. 文档介绍
**文档版本**: 2.3
**日期**: 2023-10-27

本文档描述了“易购”电商平台的后端系统架构设计、模块划分及数据库设计，旨在为开发团队提供详细的技术指导。

## 2. 系统架构概要
本系统采用前后端分离的微服务架构。前端通过 Nginx 反向代理访问后端 API 网关（Spring Cloud Gateway）。后端服务划分为多个独立的微服务，包括用户服务、商品服务、订单服务、支付服务和库存服务。

- **服务注册与发现**: Nacos
- **配置中心**: Nacos
- **RPC 调用**: OpenFeign
- **数据库**: MySQL 8.0 (主从复制)
- **缓存**: Redis Cluster
- **消息队列**: RocketMQ (用于削峰填谷及解耦)

## 3. 模块设计

### 3.1 用户服务 (User Service)
负责用户账号的全生命周期管理及鉴权。
- **功能描述**: 用户注册、登录（JWT）、个人信息修改、地址管理、实名认证。
- **对外接口**:
    - `POST /api/v1/users/register`: 用户注册
    - `POST /api/v1/users/login`: 用户登录，返回 Token
    - `GET /api/v1/users/profile`: 获取个人信息
    - `PUT /api/v1/users/address`: 更新收货地址

### 3.2 订单服务 (Order Service)
核心交易链路，处理订单状态流转。
- **功能描述**: 购物车管理、创建订单、取消订单、订单超时自动关闭（延迟队列）、查询订单详情。
- **对外接口**:
    - `POST /api/v1/orders/create`: 下单
    - `GET /api/v1/orders/{id}`: 查询订单详情
    - `POST /api/v1/orders/{id}/cancel`: 取消订单

### 3.3 商品服务 (Product Service)
管理商品信息、类目及属性。
- **功能描述**: 商品上下架、SKU 管理、库存扣减（调用库存服务）、商品搜索（Elasticsearch）。
- **对外接口**:
    - `GET /api/v1/products/list`: 商品列表查询
    - `GET /api/v1/products/{id}`: 商品详情

### 3.4 支付服务 (Payment Service)
对接第三方支付渠道。
- **功能描述**: 生成支付预订单、处理支付回调、退款处理、对账。
- **对外接口**:
    - `POST /api/v1/pay/unified`: 统一下单
    - `POST /api/v1/pay/callback`: 支付回调通知

## 4. 数据库设计

### 4.1 用户表 (t_user)
存储用户基础信息。
| 字段名 | 类型 | 描述 |
| :--- | :--- | :--- |
| id | BIGINT | 主键 ID |
| username | VARCHAR(64) | 用户名 |
| password_hash | VARCHAR(128) | 加密密码 |
| email | VARCHAR(128) | 邮箱 |
| phone | VARCHAR(20) | 手机号 |
| status | TINYINT | 状态 (1:正常, 0:禁用) |
| created_at | DATETIME | 创建时间 |

### 4.2 订单主表 (t_order)
存储订单概要信息。
| 字段名 | 类型 | 描述 |
| :--- | :--- | :--- |
| id | BIGINT | 订单 ID |
| user_id | BIGINT | 用户 ID |
| total_amount | DECIMAL(10,2) | 订单总金额 |
| pay_amount | DECIMAL(10,2) | 实付金额 |
| status | INT | 订单状态 (0:待支付, 1:已支付, 2:已发货, 3:已完成, 4:已取消) |
| address_snapshot | TEXT | 收货地址快照 |
| created_at | DATETIME | 下单时间 |

### 4.3 订单明细表 (t_order_item)
存储订单商品明细。
| 字段名 | 类型 | 描述 |
| :--- | :--- | :--- |
| id | BIGINT | 主键 ID |
| order_id | BIGINT | 关联订单 ID |
| sku_id | BIGINT | 商品 SKU ID |
| sku_name | VARCHAR(255) | 商品名称 |
| price | DECIMAL(10,2) | 购买单价 |
| quantity | INT | 购买数量 |

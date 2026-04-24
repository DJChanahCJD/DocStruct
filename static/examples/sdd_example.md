# 电商平台后端系统设计说明书 (SDD)

## 1. 文档介绍

### 1.1 文档信息

| 项目 | 内容 |
|------|------|
| 文档版本 | 2.3 |
| 最后更新 | 2023-10-27 |
| 编制人 | 架构组 |
| 审核人 | 技术总监 |
| 适用范围 | "易购"电商平台 v2.x |

### 1.2 文档目的

本文档描述"易购"电商平台的后端系统架构设计、模块划分、接口设计、数据库设计及关键技术方案，为开发团队提供详细的技术指导，为运维团队提供部署参考。

---

## 2. 系统架构设计

### 2.1 总体架构

本系统采用**微服务架构**，前后端分离设计。系统按业务领域划分为多个独立部署的服务单元，通过 API 网关统一对外暴露接口。

**架构图：**

```
┌─────────────────────────────────────────────────────────────────┐
│                          客户端层                                │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐         │
│  │   Web    │  │   APP    │  │  小程序   │  │  管理后台  │         │
│  │  (Vue)   │  │ (Flutter)│  │(Taro)    │  │ (React)   │         │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘         │
└───────┼─────────────┼─────────────┼─────────────┼─────────────────┘
        │             │             │             │
        └─────────────┴──────┬──────┴─────────────┘
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                        网关层 (Nginx)                           │
│         负载均衡 / SSL 终结 / 静态资源缓存                        │
└─────────────────────────────┬───────────────────────────────────┘
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      API 网关 (Spring Cloud Gateway)             │
│    路由转发 / 鉴权 / 限流 / 熔断 / 日志 / 灰度发布                  │
└─────────────────────────────┬───────────────────────────────────┘
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                        业务服务层                               │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌────────┐ │
│  │ 用户服务  │ │ 商品服务  │ │ 订单服务  │ │ 支付服务  │ │库存服务 │ │
│  │ user-svc │ │ prod-svc │ │ order-svc│ │ pay-svc  │ │stock-svc│ │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘ └────────┘ │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐           │
│  │ 购物车服务 │ │ 搜索服务  │ │ 消息服务  │ │ 文件服务  │           │
│  │ cart-svc │ │search-svc│ │ msg-svc  │ │ file-svc │           │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘           │
└─────────────────────────────────────────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        ▼                     ▼                     ▼
┌──────────────┐    ┌────────────────┐    ┌────────────────┐
│   数据存储层   │    │    中间件层     │    │    基础设施层   │
│  ┌────────┐  │    │  ┌──────────┐  │    │  ┌──────────┐  │
│  │ MySQL  │  │    │  │  Redis   │  │    │  │  Nacos   │  │
│  │(主从)  │  │    │  │ (Cluster)│  │    │  │(注册/配置)│  │
│  └────────┘  │    │  └──────────┘  │    │  └──────────┘  │
│  ┌────────┐  │    │  ┌──────────┐  │    │  ┌──────────┐  │
│  │   ES   │  │    │  │ RocketMQ │  │    │  │  Sentinel│  │
│  │(搜索)  │  │    │  │ (消息队列)│  │    │  │ (限流)   │  │
│  └────────┘  │    │  └──────────┘  │    │  └──────────┘  │
│  ┌────────┐  │    │  ┌──────────┐  │    │  ┌──────────┐  │
│  │ MinIO  │  │    │  │  Seata   │  │    │  │  SkyWalking│  │
│  │(对象存储)│  │    │  │(分布式事务)│  │    │  │ (链路追踪) │  │
│  └────────┘  │    │  └──────────┘  │    │  └──────────┘  │
└──────────────┘    └────────────────┘    └────────────────┘
```

### 2.2 技术栈选型

| 层级 | 技术组件 | 版本 | 用途 |
|------|----------|------|------|
| 网关 | Nginx | 1.24 | 负载均衡、反向代理 |
| 网关 | Spring Cloud Gateway | 3.1.x | API 网关、路由、鉴权 |
| 开发框架 | Spring Boot | 2.7.x | 业务服务开发 |
| 微服务 | Spring Cloud Alibaba | 2021.x | 微服务治理 |
| 注册/配置 | Nacos | 2.2.x | 服务注册发现、配置中心 |
| 数据库 | MySQL | 8.0 | 关系型数据存储 |
| 缓存 | Redis | 7.0 | 分布式缓存、Session |
| 消息队列 | RocketMQ | 5.0 | 异步消息、削峰填谷 |
| 搜索引擎 | Elasticsearch | 8.x | 商品搜索、日志分析 |
| 对象存储 | MinIO | 2023 | 图片、文件存储 |
| 监控 | Prometheus + Grafana | - | 指标监控、告警 |
| 链路追踪 | SkyWalking | 9.x | 分布式链路追踪 |

### 2.3 部署架构

```
┌─────────────────────────────────────────────────────────┐
│                      生产环境 (Production)                │
│  ┌──────────────────────────────────────────────────┐   │
│  │              Kubernetes Cluster                   │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌───────────┐ │   │
│  │  │  Ingress    │  │   App Pods  │  │  Service  │ │   │
│  │  │ Controller  │  │ (Multiple)  │  │  Mesh     │ │   │
│  │  └─────────────┘  └─────────────┘  └───────────┘ │   │
│  └──────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
                            │
        ┌───────────────────┼───────────────────┐
        ▼                   ▼                   ▼
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  MySQL 主从  │     │ Redis Cluster│     │ RocketMQ   │
│  3节点集群   │     │   6节点     │     │  双主架构   │
└─────────────┘     └─────────────┘     └─────────────┘
```

---

## 3. 模块详细设计

### 3.1 用户服务 (User Service)

**服务标识**：`user-service`
**端口**：`8081`
**数据库**：`db_user`

#### 3.1.1 功能职责

- 用户注册、登录、登出
- 用户信息管理（基本信息、头像）
- 收货地址管理（增删改查、默认地址）
- 用户权限与角色管理
- 第三方登录绑定（微信、QQ、支付宝）

#### 3.1.2 核心接口

| 接口 | 方法 | 路径 | 说明 |
|------|------|------|------|
| 用户注册 | POST | /api/v1/users/register | 手机号/邮箱注册 |
| 用户登录 | POST | /api/v1/users/login | 账号密码登录 |
| 获取用户信息 | GET | /api/v1/users/profile | 获取当前登录用户信息 |
| 更新用户信息 | PUT | /api/v1/users/profile | 更新用户信息 |
| 添加收货地址 | POST | /api/v1/users/addresses | 新增收货地址 |
| 获取地址列表 | GET | /api/v1/users/addresses | 获取当前用户所有地址 |

#### 3.1.3 接口详情示例

**用户注册接口**

```yaml
接口: POST /api/v1/users/register
Content-Type: application/json

请求参数:
  username:
    type: string
    required: true
    description: 用户名，4-20位字母数字下划线
    example: "zhangsan2024"
  password:
    type: string
    required: true
    description: 密码，8-20位，包含大小写字母和数字
    example: "Pass1234!"
  phone:
    type: string
    required: true
    description: 手机号
    example: "13800138000"
  smsCode:
    type: string
    required: true
    description: 短信验证码
    example: "123456"

响应参数 (成功 200):
  code:
    type: integer
    example: 200
  message:
    type: string
    example: "注册成功"
  data:
    type: object
    properties:
      userId:
        type: long
        example: 1000001
      username:
        type: string
        example: "zhangsan2024"
      token:
        type: string
        example: "eyJhbGciOiJIUzI1NiIs..."
      expiresIn:
        type: integer
        description: token有效期(秒)
        example: 7200

响应参数 (失败 400):
  code:
    type: integer
    example: 400001
  message:
    type: string
    example: "手机号已注册"
  data:
    type: null
```

### 3.2 商品服务 (Product Service)

**服务标识**：`product-service`
**端口**：`8082`
**数据库**：`db_product`

#### 3.2.1 功能职责

- 商品类目管理（多级分类）
- SPU（标准产品单位）管理
- SKU（库存量单位）管理
- 商品上下架、价格管理
- 商品搜索（基于 Elasticsearch）
- 商品详情缓存

#### 3.2.2 核心接口

| 接口 | 方法 | 路径 | 说明 |
|------|------|------|------|
| 商品搜索 | GET | /api/v1/products/search | 关键词搜索商品 |
| 商品列表 | GET | /api/v1/products | 按分类查询商品列表 |
| 商品详情 | GET | /api/v1/products/{id} | 获取商品详情 |
| SKU库存查询 | GET | /api/v1/products/skus/{skuId}/stock | 查询 SKU 实时库存 |

### 3.3 订单服务 (Order Service)

**服务标识**：`order-service`
**端口**：`8083`
**数据库**：`db_order`

#### 3.3.1 功能职责

- 购物车管理
- 订单创建、取消、删除
- 订单状态流转（待支付→已支付→已发货→已完成）
- 订单超时自动关闭（延迟消息）
- 订单拆分（多商家场景）

#### 3.3.2 订单状态机

```
┌─────────┐    创建订单     ┌─────────┐    支付成功     ┌─────────┐
│  初始   │ ────────────→ │ 待支付  │ ────────────→ │ 已支付  │
└─────────┘               └────┬────┘               └────┬────┘
                               │                         │
                    超时未支付 │                         │ 发货
                    (30分钟)   ▼                         ▼
                         ┌─────────┐               ┌─────────┐
                         │ 已取消  │               │ 已发货  │
                         └─────────┘               └────┬────┘
                                                         │
                                                         │ 确认收货
                                                         ▼
                                                   ┌─────────┐
                                                   │ 已完成  │
                                                   └─────────┘
```

### 3.4 库存服务 (Stock Service)

**服务标识**：`stock-service`
**端口**：`8084`
**数据库**：`db_stock`

#### 3.4.1 功能职责

- 库存初始化、同步
- 库存预占/扣减/释放
- 库存流水记录
- 库存预警
- 防超卖（基于 Redis + Lua 脚本）

#### 3.4.2 库存扣减流程

```
1. 订单创建时：Redis 预占库存 (DECR)
2. 支付成功时：MySQL 实际扣减库存 (UPDATE)
3. 订单取消/超时时：Redis 释放预占 (INCR)
```

### 3.5 支付服务 (Payment Service)

**服务标识**：`payment-service`
**端口**：`8085`
**数据库**：`db_payment`

#### 3.5.1 功能职责

- 支付渠道管理（支付宝、微信、银联）
- 支付订单创建
- 支付回调处理
- 退款处理
- 对账数据生成

### 3.6 购物车服务 (Cart Service)

**服务标识**：`cart-service`
**端口**：`8086`
**存储**：Redis

#### 3.6.1 功能职责

- 购物车商品增删改查
- 购物车商品选中/取消选中
- 购物车价格计算
- 购物车合并（登录前后）
- 购物车有效期管理（30天）

---

## 4. 数据库设计

### 4.1 用户表 (t_user)

| 字段名 | 类型 | 长度 | 可空 | 默认值 | 说明 |
|--------|------|------|------|--------|------|
| id | BIGINT | - | 否 | AUTO_INCREMENT | 主键 ID |
| username | VARCHAR | 64 | 否 | - | 用户名，唯一索引 |
| password_hash | VARCHAR | 128 | 否 | - | 密码哈希（bcrypt） |
| email | VARCHAR | 128 | 是 | NULL | 邮箱，唯一索引 |
| phone | VARCHAR | 20 | 否 | - | 手机号，唯一索引 |
| nickname | VARCHAR | 64 | 是 | NULL | 昵称 |
| avatar_url | VARCHAR | 512 | 是 | NULL | 头像 URL |
| status | TINYINT | - | 否 | 1 | 状态：0-禁用，1-正常 |
| created_at | DATETIME | - | 否 | CURRENT_TIMESTAMP | 创建时间 |
| updated_at | DATETIME | - | 否 | CURRENT_TIMESTAMP | 更新时间 |

**索引设计：**
```sql
PRIMARY KEY (`id`),
UNIQUE KEY `uk_username` (`username`),
UNIQUE KEY `uk_phone` (`phone`),
UNIQUE KEY `uk_email` (`email`),
KEY `idx_status` (`status`),
KEY `idx_created_at` (`created_at`)
```

### 4.2 订单主表 (t_order)

| 字段名 | 类型 | 长度 | 可空 | 默认值 | 说明 |
|--------|------|------|------|--------|------|
| id | BIGINT | - | 否 | AUTO_INCREMENT | 主键 ID |
| order_no | VARCHAR | 32 | 否 | - | 订单编号，唯一索引 |
| user_id | BIGINT | - | 否 | - | 用户 ID，外键 |
| total_amount | DECIMAL | 12,2 | 否 | 0.00 | 订单总金额 |
| discount_amount | DECIMAL | 12,2 | 否 | 0.00 | 优惠金额 |
| pay_amount | DECIMAL | 12,2 | 否 | 0.00 | 实付金额 |
| status | TINYINT | - | 否 | 0 | 订单状态 |
| pay_type | TINYINT | - | 是 | NULL | 支付方式 |
| pay_time | DATETIME | - | 是 | NULL | 支付时间 |
| address_snapshot | JSON | - | 否 | - | 收货地址快照 |
| remark | VARCHAR | 500 | 是 | NULL | 订单备注 |
| expire_time | DATETIME | - | 否 | - | 订单过期时间 |
| created_at | DATETIME | - | 否 | CURRENT_TIMESTAMP | 创建时间 |
| updated_at | DATETIME | - | 否 | CURRENT_TIMESTAMP | 更新时间 |

**索引设计：**
```sql
PRIMARY KEY (`id`),
UNIQUE KEY `uk_order_no` (`order_no`),
KEY `idx_user_id` (`user_id`),
KEY `idx_status` (`status`),
KEY `idx_created_at` (`created_at`),
KEY `idx_expire_time` (`expire_time`)
```

### 4.3 订单明细表 (t_order_item)

| 字段名 | 类型 | 长度 | 可空 | 默认值 | 说明 |
|--------|------|------|------|--------|------|
| id | BIGINT | - | 否 | AUTO_INCREMENT | 主键 ID |
| order_id | BIGINT | - | 否 | - | 订单 ID，外键 |
| sku_id | BIGINT | - | 否 | - | SKU ID |
| spu_id | BIGINT | - | 否 | - | SPU ID |
| sku_name | VARCHAR | 255 | 否 | - | 商品名称 |
| sku_image | VARCHAR | 512 | 是 | NULL | 商品图片 |
| sku_specs | JSON | - | 是 | NULL | 规格属性(JSON) |
| price | DECIMAL | 10,2 | 否 | 0.00 | 单价 |
| quantity | INT | - | 否 | 1 | 数量 |
| subtotal | DECIMAL | 12,2 | 否 | 0.00 | 小计金额 |

### 4.4 商品 SPU 表 (t_spu)

| 字段名 | 类型 | 长度 | 可空 | 默认值 | 说明 |
|--------|------|------|------|--------|------|
| id | BIGINT | - | 否 | AUTO_INCREMENT | 主键 ID |
| spu_name | VARCHAR | 255 | 否 | - | SPU 名称 |
| category_id | BIGINT | - | 否 | - | 分类 ID |
| brand_id | BIGINT | - | 是 | NULL | 品牌 ID |
| description | TEXT | - | 是 | NULL | 商品描述 |
| main_image | VARCHAR | 512 | 否 | - | 主图 URL |
| images | JSON | - | 是 | NULL | 图片列表(JSON) |
| status | TINYINT | - | 否 | 0 | 状态：0-下架，1-上架 |
| sale_count | INT | - | 否 | 0 | 销量 |
| created_at | DATETIME | - | 否 | CURRENT_TIMESTAMP | 创建时间 |

### 4.5 商品 SKU 表 (t_sku)

| 字段名 | 类型 | 长度 | 可空 | 默认值 | 说明 |
|--------|------|------|------|--------|------|
| id | BIGINT | - | 否 | AUTO_INCREMENT | 主键 ID |
| spu_id | BIGINT | - | 否 | - | SPU ID，外键 |
| sku_code | VARCHAR | 64 | 否 | - | SKU 编码，唯一 |
| sku_specs | JSON | - | 否 | - | 规格值(JSON) |
| price | DECIMAL | 10,2 | 否 | 0.00 | 售价 |
| original_price | DECIMAL | 10,2 | 否 | 0.00 | 原价 |
| status | TINYINT | - | 否 | 1 | 状态：0-禁用，1-启用 |
| created_at | DATETIME | - | 否 | CURRENT_TIMESTAMP | 创建时间 |

### 4.6 库存表 (t_stock)

| 字段名 | 类型 | 长度 | 可空 | 默认值 | 说明 |
|--------|------|------|------|--------|------|
| id | BIGINT | - | 否 | AUTO_INCREMENT | 主键 ID |
| sku_id | BIGINT | - | 否 | - | SKU ID，唯一索引 |
| available_stock | INT | - | 否 | 0 | 可用库存 |
| locked_stock | INT | - | 否 | 0 | 锁定库存 |
| version | INT | - | 否 | 0 | 乐观锁版本号 |
| updated_at | DATETIME | - | 否 | CURRENT_TIMESTAMP | 更新时间 |

---

## 5. 缓存设计

### 5.1 Redis 数据结构

| Key 模式 | 数据类型 | 说明 | 过期时间 |
|----------|----------|------|----------|
| `user:session:{token}` | String | 用户登录会话 | 2小时 |
| `user:cart:{userId}` | Hash | 用户购物车数据 | 30天 |
| `product:detail:{spuId}` | String(JSON) | 商品详情缓存 | 1小时 |
| `product:stock:{skuId}` | String | SKU 库存缓存 | 5分钟 |
| `product:category:tree` | String(JSON) | 商品分类树 | 1天 |
| `order:token:{userId}` | String | 订单防重令牌 | 30分钟 |
| `rate:limit:{userId}:{api}` | String | 接口限流计数 | 1分钟 |

### 5.2 缓存更新策略

| 场景 | 策略 | 说明 |
|------|------|------|
| 商品详情查询 | Cache-Aside | 先查缓存，未命中再查数据库并写入缓存 |
| 库存查询 | Cache-Aside + 定时同步 | Redis 缓存，定时从数据库同步 |
| 购物车数据 | Write-Through | 直接写入 Redis，作为唯一存储 |
| 热门商品 | 预热 + 定时刷新 | 系统启动时预热，定时任务刷新 |

---

## 6. 安全设计

### 6.1 认证机制

- **Token 机制**：采用 JWT (JSON Web Token) 实现无状态认证
- **Token 结构**：Header.Payload.Signature
- **Token 有效期**：Access Token 2小时，Refresh Token 7天
- **Token 存储**：客户端存储于 HttpOnly Cookie 或 LocalStorage

### 6.2 权限控制

- **RBAC 模型**：基于角色的访问控制
- **角色定义**：超级管理员、运营人员、客服人员、普通用户
- **权限粒度**：接口级别权限控制
- **注解方式**：使用自定义注解 `@RequirePermission`

### 6.3 数据安全

| 措施 | 实现方式 |
|------|----------|
| 传输加密 | 全站 HTTPS (TLS 1.3) |
| 密码存储 | bcrypt 哈希算法，cost=12 |
| 敏感数据 | AES-256 加密存储（手机号、身份证等） |
| SQL 注入 | MyBatis 参数化查询，禁用拼接 SQL |
| XSS 防护 | 前端转义 + 后端过滤 |
| CSRF 防护 | Token 验证 + SameSite Cookie |
| 接口防重放 | 请求时间戳 + 随机数 + 签名 |

### 6.4 限流熔断

- **限流组件**：Sentinel
- **限流策略**：
  - 登录接口：10 次/分钟/用户
  - 商品搜索：100 次/分钟/用户
  - 下单接口：5 次/分钟/用户
- **熔断策略**：错误率 > 50% 且 QPS >= 5 时触发熔断，10秒后尝试恢复

---

## 7. 异常处理设计

### 7.1 异常分类

| 异常类型 | 说明 | HTTP 状态码 | 错误码范围 |
|----------|------|-------------|------------|
| 业务异常 | 业务规则校验失败 | 400 | 400xxx |
| 认证异常 | 登录态失效、Token 无效 | 401 | 401xxx |
| 权限异常 | 无操作权限 | 403 | 403xxx |
| 资源异常 | 资源不存在 | 404 | 404xxx |
| 系统异常 | 服务器内部错误 | 500 | 500xxx |
| 服务异常 | 下游服务异常 | 503 | 503xxx |

### 7.2 统一响应格式

```json
{
  "code": 400001,
  "message": "参数校验失败",
  "data": null,
  "traceId": "trc_a1b2c3d4e5f6",
  "timestamp": 1698374400000
}
```

### 7.3 全局异常处理

```java
@RestControllerAdvice
public class GlobalExceptionHandler {
    
    @ExceptionHandler(BusinessException.class)
    public Result handleBusinessException(BusinessException e) {
        return Result.fail(e.getCode(), e.getMessage());
    }
    
    @ExceptionHandler(MethodArgumentNotValidException.class)
    public Result handleValidationException(MethodArgumentNotValidException e) {
        return Result.fail(400001, "参数校验失败: " + e.getMessage());
    }
    
    @ExceptionHandler(Exception.class)
    public Result handleException(Exception e) {
        log.error("系统异常", e);
        return Result.fail(500001, "系统繁忙，请稍后重试");
    }
}
```

---

## 8. 日志与监控设计

### 8.1 日志规范

| 日志级别 | 使用场景 | 输出位置 |
|----------|----------|----------|
| ERROR | 系统错误、业务异常 | 日志文件 + 告警 |
| WARN | 潜在问题、非预期情况 | 日志文件 |
| INFO | 关键业务流程记录 | 日志文件 |
| DEBUG | 调试信息 | 开发环境 |

**日志格式**：
```
2024-03-15 14:32:18.345 [http-nio-8081-exec-5] INFO  c.m.u.s.impl.UserServiceImpl - 
[trc_abc123] [uid=1000001] 用户登录成功, username=zhangsan
```

### 8.2 监控指标

| 指标类型 | 指标名称 | 告警阈值 |
|----------|----------|----------|
| 系统指标 | CPU 使用率 | > 80% |
| 系统指标 | 内存使用率 | > 85% |
| 系统指标 | 磁盘使用率 | > 85% |
| 应用指标 | JVM 堆内存 | > 80% |
| 应用指标 | GC 次数 | > 10次/分钟 |
| 业务指标 | 接口错误率 | > 5% |
| 业务指标 | 接口响应时间 | P99 > 2s |
| 业务指标 | 订单创建成功率 | < 99% |

### 8.3 链路追踪

- **组件**：SkyWalking
- **追踪维度**：Trace ID、Span ID、服务名、接口名、耗时
- **采样率**：生产环境 10%，测试环境 100%

---

## 9. 接口设计规范

### 9.1 RESTful API 规范

- **URL 规范**：全小写，使用连字符 `-` 分隔单词
- **版本控制**：URL 中包含版本号，如 `/api/v1/users`
- **HTTP 方法**：
  - GET：查询资源
  - POST：创建资源
  - PUT：更新资源（全量）
  - PATCH：更新资源（部分）
  - DELETE：删除资源

### 9.2 分页规范

```
请求参数：
  page: 当前页码，从 1 开始
  size: 每页大小，默认 20，最大 100

响应格式：
{
  "code": 200,
  "data": {
    "list": [...],
    "total": 1000,
    "page": 1,
    "size": 20,
    "pages": 50
  }
}
```

### 9.3 错误码规范

| 错误码 | 说明 |
|--------|------|
| 200 | 成功 |
| 400xxx | 客户端错误（参数、业务规则） |
| 401xxx | 认证错误 |
| 403xxx | 权限错误 |
| 404xxx | 资源不存在 |
| 500xxx | 服务端错误 |
| 503xxx | 服务不可用 |

---

**文档结束**

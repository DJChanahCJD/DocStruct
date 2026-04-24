# NebulaLab 实验编排平台 API 文档 v1.8

## 1. 概述

NebulaLab API 用于管理科研实验流程，包括实验项目、样本、设备、任务编排、数据采集、结果分析与审计日志。

Base URL:

```http
https://api.nebulalab.example.com/v1
```

数据格式：

```http
Content-Type: application/json
Accept: application/json
```

---

## 2. 鉴权

### 2.1 获取访问令牌

```http
POST /auth/token
```

请求体：

```json
{
  "client_id": "lab-client-001",
  "client_secret": "mock-secret",
  "grant_type": "client_credentials"
}
```

响应：

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "Bearer",
  "expires_in": 7200
}
```

后续请求头：

```http
Authorization: Bearer <access_token>
```

---

## 3. 错误格式

所有错误统一返回：

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid request payload",
    "details": [
      {
        "field": "sample.temperature",
        "reason": "must be between -80 and 120"
      }
    ],
    "trace_id": "trc_9f7a21c88"
  }
}
```

常见错误码：

| HTTP 状态码 | code                      | 说明      |
| -------- | ------------------------- | ------- |
| 400      | VALIDATION_ERROR          | 参数校验失败  |
| 401      | UNAUTHORIZED              | 未认证     |
| 403      | FORBIDDEN                 | 权限不足    |
| 404      | RESOURCE_NOT_FOUND        | 资源不存在   |
| 409      | CONFLICT                  | 状态冲突    |
| 422      | EXPERIMENT_RULE_VIOLATION | 实验规则不满足 |
| 429      | RATE_LIMITED              | 请求过于频繁  |
| 500      | INTERNAL_ERROR            | 服务内部错误  |

---

# 4. 实验项目 Project API

## 4.1 创建实验项目

```http
POST /projects
```

请求体：

```json
{
  "name": "高温催化剂稳定性实验",
  "code": "CAT-HT-2026-001",
  "owner": "researcher_a",
  "tags": ["catalyst", "thermal", "long-running"],
  "metadata": {
    "department": "materials",
    "priority": "high",
    "funding_id": "FUND-2026-X91"
  }
}
```

响应：

```json
{
  "project_id": "prj_01HY8ZC6XQ",
  "name": "高温催化剂稳定性实验",
  "code": "CAT-HT-2026-001",
  "status": "draft",
  "created_at": "2026-04-24T10:15:00Z"
}
```

---

## 4.2 查询项目列表

```http
GET /projects?status=active&tag=catalyst&page=1&page_size=20
```

响应：

```json
{
  "items": [
    {
      "project_id": "prj_01HY8ZC6XQ",
      "name": "高温催化剂稳定性实验",
      "status": "active",
      "created_at": "2026-04-24T10:15:00Z"
    }
  ],
  "pagination": {
    "page": 1,
    "page_size": 20,
    "total": 1
  }
}
```

---

# 5. 样本 Sample API

## 5.1 批量创建样本

```http
POST /projects/{project_id}/samples/batch
```

请求体：

```json
{
  "samples": [
    {
      "label": "CAT-A-001",
      "type": "powder",
      "mass_mg": 125.5,
      "storage": {
        "temperature_c": -20,
        "container": "sealed_vial",
        "location": "Freezer-A3"
      },
      "properties": {
        "purity": 0.982,
        "particle_size_nm": 85
      }
    },
    {
      "label": "CAT-A-002",
      "type": "powder",
      "mass_mg": 118.2,
      "storage": {
        "temperature_c": -20,
        "container": "sealed_vial",
        "location": "Freezer-A3"
      },
      "properties": {
        "purity": 0.976,
        "particle_size_nm": 91
      }
    }
  ]
}
```

响应：

```json
{
  "created": 2,
  "sample_ids": [
    "smp_01HYA1A01",
    "smp_01HYA1A02"
  ]
}
```

---

## 5.2 获取样本详情

```http
GET /samples/{sample_id}
```

响应：

```json
{
  "sample_id": "smp_01HYA1A01",
  "label": "CAT-A-001",
  "type": "powder",
  "mass_mg": 125.5,
  "status": "available",
  "storage": {
    "temperature_c": -20,
    "container": "sealed_vial",
    "location": "Freezer-A3"
  },
  "properties": {
    "purity": 0.982,
    "particle_size_nm": 85
  }
}
```

---

# 6. 设备 Device API

## 6.1 注册设备

```http
POST /devices
```

请求体：

```json
{
  "name": "Thermo Reactor 9000",
  "device_type": "reactor",
  "serial_number": "TR9K-2026-041",
  "capabilities": {
    "temperature_range_c": [-50, 1200],
    "pressure_range_bar": [0, 80],
    "supported_modes": ["isothermal", "ramp", "pulse"]
  },
  "calibration": {
    "last_calibrated_at": "2026-03-12T08:00:00Z",
    "expires_at": "2026-09-12T08:00:00Z"
  }
}
```

响应：

```json
{
  "device_id": "dev_01HYB2K91",
  "name": "Thermo Reactor 9000",
  "status": "idle"
}
```

---

## 6.2 查询设备状态

```http
GET /devices/{device_id}/status
```

响应：

```json
{
  "device_id": "dev_01HYB2K91",
  "status": "running",
  "current_task_id": "tsk_01HYC0A91",
  "metrics": {
    "temperature_c": 748.6,
    "pressure_bar": 12.4,
    "gas_flow_sccm": 55.2
  },
  "updated_at": "2026-04-24T11:01:32Z"
}
```

---

# 7. 实验任务 Experiment Task API

## 7.1 创建实验任务

```http
POST /experiments
```

请求体：

```json
{
  "project_id": "prj_01HY8ZC6XQ",
  "name": "750°C 稳定性测试",
  "sample_ids": ["smp_01HYA1A01", "smp_01HYA1A02"],
  "device_id": "dev_01HYB2K91",
  "protocol": {
    "mode": "ramp",
    "steps": [
      {
        "step_name": "preheat",
        "target_temperature_c": 200,
        "duration_min": 15,
        "pressure_bar": 1.0
      },
      {
        "step_name": "ramp_to_target",
        "start_temperature_c": 200,
        "target_temperature_c": 750,
        "ramp_rate_c_per_min": 10
      },
      {
        "step_name": "hold",
        "target_temperature_c": 750,
        "duration_min": 360,
        "pressure_bar": 12,
        "gas": {
          "type": "N2",
          "flow_sccm": 50
        }
      },
      {
        "step_name": "cooldown",
        "target_temperature_c": 25,
        "max_rate_c_per_min": 15
      }
    ]
  },
  "constraints": {
    "max_temperature_deviation_c": 3,
    "max_pressure_deviation_bar": 0.5,
    "auto_abort_on_violation": true
  }
}
```

响应：

```json
{
  "experiment_id": "exp_01HYC0A91",
  "status": "scheduled",
  "estimated_duration_min": 430,
  "created_at": "2026-04-24T11:10:00Z"
}
```

---

## 7.2 启动实验

```http
POST /experiments/{experiment_id}/start
```

响应：

```json
{
  "experiment_id": "exp_01HYC0A91",
  "status": "running",
  "started_at": "2026-04-24T11:12:00Z"
}
```

---

## 7.3 暂停实验

```http
POST /experiments/{experiment_id}/pause
```

请求体：

```json
{
  "reason": "operator_inspection"
}
```

响应：

```json
{
  "experiment_id": "exp_01HYC0A91",
  "status": "paused",
  "paused_at": "2026-04-24T12:03:21Z"
}
```

---

## 7.4 终止实验

```http
POST /experiments/{experiment_id}/abort
```

请求体：

```json
{
  "reason": "pressure exceeded safety threshold",
  "operator": "researcher_a"
}
```

响应：

```json
{
  "experiment_id": "exp_01HYC0A91",
  "status": "aborted",
  "aborted_at": "2026-04-24T12:08:00Z"
}
```

---

# 8. 数据采集 Data API

## 8.1 上传传感器数据

```http
POST /experiments/{experiment_id}/data-points
```

请求体：

```json
{
  "source": "device_sensor",
  "points": [
    {
      "timestamp": "2026-04-24T11:13:00Z",
      "temperature_c": 203.2,
      "pressure_bar": 1.01,
      "gas_flow_sccm": 49.8,
      "signal_mv": 12.44
    },
    {
      "timestamp": "2026-04-24T11:14:00Z",
      "temperature_c": 214.7,
      "pressure_bar": 1.02,
      "gas_flow_sccm": 50.1,
      "signal_mv": 12.51
    }
  ]
}
```

响应：

```json
{
  "accepted": 2,
  "rejected": 0,
  "batch_id": "bat_01HYD91QW"
}
```

---

## 8.2 查询实验数据

```http
GET /experiments/{experiment_id}/data-points?from=2026-04-24T11:00:00Z&to=2026-04-24T12:00:00Z&interval=1m
```

响应：

```json
{
  "experiment_id": "exp_01HYC0A91",
  "interval": "1m",
  "points": [
    {
      "timestamp": "2026-04-24T11:13:00Z",
      "temperature_c": 203.2,
      "pressure_bar": 1.01,
      "gas_flow_sccm": 49.8,
      "signal_mv": 12.44
    }
  ]
}
```

---

# 9. 分析 Analysis API

## 9.1 创建分析任务

```http
POST /experiments/{experiment_id}/analysis-jobs
```

请求体：

```json
{
  "analysis_type": "stability_curve",
  "parameters": {
    "baseline_window_min": 10,
    "smoothing_method": "savitzky_golay",
    "smoothing_window": 9,
    "outlier_detection": {
      "enabled": true,
      "method": "z_score",
      "threshold": 3
    }
  }
}
```

响应：

```json
{
  "analysis_job_id": "ana_01HYE2X90",
  "status": "queued",
  "created_at": "2026-04-24T13:30:00Z"
}
```

---

## 9.2 查询分析结果

```http
GET /analysis-jobs/{analysis_job_id}
```

响应：

```json
{
  "analysis_job_id": "ana_01HYE2X90",
  "status": "completed",
  "result": {
    "stability_score": 0.934,
    "degradation_rate_per_hour": 0.012,
    "outliers_detected": 4,
    "summary": "Sample remained stable under 750°C for 6 hours.",
    "artifacts": [
      {
        "type": "chart",
        "url": "https://files.nebulalab.example.com/artifacts/ana_01HYE2X90_curve.png"
      },
      {
        "type": "csv",
        "url": "https://files.nebulalab.example.com/artifacts/ana_01HYE2X90_points.csv"
      }
    ]
  }
}
```

---

# 10. 审计日志 Audit API

## 10.1 查询审计日志

```http
GET /audit-logs?resource_type=experiment&resource_id=exp_01HYC0A91
```

响应：

```json
{
  "items": [
    {
      "log_id": "log_01HYF9K2A",
      "actor": "researcher_a",
      "action": "experiment.start",
      "resource_type": "experiment",
      "resource_id": "exp_01HYC0A91",
      "timestamp": "2026-04-24T11:12:00Z",
      "ip": "10.1.4.23"
    }
  ]
}
```

---

# 11. Webhook

## 11.1 注册 Webhook

```http
POST /webhooks
```

请求体：

```json
{
  "url": "https://client.example.com/hooks/nebulalab",
  "events": [
    "experiment.started",
    "experiment.completed",
    "experiment.aborted",
    "analysis.completed"
  ],
  "secret": "client-webhook-secret"
}
```

响应：

```json
{
  "webhook_id": "whk_01HYZ9KQ2",
  "status": "active"
}
```

Webhook 示例：

```json
{
  "event_id": "evt_01HZ0001",
  "event_type": "experiment.completed",
  "occurred_at": "2026-04-24T18:30:00Z",
  "data": {
    "experiment_id": "exp_01HYC0A91",
    "project_id": "prj_01HY8ZC6XQ",
    "status": "completed"
  }
}
```

---

# 12. 限流规则

| 接口类型       | 限制                 |
| ---------- | ------------------ |
| 鉴权接口       | 30 次 / 分钟          |
| 查询接口       | 600 次 / 分钟         |
| 写入接口       | 120 次 / 分钟         |
| 数据上传接口     | 10,000 points / 分钟 |
| Webhook 注册 | 20 次 / 小时          |

超过限制返回：

```json
{
  "error": {
    "code": "RATE_LIMITED",
    "message": "Too many requests",
    "retry_after_seconds": 30
  }
}
```

# 智能文档系统 API

**Base URL**: `https://api.docstruct.io/v1`

---

## 文档管理

### 上传文档

```http
POST /documents
Content-Type: multipart/form-data
Authorization: Bearer {token}
```

**参数**:
- `file`: 文档文件 (PDF/Word/Markdown)
- `doc_type`: 文档类型 (srs/api/design)

**响应**:

```json
{
  "document_id": "doc_abc123",
  "status": "processing"
}
```

### 获取文档

```http
GET /documents/{document_id}
Authorization: Bearer {token}
```

---

## 搜索服务

### 全文搜索

```http
POST /search
Authorization: Bearer {token}
```

**请求体**:

```json
{
  "query": "用户注册",
  "filters": { "doc_type": ["srs"] }
}
```

---

## 错误码

| 码 | 说明 |
|--|--|
| 400 | 参数错误 |
| 401 | 未授权 |
| 404 | 资源不存在 |
| 500 | 服务器错误 |

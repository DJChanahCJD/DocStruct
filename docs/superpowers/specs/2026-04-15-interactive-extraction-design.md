# 人在环中交互式提取 — 设计文档

**日期**：2026-04-15  
**状态**：已批准，待实现

---

## 背景与目标

当前提取流程为一次性线性：上传 → 自动分类 → 自动提取 → 保存，用户无法干预提取过程。

目标：在 `doc-preview-panel` 的 JSON 视图中，支持用户对初步提取结果发起多轮交互式重提取——可全量覆盖，也可针对单个字段修正，输入自由补充指示，查看新旧对比后手动确认保存。

---

## 范围

| 层 | 改动文件 | 说明 |
|----|---------|------|
| 后端 | `core/extractor.py` | +1 函数 `re_extract_with_instruction` |
| 后端 | `schemas/dto.py` | +2 schema：`ReExtractRequest`、`ReExtractResponse` |
| 后端 | `main.py` | +1 端点 `POST /api/documents/{doc_id}/re-extract` |
| 前端 | `frontend/src/lib/api.ts` | +1 函数 `reExtractDocument` |
| 前端 | `frontend/src/hooks/use-api.ts` | +1 hook `useReExtract` |
| 前端 | `frontend/src/components/doc-preview-panel.tsx` | 小改：增加"重新提取"按钮，集成子组件 |
| 前端 | `frontend/src/components/re-extract-panel.tsx` | 新增：配置 + 执行 + diff 子组件 |

不涉及数据库 schema 变更，不影响现有上传/问答流程。

---

## 后端设计

### 新增 API 端点

```
POST /api/documents/{doc_id}/re-extract
```

**请求体 `ReExtractRequest`：**
```json
{
  "scope": "full" | "field",
  "field_key": "steps",           // scope=field 时必填，否则忽略
  "instruction": "重点提取每个步骤的前置条件"  // 可选
}
```

`field_key` 在 `scope=field` 时由 model validator 强制校验不为空。

**响应体 `ReExtractResponse`：**
```json
{
  "result": { ...新提取的 JSON... },
  "scope": "full" | "field",
  "field_key": "steps"
}
```

**端点不写库**——仅返回 LLM 提取结果，由前端用户确认后调用现有 `PATCH /api/documents/{doc_id}` 保存。

---

### `re_extract_with_instruction()` 函数

位置：`core/extractor.py`

```python
async def re_extract_with_instruction(
    parsed_content: str,
    doc_type: str,
    scope: str,           # "full" | "field"
    field_key: str | None,
    instruction: str | None,
    llm_model: str | None = None,
) -> dict:
```

两个分支：

**`scope=full`**：在现有 system prompt 末尾追加 `instruction`，直接复用 `extract_structure_with_meta()` 的调用路径（含分块降级逻辑），零重复代码。

**`scope=field`**：构造轻量专用 prompt：

```
你是文档结构提取助手。
从以下文档中提取字段「{field_key}」的内容，以 JSON 格式返回：{"{field_key}": ...}
[如有 instruction 则追加]

文档内容：
{parsed_content[:extraction_single_max_chars]}
```

返回 `{field_key: value}`，前端可将其 merge 到现有 `extracted_data`。

---

## 前端设计

### 状态机

JSON 标签页内的交互状态（在 `doc-preview-panel.tsx` 中管理顶层状态，`re-extract-panel.tsx` 管理子状态）：

```
idle
  → [点击"重新提取"] → configuring
    → [点击"执行"] → extracting
      → [成功] → reviewing
        → [点击"应用"] → saving → idle（数据已更新）
        → [点击"放弃"] → idle（数据不变）
      → [失败] → configuring（带错误提示）
    → [点击"取消"] → idle
```

### UI 布局（JSON 标签页，从上到下）

```
┌─────────────────────────────────────────┐
│ [当前 extracted_data，只读 pre 块]       │
│                           [编辑] [重新提取] │
├─────────────────────────────────────────┤
│ ▼ 重新提取面板（configuring 状态）       │
│  范围: [全量 ▼] / [指定字段: steps ▼]   │
│  补充指示: [___________________________] │
│                      [取消] [执行提取]   │
├─────────────────────────────────────────┤
│ ▼ 对比结果（reviewing 状态）            │
│  旧值（红色高亮变动的 key）              │
│  新值（绿色高亮变动的 key）              │
│                      [放弃] [应用并保存] │
└─────────────────────────────────────────┘
```

### `re-extract-panel.tsx` 组件接口

```typescript
interface ReExtractPanelProps {
  docId: number;
  currentData: Record<string, unknown>;
  onApply: (newData: Record<string, unknown>) => Promise<void>;
  onCancel: () => void;
}
```

对外只通过 `onApply` / `onCancel` 通信，内部封装全部子状态。

### Diff 计算（key 级别）

```typescript
type DiffStatus = "added" | "removed" | "modified" | "unchanged";

function computeDiff(
  oldData: Record<string, unknown>,
  newData: Record<string, unknown>,
  fieldKey?: string  // scope=field 时只比这一个 key
): Record<string, DiffStatus>
```

遍历两侧顶层 key，用 `JSON.stringify` 比较值，返回每个 key 的状态，渲染时据此着色。不引入外部 diff 库。

`scope=field` 的 `onApply`：将新结果 merge 到现有 `currentData`（`{ ...currentData, [field_key]: result[field_key] }`），再调用 `updateDoc.mutateAsync()`。

### `doc-preview-panel.tsx` 改动

- JSON 只读视图右上角：**[编辑] [重新提取]** 两按钮并列（原 [编辑] 保留，两者互斥）
- 点击"重新提取"时：若处于编辑状态则先清空，渲染 `<ReExtractPanel>` 在 pre 块下方
- `onApply`：调用 `updateDoc.mutateAsync({ extracted_data: mergedData })`，成功后回到 idle
- `onCancel`：直接回到 idle

---

## 错误处理

| 场景 | 处理方式 |
|------|---------|
| LLM 返回非合法 JSON | `re_extract_with_instruction` 抛出异常，端点返回 400，前端在 configuring 状态展示错误提示 |
| 网络超时 | 前端 `useMutation` onError 回调，回到 configuring 带错误提示 |
| `scope=field` 但 `field_key` 为空 | dto model validator 在请求入口拦截，返回 422 |
| 文档不存在或无原文 | 端点返回 404 |

---

## 不在范围内

- 提取历史记录的持久化（不存库）
- 流式响应（同步返回即可）
- 分类（doc_type）的重新确认
- 向量索引的自动更新（用户保存后由现有 PATCH 逻辑触发）

from __future__ import annotations

from copy import deepcopy
from typing import Any, Literal, cast

from core.extractor import re_extract_with_instruction
from schemas.models import DocType


NodeType = Literal["meta", "item"]

META_FIELD_ORDER = ["title", "summary", "version", "issue_id", "status", "severity", "expected", "actual", "extra"]
GROUP_LABELS = {
    DocType.SRS: "需求项",
    DocType.API: "接口项",
    DocType.DESIGN: "模块项",
    DocType.TEST: "测试项",
    DocType.MANUAL: "章节项",
}
ITEM_TYPE_LABELS = {
    DocType.SRS: "requirement",
    DocType.API: "endpoint",
    DocType.DESIGN: "module",
    DocType.TEST: "test_case",
    DocType.MANUAL: "section",
}
FIELD_LABELS = {
    "title": "标题",
    "summary": "摘要",
    "version": "版本",
    "extra": "补充信息",
    "id": "ID",
    "description": "描述",
    "priority": "优先级",
    "method": "Method",
    "path": "Path",
    "request": "请求",
    "response": "响应",
    "base_url": "Base URL",
    "name": "名称",
    "architecture": "架构",
    "test_stage": "测试阶段",
    "steps": "步骤",
    "expected": "期望结果",
    "actual": "实际结果",
    "status": "状态",
    "severity": "严重级别",
    "issue_id": "问题编号",
    "content": "内容",
}


def _field_label(field_key: str) -> str:
    return FIELD_LABELS.get(field_key, field_key.replace("_", " ").title())


def _value_type(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return "number"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    return "string"


def _sanitize_token(value: str) -> str:
    sanitized = "".join(ch.lower() if ch.isalnum() else "-" for ch in value.strip())
    sanitized = "-".join(filter(None, sanitized.split("-")))
    return sanitized or "item"


def _ordered_keys(data: dict[str, Any], preferred: list[str] | None = None) -> list[str]:
    preferred = preferred or []
    remaining = [key for key in data.keys() if key not in preferred]
    return [key for key in preferred if key in data] + sorted(remaining)


def _build_meta_fields(doc_type: DocType, extracted_data: dict[str, Any]) -> list[dict[str, Any]]:
    preferred = list(META_FIELD_ORDER)
    if doc_type == DocType.API:
        preferred.insert(3, "base_url")
    if doc_type == DocType.DESIGN:
        preferred.insert(3, "architecture")
    if doc_type == DocType.TEST:
        preferred.insert(3, "test_stage")

    reserved = {"doc_type", "items", "steps"}
    fields: list[dict[str, Any]] = []
    for key in _ordered_keys(extracted_data, preferred):
        if key in reserved:
            continue
        fields.append(
            {
                "node_id": f"meta:{key}",
                "field_key": key,
                "label": _field_label(key),
                "value": deepcopy(extracted_data.get(key)),
                "value_type": _value_type(extracted_data.get(key)),
                "editable": True,
            }
        )
    return fields


def _item_identifier(doc_type: DocType, group_key: str, item: Any, index: int) -> str:
    if isinstance(item, dict):
        if item.get("id"):
            return f"{group_key}:id:{_sanitize_token(str(item['id']))}"
        if group_key == "items" and doc_type == DocType.API:
            method = str(item.get("method") or "").strip()
            path = str(item.get("path") or "").strip()
            if method and path:
                return f"{group_key}:endpoint:{_sanitize_token(f'{method}-{path}')}"
        if item.get("issue_id"):
            return f"{group_key}:issue:{_sanitize_token(str(item['issue_id']))}"
        if item.get("name"):
            return f"{group_key}:name:{_sanitize_token(str(item['name']))}"
    return f"{group_key}:idx:{index}"


def _item_title(item: Any, index: int) -> str:
    if isinstance(item, dict):
        for key in ("title", "name", "path", "id"):
            value = item.get(key)
            if value:
                return str(value)
    if isinstance(item, str) and item.strip():
        return item.strip()[:80]
    return f"Item {index + 1}"


def _item_summary(item: Any) -> str | None:
    if isinstance(item, dict):
        for key in ("summary", "description", "content", "expected", "response"):
            value = item.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return None


def _item_fields(node_id: str, item: Any, preferred: list[str] | None = None) -> list[dict[str, Any]]:
    if isinstance(item, dict):
        return [
            {
                "node_id": node_id,
                "field_key": key,
                "label": _field_label(key),
                "value": deepcopy(item.get(key)),
                "value_type": _value_type(item.get(key)),
                "editable": True,
            }
            for key in _ordered_keys(item, preferred or ["id", "title", "name", "description", "summary"])
        ]
    return [
        {
            "node_id": node_id,
            "field_key": "content",
            "label": _field_label("content"),
            "value": deepcopy(item),
            "value_type": _value_type(item),
            "editable": True,
        }
    ]


def _build_groups(doc_type: DocType, extracted_data: dict[str, Any]) -> list[dict[str, Any]]:
    groups: list[dict[str, Any]] = []

    items = extracted_data.get("items")
    if isinstance(items, list):
        field_order = {
            DocType.SRS: ["id", "title", "description", "priority"],
            DocType.API: ["method", "path", "summary", "request", "response"],
            DocType.DESIGN: ["name", "description"],
            DocType.TEST: ["id", "title", "steps", "expected", "actual", "status"],
            DocType.MANUAL: ["title", "content"],
        }.get(doc_type)
        groups.append(
            {
                "group_key": "items",
                "label": GROUP_LABELS.get(doc_type, "条目"),
                "item_type": ITEM_TYPE_LABELS.get(doc_type, "item"),
                "items": [
                    {
                        "node_id": item_node_id,
                        "title": _item_title(item, index),
                        "summary": _item_summary(item),
                        "order": index,
                        "fields": _item_fields(item_node_id, item, field_order),
                    }
                    for index, item in enumerate(items)
                    for item_node_id in [_item_identifier(doc_type, "items", item, index)]
                ],
            }
        )

    if doc_type == DocType.ISSUE and isinstance(extracted_data.get("steps"), list):
        groups.append(
            {
                "group_key": "steps",
                "label": "复现步骤",
                "item_type": "step",
                "items": [
                    {
                        "node_id": f"steps:idx:{index}",
                        "title": f"步骤 {index + 1}",
                        "summary": None,
                        "order": index,
                        "fields": _item_fields(f"steps:idx:{index}", step),
                    }
                    for index, step in enumerate(cast(list[Any], extracted_data["steps"]))
                ],
            }
        )

    return groups


def build_review_model(doc_type: DocType, extracted_data: dict[str, Any] | None) -> dict[str, Any]:
    source = deepcopy(extracted_data) if isinstance(extracted_data, dict) else {}
    return {
        "doc_type": doc_type.value,
        "meta_fields": _build_meta_fields(doc_type, source),
        "groups": _build_groups(doc_type, source),
    }


def _locate_item_ref(doc_type: DocType, extracted_data: dict[str, Any], node_id: str) -> dict[str, Any] | None:
    for group in _build_groups(doc_type, extracted_data):
        for item in group["items"]:
            if item["node_id"] == node_id:
                return {
                    "node_type": "item",
                    "group_key": group["group_key"],
                    "index": item["order"],
                    "node_id": node_id,
                    "label": group["label"],
                }
    return None


def locate_node_ref(doc_type: DocType, extracted_data: dict[str, Any], node_id: str) -> dict[str, Any] | None:
    if node_id.startswith("meta:"):
        field_key = node_id.split(":", 1)[1]
        if field_key in extracted_data:
            return {"node_type": "meta", "field_key": field_key, "node_id": node_id, "label": _field_label(field_key)}
        return None
    return _locate_item_ref(doc_type, extracted_data, node_id)


def apply_review_changes(
    doc_type: DocType,
    extracted_data: dict[str, Any] | None,
    changes: list[dict[str, Any]],
) -> dict[str, Any]:
    source = deepcopy(extracted_data) if isinstance(extracted_data, dict) else {}
    grouped: dict[str, list[dict[str, Any]]] = {}
    for change in changes:
        grouped.setdefault(str(change["node_id"]), []).append(change)

    refs: dict[str, dict[str, Any]] = {}
    for node_id in grouped:
        ref = locate_node_ref(doc_type, source, node_id)
        if ref is None:
            raise ValueError(f"未找到目标节点: {node_id}")
        refs[node_id] = ref

    for node_id, node_changes in grouped.items():
        ref = refs[node_id]
        if ref["node_type"] == "meta":
            for change in node_changes:
                source[str(change["field_key"])] = deepcopy(change["value"])
            continue

        group_key = str(ref["group_key"])
        index = int(ref["index"])
        target_group = source.get(group_key)
        if not isinstance(target_group, list) or index >= len(target_group):
            raise ValueError(f"节点已失效: {node_id}")

        target_item = deepcopy(target_group[index])
        for change in node_changes:
            field_key = str(change["field_key"])
            value = deepcopy(change["value"])
            if isinstance(target_item, dict):
                target_item[field_key] = value
            elif field_key == "content":
                target_item = value
            else:
                raise ValueError(f"节点 {node_id} 不支持字段 {field_key}")
        target_group[index] = target_item

    return source


def get_review_node(
    doc_type: DocType,
    extracted_data: dict[str, Any] | None,
    node_id: str,
) -> dict[str, Any]:
    source = deepcopy(extracted_data) if isinstance(extracted_data, dict) else {}
    ref = locate_node_ref(doc_type, source, node_id)
    if ref is None:
        raise ValueError(f"未找到目标节点: {node_id}")

    if ref["node_type"] == "meta":
        field_key = str(ref["field_key"])
        value = source.get(field_key)
        return {
            "node_id": node_id,
            "node_type": "meta",
            "label": _field_label(field_key),
            "group_key": None,
            "title": _field_label(field_key),
            "fields": [
                {
                    "node_id": node_id,
                    "field_key": field_key,
                    "label": _field_label(field_key),
                    "value": deepcopy(value),
                    "value_type": _value_type(value),
                    "editable": True,
                }
            ],
        }

    review_model = build_review_model(doc_type, source)
    for group in review_model["groups"]:
        for item in group["items"]:
            if item["node_id"] == node_id:
                return {
                    "node_id": node_id,
                    "node_type": "item",
                    "label": group["label"],
                    "group_key": group["group_key"],
                    "title": item["title"],
                    "fields": deepcopy(item["fields"]),
                }
    raise ValueError(f"未找到目标节点: {node_id}")


async def preview_reextract_node(
    *,
    doc_type: DocType,
    extracted_data: dict[str, Any] | None,
    parsed_content: str,
    response_model: type[Any],
    node_id: str,
    instruction: str | None,
    llm_model: str | None,
    use_rag: bool,
    doc_id: int | None = None,
) -> dict[str, Any]:
    current_data = deepcopy(extracted_data) if isinstance(extracted_data, dict) else {}
    ref = locate_node_ref(doc_type, current_data, node_id)
    if ref is None:
        raise ValueError(f"未找到目标节点: {node_id}")

    if ref["node_type"] == "meta":
        field_key = str(ref["field_key"])
        result = await re_extract_with_instruction(
            parsed_content=parsed_content,
            response_model=response_model,
            scope="field",
            field_key=field_key,
            instruction=instruction,
            llm_model=llm_model,
            use_rag=use_rag,
            doc_id=doc_id,
        )
        candidate = deepcopy(current_data)
        candidate[field_key] = result[field_key]
        return get_review_node(doc_type, candidate, node_id)

    group_key = str(ref["group_key"])
    index = int(ref["index"])
    item_hint = f"仅重新提取字段 `{group_key}` 中的第 {index + 1} 项，并尽量保持其他项不变。"
    if instruction:
        item_hint = f"{item_hint}\n用户补充指示：{instruction}"

    result = await re_extract_with_instruction(
        parsed_content=parsed_content,
        response_model=response_model,
        scope="field",
        field_key=group_key,
        instruction=item_hint,
        llm_model=llm_model,
        use_rag=use_rag,
        doc_id=doc_id,
    )
    candidate = deepcopy(current_data)
    candidate[group_key] = result[group_key]
    try:
        return get_review_node(doc_type, candidate, node_id)
    except ValueError:
        group_items = build_review_model(doc_type, candidate)["groups"]
        for group in group_items:
            if group["group_key"] != group_key:
                continue
            if index >= len(group["items"]):
                break
            item = group["items"][index]
            return {
                "node_id": item["node_id"],
                "node_type": "item",
                "label": group["label"],
                "group_key": group["group_key"],
                "title": item["title"],
                "fields": deepcopy(item["fields"]),
            }
        raise

from __future__ import annotations

import json
import re
from typing import Any

from pydantic import BaseModel

from schemas.models import BaseNode, DocumentElement, DocumentIR


# Legacy slots for backward compatibility
OBJECT_SLOTS = ("entities", "processes", "requirements", "interfaces", "artifacts")

# Non-slot fields to exclude from dynamic discovery.
# Keep in sync with frontend/src/lib/evidence.ts discoverSlotConfigs knownKeys.
_NON_SLOT_FIELDS = {"doc_type", "title", "version", "extra", "evidence", "base_url", "test_stage"}


def discover_slots(model: type[BaseModel]) -> list[str]:
    """从 response_model 动态发现抽取槽位（list[BaseNode子类] 类型的字段）。"""
    slots: list[str] = []
    for field_name, field_info in model.model_fields.items():
        if field_name in _NON_SLOT_FIELDS:
            continue
        annotation = field_info.annotation
        if annotation is None:
            continue
        origin = getattr(annotation, "__origin__", None)
        if origin is not list:
            continue
        args = getattr(annotation, "__args__", ())
        if not args:
            continue
        item_type = args[0]
        if isinstance(item_type, type) and issubclass(item_type, BaseNode):
            slots.append(field_name)
    if not slots:
        return list(OBJECT_SLOTS)  # fallback
    return slots


def _generate_prefix(slot: str) -> str:
    """从槽位名生成 ID 前缀。"""
    prefix_map = {
        "entities": "ENT", "interfaces": "INT",
        "functional_requirements": "FREQ", "non_functional_requirements": "NFR",
        "endpoints": "EP", "schemas": "SCH", "auth": "AUTH",
        "modules": "MOD", "decisions": "DEC",
        "test_cases": "TC", "test_steps": "TS", "defects": "DEF",
        "procedures": "PROC", "ui_elements": "UI", "notes": "NOTE",
        "symptoms": "SYM", "reproduction_steps": "RST", "environment": "ENV",
        "processes": "PROC", "requirements": "REQ", "artifacts": "ART",
    }
    return prefix_map.get(slot, slot[:4].upper())


def reduce_extraction_results(
    *,
    doc_type: str,
    title: str | None,
    chunk_results: list[dict[str, Any]],
    document_ir: DocumentIR,
    response_model: type[BaseModel] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    slots = discover_slots(response_model) if response_model else list(OBJECT_SLOTS)

    reduced: dict[str, Any] = {
        "doc_type": doc_type,
        "title": title,
        "evidence": [],
        "extra": {},
    }
    for slot in slots:
        reduced[slot] = []

    for slot in slots:
        slot_items = _collect_slot_items(slot, chunk_results)
        merged_items = _merge_slot_items(slot, slot_items)
        reduced[slot] = _assign_global_ids(slot, merged_items)

    evidence, evidence_meta = bind_evidence(reduced, document_ir.elements, slots)
    reduced["evidence"] = evidence
    return _clean_empty_values(reduced), evidence_meta


def bind_evidence(
    extracted_data: dict[str, Any],
    elements: list[DocumentElement],
    slots: list[str] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if slots is None:
        slots = list(OBJECT_SLOTS)
    element_map = {element.element_id: element for element in elements}
    evidence: list[dict[str, Any]] = []
    seen: set[tuple[str, str | None, str | None]] = set()
    total_objects = 0
    objects_with_evidence = 0

    for slot in slots:
        for item in extracted_data.get(slot) or []:
            if not isinstance(item, dict):
                continue
            object_id = str(item.get("id") or "").strip()
            if not object_id:
                continue

            total_objects += 1
            item_evidence = _evidence_for_item(object_id, item, element_map)
            if item_evidence:
                objects_with_evidence += 1

            for entry in item_evidence:
                marker = (
                    str(entry.get("object_id") or ""),
                    entry.get("element_id"),
                    entry.get("text_span"),
                )
                if marker in seen:
                    continue
                seen.add(marker)
                evidence.append(entry)

    coverage = objects_with_evidence / total_objects if total_objects else 0.0
    return evidence, {
        "evidence_count": len(evidence),
        "objects_total": total_objects,
        "objects_with_evidence": objects_with_evidence,
        "evidence_coverage": round(coverage, 4),
    }


def _collect_slot_items(slot: str, chunk_results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for result in chunk_results:
        raw_items = result.get(slot) if isinstance(result, dict) else None
        if not isinstance(raw_items, list):
            continue
        for item in raw_items:
            if isinstance(item, dict):
                cleaned = _clean_empty_values(item)
                if isinstance(cleaned, dict) and _has_object_content(cleaned):
                    items.append(cleaned)
    return items


def _merge_slot_items(slot: str, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    order: list[str] = []
    for item in items:
        identity = _identity_for_item(slot, item)
        if identity in merged:
            merged[identity] = _merge_dicts(merged[identity], item)
        else:
            merged[identity] = dict(item)
            order.append(identity)
    return [merged[key] for key in order]


def _assign_global_ids(slot: str, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    prefix = _generate_prefix(slot)
    assigned: list[dict[str, Any]] = []
    for index, item in enumerate(items, start=1):
        item["id"] = f"{prefix}-{index:03d}"
        assigned.append(item)
    return assigned


def _is_generated_id(slot: str, value: str) -> bool:
    """Return whether a value already looks like DocStruct's generated object ID."""
    prefix = _generate_prefix(slot)
    return bool(re.fullmatch(rf"{re.escape(prefix)}-\d{{3,}}", value.strip(), flags=re.IGNORECASE))


def _evidence_for_item(
    object_id: str,
    item: dict[str, Any],
    element_map: dict[str, DocumentElement],
) -> list[dict[str, Any]]:
    """绑定对象声明的有效证据元素，不在 reducer 层裁剪数量。"""
    evidence_entries: list[dict[str, Any]] = []
    evidence_ids = _dedupe_strings(item.get("evidence_element_ids") or [])
    valid_evidence_ids: list[str] = []

    for element_id in evidence_ids:
        element = element_map.get(element_id)
        if not element:
            continue
        valid_evidence_ids.append(element_id)
        evidence_entries.append(_entry_from_element(object_id, element))

    item["evidence_element_ids"] = valid_evidence_ids
    return evidence_entries

def _entry_from_element(
    object_id: str,
    element: DocumentElement,
    *,
    text_span: str | None = None,
) -> dict[str, Any]:
    return {
        "object_id": object_id,
        "element_id": element.element_id,
        "text_span": _truncate_span(text_span or element.text or element.markdown or ""),
        "page": element.page,
        "bbox": element.bbox,
    }


def _identity_for_item(slot: str, item: dict[str, Any]) -> str:
    # Existing slot-specific logic (legacy + common types)
    if slot == "interfaces":
        interface_type = _norm(item.get("interface_type"))
        http_method = _norm(item.get("http_method"))
        endpoint = _norm(item.get("endpoint"))
        if endpoint:
            return f"interface_endpoint::{interface_type}::{http_method}::{endpoint}"
        name = _norm(item.get("name"))
        provider = _norm(item.get("provider"))
        consumer = _norm(item.get("consumer"))
        if name or provider or consumer:
            return f"interface_name::{interface_type}::{name}::{provider}::{consumer}"

    if slot == "entities":
        name = _norm(item.get("name"))
        entity_type = _norm(item.get("entity_type"))
        if name:
            return f"entity::{entity_type}::{name}"

    if slot == "processes":
        name = _norm(item.get("name"))
        process_type = _norm(item.get("process_type"))
        if name:
            return f"process::{process_type}::{name}"

    if slot == "requirements":
        raw_id = _norm(item.get("id"))
        if raw_id and not raw_id.startswith("chunk") and not _is_generated_id(slot, raw_id):
            return f"requirement_id::{raw_id}"
        name = _norm(item.get("name"))
        requirement_type = _norm(item.get("requirement_type"))
        text_parts = _flatten_text_values([item.get("points"), item.get("criteria")])
        text_key = "::".join(text_parts)
        if name or text_key:
            return f"requirement::{requirement_type}::{name}::{text_key[:160]}"

    if slot == "artifacts":
        name = _norm(item.get("name"))
        artifact_type = _norm(item.get("artifact_type"))
        if name:
            return f"artifact::{artifact_type}::{name}"

    # Generic fallback for doc-type-specific slots
    name = _norm(item.get("name"))
    if name:
        type_field = _find_type_field(item)
        if type_field:
            return f"{slot}::{type_field}::{name}"
        return f"{slot}::name::{name}"

    raw_id = _norm(item.get("id"))
    if raw_id:
        return f"id::{raw_id}"
    return f"raw::{json.dumps(item, ensure_ascii=False, sort_keys=True)}"


def _find_type_field(item: dict[str, Any]) -> str:
    """Find the first field ending in '_type' for generic identity."""
    for key in item:
        if key.endswith("_type") and key not in ("doc_type",):
            val = _norm(item.get(key))
            if val:
                return val
    return ""


def _merge_dicts(existing: dict[str, Any], incoming: dict[str, Any]) -> dict[str, Any]:
    merged = dict(existing)
    for key, incoming_value in incoming.items():
        if incoming_value in (None, "", [], {}):
            continue
        if key not in merged or merged[key] in (None, "", [], {}):
            merged[key] = incoming_value
            continue

        existing_value = merged[key]
        if isinstance(existing_value, dict) and isinstance(incoming_value, dict):
            merged[key] = _merge_dicts(existing_value, incoming_value)
        elif isinstance(existing_value, list) and isinstance(incoming_value, list):
            merged[key] = _merge_lists(existing_value, incoming_value)
        elif isinstance(existing_value, str) and isinstance(incoming_value, str):
            merged[key] = incoming_value if len(incoming_value.strip()) > len(existing_value.strip()) else existing_value

    return merged


def _merge_lists(existing: list[Any], incoming: list[Any]) -> list[Any]:
    result: list[Any] = []
    seen: set[str] = set()
    for item in existing + incoming:
        marker = json.dumps(item, ensure_ascii=False, sort_keys=True) if isinstance(item, (dict, list)) else str(item)
        if marker in seen:
            continue
        seen.add(marker)
        result.append(item)
    return result


def _clean_empty_values(data: Any) -> Any:
    if isinstance(data, dict):
        cleaned = {}
        for key, value in data.items():
            next_value = _clean_empty_values(value)
            if next_value not in (None, "", [], {}):
                cleaned[key] = next_value
        return cleaned
    if isinstance(data, list):
        cleaned_list = []
        for item in data:
            next_item = _clean_empty_values(item)
            if next_item not in (None, "", [], {}):
                cleaned_list.append(next_item)
        return cleaned_list
    if isinstance(data, str):
        stripped = data.strip()
        return stripped if stripped else None
    return data


def _has_object_content(item: dict[str, Any]) -> bool:
    for key, value in item.items():
        if key in {"id", "evidence_element_ids"}:
            continue
        if value not in (None, "", [], {}):
            return True
    return False


def _dedupe_strings(values: Any) -> list[str]:
    if not isinstance(values, list):
        return []
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result


def _compact_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _truncate_span(value: str, limit: int = 500) -> str | None:
    compact = _compact_text(value)
    if not compact:
        return None
    if len(compact) <= limit:
        return compact
    return f"{compact[:limit].rstrip()}..."


def _norm(value: Any) -> str:
    return _compact_text(str(value or "")).lower()


def _flatten_text_values(values: list[Any]) -> list[str]:
    """Return normalized scalar text from shallow list fields for identity keys."""
    result: list[str] = []
    for value in values:
        if isinstance(value, list):
            for item in value:
                text = _norm(item)
                if text:
                    result.append(text)
            continue
        text = _norm(value)
        if text:
            result.append(text)
    return result

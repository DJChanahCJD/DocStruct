from __future__ import annotations

import json
import re
from typing import Any

from schemas.models import DocumentElement, DocumentIR


OBJECT_SLOTS = ("entities", "processes", "requirements", "interfaces", "artifacts")
ID_PREFIXES = {
    "entities": "ENT",
    "processes": "PROC",
    "requirements": "REQ",
    "interfaces": "INT",
    "artifacts": "ART",
}


def reduce_extraction_results(
    *,
    doc_type: str,
    title: str | None,
    chunk_results: list[dict[str, Any]],
    document_ir: DocumentIR,
) -> tuple[dict[str, Any], dict[str, Any]]:
    reduced: dict[str, Any] = {
        "doc_type": doc_type,
        "title": title,
        "entities": [],
        "processes": [],
        "requirements": [],
        "interfaces": [],
        "artifacts": [],
        "views": [],
        "evidence": [],
        "extra": {},
    }

    for slot in OBJECT_SLOTS:
        merged_items = _merge_slot_items(slot, _collect_slot_items(slot, chunk_results))
        reduced[slot] = _assign_global_ids(slot, merged_items)

    reduced["views"] = _build_business_views(reduced)
    evidence, evidence_meta = bind_evidence(reduced, document_ir.elements)
    reduced["evidence"] = evidence
    return _clean_empty_values(reduced), evidence_meta


def bind_evidence(
    extracted_data: dict[str, Any],
    elements: list[DocumentElement],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    element_map = {element.element_id: element for element in elements}
    evidence: list[dict[str, Any]] = []
    seen: set[tuple[str, str | None, str | None]] = set()
    total_objects = 0
    objects_with_evidence = 0

    for slot in OBJECT_SLOTS:
        for item in extracted_data.get(slot) or []:
            if not isinstance(item, dict):
                continue
            object_id = str(item.get("id") or "").strip()
            if not object_id:
                continue

            total_objects += 1
            item_evidence = _evidence_for_item(object_id, item, element_map, elements)
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
                entry["evidence_id"] = f"EVD-{len(evidence) + 1:03d}"
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
    prefix = ID_PREFIXES[slot]
    assigned: list[dict[str, Any]] = []
    for index, item in enumerate(items, start=1):
        next_item = dict(item)
        next_item["id"] = f"{prefix}-{index:03d}"
        assigned.append(next_item)
    return assigned


def _build_business_views(extracted_data: dict[str, Any]) -> list[dict[str, Any]]:
    views: list[dict[str, Any]] = []
    requirement_groups: dict[str, list[str]] = {}
    for requirement in extracted_data.get("requirements") or []:
        if not isinstance(requirement, dict):
            continue
        category = str(requirement.get("category") or "").strip()
        object_id = str(requirement.get("id") or "").strip()
        if category and object_id:
            requirement_groups.setdefault(category, []).append(object_id)

    for category, object_ids in requirement_groups.items():
        if len(object_ids) < 2:
            continue
        views.append(
            {
                "view_name": f"{category} requirements",
                "view_type": "requirement_group",
                "object_ids": object_ids,
            }
        )
    return views


def _evidence_for_item(
    object_id: str,
    item: dict[str, Any],
    element_map: dict[str, DocumentElement],
    elements: list[DocumentElement],
) -> list[dict[str, Any]]:
    evidence_entries: list[dict[str, Any]] = []
    evidence_ids = _dedupe_strings(item.get("evidence_element_ids") or [])

    for element_id in evidence_ids:
        element = element_map.get(element_id)
        if not element:
            continue
        evidence_entries.append(_entry_from_element(object_id, element))

    if evidence_entries:
        return evidence_entries

    fallback_text = _fallback_text_candidate(item)
    if not fallback_text:
        return []

    matched_element = _find_element_by_text(fallback_text, elements)
    if matched_element:
        return [_entry_from_element(object_id, matched_element, text_span=fallback_text)]

    return [
        {
            "object_id": object_id,
            "element_id": None,
            "text_span": _truncate_span(fallback_text),
            "section_path": [],
            "page": None,
            "bbox": None,
        }
    ]


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
        "section_path": list(element.section_path),
        "page": element.page,
        "bbox": element.bbox,
    }


def _identity_for_item(slot: str, item: dict[str, Any]) -> str:
    if slot == "interfaces":
        method = _norm(item.get("method")).upper()
        path = _norm(item.get("path"))
        if method and path:
            return f"method_path::{method}::{path}"

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
        if raw_id and not raw_id.startswith("chunk"):
            return f"requirement_id::{raw_id}"
        name = _norm(item.get("name"))
        req_type = _norm(item.get("requirement_type"))
        description = _norm(item.get("description"))
        if name or description:
            return f"requirement::{req_type}::{name}::{description[:120]}"

    if slot == "artifacts":
        name = _norm(item.get("name"))
        artifact_type = _norm(item.get("artifact_type"))
        if name:
            return f"artifact::{artifact_type}::{name}"

    raw_id = _norm(item.get("id"))
    if raw_id:
        return f"id::{raw_id}"
    return f"raw::{json.dumps(item, ensure_ascii=False, sort_keys=True)}"


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
        if key in {"id", "evidence_element_ids", "extra"}:
            continue
        if value not in (None, "", [], {}):
            return True
    return False


def _fallback_text_candidate(item: dict[str, Any]) -> str | None:
    extra = item.get("extra")
    if isinstance(extra, dict):
        for key in ("evidence_text", "source_text", "quote"):
            value = str(extra.get(key) or "").strip()
            if len(value) >= 8:
                return value
    for key in ("description", "name"):
        value = str(item.get(key) or "").strip()
        if len(value) >= 8:
            return value
    return None


def _find_element_by_text(candidate: str, elements: list[DocumentElement]) -> DocumentElement | None:
    normalized_candidate = _compact_text(candidate)
    if len(normalized_candidate) < 8:
        return None
    for element in elements:
        haystack = _compact_text(element.text or element.markdown or "")
        if normalized_candidate and normalized_candidate in haystack:
            return element
    return None


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

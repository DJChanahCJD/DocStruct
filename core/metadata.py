from __future__ import annotations

import re
from typing import Any

from schemas.models import DocumentIR


SCAN_MAX_CHARS = 3000
VERSION_LABELS = {"文档版本", "版本", "version", "doc version", "document version"}
VERSION_VALUE_PATTERN = re.compile(r"^(?:v|V)?\d+(?:[._-]\d+)*(?:[-+][0-9A-Za-z.-]+)?$")


def extract_document_metadata(
    markdown_content: str,
    document_ir: DocumentIR | None = None,
) -> dict[str, str]:
    """从文档前部确定性提取文档级元数据。"""
    text = _metadata_source_text(markdown_content, document_ir)
    version = _extract_version(text)
    return {"version": version} if version else {}


def apply_document_metadata(
    extracted_data: dict[str, Any],
    metadata: dict[str, str],
) -> dict[str, Any]:
    """只在抽取结果为空时补齐文档级元数据。"""
    if extracted_data.get("version") in (None, "", [], {}):
        version = metadata.get("version")
        if version:
            extracted_data["version"] = version
    return extracted_data


def _metadata_source_text(
    markdown_content: str,
    document_ir: DocumentIR | None,
) -> str:
    """拼接 IR 前部元素或 Markdown 前部文本，作为元数据扫描来源。"""
    if document_ir is not None and document_ir.elements:
        parts: list[str] = []
        total_chars = 0
        for element in document_ir.elements:
            value = (element.markdown or element.text or "").strip()
            if not value:
                continue
            parts.append(value)
            total_chars += len(value)
            if total_chars >= SCAN_MAX_CHARS:
                break
        return "\n".join(parts)[:SCAN_MAX_CHARS]
    return (markdown_content or "")[:SCAN_MAX_CHARS]


def _extract_version(text: str) -> str | None:
    """从表格或键值行中提取文档版本号。"""
    for line in (text or "").splitlines():
        table_version = _extract_version_from_table_line(line)
        if table_version:
            return table_version

        key_value_version = _extract_version_from_key_value_line(line)
        if key_value_version:
            return key_value_version
    return None


def _extract_version_from_table_line(line: str) -> str | None:
    """从 Markdown 表格行中提取版本号。"""
    stripped = line.strip()
    if not stripped.startswith("|") or not stripped.endswith("|"):
        return None

    cells = [cell.strip() for cell in stripped.strip("|").split("|")]
    if len(cells) < 2:
        return None

    for index, cell in enumerate(cells[:-1]):
        if _normalize_label(cell) in VERSION_LABELS:
            return _normalize_version_value(cells[index + 1])
    return None


def _extract_version_from_key_value_line(line: str) -> str | None:
    """从普通键值行中提取版本号。"""
    match = re.match(
        r"^\s*(文档版本|版本|version|doc version|document version)\s*[:：]\s*(.+?)\s*$",
        line,
        flags=re.IGNORECASE,
    )
    if not match:
        return None
    return _normalize_version_value(match.group(2))


def _normalize_label(value: str) -> str:
    """归一化元数据标签，兼容中英文大小写和 Markdown 强调符号。"""
    cleaned = re.sub(r"[*_`]", "", value or "").strip()
    return re.sub(r"\s+", " ", cleaned).lower()


def _normalize_version_value(value: str) -> str | None:
    """清洗并校验版本号值，避免误收普通正文。"""
    cleaned = re.sub(r"[*_`]", "", value or "").strip()
    cleaned = cleaned.strip("。；;,，")
    if not cleaned:
        return None
    first_token = cleaned.split()[0]
    return first_token if VERSION_VALUE_PATTERN.fullmatch(first_token) else None

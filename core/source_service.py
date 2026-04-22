from __future__ import annotations

import mimetypes
import os
from pathlib import Path
from typing import Any

from fastapi import HTTPException

from core.config import get_settings
from schemas.models import DocumentRecord


settings = get_settings()


def _guess_mime_type(doc: DocumentRecord) -> str:
    media_type, _ = mimetypes.guess_type(doc.filename or doc.stored_path or "")
    return media_type or "application/octet-stream"


def _preview_mode(doc: DocumentRecord, mime_type: str) -> str:
    if doc.source_type == "url":
        return "external_url"
    if mime_type == "application/pdf":
        return "pdf"
    if mime_type.startswith("text/") or mime_type in {"text/markdown", "application/json"}:
        return "text"
    if mime_type in {
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/msword",
    }:
        return "office"
    return "unsupported"


def _resolve_local_path(doc: DocumentRecord) -> Path:
    if not doc.stored_path:
        raise HTTPException(404, "文件不存在")

    path = Path(doc.stored_path).resolve()
    upload_root = Path(settings.upload_dir).resolve()
    try:
        path.relative_to(upload_root)
    except ValueError as exc:
        raise HTTPException(400, "非法文件路径") from exc
    if not path.exists() or not path.is_file():
        raise HTTPException(404, "文件不存在")
    return path


def build_source_meta(doc: DocumentRecord) -> dict[str, Any]:
    mime_type = _guess_mime_type(doc)
    return {
        "source_type": doc.source_type,
        "filename": doc.filename,
        "mime_type": mime_type,
        "preview_mode": _preview_mode(doc, mime_type),
        "download_url": f"/api/documents/{doc.id}/source",
        "source_url": doc.source_url,
    }


def get_local_source_path(doc: DocumentRecord) -> str:
    return os.fspath(_resolve_local_path(doc))

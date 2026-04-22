from __future__ import annotations

import asyncio
import logging
import os
import uuid

import aiofiles
from fastapi import HTTPException, UploadFile

from core.extractor import extract_structure_with_meta
from core.parser import ParserFactory
from schemas.dto import UploadResponse
from schemas.models import (
    ApiDocument,
    DesignDocument,
    DocType,
    DocumentRecord,
    IssueDocument,
    ManualDocument,
    SrsDocument,
    TestDocument,
)


logger = logging.getLogger(__name__)

TYPE_MODEL_MAP = {
    DocType.SRS: SrsDocument,
    DocType.API: ApiDocument,
    DocType.DESIGN: DesignDocument,
    DocType.TEST: TestDocument,
    DocType.MANUAL: ManualDocument,
    DocType.ISSUE: IssueDocument,
}

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".md", ".txt"}


def ensure_upload_dir(upload_dir: str) -> None:
    os.makedirs(upload_dir, exist_ok=True)


def normalize_doc_type(doc_type: str | DocType | None) -> DocType:
    if isinstance(doc_type, DocType):
        return doc_type
    if doc_type is None or not str(doc_type).strip():
        raise ValueError("doc_type 不能为空")
    try:
        return DocType(str(doc_type).strip())
    except ValueError as exc:
        allowed = ", ".join(item.value for item in DocType)
        raise ValueError(f"非法 doc_type: {doc_type}。仅支持: {allowed}") from exc


def validate_file_extension(filename: str) -> str:
    file_ext = os.path.splitext(filename)[1].lower()
    if file_ext not in ALLOWED_EXTENSIONS:
        raise ValueError(f"不支持的文件类型: {file_ext}。仅支持: {', '.join(sorted(ALLOWED_EXTENSIONS))}")
    return file_ext


async def process_uploaded_file(
    file: UploadFile,
    *,
    doc_type: str | DocType | None,
    upload_dir: str,
) -> UploadResponse:
    normalized_doc_type = normalize_doc_type(doc_type)
    file_ext = validate_file_extension(file.filename)
    ensure_upload_dir(upload_dir)

    file_path = os.path.join(upload_dir, f"{uuid.uuid4()}{file_ext}")
    async with aiofiles.open(file_path, "wb") as handle:
        await handle.write(await file.read())

    doc = await DocumentRecord.create(
        filename=file.filename,
        stored_path=file_path,
        status="processing",
        doc_type=normalized_doc_type.value,
    )

    try:
        parser = ParserFactory.get_parser(file_path)
        markdown_text = await asyncio.to_thread(parser.parse, file_path)

        target_model = TYPE_MODEL_MAP.get(normalized_doc_type)
        extracted_payload = None
        if target_model is not None:
            extracted, _ = await extract_structure_with_meta(markdown_text, target_model)
            extracted_payload = extracted.model_dump(mode="json")

        await doc.update_from_dict(
            {
                "status": "completed",
                "parsed_content": markdown_text,
                "extracted_data": extracted_payload,
                "error_message": None,
            }
        ).save()
        return UploadResponse(
            id=doc.id,
            filename=doc.filename,
            status=doc.status,
            message=f"已按 {normalized_doc_type.value} 类型完成处理",
        )
    except ValueError as exc:
        await doc.update_from_dict({"status": "failed", "error_message": str(exc)}).save()
        raise HTTPException(400, str(exc)) from exc
    except Exception as exc:
        logger.error("Error processing document %s: %s", file.filename, exc, exc_info=True)
        await doc.update_from_dict({"status": "failed", "error_message": str(exc)}).save()
        raise HTTPException(500, f"处理失败: {exc}") from exc

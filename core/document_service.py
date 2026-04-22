from __future__ import annotations

import asyncio
import logging
import os
import uuid

import aiofiles
from fastapi import HTTPException, UploadFile

from core.extractor import extract_structure_with_meta
from core.parser import ParserFactory
from core.schema_registry import TYPE_MODEL_MAP, normalize_doc_type
from schemas.dto import UploadResponse
from schemas.models import DocType, DocumentRecord


logger = logging.getLogger(__name__)

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".md", ".txt"}


async def retry_extraction(doc: DocumentRecord) -> DocumentRecord:
    """
    重试提取结构化数据。
    仅当 parsed_content 存在时有效。
    """
    if not doc.parsed_content:
        raise ValueError("文档尚未解析，无法重试提取")

    normalized_doc_type = normalize_doc_type(doc.doc_type)
    target_model = TYPE_MODEL_MAP.get(normalized_doc_type)
    if target_model is None:
        raise ValueError(f"不支持的文档类型: {doc.doc_type}")

    await doc.update_from_dict({"status": "processing", "error_message": None}).save()

    try:
        extracted, _ = await extract_structure_with_meta(doc.parsed_content, target_model)
        await doc.update_from_dict(
            {
                "status": "completed",
                "extracted_data": extracted.model_dump(mode="json"),
                "error_message": None,
            }
        ).save()
        return doc
    except Exception as exc:
        logger.warning("Retry extraction failed for doc %s: %s", doc.id, exc)
        await doc.update_from_dict(
            {
                "status": "failed",
                "error_message": f"提取失败: {exc}",
            }
        ).save()
        raise


def ensure_upload_dir(upload_dir: str) -> None:
    os.makedirs(upload_dir, exist_ok=True)


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

    # 阶段 1: 解析文件为 markdown
    try:
        parser = ParserFactory.get_parser(file_path)
        markdown_text = await asyncio.to_thread(parser.parse, file_path)
    except Exception as parse_exc:
        logger.error("Parse failed for %s: %s", file.filename, parse_exc)
        await doc.update_from_dict({"status": "failed", "error_message": f"解析失败: {parse_exc}"}).save()
        raise HTTPException(500, f"文件解析失败: {parse_exc}") from parse_exc

    # 解析成功，先保存 markdown
    await doc.update_from_dict({"parsed_content": markdown_text}).save()

    # 阶段 2: 提取结构化数据
    target_model = TYPE_MODEL_MAP.get(normalized_doc_type)
    if target_model is None:
        await doc.update_from_dict({"status": "completed"}).save()
        return UploadResponse(
            id=doc.id,
            filename=doc.filename,
            status=doc.status,
            message=f"已按 {normalized_doc_type.value} 类型完成处理（无结构化提取）",
        )

    try:
        extracted, _ = await extract_structure_with_meta(markdown_text, target_model)
        extracted_payload = extracted.model_dump(mode="json")
        await doc.update_from_dict(
            {
                "status": "completed",
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
    except Exception as extract_exc:
        logger.warning("Extraction failed for %s: %s", file.filename, extract_exc)
        await doc.update_from_dict(
            {
                "status": "failed",
                "error_message": f"提取失败: {extract_exc}",
            }
        ).save()
        # 提取失败但不抛出异常，允许用户查看 markdown 并重试
        return UploadResponse(
            id=doc.id,
            filename=doc.filename,
            status=doc.status,
            message=f"解析成功，但结构化提取失败: {extract_exc}",
        )

from __future__ import annotations

import asyncio
import logging
import os
import uuid

import aiofiles
from fastapi import UploadFile

from core.extractor import extract_structure_with_meta
from core.ir import build_basic_ir_from_markdown, document_ir_to_payload, parse_result_to_ir
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

    await doc.update_from_dict({"status": "extracting", "error_message": None}).save()

    try:
        document_ir = doc.document_ir
        if document_ir is None:
            regenerated_ir = build_basic_ir_from_markdown(doc.parsed_content, doc_type=normalized_doc_type)
            document_ir = document_ir_to_payload(regenerated_ir)
            await doc.update_from_dict({"document_ir": document_ir}).save()

        extracted, extraction_meta = await extract_structure_with_meta(
            doc.parsed_content,
            target_model,
            document_ir=document_ir,
        )
        await doc.update_from_dict(
            {
                "status": "completed",
                "extracted_data": extracted.model_dump(mode="json"),
                "error_message": None,
            }
        ).save()
        if extraction_meta.get("partial"):
            logger.warning(
                "Retry extraction partially succeeded for doc %s: failed chunks %s/%s",
                doc.id,
                extraction_meta.get("failed_chunks"),
                extraction_meta.get("chunk_count"),
            )
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
        status="uploaded",
        doc_type=normalized_doc_type.value,
    )

    return UploadResponse(
        id=doc.id,
        filename=doc.filename,
        status=doc.status,
        message="文件已上传，正在后台处理中",
    )


async def process_document_record(doc_id: int) -> None:
    doc = await DocumentRecord.get_or_none(id=doc_id)
    if doc is None:
        logger.warning("Document record not found for processing: %s", doc_id)
        return

    normalized_doc_type = normalize_doc_type(doc.doc_type)

    # 阶段 1: 解析文件为 markdown
    try:
        await doc.update_from_dict({"status": "parsing", "error_message": None}).save()
        parser = ParserFactory.get_parser(doc.stored_path)
        parse_result = await asyncio.to_thread(parser.parse_to_result, doc.stored_path)
        markdown_text = parse_result.markdown
        document_ir = parse_result_to_ir(parse_result, doc_type=normalized_doc_type)
        document_ir_payload = document_ir_to_payload(document_ir)
    except Exception as parse_exc:
        logger.error("Parse failed for doc %s: %s", doc.id, parse_exc)
        await doc.update_from_dict({"status": "failed", "error_message": f"解析失败: {parse_exc}"}).save()
        return

    # 解析成功，先保存 Markdown 预览和机器可读 IR
    await doc.update_from_dict(
        {
            "parsed_content": markdown_text,
            "document_ir": document_ir_payload,
        }
    ).save()

    # 阶段 2: 提取结构化数据
    target_model = TYPE_MODEL_MAP.get(normalized_doc_type)
    if target_model is None:
        await doc.update_from_dict({"status": "completed"}).save()
        return

    try:
        await doc.update_from_dict({"status": "extracting", "error_message": None}).save()
        extracted, extraction_meta = await extract_structure_with_meta(
            markdown_text,
            target_model,
            document_ir=document_ir_payload,
        )
        extracted_payload = extracted.model_dump(mode="json")
        await doc.update_from_dict(
            {
                "status": "completed",
                "extracted_data": extracted_payload,
                "error_message": None,
            }
        ).save()
        partial = bool(extraction_meta.get("partial"))
        if partial:
            failed_chunks = extraction_meta.get("failed_chunks", 0)
            chunk_count = extraction_meta.get("chunk_count", 0)
            logger.warning(
                "Extraction partially succeeded for doc %s: failed chunks %s/%s",
                doc.id,
                failed_chunks,
                chunk_count,
            )
    except Exception as extract_exc:
        logger.warning("Extraction failed for doc %s: %s", doc.id, extract_exc)
        await doc.update_from_dict(
            {
                "status": "failed",
                "error_message": f"提取失败: {extract_exc}",
            }
        ).save()

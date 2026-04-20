import asyncio
import logging
import os
import sqlite3
import uuid

import aiofiles
from fastapi import HTTPException, UploadFile

from core.config import get_settings
from core.extractor import classify_document, extract_structure_with_meta
from core.parser import ParserFactory
from core.retrieval import build_retrieval_corpus
from core.text_models import resolve_text_model
from core.url_parser import parse_url_to_markdown
import json

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
from schemas.dto import UploadResponse


logger = logging.getLogger(__name__)
settings = get_settings()
os.makedirs(settings.upload_dir, exist_ok=True)

TYPE_MODEL_MAP = {
    DocType.SRS: SrsDocument,
    DocType.API: ApiDocument,
    DocType.DESIGN: DesignDocument,
    DocType.TEST: TestDocument,
    DocType.MANUAL: ManualDocument,
    DocType.ISSUE: IssueDocument,
}

REQUIRED_DOCUMENT_COLUMNS: dict[str, str] = {
    "source_type": "TEXT DEFAULT 'file'",
    "source_url": "TEXT",
    "llm_model": "TEXT",
    "updated_at": "DATETIME",
    "classification_result": "TEXT",
    "schema_version": "TEXT",
}



def ensure_document_record_schema() -> None:
    """补齐旧版本数据库缺失的文档记录字段。"""
    if not os.path.exists(settings.db_path):
        return

    conn = sqlite3.connect(settings.db_path)
    try:
        cursor = conn.execute("PRAGMA table_info(document_records)")
        existing_columns = {row[1] for row in cursor.fetchall()}
        if not existing_columns:
            return

        for column_name, column_type in REQUIRED_DOCUMENT_COLUMNS.items():
            if column_name in existing_columns:
                continue
            conn.execute(f"ALTER TABLE document_records ADD COLUMN {column_name} {column_type}")

        conn.execute("UPDATE document_records SET source_type = 'file' WHERE source_type IS NULL OR source_type = ''")
        conn.execute("UPDATE document_records SET updated_at = upload_time WHERE updated_at IS NULL")
        conn.commit()
    finally:
        conn.close()



def _build_message(doc_type: str, vector_warning: str | None) -> str:
    """生成上传完成后的统一反馈文案。"""
    message = f"识别为: {doc_type}"
    if vector_warning:
        message += "（向量索引构建失败，可稍后重建）"
    return message



async def _finalize_document(
    doc: DocumentRecord,
    markdown_text: str,
    *,
    llm_model: str | None = None,
) -> UploadResponse:
    """完成文档分类、结构化提取和检索索引构建。"""
    model_spec = resolve_text_model(llm_model)

    logger.info("Parsed content length: %s", len(markdown_text))
    logger.info("Classifying document type using %s...", model_spec.id)
    cls_result = classify_document(markdown_text, llm_model=model_spec.id)
    logger.info("Classification result: %s", cls_result)

    target_model = TYPE_MODEL_MAP.get(cls_result.doc_type)
    if not target_model:
        logger.warning("Unknown document type: %s", cls_result.doc_type)
        doc.update_from_dict(
            {
                "status": "completed",
                "doc_type": cls_result.doc_type.value,
                "parsed_content": markdown_text,
                "error_message": "未知的文档类型",
                "llm_model": model_spec.id,
            }
        )
    else:
        logger.info("Extracting structure using %s with text model %s", target_model.__name__, model_spec.id)
        extracted, extraction_meta = extract_structure_with_meta(
            markdown_text,
            target_model,
            llm_model=model_spec.id,
        )
        logger.info(
            "Extraction meta: mode=%s, chunk_count=%s, failed_chunks=%s, fallback_used=%s",
            extraction_meta.get("mode"),
            extraction_meta.get("chunk_count"),
            extraction_meta.get("failed_chunks"),
            extraction_meta.get("fallback_used"),
        )
        doc.update_from_dict(
            {
                "status": "completed",
                "doc_type": cls_result.doc_type.value,
                "parsed_content": markdown_text,
                "extracted_data": extracted.model_dump(mode="json"),
                "llm_model": model_spec.id,
                "classification_result": json.dumps(
                    {
                        "doc_type": cls_result.doc_type.value,
                        "confidence": cls_result.confidence,
                        "reasoning": cls_result.reasoning,
                    },
                    ensure_ascii=False,
                ),
                "schema_version": "v3",
            }
        )

    await doc.save()

    vector_warning = None
    try:
        await build_retrieval_corpus(doc.id)
    except Exception as exc:
        vector_warning = str(exc)
        logger.warning("Vector build failed but upload remains successful. doc_id=%s error=%s", doc.id, exc)
        await doc.update_from_dict({"error_message": f"向量索引构建失败: {vector_warning}"}).save()
    else:
        if doc.status == "completed" and doc.extracted_data:
            await doc.update_from_dict({"error_message": None}).save()

    return UploadResponse(
        id=doc.id,
        filename=doc.filename,
        status="completed",
        message=_build_message(doc.doc_type, vector_warning),
    )



async def process_uploaded_file(file: UploadFile, llm_model: str | None = None) -> UploadResponse:
    """处理文件上传，并按当前活动文本模型完成分类与抽取。"""
    model_spec = resolve_text_model(llm_model)
    allowed_extensions = {".pdf", ".docx", ".md", ".txt"}
    file_ext = os.path.splitext(file.filename)[1].lower()
    if file_ext not in allowed_extensions:
        raise HTTPException(400, f"不支持的文件类型: {file_ext}。仅支持: {', '.join(allowed_extensions)}")

    file_path = os.path.join(settings.upload_dir, f"{uuid.uuid4()}{file_ext}")
    async with aiofiles.open(file_path, "wb") as f:
        await f.write(await file.read())

    logger.info("Start processing file: %s -> %s", file.filename, file_path)
    doc = await DocumentRecord.create(
        filename=file.filename,
        stored_path=file_path,
        source_type="file",
        source_url=None,
        status="processing",
        llm_model=model_spec.id,
    )

    try:
        parser = ParserFactory.get_parser(file_path)
        markdown_text = await asyncio.to_thread(parser.parse, file_path)
        return await _finalize_document(doc, markdown_text, llm_model=model_spec.id)
    except Exception as exc:
        logger.error("Error processing document %s: %s", file.filename, exc, exc_info=True)
        await doc.update_from_dict({"status": "failed", "error_message": str(exc)}).save()
        raise HTTPException(500, f"处理失败: {exc}")



async def process_url_document(url: str, llm_model: str | None = None) -> UploadResponse:
    """处理 URL 导入，并按当前活动文本模型完成分类与抽取。"""
    model_spec = resolve_text_model(llm_model)
    logger.info("Start processing url: %s", url)
    try:
        title, markdown_text = await asyncio.to_thread(parse_url_to_markdown, url)
    except Exception as exc:
        logger.error("Error fetching url %s: %s", url, exc, exc_info=True)
        raise HTTPException(400, f"URL 处理失败: {exc}")

    doc = await DocumentRecord.create(
        filename=title,
        stored_path=url,
        source_type="url",
        source_url=url,
        status="processing",
        llm_model=model_spec.id,
    )

    try:
        return await _finalize_document(doc, markdown_text, llm_model=model_spec.id)
    except Exception as exc:
        logger.error("Error processing url document %s: %s", url, exc, exc_info=True)
        await doc.update_from_dict({"status": "failed", "error_message": str(exc)}).save()
        raise HTTPException(500, f"处理失败: {exc}")

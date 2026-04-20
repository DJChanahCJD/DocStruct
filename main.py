import logging
import os

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse
import mimetypes
from tortoise.contrib.fastapi import register_tortoise

from core.config import get_settings
from core.document_service import TYPE_MODEL_MAP, ensure_document_record_schema, process_uploaded_file, process_url_document
from core.extractor import re_extract_with_instruction
from core.retrieval import answer_question, build_retrieval_corpus
from core.text_models import list_text_models
from schemas.models import DocType, DocumentRecord
from schemas.dto import (
    DocumentRecordDTO,
    DocumentUpdateRequest,
    QaRequest,
    QaResponse,
    ReExtractRequest,
    ReExtractResponse,
    TextModelListResponse,
    TextModelOption,
    UploadResponse,
    UrlUploadRequest,
)


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
settings = get_settings()

app = FastAPI(title="DocStruct MVP")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def init_runtime_schema() -> None:
    """在应用启动时补齐轻量数据库兼容字段。"""
    ensure_document_record_schema()


@app.get("/api/text-models", response_model=TextModelListResponse)
async def get_text_models() -> TextModelListResponse:
    """返回前端允许选择的文本模型列表。"""
    return TextModelListResponse(models=[TextModelOption.model_validate(item) for item in list_text_models()])


@app.post("/api/upload", response_model=UploadResponse)
async def upload_document(file: UploadFile = File(...), llm_model: str | None = Form(None)) -> UploadResponse:
    """处理文件上传，并透传当前活动文本模型。"""
    try:
        return await process_uploaded_file(file, llm_model=llm_model)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@app.get("/api/documents", response_model=list[DocumentRecordDTO])
async def list_documents():
    """按时间倒序返回文档列表。"""
    ensure_document_record_schema()
    docs = await DocumentRecord.all().order_by("-id")
    return [DocumentRecordDTO.model_validate(doc) for doc in docs]


@app.get("/api/documents/{doc_id}", response_model=DocumentRecordDTO)
async def get_document(doc_id: int):
    """返回单篇文档详情。"""
    ensure_document_record_schema()
    doc = await DocumentRecord.get_or_none(id=doc_id)
    if not doc:
        raise HTTPException(404, "记录不存在")
    return DocumentRecordDTO.model_validate(doc)


@app.get("/api/documents/{doc_id}/file")
async def download_document_file(doc_id: int):
    """下载或重定向文档原始文件。

    - source_type == 'file'：返回本地文件内容（FileResponse）
    - source_type == 'url'：302 重定向到原始 URL
    """
    doc = await DocumentRecord.get_or_none(id=doc_id)
    if not doc:
        raise HTTPException(404, "记录不存在")

    if doc.source_type == "url":
        return RedirectResponse(url=doc.stored_path, status_code=302)

    if not doc.stored_path or not os.path.exists(doc.stored_path):
        raise HTTPException(404, "文件不存在")

    media_type, _ = mimetypes.guess_type(doc.stored_path)
    media_type = media_type or "application/octet-stream"

    return FileResponse(
        path=doc.stored_path,
        media_type=media_type,
        filename=doc.filename,
    )


@app.patch("/api/documents/{doc_id}", response_model=DocumentRecordDTO)
async def update_document(doc_id: int, body: DocumentUpdateRequest):
    """更新文档的结构化 JSON 数据（extracted_data）。"""
    doc = await DocumentRecord.get_or_none(id=doc_id)
    if not doc:
        raise HTTPException(404, "记录不存在")
    doc.extracted_data = body.extracted_data
    await doc.save(update_fields=["extracted_data", "updated_at"])
    return DocumentRecordDTO.model_validate(doc)


@app.delete("/api/documents/{doc_id}")
async def delete_document(doc_id: int):
    """删除文档记录及其本地文件。"""
    ensure_document_record_schema()
    doc = await DocumentRecord.get_or_none(id=doc_id)
    if not doc:
        raise HTTPException(404, "记录不存在")

    if doc.stored_path and os.path.exists(doc.stored_path):
        try:
            os.remove(doc.stored_path)
        except Exception as exc:
            logger.warning("删除文件失败: %s", exc)

    await doc.delete()
    return {"message": "删除成功", "id": doc_id}


@app.post("/api/reindex/{doc_id}")
async def reindex_document(doc_id: int):
    """重建指定文档的向量索引。"""
    ensure_document_record_schema()
    doc = await DocumentRecord.get_or_none(id=doc_id)
    if not doc:
        raise HTTPException(404, "记录不存在")
    try:
        await build_retrieval_corpus(doc_id)
        return {"message": "重建索引成功", "doc_id": doc_id}
    except Exception as exc:
        logger.error("Reindex failed for doc %s: %s", doc_id, exc, exc_info=True)
        raise HTTPException(500, f"重建索引失败: {str(exc)}") from exc


@app.post("/api/qa", response_model=QaResponse)
async def qa(request: QaRequest):
    """基于检索上下文执行问答，并按请求切换文本模型。"""
    try:
        result = await answer_question(
            question=request.question,
            doc_id=request.doc_id,
            top_k=request.top_k,
            llm_model=request.llm_model,
        )
        return QaResponse.model_validate(result)

    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except Exception as exc:
        logger.error("QA failed: %s", exc, exc_info=True)
        raise HTTPException(500, f"问答失败: {str(exc)}") from exc


@app.post("/api/documents/{doc_id}/re-extract", response_model=ReExtractResponse)
async def re_extract_document(doc_id: int, body: ReExtractRequest):
    """对已有文档发起重新提取，结果仅返回不持久化，由前端确认后调用 PATCH 保存。"""
    doc = await DocumentRecord.get_or_none(id=doc_id)
    if not doc:
        raise HTTPException(404, "记录不存在")
    if not doc.parsed_content:
        raise HTTPException(400, "文档尚无原文内容，无法重新提取")

    doc_type = DocType(doc.doc_type) if doc.doc_type in DocType._value2member_map_ else None
    response_model = TYPE_MODEL_MAP.get(doc_type) if doc_type else None
    if response_model is None:
        raise HTTPException(400, f"不支持的文档类型 '{doc.doc_type}'，无法重新提取")

    try:
        result = await re_extract_with_instruction(
            parsed_content=doc.parsed_content,
            response_model=response_model,
            scope=body.scope,
            doc_id=doc_id,
            field_key=body.field_key,
            instruction=body.instruction,
            llm_model=doc.llm_model,
            use_rag=body.use_rag,
        )
        return ReExtractResponse(result=result, scope=body.scope, field_key=body.field_key)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except Exception as exc:
        logger.error("Re-extract failed for doc %s: %s", doc_id, exc, exc_info=True)
        raise HTTPException(500, f"重新提取失败: {str(exc)}") from exc


@app.post("/api/upload/url", response_model=UploadResponse)
async def upload_from_url(request: UrlUploadRequest):
    """从公开 URL 导入文档，并沿用统一的文档处理服务。"""
    try:
        return await process_url_document(request.url.strip(), llm_model=request.llm_model)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


register_tortoise(
    app,
    db_url=f"sqlite://{settings.db_path}",
    modules={"models": ["schemas.models"]},
    generate_schemas=True,
    add_exception_handlers=True,
)

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8001, reload=False)

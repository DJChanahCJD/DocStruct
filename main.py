import logging
import os

from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from tortoise.contrib.fastapi import register_tortoise

from core.config import get_settings
from core.chunker import split_ir_into_chunks
from core.document_service import process_document_record, process_uploaded_file, retry_extraction
from core.extractor import build_extraction_contract
from core.ir import build_basic_ir_from_markdown, document_ir_from_payload
from core.schema_registry import get_response_model
from schemas.dto import (
    DocumentChunkDebugDTO,
    DocumentChunksResponse,
    DocumentRecordDTO,
    DocumentUpdateRequest,
    UploadResponse,
)
from schemas.models import DocumentChunk, DocumentRecord, DocumentIR


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
settings = get_settings()

db_dir = os.path.dirname(settings.db_path)
if db_dir:
    os.makedirs(db_dir, exist_ok=True)
os.makedirs(settings.upload_dir, exist_ok=True)

app = FastAPI(title="DocStruct Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/api/upload", response_model=UploadResponse)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    doc_type: str | None = Form(None),
) -> UploadResponse:
    response = await process_uploaded_file(file, doc_type=doc_type, upload_dir=settings.upload_dir)
    background_tasks.add_task(process_document_record, response.id)
    return response


@app.get("/api/documents", response_model=list[DocumentRecordDTO])
async def list_documents() -> list[DocumentRecordDTO]:
    docs = await DocumentRecord.all().order_by("-id")
    return [DocumentRecordDTO.model_validate(doc) for doc in docs]


@app.get("/api/documents/{doc_id}", response_model=DocumentRecordDTO)
async def get_document(doc_id: int) -> DocumentRecordDTO:
    doc = await DocumentRecord.get_or_none(id=doc_id)
    if not doc:
        raise HTTPException(404, "记录不存在")
    return DocumentRecordDTO.model_validate(doc)


@app.patch("/api/documents/{doc_id}", response_model=DocumentRecordDTO)
async def update_document(doc_id: int, body: DocumentUpdateRequest) -> DocumentRecordDTO:
    doc = await DocumentRecord.get_or_none(id=doc_id)
    if not doc:
        raise HTTPException(404, "记录不存在")

    update_fields: list[str] = []
    if body.raw_text is not None and body.raw_text != doc.raw_text:
        doc.raw_text = body.raw_text
        doc.document_ir = None
        update_fields.append("raw_text")
        update_fields.append("document_ir")
    if body.summary is not None and body.summary != doc.summary:
        doc.summary = body.summary
        update_fields.append("summary")
    if body.extracted_data is not None and body.extracted_data != doc.extracted_data:
        doc.extracted_data = body.extracted_data
        update_fields.append("extracted_data")

    if update_fields:
        await doc.save(update_fields=update_fields)
    await doc.refresh_from_db()
    return DocumentRecordDTO.model_validate(doc)


@app.get("/api/documents/{doc_id}/chunks", response_model=DocumentChunksResponse)
async def get_document_chunks(doc_id: int) -> DocumentChunksResponse:
    """返回当前分块规则生成的只读调试数据。"""
    doc = await DocumentRecord.get_or_none(id=doc_id)
    if not doc:
        raise HTTPException(404, "记录不存在")

    try:
        return build_document_chunks_response(doc)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@app.delete("/api/documents/{doc_id}")
async def delete_document(doc_id: int) -> dict[str, object]:
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


@app.post("/api/documents/{doc_id}/retry-extraction", response_model=DocumentRecordDTO)
async def retry_extraction_endpoint(doc_id: int) -> DocumentRecordDTO:
    """重试提取结构化数据"""
    doc = await DocumentRecord.get_or_none(id=doc_id)
    if not doc:
        raise HTTPException(404, "记录不存在")

    try:
        updated_doc = await retry_extraction(doc)
        return DocumentRecordDTO.model_validate(updated_doc)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except Exception as exc:
        raise HTTPException(500, f"重试提取失败: {exc}") from exc


@app.get("/api/documents/{doc_id}/file")
async def get_document_file(doc_id: int) -> FileResponse:
    doc = await DocumentRecord.get_or_none(id=doc_id)
    if not doc:
        raise HTTPException(404, "记录不存在")
    if not doc.stored_path or not os.path.exists(doc.stored_path):
        raise HTTPException(404, "原始文件不存在")

    return FileResponse(path=doc.stored_path, filename=doc.title)


def build_document_chunks_response(doc: DocumentRecord) -> DocumentChunksResponse:
    """基于文档当前 IR 或 Markdown 即时生成分块调试响应。"""
    document_ir = _prepare_debug_document_ir(doc)
    response_model = get_response_model(doc.doc_type)
    if response_model is None:
        raise ValueError(f"不支持的文档类型: {doc.doc_type}")
    contract = build_extraction_contract(doc.doc_type, response_model)
    chunks = split_ir_into_chunks(
        document_ir,
        max_chars=settings.extraction_chunk_max_chars,
        ignore_sections=contract.ignore_sections,
    )
    return DocumentChunksResponse(
        doc_id=doc.id,
        chunk_count=len(chunks),
        chunk_max_chars=settings.extraction_chunk_max_chars,
        ignored_sections=list(contract.ignore_sections),
        chunks=[_chunk_to_debug_dto(chunk) for chunk in chunks],
    )


def _prepare_debug_document_ir(doc: DocumentRecord) -> DocumentIR:
    """读取已保存 IR，缺失时用 raw_text 临时构造基础 IR。"""
    if doc.document_ir:
        return document_ir_from_payload(doc.document_ir)
    if doc.raw_text:
        return build_basic_ir_from_markdown(doc.raw_text, doc_type=doc.doc_type)
    raise ValueError("文档尚未解析，暂无分块数据")


def _chunk_to_debug_dto(chunk: DocumentChunk) -> DocumentChunkDebugDTO:
    """将内部 DocumentChunk 转换为前端调试视图需要的 DTO。"""
    return DocumentChunkDebugDTO(
        chunk_id=chunk.chunk_id,
        section_path=list(chunk.section_path),
        page_start=chunk.page_start,
        page_end=chunk.page_end,
        element_count=len(chunk.elements),
        markdown_chars=len(chunk.markdown),
        element_ids=[element.element_id for element in chunk.elements],
        markdown=chunk.markdown,
    )


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

import logging
import os

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from tortoise.contrib.fastapi import register_tortoise

from core.config import get_settings
from core.document_service import process_uploaded_file
from schemas.dto import DocumentRecordDTO, DocumentUpdateRequest, UploadResponse
from schemas.models import DocumentRecord


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
settings = get_settings()

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
    file: UploadFile = File(...),
    doc_type: str | None = Form(None),
) -> UploadResponse:
    return await process_uploaded_file(file, doc_type=doc_type, upload_dir=settings.upload_dir)


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
    if body.parsed_content is not None and body.parsed_content != doc.parsed_content:
        doc.parsed_content = body.parsed_content
        update_fields.append("parsed_content")
    if body.extracted_data is not None and body.extracted_data != doc.extracted_data:
        doc.extracted_data = body.extracted_data
        update_fields.append("extracted_data")

    if update_fields:
        await doc.save(update_fields=update_fields)
    await doc.refresh_from_db()
    return DocumentRecordDTO.model_validate(doc)


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

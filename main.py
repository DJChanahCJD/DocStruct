import os, uuid, aiofiles, logging
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from tortoise.contrib.fastapi import register_tortoise

from core.parser import ParserFactory
from core.extractor import extract_structure_with_meta, classify_document
from core.retrieval import build_retrieval_corpus, answer_question
from schemas.models import (
    DocumentRecord, SrsDocument, ApiDocument, 
    DesignDocument, UserManualDocument,
    TestPlanDocument, TestCaseDocument, TestReportDocument,
    UploadResponse, DocType, QaRequest, QaResponse
)

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="DocStruct MVP")

# 1. 映射配置：将文档类型直接映射到对应的 Pydantic 模型
TYPE_MODEL_MAP = {
    DocType.SRS: SrsDocument,
    DocType.API: ApiDocument,
    DocType.DESIGN: DesignDocument,
    DocType.TEST_PLAN: TestPlanDocument,
    DocType.TEST_CASE: TestCaseDocument,
    DocType.TEST_REPORT: TestReportDocument,
    DocType.USER_MANUAL: UserManualDocument,
}

UPLOAD_DIR = "db/uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# 静态资源处理
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
async def read_root():
    return FileResponse("static/index.html")

@app.post("/api/upload", response_model=UploadResponse)
async def upload_document(file: UploadFile = File(...)):
    # 扩展名校验
    allowed_extensions = {".pdf", ".docx", ".md", ".txt"}
    file_ext = os.path.splitext(file.filename)[1].lower()
    
    if file_ext not in allowed_extensions:
        raise HTTPException(400, f"不支持的文件类型: {file_ext}。仅支持: {', '.join(allowed_extensions)}")

    # 保存文件
    file_path = os.path.join(UPLOAD_DIR, f"{uuid.uuid4()}{file_ext}")
    async with aiofiles.open(file_path, 'wb') as f:
        await f.write(await file.read())

    # 创建初始数据库记录
    logger.info(f"Start processing file: {file.filename} -> {file_path}")
    doc = await DocumentRecord.create(filename=file.filename, stored_path=file_path, status="processing")

    try:
        # A. 解析与分类
        # 使用工厂模式获取对应的解析器
        logger.info("Parsing document content...")
        parser = ParserFactory.get_parser(file_path)
        md_text = parser.parse(file_path)
        logger.info(f"Parsed content length: {len(md_text)}")
        
        logger.info("Classifying document type...")
        cls_result = classify_document(md_text)
        logger.info(f"Classification result: {cls_result}")
        
        # B. 匹配模型并提取
        target_model = TYPE_MODEL_MAP.get(cls_result.doc_type)
        if not target_model:
            logger.warning(f"Unknown document type: {cls_result.doc_type}")
            doc.update_from_dict({"status": "completed", "doc_type": cls_result.doc_type.value, "error_message": "未知的文档类型"})
        else:
            # 结构化提取
            logger.info(f"Extracting structure using model: {target_model.__name__}")
            extracted, extraction_meta = extract_structure_with_meta(md_text, target_model)
            logger.info(
                "Extraction meta: mode=%s, chunk_count=%s, failed_chunks=%s, fallback_used=%s",
                extraction_meta.get("mode"),
                extraction_meta.get("chunk_count"),
                extraction_meta.get("failed_chunks"),
                extraction_meta.get("fallback_used"),
            )
            doc.update_from_dict({
                "status": "completed",
                "doc_type": cls_result.doc_type.value,
                "parsed_content": md_text,
                "extracted_data": extracted.model_dump()
            })
            logger.info("Extraction completed successfully.")
        
        await doc.save()

        vector_warning = None
        try:
            await build_retrieval_corpus(doc.id)
        except Exception as ve:
            vector_warning = str(ve)
            logger.warning("Vector build failed but upload remains successful. doc_id=%s error=%s", doc.id, ve)
            await doc.update_from_dict({"error_message": f"向量索引构建失败: {vector_warning}"}).save()
        else:
            if doc.status == "completed" and doc.extracted_data:
                await doc.update_from_dict({"error_message": None}).save()

        message = f"识别为: {doc.doc_type}"
        if vector_warning:
            message += "（向量索引构建失败，可稍后重建）"
        return UploadResponse(id=doc.id, filename=doc.filename, status="completed", message=message)

    except Exception as e:
        logger.error(f"Error processing document {file.filename}: {e}", exc_info=True)
        await doc.update_from_dict({"status": "failed", "error_message": str(e)}).save()
        raise HTTPException(500, f"处理失败: {str(e)}")

@app.get("/api/documents")
async def list_documents():
    return await DocumentRecord.all().order_by("-id")

@app.get("/api/documents/{doc_id}")
async def get_document(doc_id: int):
    doc = await DocumentRecord.get_or_none(id=doc_id)
    if not doc:
        raise HTTPException(404, "记录不存在")
    return doc

@app.delete("/api/documents/{doc_id}")
async def delete_document(doc_id: int):
    doc = await DocumentRecord.get_or_none(id=doc_id)
    if not doc:
        raise HTTPException(404, "记录不存在")
    
    # 删除物理文件
    if doc.stored_path and os.path.exists(doc.stored_path):
        try:
            os.remove(doc.stored_path)
        except Exception as e:
            print(f"删除文件失败: {e}")
            
    await doc.delete()
    return {"message": "删除成功", "id": doc_id}


@app.post("/api/reindex/{doc_id}")
async def reindex_document(doc_id: int):
    doc = await DocumentRecord.get_or_none(id=doc_id)
    if not doc:
        raise HTTPException(404, "记录不存在")
    try:
        await build_retrieval_corpus(doc_id)
        return {"message": "重建索引成功", "doc_id": doc_id}
    except Exception as e:
        logger.error(f"Reindex failed for doc {doc_id}: {e}", exc_info=True)
        raise HTTPException(500, f"重建索引失败: {str(e)}")


@app.post("/api/qa", response_model=QaResponse)
async def qa(request: QaRequest):
    try:
        result = await answer_question(
            question=request.question,
            doc_id=request.doc_id,
            top_k=request.top_k,
        )
        return QaResponse(**result)
    except Exception as e:
        logger.error(f"QA failed: {e}", exc_info=True)
        raise HTTPException(500, f"问答失败: {str(e)}")

# 注册 Tortoise ORM
register_tortoise(
    app, db_url="sqlite://db/db.sqlite3",
    modules={"models": ["schemas.models"]},
    generate_schemas=True, add_exception_handlers=True,
)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8001, reload=False)  # reload 为True时似乎不会打印日志

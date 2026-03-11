import os, uuid, aiofiles
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from tortoise.contrib.fastapi import register_tortoise

from core.parser import parse_pdf_to_markdown
from core.extractor import extract_structure, classify_document
from schemas.models import (
    DocumentRecord, SrsDocument, ApiDocument, 
    TestReportDocument, UploadResponse, DocType
)

app = FastAPI(title="DocStruct MVP")

# 1. 映射配置：将文档类型直接映射到对应的 Pydantic 模型
TYPE_MODEL_MAP = {
    DocType.SRS: SrsDocument,
    DocType.API: ApiDocument,
    DocType.TEST: TestReportDocument,
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
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(400, "仅支持 PDF 文件")

    # 保存文件
    file_path = os.path.join(UPLOAD_DIR, f"{uuid.uuid4()}_{file.filename}")
    async with aiofiles.open(file_path, 'wb') as f:
        await f.write(await file.read())

    # 创建初始数据库记录
    doc = await DocumentRecord.create(filename=file.filename, stored_path=file_path, status="processing")

    try:
        # A. 解析与分类
        md_text = parse_pdf_to_markdown(file_path)
        cls_result = classify_document(md_text)
        
        # B. 匹配模型并提取
        target_model = TYPE_MODEL_MAP.get(cls_result.doc_type)
        if not target_model:
            doc.update_from_dict({"status": "completed", "doc_type": cls_result.doc_type.value, "error_message": "未知的文档类型"})
        else:
            # 结构化提取
            extracted = extract_structure(md_text, target_model)
            doc.update_from_dict({
                "status": "completed",
                "doc_type": cls_result.doc_type.value,
                "parsed_content": md_text,
                "extracted_data": extracted.model_dump()
            })
        
        await doc.save()
        return UploadResponse(id=doc.id, filename=doc.filename, status="completed", message=f"识别为: {doc.doc_type}")

    except Exception as e:
        await doc.update_from_dict({"status": "failed", "error_message": str(e)}).save()
        raise HTTPException(500, f"处理失败: {str(e)}")

@app.get("/api/documents")
async def list_documents():
    return await DocumentRecord.all().order_by("-id")

@app.get("/api/documents/{doc_id}")
async def get_document(doc_id: int):
    doc = await DocumentRecord.get_or_none(id=doc_id)
    return doc or HTTPException(404, "记录不存在")

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

# 注册 Tortoise ORM
register_tortoise(
    app, db_url="sqlite://db/db.sqlite3",
    modules={"models": ["schemas.models"]},
    generate_schemas=True, add_exception_handlers=True,
)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)

from tortoise import fields, models
from pydantic import BaseModel, Field
from typing import Literal, List, Optional
from enum import Enum

# --- Enums ---

class DocType(str, Enum):
    SRS = "srs"
    API = "api"
    TEST = "test"
    UNKNOWN = "unknown"

# --- Tortoise ORM Models (Database) ---

class DocumentRecord(models.Model):
    """
    文档记录表，存储上传的文档元数据及提取结果
    """
    id = fields.IntField(pk=True)
    filename = fields.CharField(max_length=255, description="原始文件名")
    stored_path = fields.CharField(max_length=512, description="文件存储路径")
    upload_time = fields.DatetimeField(auto_now_add=True, description="上传时间")
    doc_type = fields.CharField(max_length=50, default="unknown", description="文档类型") # 新增字段
    parsed_content = fields.TextField(null=True, description="解析后的Markdown内容")
    extracted_data = fields.JSONField(null=True, description="LLM提取的结构化JSON数据")
    status = fields.CharField(max_length=20, default="pending", description="状态: pending/processing/completed/failed")
    error_message = fields.TextField(null=True, description="错误信息")

    class Meta:
        table = "document_records"

# --- Pydantic Models (Classification) ---

class DocClassification(BaseModel):
    """
    文档类型分类结果
    """
    doc_type: DocType = Field(..., description="文档类型")
    confidence: float = Field(..., description="置信度 (0.0-1.0)")
    reasoning: str = Field(..., description="分类理由")

# --- Pydantic Models (LLM Extraction & API) ---

# 1. SRS (Software Requirements Specification)
class RequirementItem(BaseModel):
    """
    单条需求定义
    """
    id: str = Field(..., description="需求ID，如 REQ-001")
    description: str = Field(..., description="需求描述文本")
    priority: Literal["low", "medium", "high"] = Field(default="medium", description="优先级")

class SrsDocument(BaseModel):
    """
    软件需求规格说明书 (SRS) 结构
    """
    doc_type: Literal["srs"] = Field(default="srs", description="文档类型标识")
    title: str = Field(..., description="文档标题")
    version: str = Field(default="1.0", description="文档版本")
    requirements: List[RequirementItem] = Field(..., description="提取的需求列表")

# 2. API Documentation
class ApiEndpoint(BaseModel):
    """
    API 接口定义
    """
    method: Literal["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"] = Field(..., description="HTTP 方法")
    path: str = Field(..., description="接口路径，如 /api/v1/users")
    summary: str = Field(..., description="接口简要说明")
    description: Optional[str] = Field(None, description="详细描述")

class ApiDocument(BaseModel):
    """
    API 接口文档结构
    """
    doc_type: Literal["api"] = Field(default="api", description="文档类型标识")
    title: str = Field(..., description="文档标题")
    version: str = Field(default="1.0", description="API 版本")
    base_url: Optional[str] = Field(None, description="基础 URL")
    endpoints: List[ApiEndpoint] = Field(..., description="提取的接口列表")

# 3. Test Report
class TestCase(BaseModel):
    """
    测试用例结果
    """
    id: str = Field(..., description="测试用例ID")
    name: str = Field(..., description="测试用例名称")
    status: Literal["pass", "fail", "skipped", "error"] = Field(..., description="执行状态")
    failure_reason: Optional[str] = Field(None, description="失败原因（如果有）")

class TestReportDocument(BaseModel):
    """
    测试报告结构
    """
    doc_type: Literal["test"] = Field(default="test", description="文档类型标识")
    title: str = Field(..., description="报告标题")
    summary: str = Field(..., description="测试执行摘要")
    total_tests: int = Field(..., description="测试总数")
    passed_tests: int = Field(..., description="通过数量")
    failed_tests: int = Field(..., description="失败数量")
    test_cases: List[TestCase] = Field(..., description="测试用例详情列表")

# --- API Response Models ---

class UploadResponse(BaseModel):
    id: int
    filename: str
    status: str
    message: str

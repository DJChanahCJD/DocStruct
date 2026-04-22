"""
数据库 ORM 模型（Tortoise）及结构化提取 Pydantic 模型。

API 层 DTO 请见 schemas/dto.py。
"""

from enum import Enum
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field
from tortoise import fields, models


class DocType(str, Enum):
    SRS = "srs"
    API = "api"
    DESIGN = "design"
    TEST = "test"
    MANUAL = "manual"
    ISSUE = "issue"
    UNKNOWN = "unknown"


class DocumentRecord(models.Model):
    id = fields.IntField(pk=True)
    filename = fields.CharField(max_length=255, description="原始文件名")
    stored_path = fields.CharField(max_length=512, description="文件存储路径")
    upload_time = fields.DatetimeField(auto_now_add=True, description="上传时间")
    doc_type = fields.CharField(max_length=50, default="unknown", description="文档类型")
    parsed_content = fields.TextField(null=True, description="解析后的 Markdown 内容")
    extracted_data = fields.JSONField(null=True, description="结构化 JSON 数据")
    status = fields.CharField(max_length=20, default="pending", description="状态")
    error_message = fields.TextField(null=True, description="错误信息")

    class Meta:
        table = "document_records"


class BaseExtractedDocument(BaseModel):
    doc_type: DocType = Field(..., description="文档类型")
    title: Optional[str] = Field(None, description="文档标题")
    summary: Optional[str] = Field(None, description="文档摘要")
    version: Optional[str] = Field(None, description="版本号")
    extra: dict[str, Any] = Field(default_factory=dict, description="非核心补充信息")


class RequirementItem(BaseModel):
    id: Optional[str] = Field(None, description="需求 ID")
    title: Optional[str] = Field(None, description="需求标题")
    description: str = Field(..., description="需求描述")
    priority: Optional[Literal["low", "medium", "high"]] = Field(None, description="优先级")


class SrsDocument(BaseExtractedDocument):
    doc_type: Literal["srs"] = Field(default="srs")
    items: list[RequirementItem] = Field(default_factory=list)


class ApiEndpoint(BaseModel):
    method: str = Field(..., description="HTTP 方法")
    path: str = Field(..., description="接口路径")
    summary: Optional[str] = Field(None, description="接口摘要")
    request: Optional[str] = Field(None, description="请求摘要")
    response: Optional[str] = Field(None, description="响应摘要")


class ApiDocument(BaseExtractedDocument):
    doc_type: Literal["api"] = Field(default="api")
    base_url: Optional[str] = Field(None, description="基础 URL")
    items: list[ApiEndpoint] = Field(default_factory=list)


class DesignModule(BaseModel):
    name: str = Field(..., description="模块名称")
    description: Optional[str] = Field(None, description="模块描述")


class DesignDocument(BaseExtractedDocument):
    doc_type: Literal["design"] = Field(default="design")
    architecture: Optional[str] = Field(None, description="架构摘要")
    items: list[DesignModule] = Field(default_factory=list)


class TestItem(BaseModel):
    id: Optional[str] = Field(None, description="测试项 ID")
    title: str = Field(..., description="测试项标题")
    steps: list[str] = Field(default_factory=list, description="测试步骤")
    expected: Optional[str] = Field(None, description="预期结果")
    actual: Optional[str] = Field(None, description="实际结果")
    status: Optional[Literal["pass", "fail", "blocked", "unknown"]] = Field(None, description="测试状态")


class TestDocument(BaseExtractedDocument):
    doc_type: Literal["test"] = Field(default="test")
    test_stage: Optional[Literal["plan", "case", "report"]] = Field(None, description="测试阶段")
    items: list[TestItem] = Field(default_factory=list)


class ManualSection(BaseModel):
    title: str = Field(..., description="章节标题")
    content: str = Field(..., description="章节内容")


class ManualDocument(BaseExtractedDocument):
    doc_type: Literal["manual"] = Field(default="manual")
    items: list[ManualSection] = Field(default_factory=list)


class IssueDocument(BaseExtractedDocument):
    doc_type: Literal["issue"] = Field(default="issue")
    issue_id: Optional[str] = Field(None, description="问题编号")
    status: Optional[str] = Field(None, description="当前状态")
    severity: Optional[str] = Field(None, description="严重级别")
    steps: list[str] = Field(default_factory=list, description="复现步骤")
    expected: Optional[str] = Field(None, description="期望结果")
    actual: Optional[str] = Field(None, description="实际结果")

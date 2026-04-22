"""
数据库 ORM 模型（Tortoise）及 LLM 提取结构 Pydantic 模型。

API 层 DTO 请见 schemas/dto.py。
"""

from enum import Enum
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field
from tortoise import fields, models


class DocType(str, Enum):
    """文档类型枚举。"""

    SRS = "srs"
    API = "api"
    DESIGN = "design"
    TEST = "test"
    MANUAL = "manual"
    ISSUE = "issue"
    UNKNOWN = "unknown"


class DocumentRecord(models.Model):
    """
    文档记录表，存储上传的文档元数据及提取结果。
    """

    id = fields.IntField(pk=True)
    filename = fields.CharField(max_length=255, description="原始文件名")
    stored_path = fields.CharField(max_length=512, description="文件存储路径")
    upload_time = fields.DatetimeField(auto_now_add=True, description="上传时间")
    doc_type = fields.CharField(max_length=50, default="unknown", description="文档类型")
    source_type = fields.CharField(max_length=20, default="file", description="来源类型: file/url")
    source_url = fields.CharField(max_length=1024, null=True, description="URL 来源地址")
    llm_model = fields.CharField(max_length=100, null=True, description="处理该文档时使用的文本模型")
    parsed_content = fields.TextField(null=True, description="解析后的Markdown内容")
    extracted_data = fields.JSONField(null=True, description="LLM提取的结构化JSON数据")
    status = fields.CharField(max_length=20, default="pending", description="状态: pending/processing/completed/failed")
    error_message = fields.TextField(null=True, description="错误信息")

    class Meta:
        table = "document_records"


class ChunkRecord(models.Model):
    """
    文档分块向量表，用于向量检索。
    """

    id = fields.IntField(pk=True)
    doc = fields.ForeignKeyField("models.DocumentRecord", related_name="chunks", on_delete=fields.CASCADE)
    chunk_index = fields.IntField(description="块序号")
    title_path = fields.CharField(max_length=500, null=True, description="标题路径")
    section_title = fields.CharField(max_length=255, null=True, description="当前章节标题")
    embed_text = fields.TextField(null=True, description="向量化文本")
    display_text = fields.TextField(null=True, description="展示文本")
    vector = fields.JSONField(description="向量")

    class Meta:
        table = "chunk_records"
        unique_together = (("doc", "chunk_index"),)


class DocClassification(BaseModel):
    """文档类型分类结果。"""

    doc_type: DocType = Field(..., description="文档类型")
    confidence: float = Field(..., ge=0.0, le=1.0, description="置信度 (0.0-1.0)")
    reasoning: Optional[str] = Field(None, description="分类理由")


class BaseExtractedDocument(BaseModel):
    """统一文档外层结构。"""

    doc_type: DocType = Field(..., description="文档类型")
    title: Optional[str] = Field(None, description="文档标题")
    summary: Optional[str] = Field(None, description="文档摘要")
    version: Optional[str] = Field(None, description="版本号")
    extra: dict[str, Any] = Field(default_factory=dict, description="非核心补充信息")


class RequirementItem(BaseModel):
    """SRS 核心需求项。"""

    id: Optional[str] = Field(None, description="需求ID，如 REQ-001")
    title: Optional[str] = Field(None, description="需求标题")
    description: str = Field(..., description="需求描述文本")
    priority: Optional[Literal["low", "medium", "high"]] = Field(None, description="优先级")


class SrsDocument(BaseExtractedDocument):
    """软件需求规格说明书。"""

    doc_type: Literal["srs"] = Field(default="srs", description="文档类型标识")
    items: list[RequirementItem] = Field(default_factory=list, description="需求列表")


class ApiEndpoint(BaseModel):
    """API 接口核心字段。"""

    method: str = Field(..., description="HTTP 方法")
    path: str = Field(..., description="接口路径")
    summary: Optional[str] = Field(None, description="接口摘要")
    request: Optional[str] = Field(None, description="请求摘要")
    response: Optional[str] = Field(None, description="响应摘要")


class ApiDocument(BaseExtractedDocument):
    """API 接口文档。"""

    doc_type: Literal["api"] = Field(default="api", description="文档类型标识")
    base_url: Optional[str] = Field(None, description="基础 URL")
    items: list[ApiEndpoint] = Field(default_factory=list, description="接口列表")


class DesignModule(BaseModel):
    """设计文档中的模块项。"""

    name: str = Field(..., description="模块名称")
    description: Optional[str] = Field(None, description="模块描述")


class DesignDocument(BaseExtractedDocument):
    """系统设计文档。"""

    doc_type: Literal["design"] = Field(default="design", description="文档类型标识")
    architecture: Optional[str] = Field(None, description="架构摘要")
    items: list[DesignModule] = Field(default_factory=list, description="模块列表")


class TestItem(BaseModel):
    """统一测试项。"""

    id: Optional[str] = Field(None, description="测试项 ID")
    title: str = Field(..., description="测试项标题")
    steps: list[str] = Field(default_factory=list, description="测试步骤")
    expected: Optional[str] = Field(None, description="预期结果")
    actual: Optional[str] = Field(None, description="实际结果")
    status: Optional[Literal["pass", "fail", "blocked", "unknown"]] = Field(None, description="测试状态")


class TestDocument(BaseExtractedDocument):
    """统一测试文档。"""

    doc_type: Literal["test"] = Field(default="test", description="文档类型标识")
    test_stage: Optional[Literal["plan", "case", "report"]] = Field(None, description="测试阶段")
    items: list[TestItem] = Field(default_factory=list, description="测试项列表")


class ManualSection(BaseModel):
    """用户手册章节。"""

    title: str = Field(..., description="章节标题")
    content: str = Field(..., description="章节内容")


class ManualDocument(BaseExtractedDocument):
    """用户手册文档。"""

    doc_type: Literal["manual"] = Field(default="manual", description="文档类型标识")
    items: list[ManualSection] = Field(default_factory=list, description="章节列表")


class IssueDocument(BaseExtractedDocument):
    """问题单或缺陷单。"""

    doc_type: Literal["issue"] = Field(default="issue", description="文档类型标识")
    issue_id: Optional[str] = Field(None, description="问题编号")
    status: Optional[str] = Field(None, description="当前状态")
    severity: Optional[str] = Field(None, description="严重级别")
    steps: list[str] = Field(default_factory=list, description="复现步骤")
    expected: Optional[str] = Field(None, description="期望结果")
    actual: Optional[str] = Field(None, description="实际结果")

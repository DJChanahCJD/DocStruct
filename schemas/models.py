"""
ORM records and Pydantic models for DocStruct's extraction pipeline.

The output contract is centered on five software-engineering object slots and
evidence bindings. Source traceability is expressed through `source_id` for
document-native identifiers and `evidence_element_ids` for source grounding.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Literal, Optional, Union

from pydantic import BaseModel, Field, field_validator
from tortoise import fields, models


# =========================
# Enums
# =========================


class DocType(str, Enum):
    SRS = "srs"
    API = "api"
    DESIGN = "design"
    TEST = "test"
    MANUAL = "manual"
    ISSUE = "issue"
    UNKNOWN = "unknown"


class TestStage(str, Enum):
    PLAN = "plan"
    CASE = "case"
    REPORT = "report"



class EntityType(str, Enum):
    ACTOR = "actor"  # 参与者（人、角色等发起动作的对象）
    SYSTEM = "system" # 内部系统、模块、服务、外部系统
    DATA = "data"     # 数据实体（如数据库表、文件、日志、消息体等）
    OTHER = "other"  # 兜底类型；若占比过高，需分析和升级为主类型



class ProcessType(str, Enum):
    BUSINESS = "business"   # 业务视角的流程（含跨系统的端到端流程）
    TECHNICAL = "technical" # 系统/技术视角的内部流程（含工作流、操作步骤等）
    TEST = "test"           # 测试流程
    OTHER = "other"         # 兜底


class RequirementType(str, Enum):
    FUNCTIONAL = "functional"
    NON_FUNCTIONAL = "non_functional"
    OTHER = "other"


class DocumentStatus(str, Enum):
    PENDING = "pending"
    UPLOADED = "uploaded"
    PARSING = "parsing"
    EXTRACTING = "extracting"
    COMPLETED = "completed"
    FAILED = "failed"


# =========================
# ORM Models
# =========================


class DocumentRecord(models.Model):
    """
    File record table.

    - `parsed_content` stores the human-readable Markdown preview.
    - `document_ir` stores the parser IR used for chunking and evidence binding.
    - `extracted_data` stores the final extracted JSON.
    """

    id = fields.IntField(pk=True)
    filename = fields.CharField(max_length=255, description="原始文件名")
    stored_path = fields.CharField(max_length=512, description="文件存储路径")
    upload_time = fields.DatetimeField(auto_now_add=True, description="上传时间")

    doc_type = fields.CharField(
        max_length=50,
        default=DocType.UNKNOWN.value,
        description="文档类型",
    )

    parsed_content = fields.TextField(
        null=True,
        description="解析后的 Markdown / 文本内容",
    )
    document_ir = fields.JSONField(
        null=True,
        description="文档元素 IR，用于分块与证据回溯",
    )
    extracted_data = fields.JSONField(
        null=True,
        description="结构化 JSON 数据",
    )

    status = fields.CharField(
        max_length=20,
        default=DocumentStatus.PENDING.value,
        description="处理状态",
    )
    error_message = fields.TextField(
        null=True,
        description="错误信息",
    )

    class Meta:
        table = "document_records"


# =========================
# Document IR
# =========================


class DocumentElement(BaseModel):
    element_id: str = Field(..., description="Stable element identifier")
    element_type: str = Field(..., description="heading / paragraph / table / image / code / footer")
    text: Optional[str] = Field(None, description="Plain element text")
    markdown: Optional[str] = Field(None, description="Markdown rendering for this element")
    section_path: list[str] = Field(default_factory=list, description="Heading path containing this element")
    page: Optional[int] = Field(None, description="Source page number when available")
    bbox: Optional[list[float]] = Field(
        None,
        description="PDF point bbox [x0, y0, x1, y1] when available, usually from Docling provenance",
    )
    order: int = Field(..., description="Reading order")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Parser-specific metadata")


class DocumentOutline(BaseModel):
    title: Optional[str] = Field(None, description="Document title")
    doc_type: DocType = Field(default=DocType.UNKNOWN, description="Document type")
    sections: list[str] = Field(default_factory=list, description="Flattened section headings")
    main_topics: list[str] = Field(default_factory=list, description="Short topic hints from headings")


class DocumentChunk(BaseModel):
    chunk_id: str = Field(..., description="Chunk identifier")
    section_path: list[str] = Field(default_factory=list, description="Section path for the chunk")
    elements: list[DocumentElement] = Field(default_factory=list, description="Elements included in this chunk")
    markdown: str = Field("", description="Chunk Markdown with element markers")
    page_start: Optional[int] = Field(None, description="First source page in chunk")
    page_end: Optional[int] = Field(None, description="Last source page in chunk")


class DocumentIR(BaseModel):
    title: Optional[str] = None
    doc_type: DocType = Field(default=DocType.UNKNOWN)
    elements: list[DocumentElement] = Field(default_factory=list)
    outline: DocumentOutline = Field(default_factory=DocumentOutline)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ExtractionContract(BaseModel):
    doc_type: DocType
    target_slots: list[str]
    slot_descriptions: dict[str, str] = Field(default_factory=dict)
    rules: list[str] = Field(default_factory=list)
    ignore_sections: list[str] = Field(default_factory=list)


# =========================
# Unified Object Slots
# =========================


class BaseNode(BaseModel):
    id: Optional[str] = Field(None, description="System-generated object ID, e.g. REQ-001")
    source_id: Optional[str] = Field(None, description="Original source document ID, e.g. SRS-USER-001")
    name: str = Field(..., description="Object name")
    description: Optional[str] = Field(None, description="Object description")
    evidence_element_ids: list[str] = Field(default_factory=list, description="Source IR element IDs")
    extra: dict[str, Any] = Field(default_factory=dict, description="Small supplementary fields")

    @field_validator("extra", mode="before")
    @classmethod
    def _normalize_extra(cls, value: Any) -> dict[str, Any]:
        if value is None:
            return {}
        if isinstance(value, dict):
            return value
        return {}

class StepItem(BaseModel):
    id: Optional[str] = Field(None, description="Step ID")
    name: str = Field(..., description="Step name")
    description: Optional[str] = Field(None, description="Step description")
    evidence_element_ids: list[str] = Field(default_factory=list, description="Source IR element IDs")


class EntityItem(BaseNode):
    entity_type: EntityType = Field(default=EntityType.OTHER, description="Entity type")

    @field_validator("entity_type", mode="before")
    @classmethod
    def _normalize_entity_type(cls, value: Any) -> EntityType:
        if isinstance(value, EntityType):
            return value
        if isinstance(value, str):
            try:
                return EntityType(value)
            except ValueError:
                return EntityType.OTHER
        return EntityType.OTHER


class ProcessItem(BaseNode):
    process_type: ProcessType = Field(default=ProcessType.OTHER, description="Process type")
    steps: list[StepItem] = Field(default_factory=list, description="Ordered process steps")

    @field_validator("process_type", mode="before")
    @classmethod
    def _normalize_process_type(cls, value: Any) -> ProcessType:
        if isinstance(value, ProcessType):
            return value
        if isinstance(value, str):
            try:
                return ProcessType(value)
            except ValueError:
                return ProcessType.OTHER
        return ProcessType.OTHER


class RequirementItem(BaseNode):
    requirement_type: RequirementType = Field(default=RequirementType.OTHER, description="Requirement type")
    details: list[str] = Field(default_factory=list, description="Details or functional points")
    acceptance_criteria: list[str] = Field(default_factory=list, description="Acceptance criteria")
    metric: Optional[str] = Field(None, description="Quantified metric")

    @field_validator("requirement_type", mode="before")
    @classmethod
    def _normalize_requirement_type(cls, value: Any) -> RequirementType:
        if isinstance(value, RequirementType):
            return value
        if isinstance(value, str):
            try:
                return RequirementType(value)
            except ValueError:
                return RequirementType.OTHER
        return RequirementType.OTHER


class InterfaceItem(BaseNode):
    interface_type: str = Field(default="other", description="Interface type, e.g. http, rpc, message, ui, database, file")
    method: Optional[str] = Field(None, description="Method or call style")
    path: Optional[str] = Field(None, description="Endpoint path or protocol address")
    target: Optional[str] = Field(None, description="Target system, service, or resource")

    @field_validator("interface_type", mode="before")
    @classmethod
    def _normalize_interface_type(cls, value: Any) -> str:
        if value is None:
            return "other"
        text = str(value).strip().lower()
        return text or "other"

    @field_validator("method", mode="before")
    @classmethod
    def _normalize_method(cls, value: Any) -> Optional[str]:
        if value is None:
            return None
        text = str(value).strip()
        return text or None


class ArtifactItem(BaseNode):
    artifact_type: str = Field(default="other", description="Artifact type, e.g. test_case, decision, table, issue, section")
    details: list[str] = Field(default_factory=list, description="Artifact details")

    @field_validator("artifact_type", mode="before")
    @classmethod
    def _normalize_artifact_type(cls, value: Any) -> str:
        if value is None:
            return "other"
        text = str(value).strip().lower()
        return text or "other"


class ExtractedObjectSet(BaseModel):
    entities: list[EntityItem] = Field(default_factory=list, description="Entities")
    processes: list[ProcessItem] = Field(default_factory=list, description="Processes")
    requirements: list[RequirementItem] = Field(default_factory=list, description="Requirements")
    interfaces: list[InterfaceItem] = Field(default_factory=list, description="Interfaces")
    artifacts: list[ArtifactItem] = Field(default_factory=list, description="Artifacts")


class Evidence(BaseModel):
    object_id: str = Field(..., description="Bound object ID")
    element_id: Optional[str] = Field(None, description="Source element ID when available")
    text_span: Optional[str] = Field(None, description="Source text span")
    page: Optional[int] = Field(None, description="Source page when available")
    bbox: Optional[list[float]] = Field(
        None,
        description="Source PDF point bbox [x0, y0, x1, y1] when available for frontend evidence highlighting",
    )


# =========================
# Document Models
# =========================


class BaseExtractedDocument(BaseModel):
    doc_type: DocType = Field(..., description="Document type")
    title: Optional[str] = Field(None, description="Document title")
    summary: Optional[str] = Field(None, description="Document summary")
    version: Optional[str] = Field(None, description="Version")
    extra: dict[str, Any] = Field(default_factory=dict, description="Document-level supplementary fields")


class StructuredDocument(BaseExtractedDocument, ExtractedObjectSet):
    evidence: list[Evidence] = Field(default_factory=list, description="Evidence bindings")


class SrsDocument(StructuredDocument):
    doc_type: Literal["srs"] = Field(default="srs")


class ApiDocument(StructuredDocument):
    doc_type: Literal["api"] = Field(default="api")
    base_url: Optional[str] = Field(None, description="Base URL")


class DesignDocument(StructuredDocument):
    doc_type: Literal["design"] = Field(default="design")


class TestDocument(StructuredDocument):
    doc_type: Literal["test"] = Field(default="test")
    test_stage: Optional[TestStage] = Field(None, description="Test stage")


class ManualDocument(StructuredDocument):
    doc_type: Literal["manual"] = Field(default="manual")


class IssueDocument(StructuredDocument):
    doc_type: Literal["issue"] = Field(default="issue")


ExtractedDocument = Union[
    SrsDocument,
    ApiDocument,
    DesignDocument,
    TestDocument,
    ManualDocument,
    IssueDocument,
]

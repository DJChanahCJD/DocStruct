"""
ORM records and Pydantic models for DocStruct's final extraction design.

The output contract is centered on five software-engineering object slots plus
business views and evidence bindings. Source traceability is expressed through
`evidence_element_ids` on objects and document-level `evidence` entries, not
through per-object `source_ref` blobs.
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


class PriorityLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class TestStage(str, Enum):
    PLAN = "plan"
    CASE = "case"
    REPORT = "report"


class EntityType(str, Enum):
    ACTOR = "actor"
    MODULE = "module"
    DATA = "data"
    SYSTEM = "system"
    SERVICE = "service"
    COMPONENT = "component"
    OTHER = "other"


class ProcessType(str, Enum):
    BUSINESS = "business"
    WORKFLOW = "workflow"
    OPERATION = "operation"
    TEST = "test"
    OTHER = "other"


class RequirementType(str, Enum):
    FUNCTIONAL = "functional"
    NON_FUNCTIONAL = "non_functional"
    BUSINESS_RULE = "business_rule"
    CONSTRAINT = "constraint"
    ACCEPTANCE = "acceptance"
    OTHER = "other"


class InterfaceType(str, Enum):
    HTTP = "http"
    RPC = "rpc"
    MESSAGE = "message"
    DATABASE = "database"
    FILE = "file"
    EXTERNAL_SYSTEM = "external_system"
    HARDWARE = "hardware"
    USER_INTERFACE = "user_interface"
    OTHER = "other"


class ArtifactType(str, Enum):
    API_ENDPOINT = "api_endpoint"
    DESIGN_MODULE = "design_module"
    TEST_CASE = "test_case"
    MANUAL_SECTION = "manual_section"
    ISSUE = "issue"
    DECISION = "decision"
    TABLE = "table"
    OTHER = "other"


class DocumentStatus(str, Enum):
    PENDING = "pending"
    UPLOADED = "uploaded"
    PARSING = "parsing"
    EXTRACTING = "extracting"
    COMPLETED = "completed"
    FAILED = "failed"


class RequirementCategory(str, Enum):
    USER_MANAGEMENT = "user_management"
    PERFORMANCE = "performance"
    SECURITY = "security"
    DATA = "data"
    INTERFACE = "interface"
    OTHER = "other"


class ArtifactStatus(str, Enum):
    PENDING = "pending"
    RESOLVED = "resolved"
    PASSED = "passed"
    FAILED = "failed"


class HttpMethod(str, Enum):
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    DELETE = "DELETE"
    PATCH = "PATCH"
    OPTIONS = "OPTIONS"
    HEAD = "HEAD"
    GRPC = "gRPC"
    AMQP = "AMQP"
    OTHER = "OTHER"


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
    bbox: Optional[list[float]] = Field(None, description="Bounding box [x0, y0, x1, y1] when available")
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
    id: Optional[str] = Field(None, description="Global object ID, e.g. REQ-001")
    name: Optional[str] = Field(None, description="Object name")
    description: Optional[str] = Field(None, description="Object description")
    evidence_element_ids: list[str] = Field(default_factory=list, description="Source IR element IDs")
    extra: dict[str, Any] = Field(default_factory=dict, description="Small supplementary fields")


class StepItem(BaseModel):
    id: Optional[str] = Field(None, description="Step ID")
    name: str = Field(..., description="Step name")
    description: Optional[str] = Field(None, description="Step description")
    evidence_element_ids: list[str] = Field(default_factory=list, description="Source IR element IDs")


class EntityItem(BaseNode):
    entity_type: EntityType = Field(default=EntityType.OTHER, description="Entity type")


class ProcessItem(BaseNode):
    process_type: ProcessType = Field(default=ProcessType.OTHER, description="Process type")
    steps: list[StepItem] = Field(default_factory=list, description="Ordered process steps")


class RequirementItem(BaseNode):
    requirement_type: RequirementType = Field(default=RequirementType.OTHER, description="Requirement type")
    priority: Optional[PriorityLevel] = Field(None, description="Priority")
    category: Optional[RequirementCategory] = Field(None, description="Requirement category")
    details: list[str] = Field(default_factory=list, description="Details or functional points")
    acceptance_criteria: list[str] = Field(default_factory=list, description="Acceptance criteria")
    metric: Optional[str] = Field(None, description="Quantified metric")


class InterfaceItem(BaseNode):
    interface_type: InterfaceType = Field(default=InterfaceType.OTHER, description="Interface type")
    method: Optional[HttpMethod] = Field(None, description="Method or call style")
    path: Optional[str] = Field(None, description="Endpoint path or protocol address")
    target: Optional[str] = Field(None, description="Target system, service, or resource")

    @field_validator("path", mode="before")
    @classmethod
    def validate_path(cls, value: Optional[str], info) -> Optional[str]:
        if not value:
            return value
        interface_type = info.data.get("interface_type")
        if interface_type == InterfaceType.HTTP:
            if not value.startswith("/"):
                raise ValueError(f"HTTP interface path must start with '/', got: {value}")
            if len(value) > 255:
                raise ValueError(f"Path exceeds max length 255: {value[:50]}...")
        return value


class ArtifactItem(BaseNode):
    artifact_type: ArtifactType = Field(default=ArtifactType.OTHER, description="Artifact type")
    status: Optional[ArtifactStatus] = Field(None, description="Artifact status")


class StructuredChunk(BaseModel):
    entities: list[EntityItem] = Field(default_factory=list, description="Entities in this chunk")
    processes: list[ProcessItem] = Field(default_factory=list, description="Processes in this chunk")
    requirements: list[RequirementItem] = Field(default_factory=list, description="Requirements in this chunk")
    interfaces: list[InterfaceItem] = Field(default_factory=list, description="Interfaces in this chunk")
    artifacts: list[ArtifactItem] = Field(default_factory=list, description="Artifacts in this chunk")


class BusinessView(BaseModel):
    view_name: str = Field(..., description="Business-facing view name")
    view_type: str = Field(..., description="View type, e.g. requirement_group")
    object_ids: list[str] = Field(default_factory=list, description="Referenced object IDs")
    description: Optional[str] = Field(None, description="Short view description")
    extra: dict[str, Any] = Field(default_factory=dict, description="Small supplementary fields")


class Evidence(BaseModel):
    evidence_id: str = Field(..., description="Evidence ID, e.g. EVD-001")
    object_id: str = Field(..., description="Bound object ID")
    element_id: Optional[str] = Field(None, description="Source element ID when available")
    text_span: Optional[str] = Field(None, description="Source text span")
    section_path: list[str] = Field(default_factory=list, description="Source section path")
    page: Optional[int] = Field(None, description="Source page when available")
    bbox: Optional[list[float]] = Field(None, description="Source bbox when available")


# =========================
# Document Models
# =========================


class BaseExtractedDocument(BaseModel):
    doc_type: DocType = Field(..., description="Document type")
    title: Optional[str] = Field(None, description="Document title")
    summary: Optional[str] = Field(None, description="Document summary")
    version: Optional[str] = Field(None, description="Version")
    extra: dict[str, Any] = Field(default_factory=dict, description="Document-level supplementary fields")


class StructuredDocument(BaseExtractedDocument):
    entities: list[EntityItem] = Field(default_factory=list, description="Entities")
    processes: list[ProcessItem] = Field(default_factory=list, description="Processes")
    requirements: list[RequirementItem] = Field(default_factory=list, description="Requirements")
    interfaces: list[InterfaceItem] = Field(default_factory=list, description="Interfaces")
    artifacts: list[ArtifactItem] = Field(default_factory=list, description="Artifacts")
    views: list[BusinessView] = Field(default_factory=list, description="Business views")
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

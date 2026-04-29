"""
ORM records and Pydantic models for DocStruct's extraction pipeline.

The output contract is centered on doc-type-specific typed schemas and evidence
bindings. Source traceability is expressed through `evidence_element_ids` for
source grounding.
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
    ACTOR = "actor"      # 参与者：人、角色等发起动作的对象
    SYSTEM = "system"    # 系统边界：内部系统、模块、服务、外部系统
    DATA = "data"        # 数据对象：表、文件、日志、消息体等
    OTHER = "other"      # 兜底类型


class ProcessType(str, Enum):
    BUSINESS = "business"      # 业务视角流程
    TECHNICAL = "technical"    # 系统或技术视角流程
    TEST = "test"              # 测试流程
    OTHER = "other"            # 兜底类型


class RequirementType(str, Enum):
    FUNCTIONAL = "functional"
    NON_FUNCTIONAL = "non_functional"
    OTHER = "other"


class InterfaceType(str, Enum):
    HTTP = "http"
    RPC = "rpc"
    MESSAGE = "message"
    UI = "ui"
    DATABASE = "database"
    FILE = "file"
    OTHER = "other"


class HttpMethod(str, Enum):
    GET = "get"
    POST = "post"
    PUT = "put"
    PATCH = "patch"
    DELETE = "delete"
    HEAD = "head"
    OPTIONS = "options"


class ArtifactType(str, Enum):
    TEST_CASE = "test_case"
    DECISION = "decision"
    TABLE = "table"
    ISSUE = "issue"
    SECTION = "section"
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
    文件记录。

    - `parsed_content`：可读 Markdown / 文本预览。
    - `document_ir`：用于分块和证据回溯的文档 IR。
    - `extracted_data`：最终结构化抽取结果。
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
        description="结构化抽取结果",
    )

    status = fields.CharField(
        max_length=20,
        default=DocumentStatus.PENDING.value,
        description="处理状态",
    )
    error_message = fields.TextField(
        null=True,
        description="失败原因",
    )

    class Meta:
        table = "document_records"


# =========================
# Document IR
# =========================


class DocumentElement(BaseModel):
    element_id: str = Field(..., description="稳定元素 ID")
    element_type: str = Field(..., description="元素类型，如 heading、paragraph、table、image、code、footer")
    text: Optional[str] = None
    markdown: Optional[str] = Field(None)
    section_path: list[str] = Field(default_factory=list, description="所属标题路径")
    page: Optional[int] = Field(None, description="来源页码")
    bbox: Optional[list[float]] = Field(
        None,
        description="PDF 坐标框 [x0, y0, x1, y1]",
    )
    order: int = Field(..., description="阅读顺序")
    metadata: dict[str, Any] = Field(default_factory=dict, description="解析器附加信息")


class DocumentOutline(BaseModel):
    title: Optional[str] = None
    doc_type: DocType = Field(default=DocType.UNKNOWN)
    sections: list[str] = Field(default_factory=list, description="扁平化标题列表")
    main_topics: list[str] = Field(default_factory=list, description="由标题提取的主题提示")


class DocumentChunk(BaseModel):
    chunk_id: str = Field(..., description="分块 ID")
    section_path: list[str] = Field(default_factory=list, description="分块所属标题路径")
    elements: list[DocumentElement] = Field(default_factory=list, description="分块包含的元素")
    markdown: str = Field("", description="带元素标记的分块 Markdown")
    page_start: Optional[int] = Field(None, description="起始页码")
    page_end: Optional[int] = Field(None, description="结束页码")


class DocumentIR(BaseModel):
    title: Optional[str] = None
    doc_type: DocType = Field(default=DocType.UNKNOWN)
    elements: list[DocumentElement] = Field(default_factory=list)
    outline: DocumentOutline = Field(default_factory=DocumentOutline)
    metadata: dict[str, Any] = Field(default_factory=dict, description="文档级解析信息")


class ExtractionContract(BaseModel):
    doc_type: DocType
    target_slots: list[str] = Field(description="需要抽取的对象槽")
    slot_descriptions: dict[str, str] = Field(default_factory=dict, description="对象槽说明")
    rules: list[str] = Field(default_factory=list, description="抽取规则")
    ignore_sections: list[str] = Field(default_factory=list, description="忽略的章节或标题模式")


# =========================
# Unified Object Slots
# =========================


class BaseNode(BaseModel):
    id: Optional[str] = Field(None, description="系统生成 ID；抽取时不要编造")
    name: str = Field(..., description="对象名称；若原文存在稳定编号，可添加原文编号后缀；不要编造编号或写入系统生成 ID")
    evidence_element_ids: list[str] = Field(
        default_factory=list,
        description="来源元素 ID 锚点；只保留能定位对象的高价值锚点",
    )


class StepItem(BaseModel):
    id: Optional[str] = Field(None, description="原文显式步骤 ID；没有则留空")
    name: str


class EntityItem(BaseNode):
    entity_type: EntityType = Field(
        default=EntityType.OTHER,
        description="按对象本质分类：人/角色用 actor；系统、模块、服务、组件、外部系统用 system；数据对象用 data",
    )

    @field_validator("entity_type", mode="before")
    @classmethod
    def _normalize_entity_type(cls, value: Any) -> EntityType:
        if isinstance(value, EntityType):
            return value
        if isinstance(value, str):
            normalized = value.strip().lower()
            try:
                return EntityType(normalized)
            except ValueError:
                return EntityType.OTHER
        return EntityType.OTHER


class ProcessItem(BaseNode):
    process_type: ProcessType = Field(
        default=ProcessType.OTHER,
        description="流程类型：业务流程用 business；系统或技术流程用 technical；测试流程用 test",
    )
    steps: list[StepItem] = Field(default_factory=list, description="流程内的有序步骤")

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
    requirement_type: RequirementType = Field(
        default=RequirementType.OTHER,
        description="需求类型：functional、non_functional 或 other",
    )
    points: list[str] = Field(
        default_factory=list,
        description="同一需求下的功能点、子项、约束或补充细节",
    )
    criteria: list[str] = Field(
        default_factory=list,
        description="验收条件、通过标准、预期结果或量化指标；不要抽成独立需求",
    )

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
    interface_type: InterfaceType = Field(
        default=InterfaceType.OTHER,
        description="接口分类值：优先使用 http、rpc、message、ui、database、file；无法判断用 other；不要填写自然语言描述",
    )
    http_method: Optional[HttpMethod] = Field(
        None,
        description="仅当接口类型为 HTTP 且原文明确出现请求方法时填写；否则留空",
    )
    endpoint: Optional[str] = Field(
        None,
        description="明确入口标识，如 URL path、RPC 方法名、topic/queue、表名、文件路径或页面路由；没有明确值则留空",
    )
    provider: Optional[str] = Field(
        None,
        description="接口提供方、被调用方或外部系统；没有明确值则留空",
    )
    consumer: Optional[str] = Field(
        None,
        description="接口调用方、使用方或发起角色；没有明确值则留空",
    )

    @field_validator("interface_type", mode="before")
    @classmethod
    def _normalize_interface_type(cls, value: Any) -> InterfaceType:
        if value is None:
            return InterfaceType.OTHER
        text = str(value).strip().lower()
        aliases = {
            "api": "http",
            "rest": "http",
            "restful": "http",
            "mq": "message",
            "queue": "message",
            "topic": "message",
            "db": "database",
            "sql": "database",
            "page": "ui",
            "screen": "ui",
        }
        normalized = aliases.get(text, text)
        try:
            return InterfaceType(normalized)
        except ValueError:
            return InterfaceType.OTHER

    @field_validator("http_method", mode="before")
    @classmethod
    def _normalize_http_method(cls, value: Any) -> Optional[HttpMethod]:
        """
        Normalize explicit HTTP methods and reject generic action words.
        """
        if value is None:
            return None
        text = str(value).strip().lower()
        if not text:
            return None
        try:
            return HttpMethod(text)
        except ValueError:
            return None

    @field_validator("endpoint", "provider", "consumer", mode="before")
    @classmethod
    def _normalize_optional_text(cls, value: Any) -> Optional[str]:
        """
        Normalize optional interface text fields to trimmed strings or None.
        """
        if value is None:
            return None
        text = str(value).strip()
        return text or None


class ArtifactItem(BaseNode):
    artifact_type: ArtifactType = Field(
        default=ArtifactType.OTHER,
        description="产物类型：test_case、decision、table、issue、section 或 other",
    )
    details: list[str] = Field(default_factory=list, description="产物自身的行、决策、说明或要点；不要重复需求内容")

    @field_validator("artifact_type", mode="before")
    @classmethod
    def _normalize_artifact_type(cls, value: Any) -> ArtifactType:
        if value is None:
            return ArtifactType.OTHER
        text = str(value).strip().lower()
        if not text:
            return ArtifactType.OTHER
        try:
            return ArtifactType(text)
        except ValueError:
            return ArtifactType.OTHER


# =========================
# Doc-Type-Specific Item Types
# =========================


class FunctionalReqItem(BaseNode):
    """功能需求：原文以独立编号或标题标识的功能规格单元。"""
    points: list[str] = Field(default_factory=list, description="功能点或子项")
    criteria: list[str] = Field(default_factory=list, description="验收条件或通过标准")


class NonFunctionalReqItem(BaseNode):
    """非功能需求：性能、安全、可用性等约束。"""
    category: str = Field(default="", description="分类：性能/安全/可用性/兼容性/可维护性")
    description: str = Field(default="", description="约束描述")


class EndpointItem(BaseNode):
    """API 端点。"""
    http_method: Optional[HttpMethod] = Field(None, description="HTTP 方法")
    path: str = Field(default="", description="URL 路径")
    summary: str = Field(default="", description="功能简述")
    request_schema: str = Field(default="", description="请求体结构名称或描述")
    response_schema: str = Field(default="", description="响应体结构名称或描述")

    @field_validator("http_method", mode="before")
    @classmethod
    def _normalize_http_method(cls, value: Any) -> Optional[HttpMethod]:
        if value is None:
            return None
        text = str(value).strip().lower()
        if not text:
            return None
        try:
            return HttpMethod(text)
        except ValueError:
            return None


class SchemaItem(BaseNode):
    """数据模型/结构定义。"""
    fields: list[str] = Field(default_factory=list, description="字段名及类型")
    description: str = Field(default="", description="结构用途说明")


class AuthItem(BaseNode):
    """认证/授权方式。"""
    auth_type: str = Field(default="", description="认证类型：JWT/OAuth2/API Key/Basic")
    description: str = Field(default="", description="认证说明")


class ModuleItem(BaseNode):
    """系统模块/组件。"""
    responsibility: str = Field(default="", description="模块职责")
    sub_modules: list[str] = Field(default_factory=list, description="子模块名称列表")


class DecisionItem(BaseNode):
    """架构决策记录。"""
    rationale: str = Field(default="", description="决策理由")
    alternatives: list[str] = Field(default_factory=list, description="考虑过的替代方案")


class TestCaseItem(BaseNode):
    """测试用例。"""
    precondition: str = Field(default="", description="前置条件")
    expected_result: str = Field(default="", description="预期结果")


class TestStepItem(BaseNode):
    """测试步骤。"""
    action: str = Field(default="", description="操作描述")
    expected: str = Field(default="", description="预期行为")


class DefectItem(BaseNode):
    """缺陷记录。"""
    severity: str = Field(default="", description="严重程度")
    description: str = Field(default="", description="缺陷描述")


class ProcedureItem(BaseNode):
    """操作步骤流程。"""
    steps: list[StepItem] = Field(default_factory=list, description="有序步骤")


class UIElementItem(BaseNode):
    """界面元素描述。"""
    element_type: str = Field(default="", description="元素类型：按钮/输入框/菜单/弹窗")
    location: str = Field(default="", description="所在页面或区域")


class NoteItem(BaseNode):
    """注意事项或提示。"""
    content: str = Field(default="", description="提示内容")


class SymptomItem(BaseNode):
    """问题现象。"""
    description: str = Field(default="", description="现象描述")


class ReproStepItem(BaseNode):
    """复现步骤。"""
    action: str = Field(default="", description="操作")
    expected: str = Field(default="", description="预期行为")
    actual: str = Field(default="", description="实际行为")


class EnvItem(BaseNode):
    """环境信息。"""
    value: str = Field(default="", description="环境配置值")


# =========================
# Doc-Type-Specific Extraction Containers
# =========================


class SrsExtraction(BaseModel):
    entities: list[EntityItem] = Field(
        default_factory=list,
        description="系统组件、角色、数据对象。外部系统（如企业微信、GitLab）即使同时作为接口提供方，也应归入此槽而非 interfaces。"
    )
    functional_requirements: list[FunctionalReqItem] = Field(default_factory=list, description="功能需求")
    non_functional_requirements: list[NonFunctionalReqItem] = Field(default_factory=list, description="非功能需求")
    interfaces: list[InterfaceItem] = Field(default_factory=list, description="系统接口")


class ApiExtraction(BaseModel):
    endpoints: list[EndpointItem] = Field(default_factory=list, description="API 端点")
    schemas: list[SchemaItem] = Field(default_factory=list, description="数据模型定义")
    auth: list[AuthItem] = Field(default_factory=list, description="API 认证机制类型（如 Bearer Token、OAuth 2.0、API Key），而非获取令牌的具体端点")


class DesignExtraction(BaseModel):
    modules: list[ModuleItem] = Field(default_factory=list, description="系统模块")
    interfaces: list[InterfaceItem] = Field(default_factory=list, description="模块间接口")
    decisions: list[DecisionItem] = Field(default_factory=list, description="架构决策")


class TestExtraction(BaseModel):
    test_cases: list[TestCaseItem] = Field(default_factory=list, description="测试用例")
    test_steps: list[TestStepItem] = Field(default_factory=list, description="测试步骤")
    defects: list[DefectItem] = Field(default_factory=list, description="缺陷记录")


class ManualExtraction(BaseModel):
    entities: list[EntityItem] = Field(default_factory=list, description="涉及的系统组件")
    procedures: list[ProcedureItem] = Field(default_factory=list, description="操作步骤")
    ui_elements: list[UIElementItem] = Field(default_factory=list, description="界面元素")
    notes: list[NoteItem] = Field(default_factory=list, description="注意事项")


class IssueExtraction(BaseModel):
    entities: list[EntityItem] = Field(default_factory=list, description="涉及的系统组件")
    symptoms: list[SymptomItem] = Field(default_factory=list, description="问题现象")
    reproduction_steps: list[ReproStepItem] = Field(default_factory=list, description="复现步骤")
    environment: list[EnvItem] = Field(default_factory=list, description="环境信息")


# =========================
# Phase 0 Pre-scan Result
# =========================


class Phase0Result(BaseModel):
    """文档预扫描结果，作为每个 chunk 的提取上下文注入。"""
    doc_type: DocType = Field(description="确认的文档类型")
    doc_type_confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="类型置信度")
    key_entities: list[str] = Field(default_factory=list, description="文档中出现的系统/角色/数据名")
    section_themes: dict[str, str] = Field(default_factory=dict, description="章节路径 → 主题描述")
    extraction_hints: list[str] = Field(default_factory=list, description="针对本文档的提取注意事项")


class Evidence(BaseModel):
    object_id: str  # 对象 ID，如 entity_id、process_id、requirement_id、interface_id、artifact_id
    element_id: Optional[str] = None
    text_span: Optional[str] = None
    page: Optional[int] = None
    bbox: Optional[list[float]] = Field(
        None,
        description="PDF 坐标框 [x0, y0, x1, y1]",
    )


# =========================
# Document Models
# =========================


class BaseExtractedDocument(BaseModel):
    doc_type: DocType
    title: Optional[str] = None     # TODO: 改为直接延用上传文件的文件名
    version: Optional[str] = None
    extra: dict[str, Any] = Field(
        default_factory=dict,
        description="少量高价值文档级元数据；仅保存无法归入声明字段但有检索、展示或追溯价值的原文属性",
    )


class SrsExtractedDocument(SrsExtraction, BaseExtractedDocument):
    doc_type: Literal["srs"] = Field(default="srs")
    evidence: list[Evidence] = Field(default_factory=list, description="证据绑定；抽取时不要编造")


class ApiExtractedDocument(ApiExtraction, BaseExtractedDocument):
    doc_type: Literal["api"] = Field(default="api")
    base_url: Optional[str] = None
    evidence: list[Evidence] = Field(default_factory=list, description="证据绑定；抽取时不要编造")


class DesignExtractedDocument(DesignExtraction, BaseExtractedDocument):
    doc_type: Literal["design"] = Field(default="design")
    evidence: list[Evidence] = Field(default_factory=list, description="证据绑定；抽取时不要编造")


class TestExtractedDocument(TestExtraction, BaseExtractedDocument):
    doc_type: Literal["test"] = Field(default="test")
    test_stage: Optional[TestStage] = Field(None, description="测试阶段")
    evidence: list[Evidence] = Field(default_factory=list, description="证据绑定；抽取时不要编造")


class ManualExtractedDocument(ManualExtraction, BaseExtractedDocument):
    doc_type: Literal["manual"] = Field(default="manual")
    evidence: list[Evidence] = Field(default_factory=list, description="证据绑定；抽取时不要编造")


class IssueExtractedDocument(IssueExtraction, BaseExtractedDocument):
    doc_type: Literal["issue"] = Field(default="issue")
    evidence: list[Evidence] = Field(default_factory=list, description="证据绑定；抽取时不要编造")


TypedExtractedDocument = Union[
    SrsExtractedDocument,
    ApiExtractedDocument,
    DesignExtractedDocument,
    TestExtractedDocument,
    ManualExtractedDocument,
    IssueExtractedDocument,
]

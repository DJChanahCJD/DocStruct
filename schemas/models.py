"""
数据库 ORM 模型（Tortoise）及结构化提取 Pydantic 模型。

设计说明：
1. ORM 层只负责文件记录与提取结果持久化，不直接承载复杂业务语义。
2. Pydantic 层采用“统一结构化对象 + 文档类型轻特化”结构。
3. 结构化结果统一收敛到 entities / processes / requirements / interfaces /
   artifacts 五类主槽位，优先保证单文档抽取结果稳定、可校验、可人工修订。
4. 不构建知识图谱，不维护 relations；量化指标优先放入 RequirementItem.metric。
5. 文档类型仅保留少量必要特化字段，不再为每类文档维护独立顶层条目结构。
6. 保留 source_ref，支持结构化条目回溯到原文位置。
"""

# TODO: 如果能够细化到某一个小的提取结果能够直接关联对应原文档的具体位置，“后校验”就简单很多了

from __future__ import annotations

from enum import Enum
from typing import Any, Literal, Optional, Union

from pydantic import BaseModel, Field
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


# =========================
# ORM Models
# =========================


class DocumentRecord(models.Model):
    """
    文件记录表：
    - parsed_content 存文档解析后的 Markdown / 文本
    - extracted_data 存结构化抽取结果 JSON
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
    extracted_data = fields.JSONField(
        null=True,
        description="结构化 JSON 数据",
    )

    status = fields.CharField(
        max_length=20,
        default="pending",
        description="处理状态：pending/processing/completed/failed",
    )
    error_message = fields.TextField(
        null=True,
        description="错误信息",
    )

    class Meta:
        table = "document_records"


# =========================
# Common Pydantic Models
# =========================


class SourceRef(BaseModel):
    """结构化条目的来源定位信息。"""

    section: Optional[str] = Field(None, description="来源章节号或章节标题，如 3.6.1")
    page: Optional[int] = Field(None, description="来源页码；纯文本/Markdown 可为空")
    text_span: Optional[str] = Field(None, description="对应原文片段；不宜过长")


class BaseNode(BaseModel):
    """统一结构化对象基类。"""

    id: Optional[str] = Field(None, description="对象 ID，如需求编号、用例编号、接口编号")
    name: Optional[str] = Field(None, description="对象名称")
    description: Optional[str] = Field(None, description="对象描述")
    source_ref: Optional[SourceRef] = Field(None, description="来源定位")
    extra: dict[str, Any] = Field(default_factory=dict, description="少量补充字段")


class StepItem(BaseModel):
    """流程或操作步骤。"""

    id: Optional[str] = Field(None, description="步骤 ID")
    name: str = Field(..., description="步骤名称")
    description: Optional[str] = Field(None, description="步骤描述")
    source_ref: Optional[SourceRef] = Field(None, description="来源定位")


# =========================
# Unified Object Slots
# =========================


class EntityItem(BaseNode):
    """
    实体对象。

    用于承载角色、模块、系统、服务、组件、数据对象等名词型对象。
    不建议用于术语表中的普通缩写解释，术语表更适合放入文档 extra。
    """

    entity_type: EntityType = Field(default=EntityType.OTHER, description="实体类型")


class ProcessItem(BaseNode):
    """
    流程对象。

    用于承载业务流程、工作流、操作流程、测试流程等具有步骤顺序的信息。
    """

    process_type: ProcessType = Field(default=ProcessType.OTHER, description="流程类型")
    steps: list[StepItem] = Field(default_factory=list, description="流程步骤")


class RequirementItem(BaseNode):
    """
    需求对象。

    用于承载功能需求、非功能需求、业务规则、约束和验收要求。
    对于 SRS 中带需求编号的条目，建议每个需求编号生成一个 RequirementItem；
    功能点放入 details，验收标准放入 acceptance_criteria，避免拆成多个碎片需求。
    """

    requirement_type: RequirementType = Field(default=RequirementType.OTHER, description="需求类型")
    priority: Optional[PriorityLevel] = Field(None, description="优先级")
    category: Optional[str] = Field(
        None,
        description="需求细分类，如 user_management / performance / security / data / interface",
    )
    details: list[str] = Field(default_factory=list, description="功能点、规则细节或补充说明")
    acceptance_criteria: list[str] = Field(default_factory=list, description="验收标准")
    metric: Optional[str] = Field(None, description="量化指标，如 < 3 秒、> 99.9%、RPO < 24h")


class InterfaceItem(BaseNode):
    """
    接口对象。

    用于承载 HTTP/RPC/消息/数据库/文件/外部系统/硬件/用户界面等交互接口。
    """

    interface_type: InterfaceType = Field(default=InterfaceType.OTHER, description="接口类型")
    method: Optional[str] = Field(None, description="调用方式，如 GET / POST / gRPC / AMQP")
    path: Optional[str] = Field(None, description="接口路径或协议地址")
    target: Optional[str] = Field(None, description="目标系统、目标服务或目标资源")


class ArtifactItem(BaseNode):
    """
    文档产物。

    用于承载测试用例、手册章节、缺陷项、待确认问题、API endpoint 元数据、
    设计模块说明等文档内部产物。
    不建议用于术语表、参考资料、普通功能点。
    """

    artifact_type: ArtifactType = Field(default=ArtifactType.OTHER, description="产物类型")
    status: Optional[str] = Field(None, description="状态，如待确认、已解决、通过、失败")


# =========================
# Document Models
# =========================


class BaseExtractedDocument(BaseModel):
    """所有结构化文档的公共基类。"""

    doc_type: DocType = Field(..., description="文档类型")
    title: Optional[str] = Field(None, description="文档标题")
    summary: Optional[str] = Field(None, description="文档摘要")
    version: Optional[str] = Field(None, description="版本号")
    language: Optional[str] = Field("zh-CN", description="文档语言")
    extra: dict[str, Any] = Field(default_factory=dict, description="非核心补充信息")


class StructuredDocument(BaseExtractedDocument):
    """统一结构化文档主干。"""

    entities: list[EntityItem] = Field(default_factory=list, description="实体对象")
    processes: list[ProcessItem] = Field(default_factory=list, description="流程对象")
    requirements: list[RequirementItem] = Field(default_factory=list, description="需求对象")
    interfaces: list[InterfaceItem] = Field(default_factory=list, description="接口对象")
    artifacts: list[ArtifactItem] = Field(default_factory=list, description="文档产物")


# =========================
# Document-Specific Views
# =========================


class SrsDocument(StructuredDocument):
    doc_type: Literal["srs"] = Field(default="srs")


class ApiDocument(StructuredDocument):
    doc_type: Literal["api"] = Field(default="api")
    base_url: Optional[str] = Field(None, description="基础 URL")


class DesignDocument(StructuredDocument):
    doc_type: Literal["design"] = Field(default="design")


class TestDocument(StructuredDocument):
    doc_type: Literal["test"] = Field(default="test")
    test_stage: Optional[TestStage] = Field(None, description="测试阶段")


class ManualDocument(StructuredDocument):
    doc_type: Literal["manual"] = Field(default="manual")


class IssueDocument(StructuredDocument):
    doc_type: Literal["issue"] = Field(default="issue")


# =========================
# Union Type
# =========================


ExtractedDocument = Union[
    SrsDocument,
    ApiDocument,
    DesignDocument,
    TestDocument,
    ManualDocument,
    IssueDocument,
]
"""
数据库 ORM 模型（Tortoise）及 LLM 提取结构 Pydantic 模型。

API 层 DTO 请见 schemas/dto.py。
"""

from tortoise import fields, models
from pydantic import BaseModel, Field
from typing import Literal, List, Optional
from enum import Enum

# --- Enums ---

class DocType(str, Enum):
    """文档类型枚举"""
    SRS = "srs"  # 软件需求规格说明书
    API = "api"  # API 接口文档
    DESIGN = "design"  # 系统设计文档
    TEST_PLAN = "test_plan"  # 测试计划
    TEST_CASE = "test_case"  # 测试用例
    TEST_REPORT = "test_report"  # 测试报告
    USER_MANUAL = "user_manual"  # 用户手册
    BUG_REPORT = "bug_report"  # 缺陷报告
    ADR = "adr"  # 架构决策记录
    UNKNOWN = "unknown"  # 未知类型


class RequirementCategory(str, Enum):
    """需求分类枚举（按软件工程语义分层）"""
    BUSINESS = "business"          # 业务需求
    USER_ROLE = "user_role"        # 用户角色需求
    FUNCTIONAL = "functional"      # 功能需求
    NON_FUNCTIONAL = "non_functional"  # 非功能需求（性能/安全/可靠性等）
    INTERFACE = "interface"        # 接口需求
    DATA = "data"                  # 数据需求
    CONSTRAINT = "constraint"      # 约束条件
    OTHER = "other"                # 其他

# --- Tortoise ORM Models (Database) ---

class DocumentRecord(models.Model):
    """
    文档记录表，存储上传的文档元数据及提取结果。
    """
    id = fields.IntField(pk=True)
    filename = fields.CharField(max_length=255, description="原始文件名")
    stored_path = fields.CharField(max_length=512, description="文件存储路径")
    upload_time = fields.DatetimeField(auto_now_add=True, description="上传时间")
    updated_at = fields.DatetimeField(auto_now=True, description="最后更新时间")
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
    heading_path = fields.CharField(max_length=500, null=True, description="兼容字段：标题路径")
    title_path = fields.CharField(max_length=500, null=True, description="标题路径")
    section_title = fields.CharField(max_length=255, null=True, description="当前章节标题")
    chunk_type = fields.CharField(max_length=50, null=True, description="块类型")
    order_index = fields.IntField(null=True, description="文档内顺序索引")
    content = fields.TextField(description="兼容字段：块文本")
    embed_text = fields.TextField(null=True, description="向量化文本")
    display_text = fields.TextField(null=True, description="展示文本")
    vector = fields.JSONField(description="向量")
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "chunk_records"
        unique_together = (("doc", "chunk_index"),)

# --- Pydantic Models (Classification) ---

class DocClassification(BaseModel):
    """
    文档类型分类结果
    """
    doc_type: DocType = Field(..., description="文档类型")
    confidence: float = Field(..., ge=0.0, le=1.0, description="置信度 (0.0-1.0)")
    reasoning: Optional[str] = Field(None, description="分类理由")

# --- Pydantic Models (LLM Extraction) ---

# 1. SRS (Software Requirements Specification)
class RequirementItem(BaseModel):
    """
    单条需求定义
    """
    id: str = Field(..., description="需求ID，如 REQ-001")
    description: str = Field(..., description="需求描述文本")
    priority: Literal["low", "medium", "high"] = Field(default="medium", description="优先级")
    category: RequirementCategory = Field(default=RequirementCategory.OTHER, description="需求分类")
    title: Optional[str] = Field(None, description="需求标题（简短摘要）")

class SrsDocument(BaseModel):
    """
    软件需求规格说明书 (SRS) 结构
    """
    doc_type: Literal["srs"] = Field(default="srs", description="文档类型标识")
    title: str = Field(..., description="文档标题")
    version: Optional[str] = Field(None, description="版本号")
    overview: Optional[str] = Field(None, description="文档概述")
    requirements: List[RequirementItem] = Field(..., description="提取的需求列表")
    extras: dict = Field(default_factory=dict, description="其他重要但非核心内容")

# 2. API Documentation
class ApiEndpoint(BaseModel):
    """
    API 接口定义（字段对齐 OpenAPI 语义）
    """
    method: Literal["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"] = Field(..., description="HTTP 方法")
    path: str = Field(..., description="接口路径，如 /api/v1/users")
    summary: str = Field(..., description="接口简要说明")
    description: Optional[str] = Field(None, description="详细描述")
    parameters: Optional[dict] = Field(None, description="参数对象，包含query/header/path等类型的参数列表")
    request_body: Optional[dict] = Field(None, description="请求体 Schema")
    responses: Optional[dict] = Field(None, description="响应码及 Schema 映射")
    auth: Optional[str] = Field(None, description="鉴权方式，如 Bearer/API Key/None")

class ApiDocument(BaseModel):
    """
    API 接口文档结构
    """
    doc_type: Literal["api"] = Field(default="api", description="文档类型标识")
    title: str = Field(..., description="文档标题")
    version: str = Field(default="1.0", description="API 版本")
    base_url: Optional[str] = Field(None, description="基础 URL")
    endpoints: List[ApiEndpoint] = Field(..., description="提取的接口列表")

# 3. Unified Test Document (Split by Subtypes)
class TestCaseDefinition(BaseModel):
    """
    测试用例定义 (for Test Case Document)
    """
    id: str = Field(..., description="测试用例ID")
    title: str = Field(..., description="测试用例标题")
    preconditions: Optional[str] = Field(None, description="前置条件")
    steps: List[str] = Field(default_factory=list, description="测试步骤列表")
    expected_result: Optional[str] = Field(None, description="预期结果")
    priority: Optional[Literal["P0", "P1", "P2", "P3"]] = Field(None, description="优先级")

class TestCaseResult(BaseModel):
    """
    测试用例结果 (for Test Report)
    """
    id: str = Field(..., description="测试用例ID")
    title: str = Field(..., description="测试用例标题")
    status: Literal["pass", "fail", "skipped", "error"] = Field(..., description="执行状态")
    failure_reason: Optional[str] = Field(None, description="失败原因（可选）")

class TestPlanResource(BaseModel):
    """
    测试资源定义
    """
    human_resources: Optional[List[dict[str, object]]] = Field(None, description="人力资源列表")
    environment: Optional[List[str]] = Field(None, description="测试环境配置")
    tools: Optional[List[str]] = Field(None, description="测试工具列表")


class TestPlanStrategy(BaseModel):
    """
    测试策略定义
    """
    functional_test_strategy: Optional[str] = Field(None, description="功能测试策略")
    interface_test_strategy: Optional[str] = Field(None, description="接口测试策略")
    performance_test_strategy: Optional[str] = Field(None, description="性能测试策略")
    compatibility_test_strategy: Optional[str] = Field(None, description="兼容性测试策略")


class TestPlanDocument(BaseModel):
    """
    测试计划文档 (Test Plan)
    """
    doc_type: Literal["test_plan"] = Field(default="test_plan", description="文档类型标识")
    title: str = Field(..., description="文档标题")
    scope: Optional[str] = Field(None, description="测试范围")
    resources: Optional[TestPlanResource] = Field(None, description="资源需求")
    schedule: Optional[str] = Field(None, description="进度安排")
    strategy: Optional[TestPlanStrategy] = Field(None, description="测试策略")
    deliverables: List[str] = Field(default_factory=list, description="交付物列表")

class TestCaseDocument(BaseModel):
    """
    测试用例文档 (Test Case)
    """
    doc_type: Literal["test_case"] = Field(default="test_case", description="文档类型标识")
    title: str = Field(..., description="文档标题")
    test_cases: List[TestCaseDefinition] = Field(default_factory=list, description="测试用例列表")

class TestReportDocument(BaseModel):
    """
    测试报告 (Test Report)
    """
    doc_type: Literal["test_report"] = Field(default="test_report", description="文档类型标识")
    title: str = Field(..., description="文档标题")
    summary: Optional[str] = Field(None, description="测试执行摘要")
    total_tests: Optional[int] = Field(None, description="测试总数")
    passed_tests: Optional[int] = Field(None, description="通过数量")
    failed_tests: Optional[int] = Field(None, description="失败数量")
    test_cases: List[TestCaseResult] = Field(default_factory=list, description="测试用例列表（包含执行结果）")

# 4. System Design Document (Design)
class DesignModule(BaseModel):
    """
    系统模块定义
    """
    name: str = Field(..., description="模块名称")
    description: str = Field(..., description="模块功能描述")
    interfaces: List[str] = Field(default_factory=list, description="模块提供的接口或方法列表")

class DesignDatabaseTable(BaseModel):
    """
    数据库表定义
    """
    name: str = Field(..., description="表名")
    description: Optional[str] = Field(None, description="表描述")
    columns: List[str] = Field(..., description="包含的列名列表")

class DesignDocument(BaseModel):
    """
    系统设计说明书 (Design) 结构
    """
    doc_type: Literal["design"] = Field(default="design", description="文档类型标识")
    title: str = Field(..., description="文档标题")
    version: str = Field(default="1.0", description="版本号")
    architecture_summary: str = Field(..., description="系统架构概要描述")
    modules: List[DesignModule] = Field(..., description="系统模块列表")
    database_design: List[DesignDatabaseTable] = Field(default_factory=list, description="数据库设计（可选）")

# 5. User Manual
class TroubleshootingItem(BaseModel):
    """
    故障排除条目
    """
    problem: str = Field(..., description="问题描述")
    solution: str = Field(..., description="解决方案")

class UserManualSection(BaseModel):
    """
    用户手册章节
    """
    title: str = Field(..., description="章节标题，如'安装'、'登录'")
    content: str = Field(..., description="章节具体内容或步骤描述")

class UserManualDocument(BaseModel):
    """
    用户手册结构
    """
    doc_type: Literal["user_manual"] = Field(default="user_manual", description="文档类型标识")
    title: str = Field(..., description="手册标题")
    target_audience: Optional[str] = Field(None, description="目标用户群体")
    sections: List[UserManualSection] = Field(..., description="主要章节列表（安装、使用说明等）")
    troubleshooting: List[TroubleshootingItem] = Field(default_factory=list, description="故障排除列表")


# 6. ADR (Architecture Decision Record)
class AdrDecision(BaseModel):
    """
    单条架构决策记录
    """
    title: str = Field(..., description="决策标题")
    status: Optional[Literal["proposed", "accepted", "deprecated", "superseded"]] = Field(None, description="决策状态")
    context: Optional[str] = Field(None, description="决策背景与约束")
    decision: str = Field(..., description="具体决策内容")
    consequences: Optional[str] = Field(None, description="决策影响与后果")


class AdrDocument(BaseModel):
    """
    架构决策记录文档 (ADR) 结构
    """
    doc_type: Literal["adr"] = Field(default="adr", description="文档类型标识")
    title: str = Field(..., description="文档标题")
    version: Optional[str] = Field(None, description="版本号")
    decisions: List[AdrDecision] = Field(default_factory=list, description="架构决策条目列表")
    extras: dict = Field(default_factory=dict, description="其他重要但非核心内容")


# 7. Bug Report
class BugReportDocument(BaseModel):
    """
    缺陷报告结构
    """
    doc_type: Literal["bug_report"] = Field(default="bug_report", description="文档类型标识")
    title: str = Field(..., description="缺陷标题")
    bug_id: Optional[str] = Field(None, description="缺陷编号，如 BUG-123")
    summary: Optional[str] = Field(None, description="问题摘要")
    status: Optional[str] = Field(None, description="当前状态，如 open/fixed/closed")
    severity: Optional[str] = Field(None, description="严重程度，如 critical/high/medium/low")
    priority: Optional[str] = Field(None, description="优先级，如 P0/P1/P2")
    environment: Optional[str] = Field(None, description="环境信息，如浏览器、系统、版本")
    steps_to_reproduce: List[str] = Field(default_factory=list, description="复现步骤")
    expected_result: Optional[str] = Field(None, description="期望结果")
    actual_result: Optional[str] = Field(None, description="实际结果")
    root_cause: Optional[str] = Field(None, description="根因分析")
    workaround: Optional[str] = Field(None, description="临时绕过方案")
    fix_summary: Optional[str] = Field(None, description="修复摘要")

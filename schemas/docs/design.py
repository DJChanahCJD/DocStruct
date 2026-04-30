"""
DocStruct Design document type — high-level design extraction model.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from schemas.constants import DocType
from schemas.docs.base import BaseExtractedDocument, BaseNode

class ModuleItem(BaseNode):
    """系统模块/组件。"""
    description: str = Field(default="", description="模块功能描述")
    responsibilities: list[str] = Field(default_factory=list, description="模块职责列表")


class CoreFlowItem(BaseNode):
    """核心处理流程：系统内部模块、组件或服务之间的协作流程。"""
    participants: list[str] = Field(default_factory=list, description="参与模块、组件或服务")
    steps: list[str] = Field(default_factory=list, description="流程步骤")
    outcome: str = Field(default="", description="流程结果")


class DesignDecisionItem(BaseNode):
    """关键设计决策：文档中明确写出的架构、技术或约束取舍。"""
    decision: str = Field(default="", description="决策内容")
    rationale: str = Field(default="", description="决策理由")
    tradeoffs: list[str] = Field(default_factory=list, description="相关取舍或影响")


class HLDExtraction(BaseModel):
    """概要设计文档"""
    architecture_style: str = Field(default="", description="架构风格")
    technology_stack: list[str] = Field(default_factory=list, description="技术栈")
    modules: list[ModuleItem] = Field(default_factory=list, description="系统模块")
    core_flows: list[CoreFlowItem] = Field(default_factory=list, description="核心业务流程或处理流程")
    design_decisions: list[DesignDecisionItem] = Field(default_factory=list, description="关键设计决策")

class HLDExtractedDocument(HLDExtraction, BaseExtractedDocument):
    doc_type: Literal[DocType.HLD] = Field(default=DocType.HLD)

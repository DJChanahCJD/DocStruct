"""
DocStruct SRS document type — requirements specification extraction + document model.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

from schemas.docs.base import BaseNode, BaseExtractedDocument
from schemas.constants import NonFunctionalCategory, Priority, DocType


class FunctionalReqItem(BaseNode):
    """功能需求：原文以独立编号或标题标识的功能规格单元。"""
    points: list[str] = Field(default_factory=list, description="功能点或子项")
    actor: str = Field(default="", description="执行者/角色")
    priority: Priority = Field(default=Priority.MEDIUM, description="优先级")
    acceptance_criteria: str = Field(default="", description="验收条件或通过标准")

    @field_validator("priority", mode="before")
    @classmethod
    def _normalize_priority(cls, value: Any) -> Priority:
        if isinstance(value, Priority):
            return value
        if isinstance(value, str):
            normalized = value.strip().lower()
            try:
                return Priority(normalized)
            except ValueError:
                return Priority.MEDIUM
        return Priority.MEDIUM


class NonFunctionalReqItem(BaseNode):
    """非功能需求：性能、安全、可用性等约束。"""
    category: NonFunctionalCategory = Field(default=NonFunctionalCategory.OTHER, description="非功能需求分类")
    description: str = Field(default="", description="约束描述")

    @field_validator("category", mode="before")
    @classmethod
    def _normalize_category(cls, value: Any) -> NonFunctionalCategory:
        if isinstance(value, NonFunctionalCategory):
            return value
        if isinstance(value, str):
            stripped = value.strip()
            cn_map = {
                "性能": "performance",
                "安全": "security",
                "可用性": "availability",
                "兼容性": "compatibility",
                "可维护性": "maintainability",
                "合规": "compliance",
                "存储": "storage",
                "可扩展性": "scalability",
            }
            if stripped in cn_map:
                return NonFunctionalCategory(cn_map[stripped])
            try:
                return NonFunctionalCategory(stripped.lower())
            except ValueError:
                pass
        return NonFunctionalCategory.OTHER


class BusinessFlowItem(BaseNode):
    """业务流程：用户或业务视角下完成目标的一组步骤。"""
    actor: str = Field(default="", description="主要参与者或业务角色")
    steps: list[str] = Field(default_factory=list, description="业务步骤")
    outcome: str = Field(default="", description="业务结果")


class SrsExtraction(BaseModel):
    """软件需求规格说明书。"""
    system_name: str = Field(default="", description="系统名称")
    target_users: list[str] = Field(default_factory=list, description="用户角色")
    functional_requirements: list[FunctionalReqItem] = Field(default_factory=list, description="功能需求")
    non_functional_requirements: list[NonFunctionalReqItem] = Field(default_factory=list, description="非功能需求")
    business_flows: list[BusinessFlowItem] = Field(default_factory=list, description="业务流程")

class SrsExtractedDocument(SrsExtraction, BaseExtractedDocument):
    doc_type: Literal[DocType.SRS] = Field(default=DocType.SRS)

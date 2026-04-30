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


class HLDExtraction(BaseModel):
    """概要设计文档"""
    architecture_style: str = Field(default="", description="架构风格")
    technology_stack: list[str] = Field(default_factory=list, description="技术栈")
    modules: list[ModuleItem] = Field(default_factory=list, description="系统模块")

class HLDExtractedDocument(HLDExtraction, BaseExtractedDocument):
    doc_type: Literal[DocType.HLD] = Field(default=DocType.HLD)

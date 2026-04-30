"""
DocStruct shared base models — common node, interface, evidence, extracted document base.
"""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field

from schemas.constants import DocType


class BaseNode(BaseModel):
    id: Optional[str] = Field(None, description="系统生成 ID；抽取时不要编造")
    name: str = Field(..., description="对象名称")
    evidence_element_ids: list[str] = Field(
        default_factory=list,
        description="来源元素 ID 锚点；只保留能定位对象的高价值锚点",
    )


class Evidence(BaseModel):
    object_id: str
    element_id: Optional[str] = None
    text_span: Optional[str] = None
    page: Optional[int] = None
    bbox: Optional[list[float]] = Field(
        None,
        description="页面坐标框 [x0, y0, x1, y1]",
    )


class BaseExtractedDocument(BaseModel):
    doc_type: DocType
    title: Optional[str] = None
    version: Optional[str] = None
    evidence: list[Evidence] = Field(default_factory=list, description="证据绑定；抽取时不要编造")

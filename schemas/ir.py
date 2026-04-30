"""
DocStruct Document IR models — intermediate representation for chunking and evidence tracing.
Split from models.py for modularity.
"""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field

from schemas.constants import DocType


class DocumentElement(BaseModel):
    element_id: str = Field(..., description="稳定元素 ID")
    element_type: str = Field(..., description="元素类型，如 heading、paragraph、table、image、code、footer")
    text: Optional[str] = None
    markdown: Optional[str] = Field(None)
    section_path: list[str] = Field(default_factory=list, description="所属标题路径")
    page: Optional[int] = Field(None, description="来源页码")
    bbox: Optional[list[float]] = Field(
        None,
        description="页面坐标框 [x0, y0, x1, y1]",
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

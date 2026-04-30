"""
DocStruct Document IR models — intermediate representation for chunking and evidence tracing.
Split from models.py for modularity.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

from schemas.constants import DocType


class DocumentElement(BaseModel):
    """文档最小单元。解析器将 PDF/Docx 切为有序元素，作为分块和证据绑定的基本粒度。"""
    element_id: str = Field(..., description="全局唯一稳定标识，用于 [ELEMENT: ...] 标记和证据锚定")
    element_type: str = Field(..., description="元素类型：heading / paragraph / table / image / code / footer 等")
    text: Optional[str] = Field(None, description="纯文本内容（去除 Markdown 格式标记），用于证据展示和搜索匹配")
    markdown: Optional[str] = Field(None, description="Markdown 格式内容（保留表格管道、代码围栏等结构），主要送 LLM 理解")
    section_path: list[str] = Field(default_factory=list, description="所属标题层级路径，如 ['第 3 章', '3.1 接口定义']")
    page: Optional[int] = Field(None, description="来源页码")
    bbox: Optional[list[float]] = Field(
        None,
        description="页面坐标框 [x0, y0, x1, y1]",
    )
    order: int = Field(..., description="全局阅读顺序，保证元素按原文顺序排列")


class DocumentOutline(BaseModel):
    """文档大纲。从标题层级提取，注入 LLM prompt 提供全局结构认知。"""
    title: Optional[str] = None
    doc_type: DocType = Field(default=DocType.UNKNOWN)
    sections: list[str] = Field(default_factory=list, description="扁平化标题列表")
    main_topics: list[str] = Field(default_factory=list, description="由标题提取的主题提示")


class DocumentChunk(BaseModel):
    """抽取分块。一组连续 DocumentElement 的窗口切片，携带预渲染的带标记 Markdown。"""
    chunk_id: str = Field(..., description="分块 ID")
    section_path: list[str] = Field(default_factory=list, description="分块所属标题路径")
    elements: list[DocumentElement] = Field(default_factory=list, description="分块包含的元素")
    markdown: str = Field("", description="带元素标记的分块 Markdown")
    page_start: Optional[int] = Field(None, description="起始页码")
    page_end: Optional[int] = Field(None, description="结束页码")


class DocumentIR(BaseModel):
    """文档中间表示。聚合 DocumentElement 列表与 DocumentOutline，是分块、抽取、证据绑定全流程的唯一输入源。"""
    title: Optional[str] = None
    doc_type: DocType = Field(default=DocType.UNKNOWN)
    elements: list[DocumentElement] = Field(default_factory=list)
    outline: DocumentOutline = Field(default_factory=DocumentOutline)


class ExtractionContract(BaseModel):
    """抽取契约。定义「抽取什么对象、遵守什么规则、忽略哪些章节」，约束每次 LLM 调用的输出。"""
    doc_type: DocType
    target_slots: list[str] = Field(description="需要抽取的对象槽")
    rules: list[str] = Field(default_factory=list, description="抽取规则")
    ignore_sections: list[str] = Field(default_factory=list, description="忽略的章节或标题模式")

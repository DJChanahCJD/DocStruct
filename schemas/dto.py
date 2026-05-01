"""
API 层 DTO（Data Transfer Object）定义。
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


class DocumentRecordDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    stored_path: str
    created_at: datetime
    updated_at: Optional[datetime] = None
    doc_type: str
    raw_text: Optional[str] = None
    summary: Optional[str] = None
    document_ir: Optional[dict[str, Any]] = None
    extracted_data: Optional[dict[str, Any]] = None
    extraction_meta: Optional[dict[str, Any]] = None
    status: str
    error_message: Optional[str] = None


class DocumentListItemDTO(BaseModel):
    """文档列表项 DTO，仅包含列表和 hover 展示需要的轻量字段。"""

    id: int
    title: str
    created_at: datetime
    updated_at: Optional[datetime] = None
    doc_type: str
    summary: Optional[str] = None
    extraction_meta: Optional[dict[str, Any]] = None
    status: str
    error_message: Optional[str] = None
    has_raw_text: bool = False
    has_document_ir: bool = False
    has_extracted_data: bool = False


class DocumentUpdateRequest(BaseModel):
    raw_text: Optional[str] = Field(None, description="用户修订后的 Markdown 内容")
    summary: Optional[str] = Field(None, description="用户修订后的文档摘要")
    extracted_data: Optional[dict[str, Any]] = Field(None, description="用户修改后的结构化 JSON 数据")

    @model_validator(mode="after")
    def _at_least_one_field_required(self) -> "DocumentUpdateRequest":
        if self.raw_text is None and self.summary is None and self.extracted_data is None:
            raise ValueError("raw_text、summary 和 extracted_data 至少需要提供一个")
        return self


class UploadResponse(BaseModel):
    id: int
    title: str
    status: str
    message: str


class DocumentChunkDebugDTO(BaseModel):
    chunk_id: str
    section_path: list[str]
    page_start: Optional[int] = None
    page_end: Optional[int] = None
    element_count: int
    markdown_chars: int
    element_ids: list[str]
    markdown: str


class DocumentChunksResponse(BaseModel):
    doc_id: int
    chunk_count: int
    chunk_max_chars: int
    ignored_sections: list[str]
    chunks: list[DocumentChunkDebugDTO]

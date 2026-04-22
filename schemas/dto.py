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
    filename: str
    stored_path: str
    upload_time: datetime
    doc_type: str
    parsed_content: Optional[str] = None
    extracted_data: Optional[dict[str, Any]] = None
    status: str
    error_message: Optional[str] = None


class DocumentUpdateRequest(BaseModel):
    parsed_content: Optional[str] = Field(None, description="用户修订后的 Markdown 内容")
    extracted_data: Optional[dict[str, Any]] = Field(None, description="用户修改后的结构化 JSON 数据")

    @model_validator(mode="after")
    def _at_least_one_field_required(self) -> "DocumentUpdateRequest":
        if self.parsed_content is None and self.extracted_data is None:
            raise ValueError("parsed_content 和 extracted_data 至少需要提供一个")
        return self


class UploadResponse(BaseModel):
    id: int
    filename: str
    status: str
    message: str

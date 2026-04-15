"""
API 层 DTO（Data Transfer Object）定义。

与 ORM 模型（schemas/models.py）分离，只负责序列化/反序列化 HTTP 请求与响应。
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


class DocumentRecordDTO(BaseModel):
    """文档记录 API 响应体，从 ORM DocumentRecord 转换而来。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    filename: str
    stored_path: str
    upload_time: datetime
    updated_at: Optional[datetime] = None

    @model_validator(mode="after")
    def _fallback_updated_at(self) -> "DocumentRecordDTO":
        """旧记录 updated_at 为 NULL 时，回退到 upload_time。"""
        if self.updated_at is None:
            self.updated_at = self.upload_time
        return self
    doc_type: str
    source_type: str
    source_url: Optional[str] = None
    llm_model: Optional[str] = None
    parsed_content: Optional[str] = None
    extracted_data: Optional[dict[str, Any]] = None
    status: str
    error_message: Optional[str] = None


class DocumentUpdateRequest(BaseModel):
    """PATCH /documents/{id} 请求体，仅允许更新 extracted_data。"""

    extracted_data: dict[str, Any] = Field(..., description="用户修改后的结构化 JSON 数据")


class UploadResponse(BaseModel):
    """上传或 URL 导入后的统一响应。"""

    id: int
    filename: str
    status: str
    message: str


class TextModelOption(BaseModel):
    """前端可展示的文本模型选项。"""

    id: str
    label: str
    description: str
    is_default: bool = False


class TextModelListResponse(BaseModel):
    """文本模型列表接口响应。"""

    models: List[TextModelOption] = Field(default_factory=list)


class UrlUploadRequest(BaseModel):
    """URL 导入请求。"""

    url: str = Field(..., min_length=1, description="待抓取的公开网页 URL")
    llm_model: Optional[str] = Field(None, description="可选：本次处理使用的文本模型")


class QaRequest(BaseModel):
    """问答请求。"""

    question: str = Field(..., min_length=1, description="问题文本")
    doc_id: Optional[int] = Field(None, description="可选：限定文档ID")
    top_k: int = Field(5, ge=1, le=10, description="召回片段数")
    llm_model: Optional[str] = Field(None, description="可选：本次问答使用的文本模型")


class CitationItem(BaseModel):
    """问答引用项。"""

    doc_id: int
    chunk_id: int
    score: float
    snippet: str
    title_path: Optional[str] = None


class QaResponse(BaseModel):
    """问答响应。"""

    answer: str
    citations: List[CitationItem] = Field(default_factory=list)

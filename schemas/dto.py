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


class ReviewFieldDTO(BaseModel):
    """审核视图中的可编辑字段。"""

    node_id: str
    field_key: str
    label: str
    value: Any
    value_type: str
    editable: bool = True


class ReviewItemDTO(BaseModel):
    """审核视图中的 item。"""

    node_id: str
    title: str
    summary: Optional[str] = None
    order: int
    fields: list[ReviewFieldDTO] = Field(default_factory=list)


class ReviewGroupDTO(BaseModel):
    """审核视图中的 item 分组。"""

    group_key: str
    label: str
    item_type: str
    items: list[ReviewItemDTO] = Field(default_factory=list)


class DocumentReviewModelDTO(BaseModel):
    """统一审核视图。"""

    doc_type: str
    meta_fields: list[ReviewFieldDTO] = Field(default_factory=list)
    groups: list[ReviewGroupDTO] = Field(default_factory=list)


class ReviewChangeRequest(BaseModel):
    """单个审核变更。"""

    node_id: str
    field_key: str
    value: Any


class ReviewModelUpdateRequest(BaseModel):
    """PATCH /documents/{id}/review-model 请求体。"""

    changes: list[ReviewChangeRequest] = Field(..., min_length=1)
    reindex: bool = True


class ReviewNodeDTO(BaseModel):
    """单个审核节点预览。"""

    node_id: str
    node_type: Literal["meta", "item"]
    label: str
    group_key: Optional[str] = None
    title: str
    fields: list[ReviewFieldDTO] = Field(default_factory=list)


class ReviewModelUpdateResponse(BaseModel):
    """审核修改后的统一返回。"""

    document: DocumentRecordDTO
    review_model: DocumentReviewModelDTO
    warning: Optional[str] = None


class ReviewModelReExtractRequest(BaseModel):
    """POST /documents/{id}/review-model/re-extract 请求体。"""

    node_id: str = Field(..., min_length=1)
    instruction: Optional[str] = Field(None, description="用户补充指示")
    use_rag: bool = Field(True, description="是否使用 RAG 检索相关片段")


class ReviewModelReExtractResponse(BaseModel):
    """review-model 节点级重提取预览返回。"""

    node: ReviewNodeDTO


class DocumentSourceMetaDTO(BaseModel):
    """源文件预览元信息。"""

    source_type: str
    filename: str
    mime_type: str
    preview_mode: Literal["pdf", "office", "text", "external_url", "unsupported"]
    download_url: str
    source_url: Optional[str] = None


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
    doc_type: Optional[str] = Field(None, description="上传时指定的文档类型")
    llm_model: Optional[str] = Field(None, description="可选：本次处理使用的文本模型")


class QaRequest(BaseModel):
    """问答请求。"""

    question: str = Field(..., min_length=1, description="问题文本")
    doc_ids: Optional[list[int]] = Field(None, description="可选：限定多个文档ID")
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


class ReExtractRequest(BaseModel):
    """POST /documents/{id}/re-extract 请求体。"""

    scope: Literal["full", "field"]
    field_key: Optional[str] = Field(None, description="scope=field 时必填，指定要重提取的顶层字段名")
    instruction: Optional[str] = Field(None, description="用户补充指示，追加到提取 prompt 末尾")
    use_rag: bool = Field(True, description="是否使用 RAG 检索相关片段，默认启用")

    @model_validator(mode="after")
    def _field_key_required_for_field_scope(self) -> "ReExtractRequest":
        if self.scope == "field" and not self.field_key:
            raise ValueError("scope=field 时 field_key 不能为空")
        return self


class ReExtractResponse(BaseModel):
    """POST /documents/{id}/re-extract 响应体，不持久化，由前端决定是否保存。"""

    result: dict[str, Any]
    scope: Literal["full", "field"]
    field_key: Optional[str] = None

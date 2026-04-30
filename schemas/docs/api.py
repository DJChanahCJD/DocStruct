"""
DocStruct API document type — API specification extraction + document model.
"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field
from schemas.constants import DocType

from schemas.docs.base import BaseExtractedDocument, BaseNode


class RequestParamItem(BaseModel):
    """API 请求参数。"""
    name: str = Field(..., description="参数名")
    type: str = Field(default="", description="参数类型")
    required: bool = Field(default=False, description="是否必填")
    description: str = Field(default="", description="参数说明")


class ResponseFieldItem(BaseModel):
    """API 响应字段。"""
    name: str = Field(..., description="字段名")
    type: str = Field(default="", description="字段类型")
    description: str = Field(default="", description="字段说明")


class ErrorCodeItem(BaseModel):
    """API 错误码。"""
    code: str = Field(..., description="错误码")
    message: str = Field(default="", description="错误信息")


class ApiItem(BaseNode):
    """API 接口。"""
    id: Optional[str] = Field(None, description="接口 ID")
    name: str = Field(..., description="接口名称")
    method: str = Field(default="", description="HTTP 方法")
    path: str = Field(default="", description="URL 路径")
    description: str = Field(default="", description="接口描述")
    request_parameters: list[RequestParamItem] = Field(default_factory=list, description="请求参数")
    response_fields: list[ResponseFieldItem] = Field(default_factory=list, description="响应字段")
    error_codes: list[ErrorCodeItem] = Field(default_factory=list, description="错误码")

class ApiExtraction(BaseModel):
    base_url: str = Field(default="", description="API 基础地址")
    apis: list[ApiItem] = Field(default_factory=list, description="API 接口列表")


class ApiExtractedDocument(ApiExtraction, BaseExtractedDocument):
    doc_type: Literal[DocType.API] = Field(default=DocType.API)

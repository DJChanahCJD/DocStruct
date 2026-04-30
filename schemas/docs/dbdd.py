"""
DocStruct Database Design document type — DB schema specification extraction + document model.
"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

from schemas.docs.base import BaseExtractedDocument, BaseNode
from schemas.constants import DocType


class FieldItem(BaseModel):
    """数据库字段定义。"""
    name: str = Field(..., description="字段名")
    type: str = Field(default="", description="字段类型")
    primary_key: bool = Field(default=False, description="是否主键")
    nullable: bool = Field(default=True, description="是否可为空")
    comment: str = Field(default="", description="字段说明")


class TableItem(BaseNode):
    """数据库表定义。"""
    comment: str = Field(default="", description="表注释")
    fields: list[FieldItem] = Field(default_factory=list, description="字段列表")


class DBDDExtraction(BaseModel):
    """数据库设计文档。"""
    db_name: str = Field(default="", description="数据库名称")
    db_type: str = Field(default="", description="数据库类型")
    tables: list[TableItem] = Field(default_factory=list, description="表列表")


class DBDDExtractedDocument(DBDDExtraction, BaseExtractedDocument):
    doc_type: Literal[DocType.DBDD] = Field(default=DocType.DBDD)

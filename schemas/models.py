"""
Backward-compatible re-export hub.

All types now live in their own modules under `schemas/`:
- constants.py   — all enum types (DocType, Priority, …)
- orm.py          — DocumentRecord (Tortoise ORM)
- ir.py           — DocumentElement, DocumentOutline, DocumentChunk, DocumentIR, ExtractionContract
- base.py         — BaseNode, Evidence, BaseExtractedDocument

Document-type-specific files live under `schemas/docs/`:
- srs.py          — FunctionalReqItem, NonFunctionalReqItem, SrsExtraction, SrsExtractedDocument
- api.py          — RequestParamItem, ResponseFieldItem, ErrorCodeItem, ApiItem, ApiExtraction, ApiExtractedDocument
- design.py       — ModuleItem, HLDExtraction
- test.py         — TestStepItem, TestCaseItem, TestExtraction, TestExtractedDocument
- dbdd.py         — FieldItem, TableItem, DBDDExtraction, DBDDExtractedDocument
"""

from __future__ import annotations

from schemas.constants import *
from schemas.ir import *
from schemas.docs.base import *
from schemas.docs.srs import *
from schemas.docs.api import *
from schemas.docs.design import *
from schemas.docs.test import *
from schemas.docs.dbdd import *

from tortoise import fields, models

class DocumentRecord(models.Model):
    """
    文件记录。

    - `raw_text`：解析后的原始文本 / Markdown 内容。
    - `document_ir`：用于分块和证据回溯的文档 IR。
    - `extracted_data`：最终结构化抽取结果。
    - `extraction_meta`：抽取元信息（模型、置信度、分块统计等）。
    """

    id = fields.IntField(pk=True)
    title = fields.CharField(max_length=255, description="文档标题，默认取文件名")
    stored_path = fields.CharField(max_length=512, description="文件存储路径")
    created_at = fields.DatetimeField(auto_now_add=True, description="创建时间")
    updated_at = fields.DatetimeField(null=True, description="最后修改时间")

    doc_type = fields.CharField(
        max_length=50,
        default=DocType.UNKNOWN.value,
        description="文档类型",
    )

    raw_text = fields.TextField(
        null=True,
        description="解析后的原始文本 / Markdown 内容",
    )
    summary = fields.TextField(
        null=True,
        description="文档摘要，默认从原始文本中提取",
    )
    document_ir = fields.JSONField(
        null=True,
        description="文档元素 IR，用于分块与证据回溯",
    )
    extracted_data = fields.JSONField(
        null=True,
        description="结构化抽取结果",
    )
    extraction_meta = fields.JSONField(
        null=True,
        description="抽取元信息：模型名、置信度、分块统计等",
    )

    status = fields.CharField(
        max_length=20,
        default=DocumentStatus.PENDING.value,
        description="处理状态",
    )
    error_message = fields.TextField(
        null=True,
        description="失败原因",
    )

    class Meta:
        table = "document"

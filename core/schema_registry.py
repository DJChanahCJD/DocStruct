from __future__ import annotations

from pydantic import BaseModel

from schemas.models import (
    ApiExtractedDocument,
    DBDDExtractedDocument,
    DocType,
    HLDExtractedDocument,
    SrsExtractedDocument,
    TestCaseExtractedDocument,
)


TYPED_MODEL_MAP: dict[DocType, type[BaseModel]] = {
    DocType.SRS: SrsExtractedDocument,
    DocType.API: ApiExtractedDocument,
    DocType.HLD: HLDExtractedDocument,
    DocType.TC: TestCaseExtractedDocument,
    DocType.DBDD: DBDDExtractedDocument,
}


def normalize_doc_type(doc_type: str | DocType | None) -> DocType:
    """将字符串或枚举值规范化为 DocType 枚举；None/空/非法值统一回退为 UNKNOWN。"""
    if isinstance(doc_type, DocType):
        return doc_type
    if doc_type is None or not str(doc_type).strip():
        return DocType.UNKNOWN
    try:
        return DocType(str(doc_type).strip())
    except ValueError:
        return DocType.UNKNOWN


def get_response_model(doc_type: str | DocType | None) -> type[BaseModel] | None:
    """返回文档类型对应的唯一 typed response model。"""
    normalized = normalize_doc_type(doc_type)
    return TYPED_MODEL_MAP.get(normalized)

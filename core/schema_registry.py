from __future__ import annotations

from pydantic import BaseModel

from schemas.models import ApiDocument, DesignDocument, DocType, IssueDocument, ManualDocument, SrsDocument, TestDocument


TYPE_MODEL_MAP: dict[DocType, type[BaseModel]] = {
    DocType.SRS: SrsDocument,
    DocType.API: ApiDocument,
    DocType.DESIGN: DesignDocument,
    DocType.TEST: TestDocument,
    DocType.MANUAL: ManualDocument,
    DocType.ISSUE: IssueDocument,
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
    normalized = normalize_doc_type(doc_type)
    return TYPE_MODEL_MAP.get(normalized)

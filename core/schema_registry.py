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
    if isinstance(doc_type, DocType):
        return doc_type
    if doc_type is None or not str(doc_type).strip():
        raise ValueError("doc_type 不能为空")
    try:
        return DocType(str(doc_type).strip())
    except ValueError as exc:
        allowed = ", ".join(item.value for item in DocType)
        raise ValueError(f"非法 doc_type: {doc_type}。仅支持: {allowed}") from exc


def get_response_model(doc_type: str | DocType | None) -> type[BaseModel] | None:
    normalized = normalize_doc_type(doc_type)
    return TYPE_MODEL_MAP.get(normalized)

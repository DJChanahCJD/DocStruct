import unittest

from core.reducer import discover_document_fields, discover_slots, reduce_extraction_results
from core.utils import dump_extracted_document
from schemas.models import (
    ApiExtractedDocument,
    DocType,
    DocumentElement,
    DocumentIR,
    DocumentOutline,
    HLDExtractedDocument,
    SrsExtractedDocument,
)


def _sample_ir() -> DocumentIR:
    """构造带 API Base URL 和接口证据的最小 IR。"""
    return DocumentIR(
        title="智能文档系统 API",
        doc_type=DocType.API,
        outline=DocumentOutline(title="智能文档系统 API", doc_type=DocType.API),
        elements=[
            DocumentElement(
                element_id="el-0002",
                element_type="paragraph",
                text="Base URL : https://api.docstruct.io/v1",
                markdown="Base URL : https://api.docstruct.io/v1",
                section_path=[],
                page=1,
                bbox=[10.0, 20.0, 30.0, 40.0],
                order=1,
            ),
            DocumentElement(
                element_id="el-0005",
                element_type="code",
                text="POST /documents",
                markdown="POST /documents",
                section_path=["文档管理", "上传文档"],
                page=1,
                bbox=[50.0, 60.0, 70.0, 80.0],
                order=2,
            ),
        ],
    )


class ReducerDocumentFieldsTest(unittest.TestCase):
    """验证 reducer 同时保留文档级字段和对象证据。"""

    def test_discovers_api_document_fields_and_slots(self) -> None:
        """API schema 应把 base_url 视为文档级字段，把 apis 视为对象槽。"""
        self.assertEqual(discover_document_fields(ApiExtractedDocument), ["base_url"])
        self.assertEqual(discover_slots(ApiExtractedDocument), ["apis"])

    def test_discovers_lightweight_srs_and_hld_slots(self) -> None:
        """SRS/HLD 新增轻量槽位应作为对象槽，而不是文档级列表字段。"""
        self.assertEqual(
            discover_slots(SrsExtractedDocument),
            ["functional_requirements", "non_functional_requirements", "business_flows"],
        )
        self.assertEqual(
            discover_slots(HLDExtractedDocument),
            ["modules", "core_flows", "design_decisions"],
        )
        self.assertEqual(
            discover_document_fields(SrsExtractedDocument),
            ["system_name", "target_users"],
        )
        self.assertEqual(
            discover_document_fields(HLDExtractedDocument),
            ["architecture_style", "technology_stack"],
        )

    def test_reduce_preserves_base_url_and_binds_api_evidence(self) -> None:
        """归并结果应保留 base_url，并为 apis 生成证据记录。"""
        reduced, meta = reduce_extraction_results(
            doc_type=DocType.API.value,
            title="智能文档系统 API",
            chunk_results=[
                {
                    "base_url": "https://api.docstruct.io/v1",
                    "apis": [
                        {
                            "name": "上传文档",
                            "method": "post",
                            "path": "/documents",
                            "evidence_element_ids": ["el-0005"],
                        }
                    ],
                }
            ],
            document_ir=_sample_ir(),
            response_model=ApiExtractedDocument,
        )

        self.assertEqual(reduced["base_url"], "https://api.docstruct.io/v1")
        self.assertEqual(reduced["apis"][0]["id"], "APIS-001")
        self.assertEqual(reduced["evidence"][0]["object_id"], "APIS-001")
        self.assertEqual(reduced["evidence"][0]["bbox"], [50.0, 60.0, 70.0, 80.0])
        self.assertEqual(meta["evidence_count"], 1)

    def test_dump_extracted_document_places_evidence_last(self) -> None:
        """结构化结果序列化时 evidence 应位于 JSON 对象末尾。"""
        reduced, _meta = reduce_extraction_results(
            doc_type=DocType.API.value,
            title="智能文档系统 API",
            chunk_results=[
                {
                    "base_url": "https://api.docstruct.io/v1",
                    "apis": [
                        {
                            "name": "上传文档",
                            "method": "POST",
                            "path": "/documents",
                            "evidence_element_ids": ["el-0005"],
                        }
                    ],
                }
            ],
            document_ir=_sample_ir(),
            response_model=ApiExtractedDocument,
        )
        validated = ApiExtractedDocument.model_validate(reduced)
        dumped = dump_extracted_document(validated)

        self.assertEqual(list(dumped)[-1], "evidence")


if __name__ == "__main__":
    unittest.main()

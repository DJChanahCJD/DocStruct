import unittest

from core.reducer import bind_evidence, reduce_extraction_results
from schemas.models import DocumentElement, DocumentIR, DocumentOutline


class ReducerTests(unittest.TestCase):
    def test_reduce_merges_duplicate_requirements_and_binds_element_evidence(self) -> None:
        elements = [
            DocumentElement(
                element_id="el-0001",
                element_type="paragraph",
                text="System shall support account registration.",
                section_path=["Product Spec", "Requirements"],
                page=3,
                bbox=[1, 2, 3, 4],
                order=0,
            ),
            DocumentElement(
                element_id="el-0002",
                element_type="paragraph",
                text="Acceptance: email must be unique.",
                section_path=["Product Spec", "Requirements"],
                page=3,
                bbox=None,
                order=1,
            ),
        ]
        document_ir = DocumentIR(
            title="Product Spec",
            doc_type="srs",
            elements=elements,
            outline=DocumentOutline(title="Product Spec", doc_type="srs", sections=["Requirements"]),
        )
        chunk_results = [
            {
                "requirements": [
                    {
                        "id": "chunk-1-req-1",
                        "name": "Account registration",
                        "description": "System shall support account registration.",
                        "requirement_type": "functional",
                        "evidence_element_ids": ["el-0001"],
                    }
                ]
            },
            {
                "requirements": [
                    {
                        "id": "chunk-2-req-1",
                        "name": "Account registration",
                        "description": "System shall support account registration.",
                        "requirement_type": "functional",
                        "acceptance_criteria": ["email must be unique"],
                        "evidence_element_ids": ["el-0002"],
                    }
                ]
            },
        ]

        reduced, meta = reduce_extraction_results(
            doc_type="srs",
            title="Product Spec",
            chunk_results=chunk_results,
            document_ir=document_ir,
        )

        self.assertEqual(len(reduced["requirements"]), 1)
        requirement = reduced["requirements"][0]
        self.assertEqual(requirement["id"], "REQ-001")
        self.assertEqual(requirement["acceptance_criteria"], ["email must be unique"])
        self.assertEqual(requirement["evidence_element_ids"], ["el-0001", "el-0002"])
        self.assertEqual(len(reduced["evidence"]), 2)
        self.assertEqual(reduced["evidence"][0]["page"], 3)
        self.assertEqual(reduced["evidence"][0]["bbox"], [1.0, 2.0, 3.0, 4.0])
        self.assertEqual(meta["objects_with_evidence"], 1)
        self.assertEqual(meta["evidence_coverage"], 1.0)

    def test_evidence_binding_uses_conservative_text_fallback(self) -> None:
        elements = [
            DocumentElement(
                element_id="el-0001",
                element_type="paragraph",
                text="System shall export audit reports within 3 seconds.",
                section_path=["Non-functional"],
                page=None,
                bbox=None,
                order=0,
            )
        ]
        extracted_data = {
            "requirements": [
                {
                    "id": "REQ-001",
                    "name": "Audit export performance",
                    "description": "export audit reports within 3 seconds",
                    "requirement_type": "non_functional",
                    "evidence_element_ids": [],
                }
            ]
        }

        evidence, meta = bind_evidence(extracted_data, elements)

        self.assertEqual(len(evidence), 1)
        self.assertEqual(evidence[0]["element_id"], "el-0001")
        self.assertEqual(evidence[0]["section_path"], ["Non-functional"])
        self.assertEqual(meta["evidence_coverage"], 1.0)


if __name__ == "__main__":
    unittest.main()

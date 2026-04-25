import unittest

from core.chunker import split_ir_into_chunks
from core.ir import build_basic_ir_from_markdown


class IrChunkerTests(unittest.TestCase):
    def test_basic_markdown_ir_has_stable_order_and_sections(self) -> None:
        markdown = """# Product Spec

## 1 User Management

System shall support account registration.

| Field | Rule |
| --- | --- |
| email | unique |

```json
{"status": "ok"}
```
"""

        document_ir = build_basic_ir_from_markdown(markdown, doc_type="srs")

        self.assertEqual(document_ir.doc_type.value, "srs")
        self.assertEqual(document_ir.title, "Product Spec")
        self.assertEqual([element.order for element in document_ir.elements], list(range(len(document_ir.elements))))
        self.assertTrue(any(element.element_type == "table" for element in document_ir.elements))
        self.assertTrue(any(element.element_type == "code" for element in document_ir.elements))
        paragraph = next(element for element in document_ir.elements if element.element_type == "paragraph")
        self.assertEqual(paragraph.section_path, ["Product Spec", "1 User Management"])

    def test_ir_chunk_markers_reference_elements_without_splitting_atomic_blocks(self) -> None:
        markdown = """# Product Spec

## 1 User Management

System shall support account registration.

| Field | Rule |
| --- | --- |
| email | unique |
| phone | unique |
"""

        document_ir = build_basic_ir_from_markdown(markdown, doc_type="srs")
        chunks = split_ir_into_chunks(document_ir, max_chars=90)

        self.assertGreaterEqual(len(chunks), 2)
        element_ids = {element.element_id for element in document_ir.elements}
        marker_ids = {
            element.element_id
            for chunk in chunks
            for element in chunk.elements
            if f"[ELEMENT: {element.element_id}" in chunk.markdown
        }
        self.assertEqual(marker_ids, element_ids)

        table_chunks = [chunk for chunk in chunks if any(element.element_type == "table" for element in chunk.elements)]
        self.assertEqual(len(table_chunks), 1)
        self.assertIn("| email | unique |", table_chunks[0].markdown)
        self.assertIn("| phone | unique |", table_chunks[0].markdown)


if __name__ == "__main__":
    unittest.main()

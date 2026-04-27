import asyncio
import unittest
from unittest.mock import AsyncMock, patch

from fastapi import HTTPException

import main
from core.ir import build_basic_ir_from_markdown, document_ir_to_payload
from schemas.models import DocumentRecord


class DocumentChunksApiTests(unittest.TestCase):
    """Tests for the document chunk debug API helpers and route behavior."""

    def test_existing_document_ir_returns_chunk_debug_payload(self) -> None:
        """Ensure saved IR is split into chunk debug DTOs with element markers."""
        markdown = """# 系统需求规格说明书

## 1. 引言

需求描述：系统应支持文档分块调试。
"""
        document_ir = build_basic_ir_from_markdown(markdown, doc_type="srs")
        doc = _make_document(document_ir=document_ir_to_payload(document_ir))

        response = main.build_document_chunks_response(doc)

        self.assertEqual(response.doc_id, 1)
        self.assertEqual(response.chunk_count, 1)
        self.assertGreater(response.chunk_max_chars, 0)
        self.assertIn("附录", response.ignored_sections)
        self.assertEqual(response.chunks[0].chunk_id, "chunk-0001")
        self.assertEqual(response.chunks[0].element_count, len(document_ir.elements))
        self.assertEqual(response.chunks[0].element_ids[0], "el-0001")
        self.assertIn("[ELEMENT: el-0001]", response.chunks[0].markdown)

    def test_parsed_content_fallback_generates_chunks(self) -> None:
        """Ensure parsed Markdown can generate temporary IR when saved IR is absent."""
        doc = _make_document(
            document_ir=None,
            parsed_content="""# 概要设计

## 模块设计

模块 A 负责上传文件。
""",
        )

        response = main.build_document_chunks_response(doc)

        self.assertEqual(response.chunk_count, 1)
        self.assertEqual(response.chunks[0].section_path, ["概要设计"])
        self.assertIn("[ELEMENT:", response.chunks[0].markdown)

    def test_missing_document_returns_404(self) -> None:
        """Ensure the route returns 404 when the document record does not exist."""
        with patch("main.DocumentRecord.get_or_none", new=AsyncMock(return_value=None)):
            with self.assertRaises(HTTPException) as context:
                asyncio.run(main.get_document_chunks(404))

        self.assertEqual(context.exception.status_code, 404)

    def test_unparsed_document_returns_400(self) -> None:
        """Ensure documents without IR or parsed Markdown return a 400 error."""
        doc = _make_document(document_ir=None, parsed_content=None)
        with patch("main.DocumentRecord.get_or_none", new=AsyncMock(return_value=doc)):
            with self.assertRaises(HTTPException) as context:
                asyncio.run(main.get_document_chunks(1))

        self.assertEqual(context.exception.status_code, 400)


def _make_document(
    *,
    document_ir: dict | None = None,
    parsed_content: str | None = "parsed",
) -> DocumentRecord:
    """Create an in-memory DocumentRecord suitable for route helper tests."""
    return DocumentRecord(
        id=1,
        filename="demo.md",
        stored_path="demo.md",
        doc_type="srs",
        parsed_content=parsed_content,
        document_ir=document_ir,
        extracted_data=None,
        status="completed",
        error_message=None,
    )


if __name__ == "__main__":
    unittest.main()

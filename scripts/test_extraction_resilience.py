from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from core.chunker import MarkdownChunk, split_markdown_into_chunks
from core.extractor import extract_structure_with_meta
from schemas.models import ApiDocument


class ExtractionResilienceTest(unittest.IsolatedAsyncioTestCase):
    def test_api_example_chunk_count_is_reduced(self) -> None:
        markdown_text = Path("static/examples/api_example.md").read_text(encoding="utf-8")
        chunks = split_markdown_into_chunks(markdown_text, max_chars=5000, overlap_chars=200, doc_type="api")
        self.assertLessEqual(len(chunks), 15)
        self.assertFalse(any("sample.temperature" in chunk.text for chunk in chunks))

    async def test_chunk_extraction_tolerates_partial_failures(self) -> None:
        chunks = [
            MarkdownChunk(0, ["API", "A"], "A", "section", 0, "one", "one"),
            MarkdownChunk(1, ["API", "B"], "B", "section", 1, "two", "two"),
            MarkdownChunk(2, ["API", "C"], "C", "section", 2, "three", "three"),
        ]
        valid_result = {
            "title": "NebulaLab API",
            "base_url": "https://api.nebulalab.example.com/v1",
            "interfaces": [
                {
                    "id": "api_get_projects",
                    "interface_type": "http",
                    "method": "GET",
                    "path": "/projects",
                    "description": "List projects",
                }
            ],
        }

        with (
            patch("core.extractor.split_markdown_into_chunks", return_value=chunks),
            patch(
                "core.extractor._extract_chunk",
                new=AsyncMock(side_effect=[valid_result, ValueError("bad chunk"), {"error": {"code": "VALIDATION_ERROR"}}]),
            ),
        ):
            extracted, meta = await extract_structure_with_meta("x" * 9000, ApiDocument)

        self.assertEqual(extracted.title, "NebulaLab API")
        self.assertTrue(meta["partial"])
        self.assertEqual(meta["failed_chunks"], 2)
        self.assertEqual(meta["failed_chunk_indexes"], [1, 2])

    async def test_chunk_extraction_fails_when_all_chunks_fail(self) -> None:
        chunks = [
            MarkdownChunk(0, ["API", "A"], "A", "section", 0, "one", "one"),
            MarkdownChunk(1, ["API", "B"], "B", "section", 1, "two", "two"),
        ]

        with (
            patch("core.extractor.split_markdown_into_chunks", return_value=chunks),
            patch(
                "core.extractor._extract_chunk",
                new=AsyncMock(side_effect=[ValueError("bad chunk"), {"error": {"code": "VALIDATION_ERROR"}}]),
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "分块提取失败"):
                await extract_structure_with_meta("x" * 9000, ApiDocument)


if __name__ == "__main__":
    unittest.main()

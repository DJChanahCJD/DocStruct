from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from core.chunker import MarkdownChunk, split_markdown_into_chunks
from core.extractor import extract_structure_with_meta
from core.utils import finalize_merged_result
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
        metadata_result = {
            "title": "NebulaLab API",
            "base_url": "https://api.nebulalab.example.com/v1",
        }
        valid_chunk_result = {
            "interfaces": [
                {
                    "id": "api_get_projects",
                    "interface_type": "http",
                    "method": "GET",
                    "path": "/projects",
                    "description": "List projects",
                }
            ],
            "requirements": [],
        }

        with (
            patch("core.extractor.split_markdown_into_chunks", return_value=chunks),
            patch("core.extractor.get_metadata_window", return_value="metadata window"),
            patch("core.extractor.asyncio.to_thread", new=AsyncMock(return_value=metadata_result)),
            patch(
                "core.extractor._extract_chunk",
                new=AsyncMock(side_effect=[valid_chunk_result, ValueError("bad chunk"), {"error": {"code": "VALIDATION_ERROR"}}]),
            ),
        ):
            extracted, meta = await extract_structure_with_meta("x" * 9000, ApiDocument)

        self.assertEqual(extracted.title, "NebulaLab API")
        self.assertEqual(extracted.base_url, "https://api.nebulalab.example.com/v1")
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
            patch("core.extractor.asyncio.to_thread", new=AsyncMock(return_value={"title": "test"})),
            patch(
                "core.extractor._extract_chunk",
                new=AsyncMock(side_effect=[ValueError("bad chunk"), {"error": {"code": "VALIDATION_ERROR"}}]),
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "分块提取失败"):
                await extract_structure_with_meta("x" * 9000, ApiDocument)

    def test_finalize_normalization_rules(self) -> None:
        metadata = {"title": "Doc Title", "doc_type": "srs", "version": "1.0"}
        chunk_results = [
            {
                "title": "Noise Title from chunk",  # Should be ignored
                "requirements": [
                    {"id": "REQ-1", "name": "req 1", "priority": "High "},
                    {"id": "REQ-1", "name": "req 1 duplicate", "priority": "P0"},
                    {"name": "Performance", "description": "Needs to be fast", "requirement_type": "other"},
                    {"name": "Auth", "description": "Users should login", "requirement_type": "other"},
                    {"name": "Empty", "description": "", "priority": ""},
                ],
                "artifacts": [
                    {"name": "Term 1", "description": "Just a term", "artifact_type": "other"},
                    {"name": "Valid TestCase", "artifact_type": "test_case", "status": "passed"},
                ],
                "interfaces": [
                    {"method": "GET", "path": "/api/v1/users"}
                ]
            }
        ]
        
        final_dict = finalize_merged_result(metadata, chunk_results)
        
        # Test doc-level fields from metadata
        self.assertEqual(final_dict["title"], "Doc Title")
        self.assertEqual(final_dict["doc_type"], "srs")
        self.assertEqual(final_dict["version"], "1.0")
        
        # Test requirements deduplication and priority normalization
        reqs = final_dict.get("requirements", [])
        self.assertEqual(len(reqs), 4) # REQ-1 (deduped), Performance, Auth, Empty
        
        # REQ-1
        self.assertEqual(reqs[0]["id"], "REQ-1")
        self.assertEqual(reqs[0]["priority"], "high")
        
        # Performance
        self.assertEqual(reqs[1]["name"], "Performance")
        self.assertEqual(reqs[1]["requirement_type"], "non_functional")
        
        # Auth
        self.assertEqual(reqs[2]["name"], "Auth")
        self.assertEqual(reqs[2]["requirement_type"], "functional")
        
        # Empty (should have empty strings stripped, and priority converted to medium or None)
        # Note _clean_empty_values stripped description & priority
        self.assertNotIn("description", reqs[3])
        self.assertNotIn("priority", reqs[3])

        # Test artifact filtering
        arts = final_dict.get("artifacts", [])
        self.assertEqual(len(arts), 1)
        self.assertEqual(arts[0]["name"], "Valid TestCase")


if __name__ == "__main__":
    unittest.main()

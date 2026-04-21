import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

import main


def _make_doc() -> MagicMock:
    doc = MagicMock()
    doc.id = 7
    doc.filename = "需求文档.md"
    doc.stored_path = "db/uploads/a.md"
    doc.upload_time = "2026-04-21T10:00:00"
    doc.updated_at = "2026-04-21T10:00:00"
    doc.doc_type = "srs"
    doc.source_type = "file"
    doc.source_url = None
    doc.llm_model = "qwen-doc-turbo"
    doc.parsed_content = "# SRS\n内容"
    doc.extracted_data = {
        "doc_type": "srs",
        "title": "订单系统 SRS",
        "items": [
            {"id": "REQ-1", "title": "登录", "description": "旧描述", "priority": "high"},
        ],
    }
    doc.status = "completed"
    doc.error_message = None
    doc.save = AsyncMock(return_value=doc)
    doc.refresh_from_db = AsyncMock(return_value=None)
    return doc


class ReviewModelContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(main.app)
        self.client.__enter__()

    def tearDown(self) -> None:
        self.client.__exit__(None, None, None)

    def test_get_review_model_returns_canonical_shape(self) -> None:
        with patch("main.DocumentRecord.get_or_none", new=AsyncMock(return_value=_make_doc())):
            response = self.client.get("/api/documents/7/review-model")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["doc_type"], "srs")
        self.assertEqual(body["groups"][0]["items"][0]["node_id"], "items:id:req-1")

    def test_patch_review_model_updates_and_reindexes(self) -> None:
        doc = _make_doc()
        with (
            patch("main.DocumentRecord.get_or_none", new=AsyncMock(return_value=doc)),
            patch("main.build_retrieval_corpus", new=AsyncMock(return_value=None)) as mock_reindex,
        ):
            response = self.client.patch(
                "/api/documents/7/review-model",
                json={
                    "changes": [
                        {
                            "node_id": "items:id:req-1",
                            "field_key": "description",
                            "value": "新描述",
                        }
                    ],
                    "reindex": True,
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(doc.extracted_data["items"][0]["description"], "新描述")
        self.assertIsNone(response.json()["warning"])
        mock_reindex.assert_awaited_once_with(7)

    def test_patch_review_model_returns_warning_when_reindex_fails(self) -> None:
        doc = _make_doc()
        with (
            patch("main.DocumentRecord.get_or_none", new=AsyncMock(return_value=doc)),
            patch(
                "main.build_retrieval_corpus",
                new=AsyncMock(side_effect=RuntimeError("faiss unavailable")),
            ),
        ):
            response = self.client.patch(
                "/api/documents/7/review-model",
                json={
                    "changes": [{"node_id": "meta:title", "field_key": "title", "value": "新标题"}],
                    "reindex": True,
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertIn("向量索引构建失败", response.json()["warning"])

    def test_review_model_reextract_returns_preview_node(self) -> None:
        doc = _make_doc()
        preview_node = {
            "node_id": "items:id:req-1",
            "node_type": "item",
            "label": "需求项",
            "group_key": "items",
            "title": "登录",
            "fields": [
                {
                    "node_id": "items:id:req-1",
                    "field_key": "description",
                    "label": "描述",
                    "value": "AI 新描述",
                    "value_type": "string",
                    "editable": True,
                }
            ],
        }
        with (
            patch("main.DocumentRecord.get_or_none", new=AsyncMock(return_value=doc)),
            patch("main.preview_reextract_node", new=AsyncMock(return_value=preview_node)) as mock_preview,
        ):
            response = self.client.post(
                "/api/documents/7/review-model/re-extract",
                json={"node_id": "items:id:req-1", "instruction": "统一表述"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["node"]["fields"][0]["value"], "AI 新描述")
        mock_preview.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()

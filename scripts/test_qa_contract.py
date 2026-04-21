import unittest
from typing import cast
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

import main


class QaContractTests(unittest.TestCase):
    """验证问答与模型切换相关接口契约。"""

    def __init__(self, methodName: str = "runTest") -> None:
        super().__init__(methodName)
        self.client: TestClient | None = None

    def _client(self) -> TestClient:
        """返回已初始化的测试客户端。"""
        return cast(TestClient, self.client)

    def setUp(self) -> None:
        self.client = TestClient(main.app)
        self._client().__enter__()

    def tearDown(self) -> None:
        self._client().__exit__(None, None, None)

    def test_text_models_endpoint_returns_allowlist(self) -> None:
        mock_models = [
            {
                "id": "qwen-doc-turbo",
                "label": "Qwen Doc Turbo",
                "description": "默认文档理解模型",
                "is_default": True,
            },
            {
                "id": "kimi/kimi-k2.5",
                "label": "Kimi K2.5",
                "description": "长文本模型",
                "is_default": False,
            },
        ]

        with patch("main.list_text_models", return_value=mock_models) as mock_list_models:
            response = self._client().get("/api/text-models")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["models"][0]["id"], "qwen-doc-turbo")
        mock_list_models.assert_called_once_with()

    def test_api_qa_accepts_expected_json_contract(self) -> None:
        mock_result = {
            "answer": "测试回答",
            "citations": [
                {"doc_id": 1, "chunk_id": 2, "score": 0.9, "snippet": "证据片段"},
            ],
        }

        with patch("main.answer_question", new=AsyncMock(return_value=mock_result)) as mock_qa:
            response = self._client().post(
                "/api/qa",
                json={
                    "question": "系统支持哪些 API？",
                    "doc_ids": [1],
                    "top_k": 3,
                    "llm_model": "kimi/kimi-k2.5",
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["answer"], "测试回答")
        mock_qa.assert_awaited_once_with(
            question="系统支持哪些 API？",
            doc_ids=[1],
            top_k=3,
            llm_model="kimi/kimi-k2.5",
        )

    def test_api_qa_defaults_model_when_omitted(self) -> None:
        mock_result = {
            "answer": "默认模型回答",
            "citations": [],
        }

        with patch("main.answer_question", new=AsyncMock(return_value=mock_result)) as mock_qa:
            response = self._client().post(
                "/api/qa",
                json={"question": "默认模型会被使用吗？"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["answer"], "默认模型回答")
        mock_qa.assert_awaited_once_with(
            question="默认模型会被使用吗？",
            doc_ids=None,
            top_k=5,
            llm_model=None,
        )

    def test_api_qa_rejects_invalid_model(self) -> None:
        with patch(
            "main.answer_question",
            new=AsyncMock(side_effect=ValueError("不支持的文本模型: bad-model")),
        ):
            response = self._client().post(
                "/api/qa",
                json={"question": "测试", "llm_model": "bad-model"},
            )

        self.assertEqual(response.status_code, 400)
        self.assertIn("不支持的文本模型", response.text)

    def test_api_qa_rejects_missing_question(self) -> None:
        response = self._client().post("/api/qa", json={"doc_ids": [1], "top_k": 3})

        self.assertEqual(response.status_code, 422)
        self.assertIn("question", response.text)

    def test_list_documents_returns_json_array(self) -> None:
        response = self._client().get("/api/documents")

        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(response.json(), list)

    def test_get_document_rejects_missing_record(self) -> None:
        response = self._client().get("/api/documents/999999")

        self.assertEqual(response.status_code, 404)
        self.assertIn("记录不存在", response.text)

    def test_upload_rejects_unsupported_extension(self) -> None:
        response = self._client().post(
            "/api/upload",
            data={"doc_type": "srs"},
            files={"file": ("notes.csv", b"id,name\n1,test\n", "text/csv")},
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("不支持的文件类型", response.text)

    def test_upload_rejects_missing_doc_type(self) -> None:
        response = self._client().post(
            "/api/upload",
            files={"file": ("notes.txt", b"hello", "text/plain")},
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("doc_type", response.text)

    def test_upload_rejects_invalid_doc_type(self) -> None:
        response = self._client().post(
            "/api/upload",
            data={"doc_type": "project"},
            files={"file": ("notes.txt", b"hello", "text/plain")},
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("非法 doc_type", response.text)

    def test_upload_url_rejects_missing_doc_type(self) -> None:
        response = self._client().post(
            "/api/upload/url",
            json={"url": "https://example.com"},
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("doc_type", response.text)

    def test_upload_url_rejects_invalid_doc_type(self) -> None:
        response = self._client().post(
            "/api/upload/url",
            json={"url": "https://example.com", "doc_type": "project"},
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("非法 doc_type", response.text)


if __name__ == "__main__":
    unittest.main()

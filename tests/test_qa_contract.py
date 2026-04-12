import unittest
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

import main


class QaContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client_cm = TestClient(main.app)
        self.client = self.client_cm.__enter__()

    def tearDown(self) -> None:
        self.client_cm.__exit__(None, None, None)

    def test_api_qa_accepts_expected_json_contract(self) -> None:
        mock_result = {
            "answer": "测试回答",
            "citations": [
                {"doc_id": 1, "chunk_id": 2, "score": 0.9, "snippet": "证据片段"},
            ],
        }

        with patch("main.answer_question", new=AsyncMock(return_value=mock_result)) as mock_qa:
            response = self.client.post(
                "/api/qa",
                json={"question": "系统支持哪些 API？", "doc_id": 1, "top_k": 3},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["answer"], "测试回答")
        mock_qa.assert_awaited_once_with(question="系统支持哪些 API？", doc_id=1, top_k=3)

    def test_api_qa_rejects_missing_question(self) -> None:
        response = self.client.post("/api/qa", json={"doc_id": 1, "top_k": 3})

        self.assertEqual(response.status_code, 422)
        self.assertIn("question", response.text)

    def test_list_documents_returns_json_array(self) -> None:
        response = self.client.get("/api/documents")

        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(response.json(), list)

    def test_get_document_rejects_missing_record(self) -> None:
        response = self.client.get("/api/documents/999999")

        self.assertEqual(response.status_code, 404)
        self.assertIn("记录不存在", response.text)

    def test_upload_rejects_unsupported_extension(self) -> None:
        response = self.client.post(
            "/api/upload",
            files={"file": ("notes.csv", b"id,name\n1,test\n", "text/csv")},
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("不支持的文件类型", response.text)

if __name__ == "__main__":
    unittest.main()

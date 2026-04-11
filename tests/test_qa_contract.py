import unittest
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

import main


class QaContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(main.app)

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

    def test_partial_qa_accepts_form_contract(self) -> None:
        mock_result = {
            "answer": "表单回答",
            "citations": [
                {"doc_id": 3, "chunk_id": 7, "score": 0.8, "snippet": "表单证据"},
            ],
        }

        with patch("main.answer_question", new=AsyncMock(return_value=mock_result)) as mock_qa:
            response = self.client.post(
                "/partials/qa",
                data={"question": "  表单问题  ", "doc_id": "3", "top_k": "4"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertIn("表单回答", response.text)
        mock_qa.assert_awaited_once_with(question="表单问题", doc_id=3, top_k=4)

    def test_partial_qa_rejects_blank_question(self) -> None:
        response = self.client.post(
            "/partials/qa",
            data={"question": "   ", "doc_id": "", "top_k": "5"},
        )

        self.assertEqual(response.status_code, 422)
        self.assertIn("question 不能为空", response.text)


if __name__ == "__main__":
    unittest.main()

"""
re-extract 端点契约测试。

覆盖：
- 全量提取正常路径
- 指定字段正常路径
- 无补充指示（instruction 缺省）
- 文档不存在 → 404
- 文档无原文 → 400
- doc_type 不支持 → 400
- scope=field 缺 field_key → 422
- re_extract_with_instruction 抛 ValueError → 400
- re_extract_with_instruction 抛通用异常 → 500
"""
import unittest
from typing import cast
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

import main


# ── 辅助构造假 DocumentRecord ─────────────────────────────────────────────────

def _make_doc(
    doc_id: int = 1,
    doc_type: str = "srs",
    parsed_content: str = "# 需求文档\n内容",
    llm_model: str | None = None,
) -> MagicMock:
    doc = MagicMock()
    doc.id = doc_id
    doc.doc_type = doc_type
    doc.parsed_content = parsed_content
    doc.llm_model = llm_model
    return doc


# ── 测试类 ────────────────────────────────────────────────────────────────────

class ReExtractContractTests(unittest.TestCase):
    """验证 POST /api/documents/{doc_id}/re-extract 接口契约。"""

    def setUp(self) -> None:
        self.client = TestClient(main.app)
        self.client.__enter__()

    def tearDown(self) -> None:
        self.client.__exit__(None, None, None)

    # ── 正常路径 ──────────────────────────────────────────────────────────────

    def test_full_scope_returns_result(self) -> None:
        """全量提取返回完整 JSON 结果。"""
        mock_result = {"title": "系统需求", "version": "1.0", "requirements": []}

        with (
            patch("main.DocumentRecord.get_or_none", new=AsyncMock(return_value=_make_doc())),
            patch("main.re_extract_with_instruction", return_value=mock_result) as mock_fn,
        ):
            response = self.client.post(
                "/api/documents/1/re-extract",
                json={"scope": "full", "instruction": "重点关注非功能需求"},
            )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["scope"], "full")
        self.assertIsNone(body["field_key"])
        self.assertEqual(body["result"]["title"], "系统需求")
        mock_fn.assert_called_once()
        _, kwargs = mock_fn.call_args
        self.assertEqual(kwargs["scope"], "full")
        self.assertEqual(kwargs["instruction"], "重点关注非功能需求")

    def test_field_scope_returns_single_field(self) -> None:
        """指定字段提取返回目标字段的结果。"""
        mock_result = {"requirements": ["需求 A", "需求 B"]}

        with (
            patch("main.DocumentRecord.get_or_none", new=AsyncMock(return_value=_make_doc())),
            patch("main.re_extract_with_instruction", return_value=mock_result),
        ):
            response = self.client.post(
                "/api/documents/1/re-extract",
                json={"scope": "field", "field_key": "requirements"},
            )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["scope"], "field")
        self.assertEqual(body["field_key"], "requirements")
        self.assertIn("requirements", body["result"])

    def test_no_instruction_is_accepted(self) -> None:
        """instruction 字段缺省时请求合法。"""
        with (
            patch("main.DocumentRecord.get_or_none", new=AsyncMock(return_value=_make_doc())),
            patch("main.re_extract_with_instruction", return_value={}) as mock_fn,
        ):
            response = self.client.post(
                "/api/documents/1/re-extract",
                json={"scope": "full"},
            )

        self.assertEqual(response.status_code, 200)
        _, kwargs = mock_fn.call_args
        self.assertIsNone(kwargs["instruction"])

    # ── 错误路径 ──────────────────────────────────────────────────────────────

    def test_document_not_found_returns_404(self) -> None:
        """文档不存在时返回 404。"""
        with patch("main.DocumentRecord.get_or_none", new=AsyncMock(return_value=None)):
            response = self.client.post(
                "/api/documents/999/re-extract",
                json={"scope": "full"},
            )

        self.assertEqual(response.status_code, 404)

    def test_document_without_parsed_content_returns_400(self) -> None:
        """文档无原文时返回 400。"""
        doc = _make_doc(parsed_content=None)
        with patch("main.DocumentRecord.get_or_none", new=AsyncMock(return_value=doc)):
            response = self.client.post(
                "/api/documents/1/re-extract",
                json={"scope": "full"},
            )

        self.assertEqual(response.status_code, 400)
        self.assertIn("原文", response.text)

    def test_unsupported_doc_type_returns_400(self) -> None:
        """不支持的 doc_type（unknown）返回 400。"""
        doc = _make_doc(doc_type="unknown")
        with patch("main.DocumentRecord.get_or_none", new=AsyncMock(return_value=doc)):
            response = self.client.post(
                "/api/documents/1/re-extract",
                json={"scope": "full"},
            )

        self.assertEqual(response.status_code, 400)
        self.assertIn("不支持的文档类型", response.text)

    def test_field_scope_without_field_key_returns_422(self) -> None:
        """scope=field 缺少 field_key 时，Pydantic validator 应拦截并返回 422。"""
        response = self.client.post(
            "/api/documents/1/re-extract",
            json={"scope": "field"},
        )

        self.assertEqual(response.status_code, 422)

    def test_value_error_from_extractor_returns_400(self) -> None:
        """re_extract_with_instruction 抛出 ValueError 时返回 400。"""
        with (
            patch("main.DocumentRecord.get_or_none", new=AsyncMock(return_value=_make_doc())),
            patch(
                "main.re_extract_with_instruction",
                side_effect=ValueError("LLM 未返回字段 'steps'"),
            ),
        ):
            response = self.client.post(
                "/api/documents/1/re-extract",
                json={"scope": "field", "field_key": "steps"},
            )

        self.assertEqual(response.status_code, 400)
        self.assertIn("steps", response.text)

    def test_runtime_error_from_extractor_returns_500(self) -> None:
        """re_extract_with_instruction 抛出通用异常时返回 500。"""
        with (
            patch("main.DocumentRecord.get_or_none", new=AsyncMock(return_value=_make_doc())),
            patch(
                "main.re_extract_with_instruction",
                side_effect=RuntimeError("LLM Extraction failed"),
            ),
        ):
            response = self.client.post(
                "/api/documents/1/re-extract",
                json={"scope": "full"},
            )

        self.assertEqual(response.status_code, 500)


if __name__ == "__main__":
    unittest.main()

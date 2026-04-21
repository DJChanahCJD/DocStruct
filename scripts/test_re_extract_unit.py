"""
re_extract_with_instruction 单元测试。
"""
import unittest
from typing import Literal
from unittest.mock import patch

from pydantic import BaseModel

from core.extractor import re_extract_with_instruction


class _FakeDoc(BaseModel):
    title: str = ""
    requirements: list[str] = []


class _DocWithEnum(BaseModel):
    title: str = ""
    status: Literal["draft", "approved", "rejected"] = "draft"


class ReExtractWithInstructionTests(unittest.IsolatedAsyncioTestCase):
    async def test_full_scope_returns_validated_dict(self) -> None:
        fake_llm_output = '{"title": "SRS v2", "requirements": ["FR-01"]}'

        with patch("core.extractor._create_text_completion", return_value=fake_llm_output):
            result = await re_extract_with_instruction(
                parsed_content="# SRS\n内容",
                response_model=_FakeDoc,
                scope="full",
                instruction="重点关注非功能需求",
            )

        self.assertEqual(result["title"], "SRS v2")
        self.assertIn("FR-01", result["requirements"])

    async def test_full_scope_without_instruction(self) -> None:
        fake_llm_output = '{"title": "SRS", "requirements": []}'

        with patch("core.extractor._create_text_completion", return_value=fake_llm_output) as mock_llm:
            result = await re_extract_with_instruction(
                parsed_content="# SRS",
                response_model=_FakeDoc,
                scope="full",
            )

        self.assertEqual(result["title"], "SRS")
        call_messages = mock_llm.call_args.kwargs["messages"]
        user_content = call_messages[1]["content"]
        self.assertNotIn("用户补充指示", user_content)

    async def test_full_scope_instruction_appended_to_prompt(self) -> None:
        fake_llm_output = '{"title": "", "requirements": []}'

        with patch("core.extractor._create_text_completion", return_value=fake_llm_output) as mock_llm:
            await re_extract_with_instruction(
                parsed_content="# SRS",
                response_model=_FakeDoc,
                scope="full",
                instruction="只提取安全需求",
            )

        call_messages = mock_llm.call_args.kwargs["messages"]
        user_content = call_messages[1]["content"]
        self.assertIn("只提取安全需求", user_content)

    async def test_field_scope_returns_target_key(self) -> None:
        fake_llm_output = '{"requirements": ["FR-01", "FR-02"]}'

        with patch("core.extractor._create_text_completion", return_value=fake_llm_output):
            result = await re_extract_with_instruction(
                parsed_content="# SRS\n内容",
                response_model=_FakeDoc,
                scope="field",
                field_key="requirements",
            )

        self.assertIn("requirements", result)
        self.assertEqual(len(result["requirements"]), 2)
        self.assertNotIn("title", result)

    async def test_field_scope_with_instruction(self) -> None:
        fake_llm_output = '{"requirements": ["FR-SEC-01"]}'

        with patch("core.extractor._create_text_completion", return_value=fake_llm_output) as mock_llm:
            await re_extract_with_instruction(
                parsed_content="# SRS",
                response_model=_FakeDoc,
                scope="field",
                field_key="requirements",
                instruction="只提取安全需求",
            )

        call_messages = mock_llm.call_args.kwargs["messages"]
        user_content = call_messages[1]["content"]
        self.assertIn("只提取安全需求", user_content)

    async def test_field_scope_raises_when_key_missing_in_response(self) -> None:
        fake_llm_output = '{"title": "SRS"}'

        with patch("core.extractor._create_text_completion", return_value=fake_llm_output):
            with self.assertRaises(ValueError) as ctx:
                await re_extract_with_instruction(
                    parsed_content="# SRS",
                    response_model=_FakeDoc,
                    scope="field",
                    field_key="requirements",
                )

        self.assertIn("requirements", str(ctx.exception))

    async def test_field_scope_schema_hint_injected_in_prompt(self) -> None:
        fake_llm_output = '{"status": "approved"}'

        with patch("core.extractor._create_text_completion", return_value=fake_llm_output) as mock_llm:
            await re_extract_with_instruction(
                parsed_content="# Doc",
                response_model=_DocWithEnum,
                scope="field",
                field_key="status",
            )

        call_messages = mock_llm.call_args.kwargs["messages"]
        user_content = call_messages[1]["content"]
        self.assertIn("字段 Schema 约束", user_content)
        self.assertIn("approved", user_content)
        self.assertIn("draft", user_content)

    async def test_field_scope_no_schema_hint_for_unknown_key(self) -> None:
        fake_llm_output = '{"nonexistent": "value"}'

        with patch("core.extractor._create_text_completion", return_value=fake_llm_output):
            with self.assertRaises(ValueError):
                await re_extract_with_instruction(
                    parsed_content="# Doc",
                    response_model=_DocWithEnum,
                    scope="field",
                    field_key="unknown_field",
                )

    async def test_full_scope_raises_on_invalid_json(self) -> None:
        with patch("core.extractor._create_text_completion", return_value="not-json"):
            with self.assertRaises(Exception):
                await re_extract_with_instruction(
                    parsed_content="# SRS",
                    response_model=_FakeDoc,
                    scope="full",
                )


if __name__ == "__main__":
    unittest.main()

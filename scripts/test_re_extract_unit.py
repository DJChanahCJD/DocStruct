"""
re_extract_with_instruction 单元测试。

覆盖：
- full 模式：正常提取，instruction 追加到 prompt
- full 模式：无 instruction 时不追加
- field 模式：正常提取，返回目标字段
- field 模式：LLM 未返回目标字段 → ValueError
- full 模式：LLM 返回非法 JSON → 抛出异常
- field 模式：prompt 包含字段 Schema hint（含枚举约束）
"""
import unittest
from typing import Literal
from unittest.mock import MagicMock, patch

from pydantic import BaseModel

from core.extractor import re_extract_with_instruction


# ── 最小 Pydantic 模型（模拟 SrsDocument）────────────────────────────────────

class _FakeDoc(BaseModel):
    title: str = ""
    requirements: list[str] = []


class _DocWithEnum(BaseModel):
    """带枚举约束的模型，用于验证 schema hint 注入。"""
    title: str = ""
    status: Literal["draft", "approved", "rejected"] = "draft"


# ── 测试类 ────────────────────────────────────────────────────────────────────

class ReExtractWithInstructionTests(unittest.TestCase):
    """验证 re_extract_with_instruction 的两个提取分支。"""

    # ── full 模式 ─────────────────────────────────────────────────────────────

    def test_full_scope_returns_validated_dict(self) -> None:
        """full 模式返回经 response_model 验证的 dict。"""
        fake_llm_output = '{"title": "SRS v2", "requirements": ["FR-01"]}'

        with patch("core.extractor._create_text_completion", return_value=fake_llm_output):
            result = re_extract_with_instruction(
                parsed_content="# SRS\n内容",
                response_model=_FakeDoc,
                scope="full",
                instruction="重点关注非功能需求",
            )

        self.assertEqual(result["title"], "SRS v2")
        self.assertIn("FR-01", result["requirements"])

    def test_full_scope_without_instruction(self) -> None:
        """full 模式 instruction=None 时仍能正常提取。"""
        fake_llm_output = '{"title": "SRS", "requirements": []}'

        with patch("core.extractor._create_text_completion", return_value=fake_llm_output) as mock_llm:
            result = re_extract_with_instruction(
                parsed_content="# SRS",
                response_model=_FakeDoc,
                scope="full",
            )

        self.assertEqual(result["title"], "SRS")
        # 确认只调用了一次 LLM
        mock_llm.assert_called_once()
        # 确认 prompt 中不含意外的 instruction 标记
        call_messages = mock_llm.call_args.kwargs["messages"]
        user_content = call_messages[1]["content"]
        self.assertNotIn("用户补充指示", user_content)

    def test_full_scope_instruction_appended_to_prompt(self) -> None:
        """full 模式 instruction 被追加到 prompt 内容中。"""
        fake_llm_output = '{"title": "", "requirements": []}'

        with patch("core.extractor._create_text_completion", return_value=fake_llm_output) as mock_llm:
            re_extract_with_instruction(
                parsed_content="# SRS",
                response_model=_FakeDoc,
                scope="full",
                instruction="只提取安全需求",
            )

        call_messages = mock_llm.call_args.kwargs["messages"]
        user_content = call_messages[1]["content"]
        self.assertIn("只提取安全需求", user_content)

    # ── field 模式 ────────────────────────────────────────────────────────────

    def test_field_scope_returns_target_key(self) -> None:
        """field 模式返回仅含目标字段的 dict。"""
        fake_llm_output = '{"requirements": ["FR-01", "FR-02"]}'

        with patch("core.extractor._create_text_completion", return_value=fake_llm_output):
            result = re_extract_with_instruction(
                parsed_content="# SRS\n内容",
                response_model=_FakeDoc,
                scope="field",
                field_key="requirements",
            )

        self.assertIn("requirements", result)
        self.assertEqual(len(result["requirements"]), 2)
        # field 模式不应返回其他字段
        self.assertNotIn("title", result)

    def test_field_scope_with_instruction(self) -> None:
        """field 模式 instruction 被追加到 prompt 中。"""
        fake_llm_output = '{"requirements": ["FR-SEC-01"]}'

        with patch("core.extractor._create_text_completion", return_value=fake_llm_output) as mock_llm:
            re_extract_with_instruction(
                parsed_content="# SRS",
                response_model=_FakeDoc,
                scope="field",
                field_key="requirements",
                instruction="只提取安全需求",
            )

        call_messages = mock_llm.call_args.kwargs["messages"]
        user_content = call_messages[1]["content"]
        self.assertIn("只提取安全需求", user_content)

    def test_field_scope_raises_when_key_missing_in_response(self) -> None:
        """LLM 未返回目标字段时抛出 ValueError。"""
        # LLM 返回了别的字段
        fake_llm_output = '{"title": "SRS"}'

        with patch("core.extractor._create_text_completion", return_value=fake_llm_output):
            with self.assertRaises(ValueError) as ctx:
                re_extract_with_instruction(
                    parsed_content="# SRS",
                    response_model=_FakeDoc,
                    scope="field",
                    field_key="requirements",
                )

        self.assertIn("requirements", str(ctx.exception))

    def test_field_scope_schema_hint_injected_in_prompt(self) -> None:
        """field 模式的 prompt 中应包含目标字段的 Schema 约束描述。"""
        fake_llm_output = '{"status": "approved"}'

        with patch("core.extractor._create_text_completion", return_value=fake_llm_output) as mock_llm:
            re_extract_with_instruction(
                parsed_content="# Doc",
                response_model=_DocWithEnum,
                scope="field",
                field_key="status",
            )

        call_messages = mock_llm.call_args.kwargs["messages"]
        user_content = call_messages[1]["content"]
        # prompt 中应包含 schema hint 标记
        self.assertIn("字段 Schema 约束", user_content)
        # 枚举值应出现在 prompt 中
        self.assertIn("approved", user_content)
        self.assertIn("draft", user_content)

    def test_field_scope_no_schema_hint_for_unknown_key(self) -> None:
        """field_key 不在 model 属性中时，不注入 schema hint（不报错）。"""
        fake_llm_output = '{"nonexistent": "value"}'

        with patch("core.extractor._create_text_completion", return_value=fake_llm_output):
            with self.assertRaises(ValueError):
                # 会因 field_key 不在返回中而抛 ValueError，但不应因 schema hint 逻辑崩溃
                re_extract_with_instruction(
                    parsed_content="# Doc",
                    response_model=_DocWithEnum,
                    scope="field",
                    field_key="unknown_field",
                )

    # ── 异常处理 ──────────────────────────────────────────────────────────────

    def test_full_scope_raises_on_invalid_json(self) -> None:
        """LLM 返回非法 JSON 时，full 模式应抛出异常（而非静默失败）。"""
        with patch("core.extractor._create_text_completion", return_value="not-json"):
            with self.assertRaises(Exception):
                re_extract_with_instruction(
                    parsed_content="# SRS",
                    response_model=_FakeDoc,
                    scope="full",
                )


if __name__ == "__main__":
    unittest.main()

import asyncio
import unittest
from unittest.mock import AsyncMock, patch

from core.config import get_settings
from core.extractor import extract_structure_with_meta
from core.prompting import render_chunk_context, render_finalizer_input
from schemas.extraction import ExtractionContract
from schemas.models import DocType, DocumentChunk, DocumentElement, DocumentIR, DocumentOutline, SrsExtractedDocument


def _sample_ir() -> DocumentIR:
    """构造用于 prompt 渲染测试的最小文档 IR。"""
    return DocumentIR(
        title="示例文档",
        doc_type=DocType.SRS,
        outline=DocumentOutline(
            title="示例文档",
            doc_type=DocType.SRS,
            sections=["需求"],
            main_topics=["需求"],
        ),
        elements=[
            DocumentElement(
                element_id="el-1",
                element_type="paragraph",
                text="系统应支持登录。",
                markdown="系统应支持登录。",
                section_path=["需求"],
                order=1,
            )
        ],
    )


def _sample_contract() -> ExtractionContract:
    """构造用于 prompt 渲染测试的最小抽取契约。"""
    return ExtractionContract(
        doc_type=DocType.SRS,
        target_slots=["functional_requirements"],
        rules=["只抽取当前输入中明确出现的对象。"],
    )


class ExtractorPromptRenderingTest(unittest.TestCase):
    """验证抽取 prompt 的 summary 与 finalizer 边界。"""

    def test_render_chunk_context_marks_summary_as_non_evidence(self) -> None:
        """分块上下文应注入摘要，但明确摘要不能作为证据依据。"""
        ir = _sample_ir()
        chunk = DocumentChunk(
            chunk_id="chunk-0001",
            section_path=["需求"],
            elements=ir.elements,
            markdown="[ELEMENT: el-1]\n系统应支持登录。",
        )

        rendered = render_chunk_context(
            document_ir=ir,
            contract=_sample_contract(),
            chunk=chunk,
            document_summary="本文描述登录需求。",
        )

        self.assertIn("[Document Summary]", rendered)
        self.assertIn("Document Summary 只用于理解上下文", rendered)
        self.assertIn("allowed_evidence_element_ids", rendered)
        self.assertIn("el-1", rendered)

    def test_render_finalizer_input_does_not_include_full_evidence_snippets(self) -> None:
        """Finalizer 只合并候选，不再接收全文 evidence snippets。"""
        rendered = render_finalizer_input(
            document_ir=_sample_ir(),
            contract=_sample_contract(),
            chunk_results=[
                {
                    "functional_requirements": [
                        {
                            "name": "登录",
                            "points": ["系统应支持登录。"],
                            "evidence_element_ids": ["el-1"],
                        }
                    ]
                }
            ],
            document_summary="本文描述登录需求。",
        )

        self.assertIn("[Chunk Candidates]", rendered)
        self.assertNotIn("[Evidence Snippets]", rendered)
        self.assertNotIn("[ELEMENT: el-1", rendered)
        self.assertIn("evidence_element_ids", rendered)

    def test_extract_structure_meta_records_default_model_name(self) -> None:
        """未显式传入模型时，抽取元信息应记录配置中的默认模型名。"""
        chunk_result = {
            "system_name": "示例系统",
            "target_users": [],
            "functional_requirements": [
                {
                    "name": "登录",
                    "points": ["系统应支持登录。"],
                    "evidence_element_ids": ["el-1"],
                }
            ],
            "non_functional_requirements": [],
            "business_flows": [],
        }

        with patch("core.extractor._extract_chunk", new=AsyncMock(return_value=chunk_result)), patch(
            "core.extractor._finalize_extraction_once",
            return_value=chunk_result,
        ):
            _document, meta = asyncio.run(
                extract_structure_with_meta(
                    "系统应支持登录。",
                    SrsExtractedDocument,
                    document_ir=_sample_ir(),
                )
            )

        self.assertEqual(meta["llm_model"], get_settings().llm_model)


if __name__ == "__main__":
    unittest.main()

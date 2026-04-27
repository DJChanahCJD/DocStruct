import asyncio
import unittest
from unittest.mock import patch

from core.chunker import split_ir_into_chunks
from core.extractor import (
    FINALIZE_PROMPT_TEMPLATE,
    _render_finalizer_input,
    build_extraction_contract,
    extract_structure_with_meta,
)
from core.ir import parse_result_to_ir
from core.reducer import reduce_extraction_results
from core.parser import DocBlock, ParseResult
from core.parsers.docling_parser import DoclingParser
from schemas.models import DocType, DocumentElement, DocumentIR, ExtractedObjectSet, SrsDocument


class SrsRequirementBoundaryTests(unittest.TestCase):
    """Regression tests for SRS requirement section boundaries."""

    def test_srs_field_titles_do_not_open_sections(self) -> None:
        """Ensure SRS field labels stay under the numbered requirement section."""
        parse_result = ParseResult(
            markdown="",
            title="智能文档系统需求规格说明书",
            blocks=[
                DocBlock(type="title", text="2.1.2 用户登录", level=4, order=0),
                DocBlock(type="paragraph", text="系统应支持用户通过账号密码登录", order=1),
                DocBlock(type="title", text="功能点 ：", level=1, order=2),
                DocBlock(type="list", text="支持邮箱+密码登录", order=3),
                DocBlock(type="title", text="验收标准 ：", level=1, order=4),
                DocBlock(type="list", text="登录响应时间 < 2 秒", order=5),
            ],
        )

        ir = parse_result_to_ir(parse_result, doc_type=DocType.SRS)
        section_paths = {tuple(element.section_path) for element in ir.elements}

        self.assertEqual(section_paths, {("2.1.2 用户登录",)})
        self.assertEqual(ir.outline.sections, ["2.1.2 用户登录"])

    def test_srs_requirement_section_stays_in_one_chunk(self) -> None:
        """Ensure one normal requirement section is extracted as one chunk."""
        parse_result = ParseResult(
            markdown="",
            title="智能文档系统需求规格说明书",
            blocks=[
                DocBlock(type="title", text="2.1.2 用户登录", level=4, order=0),
                DocBlock(type="paragraph", text="需求编号：SRS-USER-002", order=1),
                DocBlock(type="paragraph", text="需求描述：系统应支持用户通过账号密码登录", order=2),
                DocBlock(type="title", text="功能点 ：", level=1, order=3),
                DocBlock(type="list", text="支持邮箱+密码登录\n支持记住我功能", order=4),
                DocBlock(type="title", text="验收标准 ：", level=1, order=5),
                DocBlock(type="list", text="登录响应时间 < 2 秒\nToken 有效期 2 小时", order=6),
            ],
        )

        ir = parse_result_to_ir(parse_result, doc_type=DocType.SRS)
        chunks = split_ir_into_chunks(ir, max_chars=5000)

        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0].section_path, ["2.1.2 用户登录"])
        self.assertEqual(
            [element.element_id for element in chunks[0].elements],
            [f"el-{index:04d}" for index in range(1, 8)],
        )

    def test_reducer_preserves_source_id_without_semantic_filtering(self) -> None:
        """Ensure reducer preserves source IDs but does not apply SRS semantic filters."""
        elements = [
            DocumentElement(
                element_id="el-0001",
                element_type="heading",
                text="2.1.2 用户登录",
                section_path=["2.1.2 用户登录"],
                order=0,
            ),
            DocumentElement(
                element_id="el-0002",
                element_type="paragraph",
                text="系统应支持用户通过账号密码登录",
                section_path=["2.1.2 用户登录"],
                order=1,
            ),
            DocumentElement(
                element_id="el-0003",
                element_type="paragraph",
                text="支持邮箱+密码登录",
                section_path=["2.1.2 用户登录"],
                order=2,
            ),
            DocumentElement(
                element_id="el-0004",
                element_type="paragraph",
                text="登录响应时间 < 2 秒",
                section_path=["2.1.2 用户登录"],
                order=3,
            ),
        ]
        document_ir = DocumentIR(title="智能文档系统需求规格说明书", doc_type=DocType.SRS, elements=elements)

        reduced, _ = reduce_extraction_results(
            doc_type="srs",
            title=document_ir.title,
            document_ir=document_ir,
            chunk_results=[
                {
                    "requirements": [
                        {
                            "id": "SRS-USER-002",
                            "name": "用户登录",
                            "description": "系统应支持用户通过账号密码登录",
                            "requirement_type": "functional",
                            "acceptance_criteria": ["登录响应时间 < 2 秒"],
                            "evidence_element_ids": ["el-0001", "el-0002"],
                        },
                        {
                            "id": "SRS-USER-002",
                            "name": "用户登录",
                            "requirement_type": "functional",
                            "details": ["支持邮箱+密码登录"],
                            "evidence_element_ids": ["el-0001", "el-0003"],
                        },
                        {
                            "name": "验收标准",
                            "requirement_type": "acceptance",
                            "acceptance_criteria": ["登录响应时间 < 2 秒"],
                            "evidence_element_ids": ["el-0004"],
                        },
                    ]
                }
            ],
        )

        self.assertEqual(len(reduced["requirements"]), 2)
        requirement = reduced["requirements"][0]
        acceptance = reduced["requirements"][1]
        self.assertEqual(requirement["id"], "REQ-001")
        self.assertEqual(requirement["source_id"], "SRS-USER-002")
        self.assertEqual(requirement["details"], ["支持邮箱+密码登录"])
        self.assertEqual(requirement["acceptance_criteria"], ["登录响应时间 < 2 秒"])
        self.assertEqual(acceptance["id"], "REQ-002")
        self.assertEqual(acceptance["requirement_type"], "acceptance")
        self.assertNotIn("views", reduced)
        self.assertNotIn("priority", requirement)
        self.assertNotIn("category", requirement)
        for evidence in reduced["evidence"]:
            self.assertNotIn("evidence_id", evidence)
            self.assertNotIn("section_path", evidence)

    def test_reducer_limits_evidence_to_compact_anchors(self) -> None:
        """Ensure each object keeps only a few valid evidence anchors."""
        elements = [
            DocumentElement(
                element_id=f"el-{index:04d}",
                element_type="paragraph",
                text=f"证据 {index}",
                section_path=["2.2.2 文档解析"],
                order=index,
            )
            for index in range(1, 6)
        ]
        document_ir = DocumentIR(title="智能文档系统需求规格说明书", doc_type=DocType.SRS, elements=elements)

        reduced, meta = reduce_extraction_results(
            doc_type="srs",
            title=document_ir.title,
            document_ir=document_ir,
            chunk_results=[
                {
                    "requirements": [
                        {
                            "name": "文档解析",
                            "description": "系统应自动解析上传的文档，提取结构化信息",
                            "requirement_type": "functional",
                            "evidence_element_ids": [
                                "el-0001",
                                "missing-element",
                                "el-0002",
                                "el-0003",
                                "el-0004",
                                "el-0005",
                            ],
                        }
                    ]
                }
            ],
        )

        requirement = reduced["requirements"][0]
        self.assertEqual(requirement["evidence_element_ids"], ["el-0001", "el-0002", "el-0003"])
        self.assertEqual([entry["element_id"] for entry in reduced["evidence"]], ["el-0001", "el-0002", "el-0003"])
        self.assertEqual(meta["evidence_count"], 3)

    def test_reducer_does_not_create_fallback_evidence_without_element_ids(self) -> None:
        """Ensure evidence binding only uses valid element IDs from the IR."""
        document_ir = DocumentIR(
            title="智能文档系统需求规格说明书",
            doc_type=DocType.SRS,
            elements=[
                DocumentElement(
                    element_id="el-0001",
                    element_type="table",
                    text="| 验收项 | 验收方法 | 通过标准 |",
                    section_path=["5. 验收标准"],
                    order=0,
                )
            ],
        )

        reduced, _ = reduce_extraction_results(
            doc_type="srs",
            title=document_ir.title,
            document_ir=document_ir,
            chunk_results=[
                {
                    "requirements": [
                        {
                            "name": "验收标准",
                            "description": "文档上传功能：支持所有声明格式",
                            "requirement_type": "acceptance",
                            "evidence_element_ids": ["missing-element"],
                        }
                    ]
                }
            ],
        )

        self.assertEqual(len(reduced.get("requirements", [])), 1)
        self.assertNotIn("evidence", reduced)

    def test_finalizer_input_contains_global_merge_context(self) -> None:
        """Ensure finalizer prompt input carries outline, candidates, and evidence."""
        parse_result = ParseResult(
            markdown="",
            title="智能文档系统需求规格说明书",
            blocks=[
                DocBlock(type="title", text="2.1.1 用户注册", level=4, order=0),
                DocBlock(type="paragraph", text="需求描述：系统应支持新用户通过邮箱注册账号", order=1),
                DocBlock(type="title", text="验收标准：", level=1, order=2),
                DocBlock(type="list", text="验证码 5 分钟内有效\n邮箱不可重复注册", order=3),
            ],
        )
        ir = parse_result_to_ir(parse_result, doc_type=DocType.SRS)
        contract = build_extraction_contract(DocType.SRS)

        rendered = _render_finalizer_input(
            document_ir=ir,
            contract=contract,
            chunk_results=[
                {
                    "requirements": [
                        {
                            "name": "用户注册",
                            "requirement_type": "functional",
                            "evidence_element_ids": ["el-0001", "el-0002"],
                        },
                        {
                            "name": "验证码 5 分钟内有效",
                            "requirement_type": "constraint",
                            "evidence_element_ids": ["el-0004"],
                        },
                    ]
                }
            ],
        )

        self.assertIn("[Document Outline]", rendered)
        self.assertIn("[Chunk Candidates]", rendered)
        self.assertIn("[Evidence Snippets]", rendered)
        self.assertIn("[ELEMENT: el-0004]", rendered)
        self.assertIn("Do not turn acceptance criteria lines or acceptance-standard tables", FINALIZE_PROMPT_TEMPLATE)
        self.assertIn("1-3 compact evidence_element_ids", FINALIZE_PROMPT_TEMPLATE)
        self.assertIn("Use evidence_element_ids as anchors only", rendered)

    def test_extracted_object_set_is_the_llm_facing_schema(self) -> None:
        """Ensure the LLM-facing schema exposes only the five object slots."""
        schema_fields = set(ExtractedObjectSet.model_fields)

        self.assertEqual(schema_fields, {"entities", "processes", "requirements", "interfaces", "artifacts"})

    def test_docling_pipeline_uses_backend_text_option(self) -> None:
        """Ensure Docling parser can prefer the PDF backend text layer."""
        parser = DoclingParser(enable_ocr=False, enable_table_structure=True, force_backend_text=True)

        pipeline_options = parser._build_pipeline_options()

        self.assertFalse(pipeline_options.do_ocr)
        self.assertTrue(pipeline_options.do_table_structure)
        self.assertTrue(pipeline_options.force_backend_text)

    def test_short_srs_uses_whole_document_extraction(self) -> None:
        """Ensure short documents bypass chunk Map and use one whole-document extraction call."""
        parse_result = ParseResult(
            markdown="",
            title="智能文档系统需求规格说明书",
            blocks=[
                DocBlock(type="title", text="2.1.1 用户注册", level=4, order=0),
                DocBlock(type="paragraph", text="需求描述：系统应支持新用户通过邮箱注册账号", order=1),
            ],
        )
        ir = parse_result_to_ir(parse_result, doc_type=DocType.SRS)

        with patch(
            "core.extractor._extract_once",
            return_value={
                "doc_type": "srs",
                "title": "智能文档系统需求规格说明书",
                "requirements": [
                    {
                        "name": "用户注册",
                        "description": "系统应支持新用户通过邮箱注册账号",
                        "requirement_type": "functional",
                        "evidence_element_ids": ["el-0001", "el-0002"],
                    }
                ],
            },
        ) as extract_once:
            extracted, meta = asyncio.run(
                extract_structure_with_meta(
                    "#### 2.1.1 用户注册\n需求描述：系统应支持新用户通过邮箱注册账号",
                    SrsDocument,
                    document_ir=ir,
                )
            )

        self.assertEqual(meta["mode"], "whole-document")
        self.assertEqual(meta["chunk_count"], 1)
        self.assertEqual(len(extracted.requirements), 1)
        extract_once.assert_called_once()


if __name__ == "__main__":
    unittest.main()

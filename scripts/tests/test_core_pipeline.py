import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from core.chunker import split_ir_into_chunks
from core.extractor import extract_structure_with_meta
from core.ir import parse_result_to_ir
from core.parser import DocBlock, MarkdownNormalizer, MarkdownRenderer
from core.parsers.docling_parser import DoclingParser
from core.reducer import reduce_extraction_results
from schemas.models import (
    DesignDocument,
    DocType,
    EntityItem,
    EntityType,
    InterfaceItem,
    RequirementItem,
    RequirementType,
    SrsDocument,
)


class CorePipelineTests(unittest.TestCase):
    """Tests for the parser-to-reducer extraction pipeline."""

    def test_markdown_parse_to_ir_preserves_sections_and_elements(self) -> None:
        """Ensure Markdown blocks become stable IR elements with section paths."""
        markdown = """# 系统需求规格说明书

## 2.1 用户管理

### 2.1.1 用户注册

需求描述：系统应支持邮箱注册。

- 验证码 5 分钟内有效
- 邮箱不可重复注册

| 字段 | 说明 |
| --- | --- |
| email | 邮箱 |
"""

        parse_result = MarkdownNormalizer().normalize(markdown)
        document_ir = parse_result_to_ir(parse_result, doc_type=DocType.SRS)

        self.assertEqual(document_ir.title, "系统需求规格说明书")
        self.assertEqual(document_ir.elements[0].element_id, "el-0001")
        self.assertIn("系统需求规格说明书 > 2.1 用户管理 > 2.1.1 用户注册", document_ir.outline.sections)
        self.assertEqual(document_ir.elements[-1].element_type, "table")
        self.assertEqual(document_ir.elements[-1].section_path[-1], "2.1.1 用户注册")

    def test_chunker_keeps_small_srs_sections_together_with_evidence_markers(self) -> None:
        """Ensure small SRS sections can share one chunk with evidence markers."""
        markdown = """# 系统需求规格说明书

#### 2.1.1 用户注册

需求编号：SRS-USER-001

需求描述：系统应支持邮箱注册。

功能点：

- 发送验证码
- 创建账号

#### 2.1.2 用户登录

需求编号：SRS-USER-002

需求描述：系统应支持邮箱登录。
"""
        document_ir = parse_result_to_ir(MarkdownNormalizer().normalize(markdown), doc_type=DocType.SRS)

        chunks = split_ir_into_chunks(document_ir, max_chars=5000)

        self.assertEqual(len(chunks), 1)
        self.assertEqual([element.element_id for element in chunks[0].elements], [f"el-{index:04d}" for index in range(1, 10)])
        self.assertIn("[ELEMENT: el-0002]", chunks[0].markdown)
        self.assertIn("[ELEMENT: el-0009]", chunks[0].markdown)

    def test_chunker_splits_oversized_section_on_element_boundaries(self) -> None:
        """Ensure oversized sections split without cutting individual elements."""
        markdown = """# 概要设计

## 模块设计

第一段内容用于描述模块职责和输入输出。

第二段内容用于描述核心流程和关键约束。

第三段内容用于描述异常处理和边界条件。
"""
        document_ir = parse_result_to_ir(MarkdownNormalizer().normalize(markdown), doc_type=DocType.DESIGN)

        chunks = split_ir_into_chunks(document_ir, max_chars=90)

        self.assertGreater(len(chunks), 1)
        self.assertEqual(
            [element.element_id for chunk in chunks for element in chunk.elements],
            [element.element_id for element in document_ir.elements],
        )
        self.assertTrue(all("[ELEMENT:" in chunk.markdown for chunk in chunks))

    def test_chunker_ignores_sections_without_merging_across_them(self) -> None:
        """Ensure ignored sections are skipped and break chunk merging."""
        markdown = """# 系统需求规格说明书

## 1. 正文

需求描述：系统应支持正文需求。

## 附录

这部分不参与抽取。

## 2. 后续正文

需求描述：系统应支持后续需求。
"""
        document_ir = parse_result_to_ir(MarkdownNormalizer().normalize(markdown), doc_type=DocType.SRS)

        chunks = split_ir_into_chunks(document_ir, max_chars=5000, ignore_sections=["附录"])
        all_text = "\n".join(chunk.markdown for chunk in chunks)

        self.assertEqual(len(chunks), 2)
        self.assertNotIn("这部分不参与抽取", all_text)
        self.assertIn("系统应支持正文需求", chunks[0].markdown)
        self.assertIn("系统应支持后续需求", chunks[1].markdown)

    def test_reducer_merges_objects_and_binds_valid_evidence(self) -> None:
        """Ensure reducer merges duplicate requirements and keeps valid evidence."""
        markdown = """# 系统需求规格说明书

#### 2.1.1 用户注册

需求描述：系统应支持邮箱注册。

验收标准：验证码 5 分钟内有效。
"""
        document_ir = parse_result_to_ir(MarkdownNormalizer().normalize(markdown), doc_type=DocType.SRS)

        reduced, meta = reduce_extraction_results(
            doc_type="srs",
            title=document_ir.title,
            document_ir=document_ir,
            chunk_results=[
                {
                    "requirements": [
                        {
                            "id": "SRS-USER-001",
                            "name": "用户注册",
                            "requirement_type": "functional",
                            "points": ["系统应支持邮箱注册。"],
                            "evidence_element_ids": ["el-0002", "missing"],
                        },
                        {
                            "id": "SRS-USER-001",
                            "name": "用户注册",
                            "criteria": ["验证码 5 分钟内有效。"],
                            "evidence_element_ids": ["el-0003"],
                        },
                    ]
                }
            ],
        )

        requirement = reduced["requirements"][0]
        self.assertEqual(len(reduced["requirements"]), 1)
        self.assertEqual(requirement["id"], "REQ-001")
        self.assertEqual(requirement["source_id"], "SRS-USER-001")
        self.assertEqual(requirement["evidence_element_ids"], ["el-0002", "el-0003"])
        self.assertEqual(meta["objects_with_evidence"], 1)
        self.assertEqual([entry["element_id"] for entry in reduced["evidence"]], ["el-0002", "el-0003"])

    def test_reducer_keeps_all_valid_evidence_without_count_clipping(self) -> None:
        """Ensure reducer validates evidence ids without enforcing a fixed count limit."""
        markdown = """# 系统需求规格说明书

#### 2.1.1 用户注册

需求编号：SRS-USER-001

需求描述：系统应支持邮箱注册。

功能点：发送验证码。

功能点：创建账号。

约束：邮箱不可重复注册。

验收标准：验证码 5 分钟内有效。
"""
        document_ir = parse_result_to_ir(MarkdownNormalizer().normalize(markdown), doc_type=DocType.SRS)
        valid_ids = [element.element_id for element in document_ir.elements[1:]]

        reduced, meta = reduce_extraction_results(
            doc_type="srs",
            title=document_ir.title,
            document_ir=document_ir,
            chunk_results=[
                {
                    "requirements": [
                        {
                            "id": "SRS-USER-001",
                            "name": "用户注册",
                            "requirement_type": "functional",
                            "points": ["系统应支持邮箱注册。"],
                            "evidence_element_ids": valid_ids + ["missing"],
                        }
                    ]
                }
            ],
        )

        requirement = reduced["requirements"][0]
        self.assertGreater(len(valid_ids), 5)
        self.assertEqual(requirement["evidence_element_ids"], valid_ids)
        self.assertEqual(meta["evidence_count"], len(valid_ids))
        self.assertEqual([entry["element_id"] for entry in reduced["evidence"]], valid_ids)

    def test_extract_structure_uses_whole_document_core_path(self) -> None:
        """Ensure short documents use the mocked whole-document extraction path."""
        markdown = """# 系统需求规格说明书

#### 2.1.1 用户注册

需求描述：系统应支持邮箱注册。
"""
        document_ir = parse_result_to_ir(MarkdownNormalizer().normalize(markdown), doc_type=DocType.SRS)

        with patch(
            "core.extractor._extract_once",
            return_value={
                "requirements": [
                    {
                        "name": "用户注册",
                        "requirement_type": "functional",
                        "points": ["系统应支持邮箱注册。"],
                        "evidence_element_ids": ["el-0002"],
                    }
                ]
            },
        ) as extract_once:
            extracted, meta = asyncio.run(
                extract_structure_with_meta(
                    markdown,
                    SrsDocument,
                    document_ir=document_ir,
                )
            )

        self.assertEqual(meta["mode"], "whole-document")
        self.assertEqual(meta["chunk_count"], 1)
        self.assertEqual(extracted.requirements[0].id, "REQ-001")
        self.assertEqual(extracted.requirements[0].evidence_element_ids, ["el-0002"])
        extract_once.assert_called_once()

    def test_chunk_extraction_keeps_partial_result_when_one_chunk_fails(self) -> None:
        """Ensure one failed chunk does not fail the whole long-document extraction."""
        markdown = """# 系统需求规格说明书

#### 2.1.1 用户注册

需求描述：系统应支持邮箱注册。

#### 2.1.2 用户登录

需求描述：系统应支持邮箱登录。
"""
        document_ir = parse_result_to_ir(MarkdownNormalizer().normalize(markdown), doc_type=DocType.SRS)

        async def fake_extract_chunk(semaphore, chunk, **kwargs):
            """Return data for one chunk and fail the other chunk."""
            if chunk.chunk_id == "chunk-0001":
                raise ValueError("bad json")
            return {
                "requirements": [
                    {
                        "name": "用户登录",
                        "requirement_type": "functional",
                        "points": ["系统应支持邮箱登录。"],
                        "evidence_element_ids": [chunk.elements[0].element_id],
                    }
                ]
            }

        fake_settings = SimpleNamespace(
            extraction_threshold=1,
            extraction_chunk_max_chars=80,
            extraction_max_chars=100000,
            extraction_concurrency=2,
        )
        with patch("core.extractor.settings", fake_settings), patch(
            "core.extractor._extract_chunk",
            side_effect=fake_extract_chunk,
        ), patch(
            "core.extractor._finalize_extraction_once",
            side_effect=lambda **kwargs: kwargs["chunk_results"][0],
        ):
            extracted, meta = asyncio.run(
                extract_structure_with_meta(
                    markdown,
                    SrsDocument,
                    document_ir=document_ir,
                )
            )

        self.assertTrue(meta["partial"])
        self.assertEqual(meta["failed_chunks"], 1)
        self.assertEqual(meta["failed_chunk_indexes"], [0])
        self.assertEqual(meta["failed_chunk_details"][0]["chunk_id"], "chunk-0001")
        self.assertEqual(extracted.requirements[0].name, "用户登录")

    def test_chunk_extraction_falls_back_when_finalizer_fails(self) -> None:
        """Ensure valid chunk results survive a finalizer JSON failure."""
        markdown = """# 系统需求规格说明书

#### 2.1.1 用户注册

需求描述：系统应支持邮箱注册。

#### 2.1.2 用户登录

需求描述：系统应支持邮箱登录。
"""
        document_ir = parse_result_to_ir(MarkdownNormalizer().normalize(markdown), doc_type=DocType.SRS)

        async def fake_extract_chunk(semaphore, chunk, **kwargs):
            """Return multiple requirements from one chunk."""
            return {
                "requirements": [
                    {
                        "name": "用户注册",
                        "requirement_type": "functional",
                        "points": ["系统应支持邮箱注册。"],
                        "evidence_element_ids": ["el-0003"],
                    },
                    {
                        "name": "用户登录",
                        "requirement_type": "functional",
                        "points": ["系统应支持邮箱登录。"],
                        "evidence_element_ids": ["el-0005"],
                    },
                ]
            }

        fake_settings = SimpleNamespace(
            extraction_threshold=1,
            extraction_chunk_max_chars=5000,
            extraction_max_chars=100000,
            extraction_concurrency=2,
        )
        with patch("core.extractor.settings", fake_settings), patch(
            "core.extractor._extract_chunk",
            side_effect=fake_extract_chunk,
        ), patch("core.extractor._finalize_extraction_once", side_effect=ValueError("finalizer bad json")):
            extracted, meta = asyncio.run(
                extract_structure_with_meta(
                    markdown,
                    SrsDocument,
                    document_ir=document_ir,
                )
            )

        self.assertTrue(meta["partial"])
        self.assertTrue(meta["finalizer_failed"])
        self.assertEqual(meta["failed_chunks"], 0)
        self.assertEqual([item.name for item in extracted.requirements], ["用户注册", "用户登录"])

    def test_schema_normalizers_use_safe_defaults(self) -> None:
        """Ensure schema models normalize invalid enum and extra values."""
        entity = EntityItem(name="用户", entity_type="person", extra="invalid")
        requirement = RequirementItem(name="审计日志", requirement_type="security", extra=None)
        interface = InterfaceItem(name="注册接口", interface_type="REST", extra=None)

        self.assertEqual(entity.entity_type, EntityType.OTHER)
        self.assertEqual(entity.extra, {})
        self.assertEqual(requirement.requirement_type, RequirementType.OTHER)
        self.assertEqual(requirement.extra, {})
        self.assertEqual(interface.interface_type, "http")
        self.assertEqual(interface.extra, {})

    def test_structured_document_dump_starts_with_document_fields(self) -> None:
        """Ensure extracted document JSON starts with document-level fields."""
        document = DesignDocument(title="智能文档系统概要设计")

        self.assertEqual(
            list(document.model_dump(mode="json").keys())[:5],
            ["doc_type", "title", "version", "extra", "entities"],
        )

    def test_docling_parser_infers_heading_level_from_markdown(self) -> None:
        """Ensure Docling heading Markdown controls the rendered heading level."""
        item = _FakeDoclingItem("section_header", "2.1.1 用户注册", "### 2.1.1 用户注册")
        parser = DoclingParser()

        element = parser._convert_element(item, 0, object())
        self.assertIsNotNone(element)
        block = parser._element_to_block(element, 0)

        self.assertIsNotNone(block)
        self.assertEqual(block.type, "title")
        self.assertEqual(block.level, 3)
        self.assertEqual(MarkdownRenderer().render([block]), "### 2.1.1 用户注册")

    def test_docling_parser_preserves_native_markdown_table(self) -> None:
        """Ensure Docling native Markdown tables are not rebuilt with numeric columns."""
        raw_table = """| 项目 | 内容 |
| --- | --- |
| 文档版本 | v1.0 |"""
        item = _FakeDoclingItem("table", "", raw_table)
        parser = DoclingParser()

        element = parser._convert_element(item, 0, object())
        self.assertIsNotNone(element)
        block = parser._element_to_block(element, 0)

        self.assertIsNotNone(block)
        self.assertEqual(block.type, "table")
        self.assertEqual(MarkdownRenderer().render([block]), raw_table)

    def test_docling_parser_merges_visual_line_paragraphs_conservatively(self) -> None:
        """Ensure Docling visual line fragments merge without crossing complete paragraphs."""
        parser = DoclingParser()
        blocks = [
            DocBlock(type="paragraph", text="需求编号 ：", order=0, source_page=1),
            DocBlock(type="paragraph", text="SRS-USER-001", order=1, source_page=1),
            DocBlock(type="paragraph", text="需求描述", order=2, source_page=1),
            DocBlock(type="paragraph", text="：系统应支持邮箱注册。", order=3, source_page=1),
            DocBlock(type="paragraph", text="这是完整句子。", order=4, source_page=1),
            DocBlock(type="paragraph", text="下一段不应合并", order=5, source_page=1),
        ]

        merged = parser._merge_adjacent_paragraphs(blocks)

        self.assertEqual([block.text for block in merged], [
            "需求编号 ： SRS-USER-001",
            "需求描述：系统应支持邮箱注册。",
            "这是完整句子。",
            "下一段不应合并",
        ])


class _FakeLabel:
    """Fake Docling label object with a value field."""

    def __init__(self, value: str) -> None:
        """Store a label value compatible with Docling enums."""
        self.value = value


class _FakeDoclingItem:
    """Fake Docling item for parser unit tests."""

    def __init__(self, label: str, text: str, markdown: str) -> None:
        """Create a fake item with text and Markdown export behavior."""
        self.label = _FakeLabel(label)
        self.text = text
        self.markdown = markdown

    def export_to_markdown(self, *, doc: object | None = None) -> str:
        """Return the configured Markdown representation."""
        return self.markdown


if __name__ == "__main__":
    unittest.main()

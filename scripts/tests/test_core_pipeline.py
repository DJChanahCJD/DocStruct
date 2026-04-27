import asyncio
import unittest
from unittest.mock import patch

from core.chunker import split_ir_into_chunks
from core.extractor import extract_structure_with_meta
from core.ir import parse_result_to_ir
from core.parser import MarkdownNormalizer
from core.reducer import reduce_extraction_results
from schemas.models import (
    DocType,
    EntityItem,
    EntityType,
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

    def test_chunker_renders_evidence_markers_for_requirement_section(self) -> None:
        """Ensure SRS requirement content stays chunked with evidence markers."""
        markdown = """# 系统需求规格说明书

#### 2.1.1 用户注册

需求编号：SRS-USER-001

需求描述：系统应支持邮箱注册。

功能点：

- 发送验证码
- 创建账号
"""
        document_ir = parse_result_to_ir(MarkdownNormalizer().normalize(markdown), doc_type=DocType.SRS)

        chunks = split_ir_into_chunks(document_ir, max_chars=5000)
        requirement_chunk = next(chunk for chunk in chunks if chunk.section_path[-1] == "2.1.1 用户注册")

        self.assertEqual(requirement_chunk.section_path[-1], "2.1.1 用户注册")
        self.assertEqual([element.element_id for element in requirement_chunk.elements], [f"el-{index:04d}" for index in range(2, 7)])
        self.assertIn("[ELEMENT: el-0002]", requirement_chunk.markdown)
        self.assertIn("[ELEMENT: el-0006]", requirement_chunk.markdown)

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
                            "description": "系统应支持邮箱注册。",
                            "requirement_type": "functional",
                            "evidence_element_ids": ["el-0002", "missing"],
                        },
                        {
                            "id": "SRS-USER-001",
                            "name": "用户注册",
                            "acceptance_criteria": ["验证码 5 分钟内有效。"],
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
                        "description": "系统应支持邮箱注册。",
                        "requirement_type": "functional",
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

    def test_schema_normalizers_use_safe_defaults(self) -> None:
        """Ensure schema models normalize invalid enum and extra values."""
        entity = EntityItem(name="用户", entity_type="person", extra="invalid")
        requirement = RequirementItem(name="审计日志", requirement_type="security", extra=None)

        self.assertEqual(entity.entity_type, EntityType.OTHER)
        self.assertEqual(entity.extra, {})
        self.assertEqual(requirement.requirement_type, RequirementType.OTHER)
        self.assertEqual(requirement.extra, {})


if __name__ == "__main__":
    unittest.main()

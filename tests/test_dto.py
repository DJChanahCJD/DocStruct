import unittest
from datetime import datetime, timezone

from schemas.dto import DocumentListItemDTO
from main import DOCUMENT_LIST_QUERY, _document_list_item_from_row


class DocumentListItemDTOTest(unittest.TestCase):
    """验证列表 DTO 只承载轻量字段。"""

    def test_serialized_payload_excludes_detail_only_fields(self) -> None:
        """列表 DTO 序列化结果不应包含详情大字段。"""
        payload = {
            "id": 1,
            "title": "示例文档",
            "created_at": datetime.now(timezone.utc),
            "updated_at": None,
            "doc_type": "srs",
            "summary": "摘要",
            "extraction_meta": {"chunk_count": 1},
            "status": "completed",
            "error_message": None,
            "has_raw_text": True,
            "has_document_ir": True,
            "has_extracted_data": True,
            "raw_text": "不应出现在列表中",
            "document_ir": {"elements": []},
            "extracted_data": {"doc_type": "srs"},
            "stored_path": "db/uploads/example.md",
        }

        item = DocumentListItemDTO.model_validate(payload)
        dumped = item.model_dump(mode="json")

        self.assertNotIn("raw_text", dumped)
        self.assertNotIn("document_ir", dumped)
        self.assertNotIn("extracted_data", dumped)
        self.assertNotIn("stored_path", dumped)

    def test_list_query_uses_existence_flags_for_large_fields(self) -> None:
        """列表 SQL 只能读取大字段存在性，不应取出大字段内容。"""
        normalized = " ".join(DOCUMENT_LIST_QUERY.lower().split())

        self.assertIn("raw_text is not null as has_raw_text", normalized)
        self.assertIn("document_ir is not null as has_document_ir", normalized)
        self.assertIn("extracted_data is not null as has_extracted_data", normalized)
        self.assertNotIn(" raw_text,", normalized)
        self.assertNotIn(" document_ir,", normalized)
        self.assertNotIn(" extracted_data,", normalized)

    def test_document_list_item_from_raw_sql_row(self) -> None:
        """raw SQL 行应能正确转换出 alias 标记和 JSON 元信息。"""
        row = {
            "id": 1,
            "title": "示例文档",
            "created_at": datetime.now(timezone.utc),
            "updated_at": None,
            "doc_type": "srs",
            "summary": "摘要",
            "extraction_meta": '{"llm_model":"deepseek-v4-flash","chunk_count":1}',
            "status": "completed",
            "error_message": None,
            "has_raw_text": 1,
            "has_document_ir": 1,
            "has_extracted_data": 0,
        }

        item = _document_list_item_from_row(row)

        self.assertTrue(item.has_raw_text)
        self.assertTrue(item.has_document_ir)
        self.assertFalse(item.has_extracted_data)
        self.assertEqual(item.extraction_meta["llm_model"], "deepseek-v4-flash")


if __name__ == "__main__":
    unittest.main()

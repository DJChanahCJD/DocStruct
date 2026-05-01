import unittest

from core.metadata import apply_document_metadata, extract_document_metadata


class DocumentMetadataExtractionTest(unittest.TestCase):
    """验证文档级元数据的确定性提取和补齐。"""

    def test_extracts_version_from_markdown_table(self) -> None:
        """Markdown 文档信息表中的文档版本应被识别。"""
        metadata = extract_document_metadata(
            """
# 智能文档系统需求规格说明书

| 项目 | 内容 |
|------|------|
| 文档版本 | v1.0 |
| 编制日期 | 2026-04-25 |
"""
        )

        self.assertEqual(metadata["version"], "v1.0")

    def test_extracts_version_from_key_value_line(self) -> None:
        """普通键值行中的文档版本应被识别。"""
        metadata = extract_document_metadata("文档版本：1.2.3\n系统说明正文。")

        self.assertEqual(metadata["version"], "1.2.3")

    def test_does_not_extract_unlabeled_versions(self) -> None:
        """未带文档版本标签的技术版本号不应被误识别。"""
        metadata = extract_document_metadata(
            """
# 接口说明

API v1 使用 HTTPS。
TLS 1.3 为传输安全要求。
Token 有效期 2 小时。
"""
        )

        self.assertNotIn("version", metadata)

    def test_apply_metadata_does_not_override_existing_version(self) -> None:
        """已有非空版本时，元数据补齐不应覆盖抽取结果。"""
        data = {"version": "v2.0"}

        apply_document_metadata(data, {"version": "v1.0"})

        self.assertEqual(data["version"], "v2.0")

    def test_apply_metadata_fills_empty_version(self) -> None:
        """版本为空时，元数据补齐应写入最终结果。"""
        data = {"version": None}

        apply_document_metadata(data, {"version": "v1.0"})

        self.assertEqual(data["version"], "v1.0")


if __name__ == "__main__":
    unittest.main()

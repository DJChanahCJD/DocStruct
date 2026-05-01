import unittest

from core.parsers.docling_parser import DoclingParser


class FakeDoclingItem:
    """构造最小 Docling item 替身。"""

    label = "section_header"
    text = "1. 系统概述"

    def export_to_markdown(self, doc=None) -> str:
        """模拟 Docling Markdown 导出。"""
        return self.text


class FakeDoclingDocument:
    """构造最小 Docling document 替身。"""

    def __init__(self, yielded_item) -> None:
        """保存 iterate_items 将返回的对象。"""
        self.yielded_item = yielded_item

    def iterate_items(self):
        """模拟 DoclingDocument.iterate_items。"""
        yield self.yielded_item


class DoclingParserIterateItemsTest(unittest.TestCase):
    """验证 Docling iterate_items 兼容性。"""

    def test_extract_elements_unwraps_docling_item_level_tuple(self) -> None:
        """Docling 2.91 返回 (item, level) 时应正常提取文本元素。"""
        parser = DoclingParser()
        item = FakeDoclingItem()
        document = FakeDoclingDocument((item, 2))

        elements = parser._extract_elements(document)
        blocks = parser._build_blocks(elements)

        self.assertEqual(len(elements), 1)
        self.assertEqual(elements[0].text, "1. 系统概述")
        self.assertEqual(blocks[0].type, "title")
        self.assertEqual(blocks[0].level, 2)

    def test_extract_elements_accepts_direct_item(self) -> None:
        """旧形态直接返回 item 时仍应正常提取文本元素。"""
        parser = DoclingParser()
        item = FakeDoclingItem()
        document = FakeDoclingDocument(item)

        elements = parser._extract_elements(document)

        self.assertEqual(len(elements), 1)
        self.assertEqual(elements[0].text, "1. 系统概述")


if __name__ == "__main__":
    unittest.main()

"""
Docling 解析器实现。

Docling 负责：
- 文档解析、版面识别
- 表格识别、图片定位
- OCR、页面坐标提取

DocStruct 负责：
- 软件工程语义抽取
- 字段归一化、Schema 校验
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from docling.document_converter import DocumentConverter, PdfFormatOption
from docling.datamodel.pipeline_options import PdfPipelineOptions

if TYPE_CHECKING:
    from core.parser import BaseParser, DocBlock, ParseResult


@dataclass
class ParsedElement:
    """
    中间表示：Docling 元素转换为内部结构。

    用于承载 Docling 解析后的元素信息，包括页面坐标。
    """

    id: str
    type: str  # text / heading / table / image / code / list
    text: str | None = None
    markdown: str | None = None
    page: int | None = None
    section: str | None = None
    bbox: list[float] | None = None
    extra: dict[str, Any] = field(default_factory=dict)


class DoclingParser:
    """
    基于 Docling 的文档解析器。

    特性：
    - 高质量 PDF/DOCX 解析
    - 表格结构识别
    - 图片定位与占位
    - 精确的页面坐标 (bbox)
    """

    def __init__(
        self,
        enable_ocr: bool = False,
        enable_table_structure: bool = True,
    ):
        """
        初始化 Docling 解析器。

        Args:
            enable_ocr: 是否启用 OCR（扫描件识别）
            enable_table_structure: 是否启用表格结构识别
        """
        self.enable_ocr = enable_ocr
        self.enable_table_structure = enable_table_structure

    def parse_to_result(self, file_path: str) -> "ParseResult":
        """
        解析文档并返回结构化结果。

        Args:
            file_path: 文档路径

        Returns:
            ParseResult: 包含 Markdown、DocBlock 列表和元数据
        """
        from core.parser import (
            DocBlock,
            MarkdownRenderer,
            ParseResult,
        )

        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        try:
            # 1. 配置 Docling pipeline
            pipeline_options = PdfPipelineOptions()
            pipeline_options.do_ocr = self.enable_ocr
            pipeline_options.do_table_structure = self.enable_table_structure

            # 2. 创建转换器
            converter = DocumentConverter(
                format_options={
                    "pdf": PdfFormatOption(pipeline_options=pipeline_options),
                }
            )

            # 3. 解析文档
            result = converter.convert(file_path)

            # 4. 提取元素信息
            elements = self._extract_elements(result.document)

            # 5. 构建 DocBlock 列表
            blocks = self._build_blocks(elements)

            # 6. 渲染 Markdown
            renderer = MarkdownRenderer()
            markdown = renderer.render(blocks)

            # 7. 提取标题
            title = self._extract_title(blocks)

            return ParseResult(
                markdown=markdown,
                blocks=blocks,
                title=title,
                metadata={
                    "parser_name": self.__class__.__name__,
                    "source_type": self._get_source_type(file_path),
                    "element_count": len(elements),
                    "enable_ocr": self.enable_ocr,
                    "enable_table_structure": self.enable_table_structure,
                },
            )
        except Exception as exc:
            raise RuntimeError(f"Failed to parse document with Docling: {exc}") from exc

    def _extract_elements(self, document) -> list[ParsedElement]:
        """
        从 DoclingDocument 提取元素列表。

        Args:
            document: Docling 的 DoclingDocument 对象

        Returns:
            ParsedElement 列表
        """
        elements: list[ParsedElement] = []

        # 使用 iterate_items 遍历文档元素
        if hasattr(document, "iterate_items"):
            for idx, (item, level) in enumerate(document.iterate_items()):
                element = self._convert_element(item, idx, document)
                if element:
                    elements.append(element)

        return elements

    def _convert_element(self, item, idx: int, document) -> ParsedElement | None:
        """
        将 Docling 元素转换为 ParsedElement。

        Args:
            item: Docling 的元素对象
            idx: 元素索引
            document: Docling 的 DoclingDocument 对象

        Returns:
            ParsedElement 或 None
        """
        # 获取元素类型标签
        label = getattr(item, "label", None)
        if label:
            item_type = str(label).lower()
        else:
            item_type = "text"

        # 提取文本内容
        text = ""
        if hasattr(item, "text") and item.text:
            text = str(item.text)
        elif hasattr(item, "export_to_markdown"):
            try:
                text = item.export_to_markdown(doc=document)
            except Exception:
                pass

        if not text and item_type not in ("picture", "image", "figure"):
            return None

        # 提取页面坐标
        page, bbox = self._extract_position(item)

        # 构建元素
        return ParsedElement(
            id=f"elem_{idx}",
            type=item_type,
            text=text,
            page=page,
            bbox=bbox,
            extra=self._extract_extra(item, item_type, document),
        )

    def _convert_text_element(self, text_item, idx: int) -> ParsedElement | None:
        """
        转换文本元素（备用方法）。

        Args:
            text_item: 文本元素
            idx: 索引

        Returns:
            ParsedElement 或 None
        """
        text = getattr(text_item, "text", None) or str(text_item)
        if not text or not text.strip():
            return None

        # 尝试提取位置信息
        page, bbox = self._extract_position(text_item)

        # 判断是否为标题
        item_type = "text"
        if hasattr(text_item, "label"):
            item_type = str(text_item.label).lower()

        return ParsedElement(
            id=f"elem_{idx}",
            type=item_type,
            text=text.strip(),
            page=page,
            bbox=bbox,
        )

    def _extract_text(self, item) -> str:
        """提取元素的文本内容。"""
        # 尝试多种属性获取文本
        for attr in ["text", "content", "value", "export_to_markdown"]:
            if hasattr(item, attr):
                val = getattr(item, attr)
                if callable(val) and attr == "export_to_markdown":
                    try:
                        return val()
                    except Exception:
                        continue
                if isinstance(val, str):
                    return val
        return ""

    def _extract_position(self, item) -> tuple[int | None, list[float] | None]:
        """
        提取元素的位置信息。

        Returns:
            (page, bbox) 元组
        """
        page = None
        bbox = None

        # Docling 使用 prov 属性存储位置信息
        prov = getattr(item, "prov", None)
        if prov and isinstance(prov, list) and prov:
            prov_item = prov[0]

            # 提取页码
            page = getattr(prov_item, "page_no", None)

            # 提取 bbox
            bbox_obj = getattr(prov_item, "bbox", None)
            if bbox_obj:
                # Docling 的 BoundingBox 使用 l, t, r, b (left, top, right, bottom)
                l = getattr(bbox_obj, "l", 0) or 0
                t = getattr(bbox_obj, "t", 0) or 0
                r = getattr(bbox_obj, "r", 0) or 0
                b = getattr(bbox_obj, "b", 0) or 0
                bbox = [float(l), float(b), float(r), float(t)]  # 转换为 [x0, y0, x1, y1] 格式

        return page, bbox

    def _extract_extra(self, item, item_type: str, document) -> dict[str, Any]:
        """提取额外属性。"""
        extra: dict[str, Any] = {}

        # 标题级别
        if item_type == "heading":
            for attr in ["level", "heading_level"]:
                if hasattr(item, attr):
                    extra["level"] = getattr(item, attr)
                    break

        # 表格数据
        if item_type == "table":
            if hasattr(item, "export_to_dataframe"):
                try:
                    df = item.export_to_dataframe(doc=document)
                    extra["rows"] = [df.columns.tolist()] + df.values.tolist()
                except Exception:
                    pass
            elif hasattr(item, "data"):
                extra["rows"] = item.data

        # 图片信息
        if item_type in ("image", "figure"):
            for attr in ["caption", "alt_text", "label"]:
                if hasattr(item, attr):
                    extra[attr] = getattr(item, attr)

        return extra

    def _build_blocks(self, elements: list[ParsedElement]) -> list["DocBlock"]:
        """
        将 ParsedElement 列表转换为 DocBlock 列表。

        Args:
            elements: ParsedElement 列表

        Returns:
            DocBlock 列表
        """
        from core.parser import DocBlock

        blocks: list[DocBlock] = []

        for idx, elem in enumerate(elements):
            block = self._element_to_block(elem, idx)
            if block:
                blocks.append(block)

        return blocks

    def _element_to_block(self, elem: ParsedElement, idx: int) -> "DocBlock | None":
        """
        将单个 ParsedElement 转换为 DocBlock。

        Args:
            elem: ParsedElement
            idx: 顺序索引

        Returns:
            DocBlock 或 None
        """
        from core.parser import DocBlock

        if not elem.text:
            return None

        block_type = self._map_element_type(elem.type)
        attrs: dict[str, Any] = dict(elem.extra)

        # 添加 bbox 到 attrs
        if elem.bbox:
            attrs["bbox"] = elem.bbox

        # 处理标题
        level = None
        if block_type == "title":
            level = elem.extra.get("level", 1)

        # 处理表格
        if block_type == "table" and "rows" in attrs:
            attrs["prefer_html"] = False

        return DocBlock(
            type=block_type,
            text=elem.text,
            level=level,
            order=idx,
            source_page=elem.page,
            attrs=attrs,
        )

    def _map_element_type(self, elem_type: str) -> str:
        """映射元素类型到 DocBlock 类型。"""
        type_map = {
            "section_header": "title",
            "title": "title",
            "heading": "title",
            "paragraph": "paragraph",
            "text": "paragraph",
            "table": "table",
            "picture": "image",
            "image": "image",
            "figure": "image",
            "code": "code",
            "code_block": "code",
            "list": "list",
            "list_item": "list",
        }
        return type_map.get(elem_type.lower(), "paragraph")

    def _extract_title(self, blocks: list["DocBlock"]) -> str | None:
        """从 blocks 中提取文档标题。"""
        for block in blocks:
            if block.type == "title" and block.level == 1:
                return block.text.strip()
        if blocks and blocks[0].type == "paragraph":
            first_text = blocks[0].text.strip()
            if first_text and len(first_text) <= 120 and "\n" not in first_text:
                return first_text
        return None

    def _get_source_type(self, file_path: str) -> str:
        """获取来源类型。"""
        ext = os.path.splitext(file_path)[1].lower()
        type_map = {
            ".pdf": "pdf",
            ".docx": "docx",
            ".doc": "docx",
            ".pptx": "pptx",
            ".html": "html",
            ".md": "markdown",
            ".txt": "plain_text",
        }
        return type_map.get(ext, "unknown")

from __future__ import annotations

import os
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from html import escape
from typing import Any

import fitz  # PyMuPDF
import pymupdf4llm
from docx import Document
from docx.document import Document as DocxDocument
from docx.oxml.table import CT_Tbl
from docx.oxml.text.paragraph import CT_P
from docx.table import Table
from docx.text.paragraph import Paragraph


HEADING_PATTERN = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
NUMBERED_HEADING_PATTERN = re.compile(r"^\s*(\d+(?:\.\d+)*)(?:\.)?\s+(.+?)\s*$")
LIST_ITEM_PATTERN = re.compile(r"^\s*((?:[-+*])|(?:\d+\.))\s+(.+?)\s*$")
CODE_FENCE_PATTERN = re.compile(r"^\s*(```+|~~~+)(.*)$")
TABLE_ROW_PATTERN = re.compile(r"^\s*\|.*\|\s*$")
TABLE_SEPARATOR_PATTERN = re.compile(r"^\s*\|?\s*:?-{3,}:?\s*(?:\|\s*:?-{3,}:?\s*)+\|?\s*$")
THEMATIC_BREAK_PATTERN = re.compile(r"^\s*(?:-{3,}|\*{3,}|_{3,})\s*$")


@dataclass(slots=True)
class DocBlock:
    type: str
    text: str = ""
    level: int | None = None
    order: int = 0
    source_page: int | None = None
    attrs: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ParseResult:
    markdown: str
    blocks: list[DocBlock]
    title: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class MarkdownRenderer:
    """Render parser blocks into stable Markdown."""

    def render(self, blocks: list[DocBlock]) -> str:
        rendered_blocks: list[str] = []
        for block in sorted(blocks, key=lambda item: item.order):
            rendered = self._render_block(block)
            if rendered:
                rendered_blocks.append(rendered.strip("\n"))
        return "\n\n".join(part for part in rendered_blocks if part).strip()

    def _render_block(self, block: DocBlock) -> str:
        block_type = block.type
        if block_type == "title":
            level = min(max(block.level or 1, 1), 6)
            return f'{"#" * level} {block.text.strip()}'
        if block_type == "paragraph":
            return block.text.strip()
        if block_type == "quote":
            lines = [line.rstrip() for line in block.text.splitlines() if line.strip()]
            return "\n".join(f"> {line}" for line in lines)
        if block_type == "section_break":
            return "---"
        if block_type == "code":
            language = str(block.attrs.get("language") or "").strip()
            fence = block.attrs.get("fence") or "```"
            return f"{fence}{language}\n{block.text.rstrip()}\n{fence}"
        if block_type == "list":
            return self._render_list_block(block)
        if block_type == "table":
            return self._render_table_block(block)
        if block_type == "image":
            alt = str(block.attrs.get("alt") or "").strip()
            src = str(block.attrs.get("src") or "").strip()
            return f"![{alt}]({src})" if src else block.text.strip()
        return block.text.strip()

    def _render_list_block(self, block: DocBlock) -> str:
        items = block.attrs.get("items")
        if not isinstance(items, list) or not items:
            return block.text.strip()

        ordered = bool(block.attrs.get("ordered"))
        rendered_lines: list[str] = []
        for index, raw_item in enumerate(items, start=1):
            item = str(raw_item).strip()
            if not item:
                continue
            marker = f"{index}." if ordered else "-"
            item_lines = item.splitlines()
            rendered_lines.append(f"{marker} {item_lines[0].strip()}")
            for continuation in item_lines[1:]:
                rendered_lines.append(f"  {continuation.rstrip()}")
        return "\n".join(rendered_lines)

    def _render_table_block(self, block: DocBlock) -> str:
        rows = block.attrs.get("rows")
        if not isinstance(rows, list) or not rows:
            return block.text.strip()

        normalized_rows = [self._normalize_row(row) for row in rows]
        if not normalized_rows:
            return block.text.strip()

        if block.attrs.get("prefer_html") or self._table_requires_html(normalized_rows):
            return self._render_table_html(normalized_rows)
        return self._render_table_markdown(normalized_rows)

    @staticmethod
    def _normalize_row(row: Any) -> list[str]:
        if not isinstance(row, list):
            return []
        return [str(cell or "").strip() for cell in row]

    @staticmethod
    def _table_requires_html(rows: list[list[str]]) -> bool:
        if not rows:
            return False
        col_count = len(rows[0])
        if col_count == 0:
            return False
        for row in rows:
            if len(row) != col_count:
                return True
            for cell in row:
                if "\n" in cell or "|" in cell:
                    return True
        return False

    @staticmethod
    def _render_table_markdown(rows: list[list[str]]) -> str:
        header = rows[0]
        body = rows[1:] or [[""] * len(header)]

        def render_row(row: list[str]) -> str:
            escaped_cells = [cell.replace("|", "\\|").replace("\n", "<br>") for cell in row]
            return f"| {' | '.join(escaped_cells)} |"

        output = [render_row(header), f"| {' | '.join(['---'] * len(header))} |"]
        output.extend(render_row(row) for row in body)
        return "\n".join(output)

    @staticmethod
    def _render_table_html(rows: list[list[str]]) -> str:
        output = ["<table>"]
        for row_index, row in enumerate(rows):
            tag = "th" if row_index == 0 else "td"
            output.append("  <tr>")
            for cell in row:
                cell_html = "<br>".join(escape(line) for line in cell.splitlines()) or "&nbsp;"
                output.append(f"    <{tag}>{cell_html}</{tag}>")
            output.append("  </tr>")
        output.append("</table>")
        return "\n".join(output)


class MarkdownNormalizer:
    """Normalize Markdown-like text into blocks, then render it consistently."""

    def __init__(self) -> None:
        self.renderer = MarkdownRenderer()

    def normalize(self, markdown_text: str, *, metadata: dict[str, Any] | None = None) -> ParseResult:
        blocks = self._parse_blocks(markdown_text)
        title = self._extract_title(blocks)
        rendered_markdown = self.renderer.render(blocks)
        return ParseResult(
            markdown=rendered_markdown,
            blocks=blocks,
            title=title,
            metadata=metadata or {},
        )

    def _parse_blocks(self, markdown_text: str) -> list[DocBlock]:
        text = (markdown_text or "").replace("\r\n", "\n").replace("\r", "\n").strip()
        if not text:
            return []

        lines = text.split("\n")
        blocks: list[DocBlock] = []
        index = 0
        cursor = 0

        while cursor < len(lines):
            line = lines[cursor]
            stripped = line.strip()
            if not stripped:
                cursor += 1
                continue

            heading = self._parse_heading(lines, cursor)
            if heading is not None:
                level, title = heading
                blocks.append(DocBlock(type="title", text=title, level=level, order=index))
                index += 1
                cursor += 1
                continue

            if THEMATIC_BREAK_PATTERN.match(stripped):
                blocks.append(DocBlock(type="section_break", text="---", order=index))
                index += 1
                cursor += 1
                continue

            if CODE_FENCE_PATTERN.match(line):
                block, cursor = self._collect_code_block(lines, cursor, index)
                blocks.append(block)
                index += 1
                continue

            if self._looks_like_table(lines, cursor):
                block, cursor = self._collect_table_block(lines, cursor, index)
                blocks.append(block)
                index += 1
                continue

            list_match = LIST_ITEM_PATTERN.match(stripped)
            if list_match:
                block, cursor = self._collect_list_block(lines, cursor, index)
                blocks.append(block)
                index += 1
                continue

            if stripped.startswith(">"):
                block, cursor = self._collect_quote_block(lines, cursor, index)
                blocks.append(block)
                index += 1
                continue

            block, cursor = self._collect_paragraph_block(lines, cursor, index)
            blocks.append(block)
            index += 1

        return blocks

    @staticmethod
    def _extract_title(blocks: list[DocBlock]) -> str | None:
        for block in blocks:
            if block.type == "title" and block.level == 1:
                return block.text.strip()
        if blocks and blocks[0].type == "paragraph":
            first_text = blocks[0].text.strip()
            if first_text and len(first_text) <= 120 and "\n" not in first_text:
                return first_text
        return None

    @staticmethod
    def _parse_markdown_heading(line: str) -> tuple[int, str] | None:
        markdown_match = HEADING_PATTERN.match(line)
        if markdown_match:
            return len(markdown_match.group(1)), markdown_match.group(2).strip()
        return None

    def _parse_numbered_heading(self, lines: list[str], cursor: int) -> tuple[int, str] | None:
        line = lines[cursor].strip()
        numbered_match = NUMBERED_HEADING_PATTERN.match(line)
        if not numbered_match:
            return None

        number_path = numbered_match.group(1)
        title = numbered_match.group(2).strip()
        if not title or len(title) > 120:
            return None

        prev_non_empty = ""
        for previous_index in range(cursor - 1, -1, -1):
            candidate = lines[previous_index].strip()
            if candidate:
                prev_non_empty = candidate
                break

        if prev_non_empty.endswith((":", "：")):
            return None

        next_non_empty = ""
        for next_index in range(cursor + 1, len(lines)):
            candidate = lines[next_index].strip()
            if candidate:
                next_non_empty = candidate
                break

        if "." not in number_path:
            next_numbered = NUMBERED_HEADING_PATTERN.match(next_non_empty)
            if next_numbered:
                try:
                    if int(next_numbered.group(1).split(".")[0]) == int(number_path) + 1:
                        return None
                except ValueError:
                    pass

        if title.endswith((".", ":", ";", "!", "?", "。", "：", "；", "！", "？")):
            return None

        return number_path.count(".") + 1, f"{number_path} {title}"

    def _parse_heading(self, lines: list[str], cursor: int) -> tuple[int, str] | None:
        markdown_heading = self._parse_markdown_heading(lines[cursor].strip())
        if markdown_heading is not None:
            return markdown_heading
        return self._parse_numbered_heading(lines, cursor)

    @staticmethod
    def _looks_like_table(lines: list[str], cursor: int) -> bool:
        if cursor >= len(lines):
            return False
        current = lines[cursor].strip()
        if not TABLE_ROW_PATTERN.match(current):
            return False
        next_line = lines[cursor + 1].strip() if cursor + 1 < len(lines) else ""
        return bool(TABLE_SEPARATOR_PATTERN.match(next_line))

    @staticmethod
    def _collect_code_block(lines: list[str], cursor: int, index: int) -> tuple[DocBlock, int]:
        fence_match = CODE_FENCE_PATTERN.match(lines[cursor])
        fence = fence_match.group(1) if fence_match else "```"
        language = (fence_match.group(2) or "").strip() if fence_match else ""
        collected: list[str] = []
        cursor += 1
        while cursor < len(lines):
            current = lines[cursor]
            if current.strip().startswith(fence):
                cursor += 1
                break
            collected.append(current.rstrip("\n"))
            cursor += 1
        return (
            DocBlock(
                type="code",
                text="\n".join(collected).rstrip(),
                order=index,
                attrs={"language": language, "fence": fence},
            ),
            cursor,
        )

    @staticmethod
    def _split_table_row(line: str) -> list[str]:
        stripped = line.strip().strip("|")
        return [cell.strip() for cell in stripped.split("|")]

    def _collect_table_block(self, lines: list[str], cursor: int, index: int) -> tuple[DocBlock, int]:
        rows: list[list[str]] = []
        while cursor < len(lines):
            current = lines[cursor].strip()
            if not TABLE_ROW_PATTERN.match(current):
                break
            if TABLE_SEPARATOR_PATTERN.match(current):
                cursor += 1
                continue
            rows.append(self._split_table_row(current))
            cursor += 1
        return (
            DocBlock(
                type="table",
                text="",
                order=index,
                attrs={"rows": rows, "prefer_html": False},
            ),
            cursor,
        )

    @staticmethod
    def _collect_list_block(lines: list[str], cursor: int, index: int) -> tuple[DocBlock, int]:
        items: list[str] = []
        ordered = False
        current_lines: list[str] = []

        while cursor < len(lines):
            raw_line = lines[cursor]
            stripped = raw_line.strip()
            if not stripped:
                if current_lines:
                    current_lines.append("")
                cursor += 1
                continue

            match = LIST_ITEM_PATTERN.match(stripped)
            if match:
                if current_lines:
                    items.append("\n".join(line for line in current_lines if line is not None).strip())
                current_lines = [match.group(2).strip()]
                ordered = ordered or match.group(1).endswith(".")
                cursor += 1
                continue

            if raw_line.startswith(("  ", "\t")) and current_lines:
                current_lines.append(stripped)
                cursor += 1
                continue

            break

        if current_lines:
            items.append("\n".join(line for line in current_lines if line is not None).strip())

        text = "\n".join(items)
        return (
            DocBlock(
                type="list",
                text=text,
                order=index,
                attrs={"items": [item for item in items if item], "ordered": ordered},
            ),
            cursor,
        )

    @staticmethod
    def _collect_quote_block(lines: list[str], cursor: int, index: int) -> tuple[DocBlock, int]:
        quote_lines: list[str] = []
        while cursor < len(lines):
            stripped = lines[cursor].strip()
            if not stripped.startswith(">"):
                break
            quote_lines.append(stripped[1:].strip())
            cursor += 1
        return DocBlock(type="quote", text="\n".join(quote_lines), order=index), cursor

    def _collect_paragraph_block(self, lines: list[str], cursor: int, index: int) -> tuple[DocBlock, int]:
        paragraph_lines: list[str] = []
        while cursor < len(lines):
            current = lines[cursor]
            stripped = current.strip()
            if not stripped:
                break
            if (
                self._parse_heading(lines, cursor) is not None
                or THEMATIC_BREAK_PATTERN.match(stripped)
                or CODE_FENCE_PATTERN.match(current)
                or stripped.startswith(">")
                or LIST_ITEM_PATTERN.match(stripped)
                or self._looks_like_table(lines, cursor)
            ):
                break
            paragraph_lines.append(stripped)
            cursor += 1
        if cursor < len(lines) and not lines[cursor].strip():
            cursor += 1
        return DocBlock(type="paragraph", text="\n".join(paragraph_lines), order=index), cursor


class BaseParser(ABC):
    """文档解析器抽象基类。"""

    @abstractmethod
    def parse_to_result(self, file_path: str) -> ParseResult:
        """解析文档并返回结构化解析结果。"""

    def parse(self, file_path: str) -> str:
        """兼容旧接口，仅返回最终 Markdown。"""
        return self.parse_to_result(file_path).markdown


class PdfParser(BaseParser):
    """
    PDF 解析策略：使用 pymupdf4llm，并在返回前做统一 Markdown 规范化。
    """

    OCR_TEXT_THRESHOLD = 120
    OCR_AVG_PAGE_THRESHOLD = 40
    OCR_EMPTY_PAGE_RATIO = 0.6
    OCR_SAMPLE_SIZE = 6

    def __init__(self) -> None:
        self.normalizer = MarkdownNormalizer()

    def parse_to_result(self, file_path: str, force_ocr: bool = False) -> ParseResult:
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        try:
            use_ocr = force_ocr if force_ocr else self._needs_ocr(file_path)
            markdown = pymupdf4llm.to_markdown(file_path, use_ocr=use_ocr)
            return self.normalizer.normalize(
                markdown,
                metadata={
                    "parser_name": self.__class__.__name__,
                    "use_ocr": use_ocr,
                    "source_type": "pdf",
                },
            )
        except Exception as exc:
            raise RuntimeError(f"Failed to parse PDF: {exc}") from exc

    def _needs_ocr(self, file_path: str) -> bool:
        try:
            doc = fitz.open(file_path)
            page_count = len(doc)
            if page_count == 0:
                return True

            sample_indices = self._sample_page_indices(page_count)
            total_chars = 0
            empty_pages = 0
            for page_index in sample_indices:
                text = doc.load_page(page_index).get_text().strip()
                total_chars += len(text)
                if not text:
                    empty_pages += 1
            doc.close()

            avg_chars = total_chars / max(len(sample_indices), 1)
            empty_ratio = empty_pages / max(len(sample_indices), 1)
            return (
                total_chars < self.OCR_TEXT_THRESHOLD
                or avg_chars < self.OCR_AVG_PAGE_THRESHOLD
                or empty_ratio >= self.OCR_EMPTY_PAGE_RATIO
            )
        except Exception:
            return True

    def _sample_page_indices(self, page_count: int) -> list[int]:
        if page_count <= self.OCR_SAMPLE_SIZE:
            return list(range(page_count))
        anchors = {0, page_count - 1}
        for i in range(self.OCR_SAMPLE_SIZE - 2):
            index = round((i + 1) * (page_count - 1) / max(self.OCR_SAMPLE_SIZE - 1, 1))
            anchors.add(index)
        return sorted(anchors)


class DocxParser(BaseParser):
    """DOCX 解析策略：先抽取 block，再统一渲染 Markdown。"""

    def __init__(self) -> None:
        self.renderer = MarkdownRenderer()

    def parse_to_result(self, file_path: str) -> ParseResult:
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        try:
            document = Document(file_path)
            blocks = self._parse_document_blocks(document)
            markdown = self.renderer.render(blocks)
            title = next(
                (block.text.strip() for block in blocks if block.type == "title" and block.level == 1),
                None,
            )
            return ParseResult(
                markdown=markdown,
                blocks=blocks,
                title=title,
                metadata={
                    "parser_name": self.__class__.__name__,
                    "source_type": "docx",
                    "block_count": len(blocks),
                },
            )
        except Exception as exc:
            raise RuntimeError(f"Failed to parse DOCX: {exc}") from exc

    def _parse_document_blocks(self, document: DocxDocument) -> list[DocBlock]:
        blocks: list[DocBlock] = []
        pending_list: dict[str, Any] | None = None

        def flush_pending_list() -> None:
            nonlocal pending_list
            if pending_list and pending_list["items"]:
                blocks.append(
                    DocBlock(
                        type="list",
                        text="\n".join(pending_list["items"]),
                        order=len(blocks),
                        attrs={
                            "items": list(pending_list["items"]),
                            "ordered": pending_list["ordered"],
                        },
                    )
                )
            pending_list = None

        for element in document.element.body.iterchildren():
            if isinstance(element, CT_P):
                paragraph = Paragraph(element, document)
                paragraph_block = self._parse_paragraph(paragraph)
                if paragraph_block is None:
                    continue

                if paragraph_block.type == "list":
                    ordered = bool(paragraph_block.attrs.get("ordered"))
                    items = paragraph_block.attrs.get("items") or []
                    if pending_list and pending_list["ordered"] == ordered:
                        pending_list["items"].extend(items)
                    else:
                        flush_pending_list()
                        pending_list = {"ordered": ordered, "items": list(items)}
                    continue

                flush_pending_list()
                paragraph_block.order = len(blocks)
                blocks.append(paragraph_block)
                continue

            if isinstance(element, CT_Tbl):
                flush_pending_list()
                table = Table(element, document)
                table_block = self._parse_table(table, len(blocks))
                blocks.append(table_block)

        flush_pending_list()
        return blocks

    def _parse_paragraph(self, paragraph: Paragraph) -> DocBlock | None:
        text = paragraph.text.strip()
        if not text:
            return None

        style_name = (paragraph.style.name or "").strip().lower() if paragraph.style is not None else ""
        if style_name.startswith("heading"):
            level = self._extract_heading_level(style_name)
            return DocBlock(type="title", text=text, level=level, attrs={"style_name": style_name})

        list_info = self._extract_list_info(paragraph, style_name, text)
        if list_info is not None:
            ordered, item_text = list_info
            return DocBlock(type="list", text=item_text, attrs={"ordered": ordered, "items": [item_text]})

        if self._looks_like_code_block(paragraph, style_name):
            return DocBlock(
                type="code",
                text=text,
                attrs={"language": "", "fence": "```", "style_name": style_name},
            )

        if style_name == "quote":
            return DocBlock(type="quote", text=text, attrs={"style_name": style_name})

        if THEMATIC_BREAK_PATTERN.match(text):
            return DocBlock(type="section_break", text="---", attrs={"style_name": style_name})

        return DocBlock(type="paragraph", text=text, attrs={"style_name": style_name})

    @staticmethod
    def _extract_heading_level(style_name: str) -> int:
        digits = re.findall(r"(\d+)", style_name)
        if not digits:
            return 1
        return min(max(int(digits[0]), 1), 6)

    @staticmethod
    def _extract_list_info(paragraph: Paragraph, style_name: str, text: str) -> tuple[bool, str] | None:
        num_pr = paragraph._p.pPr.numPr if paragraph._p.pPr is not None else None
        if num_pr is not None:
            ordered = "bullet" not in style_name
            return ordered, text

        lowered = style_name
        if "list bullet" in lowered:
            return False, text
        if "list number" in lowered or "list paragraph" in lowered:
            return True, text

        marker_match = LIST_ITEM_PATTERN.match(text)
        if marker_match:
            ordered = marker_match.group(1).endswith(".")
            return ordered, marker_match.group(2).strip()
        return None

    @staticmethod
    def _looks_like_code_block(paragraph: Paragraph, style_name: str) -> bool:
        if "code" in style_name:
            return True
        runs = [run.text for run in paragraph.runs if run.text.strip()]
        if not runs:
            return False
        return all(run.strip().startswith(("def ", "class ", "{", "SELECT ", "curl ")) for run in runs[:1])

    @staticmethod
    def _parse_table(table: Table, order: int) -> DocBlock:
        rows: list[list[str]] = []
        prefer_html = False
        for row in table.rows:
            cells: list[str] = []
            for cell in row.cells:
                cell_text = "\n".join(
                    paragraph.text.strip() for paragraph in cell.paragraphs if paragraph.text.strip()
                ).strip()
                if "\n" in cell_text or "|" in cell_text:
                    prefer_html = True
                cells.append(cell_text)
            rows.append(cells)
        return DocBlock(
            type="table",
            text="",
            order=order,
            attrs={"rows": rows, "prefer_html": prefer_html},
        )


class PlainTextParser(BaseParser):
    """纯文本/Markdown 解析策略。"""

    def __init__(self) -> None:
        self.normalizer = MarkdownNormalizer()

    def parse_to_result(self, file_path: str) -> ParseResult:
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        try:
            with open(file_path, "r", encoding="utf-8") as handle:
                content = handle.read()
        except UnicodeDecodeError:
            try:
                with open(file_path, "r", encoding="gbk") as handle:
                    content = handle.read()
            except Exception as exc:
                raise RuntimeError(f"Failed to read text file (encoding issue?): {exc}") from exc
        except Exception as exc:
            raise RuntimeError(f"Failed to parse text file: {exc}") from exc

        return self.normalizer.normalize(
            content,
            metadata={
                "parser_name": self.__class__.__name__,
                "source_type": "plain_text",
            },
        )


class ParserFactory:
    """解析器工厂。"""

    @staticmethod
    def get_parser(file_path: str) -> BaseParser:
        ext = os.path.splitext(file_path)[1].lower()
        if ext == ".pdf":
            return PdfParser()
        if ext == ".docx":
            return DocxParser()
        if ext in [".md", ".markdown", ".txt"]:
            return PlainTextParser()
        raise ValueError(f"Unsupported file extension: {ext}")


def parse_pdf_to_markdown(file_path: str) -> str:
    return ParserFactory.get_parser(file_path).parse(file_path)

from __future__ import annotations

import re
from typing import Any

from core.parser import DocBlock, MarkdownNormalizer, MarkdownRenderer, ParseResult
from schemas.models import DocType, DocumentElement, DocumentIR, DocumentOutline


BLOCK_TYPE_MAP = {
    "title": "heading",
    "paragraph": "paragraph",
    "quote": "paragraph",
    "section_break": "separator",
    "code": "code",
    "list": "paragraph",
    "table": "table",
    "image": "image",
}


def parse_result_to_ir(
    parse_result: ParseResult,
    *,
    doc_type: str | DocType | None = None,
    element_prefix: str = "el",
) -> DocumentIR:
    renderer = MarkdownRenderer()
    elements: list[DocumentElement] = []
    heading_stack: list[str] = []
    sections: list[str] = []
    seen_sections: set[str] = set()
    title = parse_result.title

    ordered_blocks = sorted(parse_result.blocks, key=lambda block: block.order)
    for block in ordered_blocks:
        if block.type == "title":
            level = max(1, min(block.level or 1, 6))
            heading_text = block.text.strip()
            heading_stack = heading_stack[: level - 1]
            if heading_text:
                heading_stack.append(heading_text)
                section_label = " > ".join(heading_stack)
                if section_label not in seen_sections:
                    sections.append(section_label)
                    seen_sections.add(section_label)
                if title is None and level == 1:
                    title = heading_text

        markdown = renderer.render([block])
        text = _block_plain_text(block, markdown)
        if not text and not markdown:
            continue

        metadata = _block_metadata(block)
        bbox = _normalize_bbox(block.attrs.get("bbox"))
        element = DocumentElement(
            element_id=f"{element_prefix}-{len(elements) + 1:04d}",
            element_type=BLOCK_TYPE_MAP.get(block.type, "paragraph"),
            text=text or None,
            markdown=markdown or text or None,
            section_path=list(heading_stack),
            page=block.source_page,
            bbox=bbox,
            order=len(elements),
            metadata=metadata,
        )
        elements.append(element)

    normalized_doc_type = _normalize_doc_type_value(doc_type)
    outline = DocumentOutline(
        title=title,
        doc_type=normalized_doc_type,
        sections=sections,
        main_topics=_extract_main_topics(sections),
    )
    return DocumentIR(
        title=title,
        doc_type=normalized_doc_type,
        elements=elements,
        outline=outline,
        metadata=dict(parse_result.metadata),
    )


def build_basic_ir_from_markdown(
    markdown_content: str,
    *,
    doc_type: str | DocType | None = None,
) -> DocumentIR:
    normalizer = MarkdownNormalizer()
    parse_result = normalizer.normalize(
        markdown_content,
        metadata={
            "parser_name": "MarkdownNormalizer",
            "source_type": "markdown",
            "ir_source": "parsed_content",
        },
    )
    return parse_result_to_ir(parse_result, doc_type=doc_type)


def document_ir_from_payload(payload: dict[str, Any] | DocumentIR) -> DocumentIR:
    if isinstance(payload, DocumentIR):
        return payload
    return DocumentIR.model_validate(payload)


def document_ir_to_payload(document_ir: DocumentIR) -> dict[str, Any]:
    return document_ir.model_dump(mode="json")


def _block_plain_text(block: DocBlock, markdown: str) -> str:
    if block.text and block.text.strip():
        return block.text.strip()
    if markdown:
        return markdown.strip()
    return ""


def _block_metadata(block: DocBlock) -> dict[str, Any]:
    metadata = dict(block.attrs)
    metadata.pop("bbox", None)
    if block.level is not None:
        metadata["level"] = block.level
    if block.type:
        metadata["block_type"] = block.type
    return metadata


def _normalize_bbox(value: Any) -> list[float] | None:
    if not isinstance(value, list) or len(value) != 4:
        return None
    try:
        return [float(item) for item in value]
    except (TypeError, ValueError):
        return None


def _normalize_doc_type_value(doc_type: str | DocType | None) -> DocType:
    if isinstance(doc_type, DocType):
        return doc_type
    if doc_type is None or not str(doc_type).strip():
        return DocType.UNKNOWN
    try:
        return DocType(str(doc_type).strip())
    except ValueError:
        return DocType.UNKNOWN


def _extract_main_topics(sections: list[str], limit: int = 12) -> list[str]:
    topics: list[str] = []
    seen: set[str] = set()
    for section in sections:
        leaf = section.split(">")[-1].strip()
        leaf = re.sub(r"^\d+(?:\.\d+)*\s*", "", leaf).strip()
        if not leaf or leaf in seen:
            continue
        topics.append(leaf)
        seen.add(leaf)
        if len(topics) >= limit:
            break
    return topics

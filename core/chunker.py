import re

from schemas.models import DocType, DocumentChunk, DocumentElement, DocumentIR


SRS_REQUIREMENT_SECTION_PATTERN = re.compile(r"^\s*\d+\.\d+(?:\.\d+)+\s+\S+")
DEFAULT_TARGET_SIZE = 700

__all__ = ["render_element_marker", "split_ir_into_chunks"]


def split_ir_into_chunks(
    document_ir: DocumentIR,
    max_chars: int = DEFAULT_TARGET_SIZE,
    *,
    ignore_sections: list[str] | None = None,
) -> list[DocumentChunk]:
    """
    基于 Document IR 生成章节感知的抽取分块。
    """
    target_size = max_chars or DEFAULT_TARGET_SIZE
    ignored = [item.strip().lower() for item in (ignore_sections or []) if item.strip()]
    chunks: list[DocumentChunk] = []
    current_section: tuple[str, ...] | None = None
    current_elements: list[DocumentElement] = []
    current_size = 0

    def flush() -> None:
        """将当前累计元素落成一个 DocumentChunk。"""
        nonlocal current_elements, current_size
        if not current_elements:
            return
        chunks.append(_build_ir_chunk(len(chunks), current_elements))
        current_elements = []
        current_size = 0

    for element in sorted(document_ir.elements, key=lambda item: item.order):
        if _is_ignored_section(element.section_path, ignored):
            flush()
            current_section = None
            continue

        section_key = _chunk_section_key(document_ir, element.section_path)
        rendered_size = len(render_element_marker(element))
        section_changed = current_section is not None and section_key != current_section
        over_target = current_elements and current_size + rendered_size > target_size
        if section_changed or over_target:
            flush()

        current_section = section_key
        current_elements.append(element)
        current_size += rendered_size

    flush()
    return chunks


def render_element_marker(element: DocumentElement) -> str:
    """
    渲染带稳定证据 ID 的元素文本。
    """
    page_hint = f" page={element.page}" if element.page is not None else ""
    body = (element.markdown or element.text or "").strip()
    marker = f"[ELEMENT: {element.element_id}{page_hint}]"
    return f"{marker}\n{body}".strip()


def _build_ir_chunk(index: int, elements: list[DocumentElement]) -> DocumentChunk:
    """
    将一组连续 IR 元素转换为 DocumentChunk。
    """
    pages = [element.page for element in elements if element.page is not None]
    return DocumentChunk(
        chunk_id=f"chunk-{index + 1:04d}",
        section_path=list(elements[0].section_path) if elements else [],
        elements=list(elements),
        markdown="\n\n".join(render_element_marker(element) for element in elements),
        page_start=min(pages) if pages else None,
        page_end=max(pages) if pages else None,
    )


def _is_ignored_section(section_path: list[str], ignored: list[str]) -> bool:
    """
    判断元素所在章节是否命中忽略规则。
    """
    if not ignored:
        return False
    section_text = " > ".join(section_path).lower()
    return any(item in section_text for item in ignored)


def _chunk_section_key(document_ir: DocumentIR, section_path: list[str]) -> tuple[str, ...]:
    """
    返回用于分块边界判断的章节键。
    """
    if document_ir.doc_type not in {DocType.SRS, DocType.SRS.value}:
        return tuple(section_path)

    for index in range(len(section_path) - 1, -1, -1):
        section = section_path[index].strip()
        if SRS_REQUIREMENT_SECTION_PATTERN.match(section):
            return tuple(section_path[: index + 1])
    return tuple(section_path)

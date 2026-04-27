from schemas.models import DocumentChunk, DocumentElement, DocumentIR
from core.constants import DEFAULT_EXTRACTION_CHUNK_MAX_CHARS

__all__ = ["render_element_marker", "summarize_chunk", "split_ir_into_chunks"]


def split_ir_into_chunks(
    document_ir: DocumentIR,
    max_chars: int = DEFAULT_EXTRACTION_CHUNK_MAX_CHARS,
    *,
    ignore_sections: list[str] | None = None,
) -> list[DocumentChunk]:
    """
    基于连续章节单元生成大小受控的抽取分块。
    """
    target_size = max_chars or DEFAULT_EXTRACTION_CHUNK_MAX_CHARS
    ignored = [item.strip().lower() for item in (ignore_sections or []) if item.strip()]
    unit_groups = _collect_section_unit_groups(document_ir, ignored)
    chunks: list[DocumentChunk] = []
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

    for units in unit_groups:
        for unit in units:
            unit_size = _elements_size(unit)
            if unit_size > target_size:
                flush()
                for part in _split_large_unit(unit, target_size):
                    chunks.append(_build_ir_chunk(len(chunks), part))
                continue

            if current_elements and current_size + unit_size > target_size:
                flush()

            current_elements.extend(unit)
            current_size += unit_size
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


def summarize_chunk(chunk: DocumentChunk) -> dict[str, object]:
    """
    返回用于日志定位的分块摘要。
    """
    return {
        "chunk_id": chunk.chunk_id,
        "section_path": " > ".join(chunk.section_path),
        "page_start": chunk.page_start,
        "page_end": chunk.page_end,
        "element_count": len(chunk.elements),
        "markdown_chars": len(chunk.markdown),
    }


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


def _collect_section_unit_groups(document_ir: DocumentIR, ignored: list[str]) -> list[list[list[DocumentElement]]]:
    """
    将连续章节单元按 ignored section 边界分组。
    """
    groups: list[list[list[DocumentElement]]] = []
    units: list[list[DocumentElement]] = []
    current_key: tuple[str, ...] | None = None
    current_elements: list[DocumentElement] = []

    def flush() -> None:
        """将当前章节单元落入 units。"""
        nonlocal current_elements
        if current_elements:
            units.append(current_elements)
            current_elements = []

    def flush_group() -> None:
        """将当前章节单元组落入 groups。"""
        nonlocal units
        flush()
        if units:
            groups.append(units)
            units = []

    for element in sorted(document_ir.elements, key=lambda item: item.order):
        if _is_ignored_section(element.section_path, ignored):
            flush_group()
            current_key = None
            continue

        section_key = tuple(element.section_path)
        if current_key is not None and section_key != current_key:
            flush()

        current_key = section_key
        current_elements.append(element)

    flush_group()
    return groups


def _split_large_unit(elements: list[DocumentElement], target_size: int) -> list[list[DocumentElement]]:
    """
    将超长章节单元按元素边界拆成多个分块片段。
    """
    parts: list[list[DocumentElement]] = []
    current_elements: list[DocumentElement] = []
    current_size = 0

    def flush() -> None:
        """将当前片段落入 parts。"""
        nonlocal current_elements, current_size
        if current_elements:
            parts.append(current_elements)
            current_elements = []
            current_size = 0

    for element in elements:
        rendered_size = len(render_element_marker(element))
        if current_elements and current_size + rendered_size > target_size:
            flush()
        current_elements.append(element)
        current_size += rendered_size

    flush()
    return parts


def _elements_size(elements: list[DocumentElement]) -> int:
    """
    返回元素按证据标记渲染后的近似字符数。
    """
    return sum(len(render_element_marker(element)) for element in elements)


def _is_ignored_section(section_path: list[str], ignored: list[str]) -> bool:
    """
    判断元素所在章节是否命中忽略规则。
    """
    if not ignored:
        return False
    section_text = " > ".join(section_path).lower()
    return any(item in section_text for item in ignored)

import re
from dataclasses import dataclass
from typing import Any


HEADING_PATTERN = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
NUMBERED_HEADING_PATTERN = re.compile(r"^\s*(\d+(?:\.\d+)*)(?:\.)?\s+(.+?)\s*$")
LIST_ITEM_PATTERN = re.compile(r"^\s*(?:[-+*]|\d+\.)\s+")
CODE_FENCE_PATTERN = re.compile(r"^\s*(```+|~~~+)")
TABLE_ROW_PATTERN = re.compile(r"^\s*\|.*\|\s*$")
TABLE_SEPARATOR_PATTERN = re.compile(r"^\s*\|?\s*:?-{3,}:?\s*(?:\|\s*:?-{3,}:?\s*)+\|?\s*$")
DEFAULT_TARGET_SIZE = 700
DEFAULT_OVERLAP = 80
DEFAULT_MIN_SIZE = 200


@dataclass
class MarkdownChunk:
    index: int
    title_path: list[str]
    section_title: str | None
    chunk_type: str
    order_index: int
    embed_text: str
    display_text: str

    @property
    def heading_path(self) -> list[str]:
        return self.title_path

    @property
    def text(self) -> str:
        return self.display_text

    @property
    def char_count(self) -> int:
        return len(self.display_text)


@dataclass
class _Section:
    title_path: list[str]
    body_lines: list[str]
    chunk_type: str = "section"


@dataclass
class _Block:
    chunk_type: str
    text: str

    @property
    def size(self) -> int:
        return len(self.text.strip())


def _looks_like_heading_title(title: str) -> bool:
    cleaned = title.strip()
    if not cleaned or len(cleaned) > 120:
        return False
    if cleaned[-1] in ".:;?!。；：？！":
        return False
    if cleaned.startswith(("- ", "* ", "+ ", "|", "> ", "```")):
        return False

    word_count = len(re.findall(r"[A-Za-z0-9_/\-]+", cleaned))
    cjk_count = len(re.findall(r"[\u4e00-\u9fff]", cleaned))
    if word_count > 16 or cjk_count > 40:
        return False

    return True


def _parse_heading(line: str) -> tuple[int, str] | None:
    markdown_match = HEADING_PATTERN.match(line)
    if markdown_match:
        return len(markdown_match.group(1)), markdown_match.group(2).strip()

    numbered_match = NUMBERED_HEADING_PATTERN.match(line)
    if not numbered_match:
        return None

    number_path = numbered_match.group(1)
    title = numbered_match.group(2).strip()
    if not _looks_like_heading_title(title):
        return None

    level = number_path.count(".") + 1
    return level, f"{number_path} {title}"


def _looks_like_title_candidate(line: str) -> bool:
    cleaned = line.strip()
    if not cleaned or len(cleaned) > 120:
        return False
    if _parse_heading(cleaned):
        return False
    if cleaned.startswith(("- ", "* ", "+ ", "|", "> ", "```")):
        return False
    if re.match(r"^\d+\s*$", cleaned):
        return False
    return _looks_like_heading_title(cleaned)


def _extract_document_title(lines: list[str]) -> tuple[str | None, int]:
    for idx, line in enumerate(lines[:5]):
        if not line.strip():
            continue
        if not _looks_like_title_candidate(line):
            return None, 0

        next_line = lines[idx + 1].strip() if idx + 1 < len(lines) else ""
        if not next_line or _parse_heading(next_line):
            return line.strip(), idx + 1
        return None, 0

    return None, 0


def _split_into_sections(markdown_text: str) -> list[_Section]:
    normalized_text = (markdown_text or "").strip()
    if not normalized_text:
        return []

    lines = normalized_text.splitlines()
    title, start_idx = _extract_document_title(lines)
    heading_stack: list[str] = [title] if title else []
    current_path: list[str] = list(heading_stack)
    current_body: list[str] = []
    sections: list[_Section] = []

    def flush_section() -> None:
        if current_body and any(line.strip() for line in current_body):
            sections.append(_Section(title_path=list(current_path), body_lines=list(current_body)))
        current_body.clear()

    for line in lines[start_idx:]:
        heading = _parse_heading(line)
        if heading:
            flush_section()
            level, title_text = heading
            heading_stack[:] = heading_stack[:level - 1]
            heading_stack.append(title_text)
            current_path = list(heading_stack)
            continue
        current_body.append(line)

    flush_section()

    if not sections and normalized_text:
        sections.append(_Section(title_path=list(heading_stack), body_lines=lines[start_idx:]))

    return sections


def _collect_until_blank(lines: list[str], start: int) -> tuple[list[str], int]:
    collected: list[str] = []
    idx = start
    while idx < len(lines):
        line = lines[idx]
        if not line.strip():
            break
        collected.append(line)
        idx += 1
    return collected, idx


def _collect_code_block(lines: list[str], start: int) -> tuple[str, int]:
    fence_match = CODE_FENCE_PATTERN.match(lines[start])
    fence = fence_match.group(1) if fence_match else "```"
    collected = [lines[start]]
    idx = start + 1
    while idx < len(lines):
        collected.append(lines[idx])
        if lines[idx].strip().startswith(fence[:3]):
            idx += 1
            break
        idx += 1
    return "\n".join(collected).strip(), idx


def _collect_table(lines: list[str], start: int) -> tuple[str, int]:
    collected = [lines[start]]
    idx = start + 1
    while idx < len(lines) and TABLE_ROW_PATTERN.match(lines[idx]):
        collected.append(lines[idx])
        idx += 1
    return "\n".join(collected).strip(), idx


def _collect_list(lines: list[str], start: int) -> tuple[str, int]:
    collected = [lines[start]]
    idx = start + 1
    while idx < len(lines):
        line = lines[idx]
        if not line.strip():
            break
        if LIST_ITEM_PATTERN.match(line) or line.startswith(("  ", "\t")):
            collected.append(line)
            idx += 1
            continue
        break
    return "\n".join(collected).strip(), idx


def _split_section_blocks(section: _Section) -> list[_Block]:
    lines = section.body_lines
    blocks: list[_Block] = []
    idx = 0

    while idx < len(lines):
        line = lines[idx]
        if not line.strip():
            idx += 1
            continue
        if CODE_FENCE_PATTERN.match(line):
            block_text, idx = _collect_code_block(lines, idx)
            blocks.append(_Block(chunk_type="code", text=block_text))
            continue
        if TABLE_ROW_PATTERN.match(line):
            block_text, idx = _collect_table(lines, idx)
            blocks.append(_Block(chunk_type="table", text=block_text))
            continue
        if LIST_ITEM_PATTERN.match(line):
            block_text, idx = _collect_list(lines, idx)
            blocks.append(_Block(chunk_type="list", text=block_text))
            continue

        paragraph_lines, idx = _collect_until_blank(lines, idx)
        if paragraph_lines:
            blocks.append(_Block(chunk_type="paragraph", text="\n".join(paragraph_lines).strip()))

    return blocks


def _clean_embed_text(text: str) -> str:
    compact = text.replace("\r\n", "\n").strip()
    compact = re.sub(r"[ \t]+", " ", compact)
    compact = re.sub(r"\n{3,}", "\n\n", compact)
    return compact


def _tail_overlap(text: str, overlap_chars: int) -> str:
    if overlap_chars <= 0:
        return ""
    compact = _clean_embed_text(text)
    if len(compact) <= overlap_chars:
        return compact
    return compact[-overlap_chars:]


def _build_embed_text(title_path: list[str], display_text: str, overlap_prefix: str = "") -> str:
    parts = []
    if title_path:
        parts.append(f"标题路径: {' > '.join(title_path)}")
    if overlap_prefix:
        parts.append(f"上文片段: {overlap_prefix}")
    parts.append(display_text.strip())
    return _clean_embed_text("\n\n".join(part for part in parts if part))


def _split_units_by_size(units: list[str], target_size: int) -> list[str]:
    parts: list[str] = []
    buffer = ""
    for unit in units:
        cleaned = unit.strip()
        if not cleaned:
            continue
        candidate = f"{buffer}\n{cleaned}".strip() if buffer else cleaned
        if len(candidate) <= target_size:
            buffer = candidate
            continue
        if buffer:
            parts.append(buffer)
        if len(cleaned) > target_size:
            parts.extend([cleaned[i:i + target_size] for i in range(0, len(cleaned), target_size)])
            buffer = ""
        else:
            buffer = cleaned
    if buffer:
        parts.append(buffer)
    return parts


def _split_paragraph_block(block: _Block, target_size: int) -> list[_Block]:
    if block.size <= target_size:
        return [block]

    sentences = [
        sentence.strip()
        for sentence in re.split(r"(?<=[。！？!?\.])\s+|\n", block.text)
        if sentence.strip()
    ]
    units = sentences or [block.text]
    return [_Block(chunk_type=block.chunk_type, text=part) for part in _split_units_by_size(units, target_size)]


def _split_list_block(block: _Block, target_size: int) -> list[_Block]:
    if block.size <= target_size:
        return [block]

    items: list[str] = []
    current: list[str] = []
    for line in block.text.splitlines():
        if LIST_ITEM_PATTERN.match(line) and current:
            items.append("\n".join(current).strip())
            current = [line]
        else:
            current.append(line)
    if current:
        items.append("\n".join(current).strip())
    return [_Block(chunk_type=block.chunk_type, text=part) for part in _split_units_by_size(items, target_size)]


def _split_table_block(block: _Block, target_size: int) -> list[_Block]:
    if block.size <= target_size:
        return [block]

    lines = [line for line in block.text.splitlines() if line.strip()]
    if len(lines) < 3:
        return [block]

    header = lines[:2] if TABLE_SEPARATOR_PATTERN.match(lines[1]) else lines[:1]
    rows = lines[len(header):]
    parts: list[_Block] = []
    current_rows: list[str] = []
    current_len = len("\n".join(header))

    for row in rows:
        projected = current_len + len(row) + 1
        if current_rows and projected > target_size:
            parts.append(_Block(chunk_type="table", text="\n".join(header + current_rows)))
            current_rows = [row]
            current_len = len("\n".join(header + current_rows))
            continue
        current_rows.append(row)
        current_len = projected

    if current_rows:
        parts.append(_Block(chunk_type="table", text="\n".join(header + current_rows)))

    return parts or [block]


def _split_oversized_block(block: _Block, target_size: int) -> list[_Block]:
    if block.chunk_type == "code":
        return [block]
    if block.chunk_type == "table":
        return _split_table_block(block, target_size)
    if block.chunk_type == "list":
        return _split_list_block(block, target_size)
    return _split_paragraph_block(block, target_size)


def _prepare_blocks(blocks: list[_Block], target_size: int, min_size: int) -> list[_Block]:
    expanded: list[_Block] = []
    for block in blocks:
        expanded.extend(_split_oversized_block(block, target_size))

    merged: list[_Block] = []
    for block in expanded:
        text = block.text.strip()
        if not text:
            continue
        if not merged:
            merged.append(_Block(chunk_type=block.chunk_type, text=text))
            continue

        previous = merged[-1]
        can_merge = (
            previous.chunk_type in {"paragraph", "list"}
            and block.chunk_type in {"paragraph", "list"}
            and previous.size < min_size
            and len(previous.text) + len(text) + 2 <= target_size
        )
        if can_merge:
            previous.text = f"{previous.text}\n\n{text}"
            previous.chunk_type = "list" if "list" in {previous.chunk_type, block.chunk_type} else "paragraph"
            continue

        if (
            previous.chunk_type == "paragraph"
            and block.chunk_type in {"code", "table"}
            and previous.size < min_size
            and len(previous.text) + len(text) + 2 <= int(target_size * 1.2)
        ):
            previous.text = f"{previous.text}\n\n{text}"
            previous.chunk_type = block.chunk_type
            continue

        merged.append(_Block(chunk_type=block.chunk_type, text=text))

    return merged


def _build_chunks_from_blocks(
    title_path: list[str],
    blocks: list[_Block],
    target_size: int,
    overlap_chars: int,
    start_index: int,
) -> list[MarkdownChunk]:
    chunks: list[MarkdownChunk] = []
    index = start_index
    previous_display = ""
    section_title = title_path[-1] if title_path else None

    for block in blocks:
        display_text = block.text.strip()
        if not display_text:
            continue

        overlap_prefix = _tail_overlap(previous_display, overlap_chars) if previous_display else ""
        chunks.append(
            MarkdownChunk(
                index=index,
                title_path=list(title_path),
                section_title=section_title,
                chunk_type=block.chunk_type,
                order_index=index,
                embed_text=_build_embed_text(title_path=title_path, display_text=display_text, overlap_prefix=overlap_prefix),
                display_text=display_text,
            )
        )
        previous_display = display_text
        index += 1

    return chunks


def _build_markdown_chunks(markdown_text: str, target_size: int, overlap_chars: int, min_size: int) -> list[MarkdownChunk]:
    sections = _split_into_sections(markdown_text)
    chunks: list[MarkdownChunk] = []
    next_index = 0

    for section in sections:
        blocks = _split_section_blocks(section)
        prepared_blocks = _prepare_blocks(blocks, target_size=target_size, min_size=min_size)
        section_chunks = _build_chunks_from_blocks(
            title_path=section.title_path,
            blocks=prepared_blocks,
            target_size=target_size,
            overlap_chars=overlap_chars,
            start_index=next_index,
        )
        chunks.extend(section_chunks)
        next_index += len(section_chunks)

    return chunks


def _api_structured_blocks(extracted_data: dict[str, Any]) -> list[tuple[list[str], list[_Block]]]:
    title = str(extracted_data.get("title") or "API Documentation").strip()
    version = extracted_data.get("version")
    base_url = extracted_data.get("base_url")

    overview_lines = [f"API 文档标题: {title}"]
    if version:
        overview_lines.append(f"版本: {version}")
    if base_url:
        overview_lines.append(f"基础地址: {base_url}")

    sections: list[tuple[list[str], list[_Block]]] = [
        (
            ["Structured Data", "Overview"],
            [_Block(chunk_type="structured", text="\n".join(overview_lines))],
        )
    ]

    for endpoint in extracted_data.get("endpoints") or []:
        if not isinstance(endpoint, dict):
            continue
        method = str(endpoint.get("method") or "").strip().upper()
        path = str(endpoint.get("path") or "").strip()
        summary = str(endpoint.get("summary") or "").strip()
        description = str(endpoint.get("description") or "").strip()
        if not method or not path:
            continue

        lines = [
            f"API endpoint: {method} {path}",
            f"Method: {method}",
            f"Path: {path}",
        ]
        if summary:
            lines.append(f"Summary: {summary}")
        if description:
            lines.append(f"Description: {description}")

        sections.append(
            (
                ["Structured Data", "Endpoints", f"{method} {path}"],
                [_Block(chunk_type="structured", text="\n".join(lines))],
            )
        )

    return sections


def _build_structured_chunks(
    doc_type: str | None,
    extracted_data: dict[str, Any] | None,
    target_size: int,
    overlap_chars: int,
    start_index: int,
) -> list[MarkdownChunk]:
    if not doc_type or not isinstance(extracted_data, dict):
        return []

    sections: list[tuple[list[str], list[_Block]]] = []
    if doc_type == "api":
        sections = _api_structured_blocks(extracted_data)

    chunks: list[MarkdownChunk] = []
    next_index = start_index
    for title_path, blocks in sections:
        section_chunks = _build_chunks_from_blocks(
            title_path=title_path,
            blocks=blocks,
            target_size=target_size,
            overlap_chars=overlap_chars,
            start_index=next_index,
        )
        chunks.extend(section_chunks)
        next_index += len(section_chunks)

    return chunks


def split_markdown_into_chunks(
    markdown_text: str,
    max_chars: int = DEFAULT_TARGET_SIZE,
    overlap_chars: int = DEFAULT_OVERLAP,
    doc_type: str | None = None,
    extracted_data: dict[str, Any] | None = None,
    min_chars: int = DEFAULT_MIN_SIZE,
) -> list[MarkdownChunk]:
    """
    先按 Markdown 结构切分，再按长度补切，并统一生成 embed/display 双文本。
    """
    target_size = max_chars or DEFAULT_TARGET_SIZE
    overlap = overlap_chars if overlap_chars is not None else DEFAULT_OVERLAP
    min_size = min_chars or DEFAULT_MIN_SIZE

    markdown_chunks = _build_markdown_chunks(
        markdown_text=markdown_text,
        target_size=target_size,
        overlap_chars=overlap,
        min_size=min_size,
    )

    structured_chunks = _build_structured_chunks(
        doc_type=doc_type,
        extracted_data=extracted_data,
        target_size=target_size,
        overlap_chars=overlap,
        start_index=len(markdown_chunks),
    )
    return markdown_chunks + structured_chunks

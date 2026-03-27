import re
from dataclasses import dataclass


HEADING_PATTERN = re.compile(r"^(#{1,6})\s+(.+?)\s*$")


@dataclass
class MarkdownChunk:
    index: int
    heading_path: list[str]
    text: str

    @property
    def char_count(self) -> int:
        return len(self.text)


def _split_oversized_text(text: str, max_chars: int) -> list[str]:
    if len(text) <= max_chars:
        return [text]

    paragraphs = [part for part in text.split("\n\n") if part.strip()]
    if not paragraphs:
        return [text[i:i + max_chars] for i in range(0, len(text), max_chars)]

    parts: list[str] = []
    buffer = ""
    for para in paragraphs:
        para = para.strip()
        candidate = f"{buffer}\n\n{para}".strip() if buffer else para
        if len(candidate) <= max_chars:
            buffer = candidate
            continue

        if buffer:
            parts.append(buffer)
        if len(para) > max_chars:
            parts.extend([para[i:i + max_chars] for i in range(0, len(para), max_chars)])
            buffer = ""
        else:
            buffer = para

    if buffer:
        parts.append(buffer)

    return parts


def split_markdown_into_chunks(markdown_text: str, max_chars: int = 5000, overlap_chars: int = 200) -> list[MarkdownChunk]:
    """
    按 Markdown 标题层级优先切分，再按长度做二次切分。
    """
    if not markdown_text or not markdown_text.strip():
        return []

    lines = markdown_text.splitlines()
    sections: list[tuple[list[str], str]] = []
    heading_stack: list[str] = []
    current_lines: list[str] = []
    current_path: list[str] = []

    def flush_current_section() -> None:
        if not current_lines:
            return
        section_text = "\n".join(current_lines).strip()
        if section_text:
            sections.append((list(current_path), section_text))
        current_lines.clear()

    for line in lines:
        match = HEADING_PATTERN.match(line)
        if match:
            flush_current_section()
            level = len(match.group(1))
            title = match.group(2).strip()
            heading_stack[:] = heading_stack[:level - 1]
            heading_stack.append(title)
            current_path = list(heading_stack)
            current_lines.append(line)
        else:
            current_lines.append(line)

    flush_current_section()

    if not sections:
        sections = [([], markdown_text.strip())]

    chunks: list[MarkdownChunk] = []
    idx = 0
    prev_tail = ""

    for heading_path, section_text in sections:
        section_parts = _split_oversized_text(section_text, max_chars=max_chars)
        for part in section_parts:
            body = part.strip()
            if not body:
                continue

            if prev_tail:
                body = f"{prev_tail}\n\n{body}"

            chunks.append(MarkdownChunk(index=idx, heading_path=heading_path, text=body))
            idx += 1
            prev_tail = body[-overlap_chars:] if overlap_chars > 0 else ""

    return chunks

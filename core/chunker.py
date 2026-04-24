import re
from dataclasses import dataclass
from typing import Any

from core.parser import ParseResult


HEADING_PATTERN = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
NUMBERED_HEADING_PATTERN = re.compile(r"^\s*(\d+(?:\.\d+)*)(?:\.)?\s+(.+?)\s*$")
LIST_ITEM_PATTERN = re.compile(r"^\s*(?:[-+*]|\d+\.)\s+")
CODE_FENCE_PATTERN = re.compile(r"^\s*(```+|~~~+)")
TABLE_ROW_PATTERN = re.compile(r"^\s*\|.*\|\s*$")
TABLE_SEPARATOR_PATTERN = re.compile(r"^\s*\|?\s*:?-{3,}:?\s*(?:\|\s*:?-{3,}:?\s*)+\|?\s*$")
FACT_PATTERN = re.compile(
    r"(failed|error|pass|passed|fail|bug\s*#|/api/|tc\d+|req-\d+|method:|path:|\|\s*[^|]+\s*\|)",
    re.IGNORECASE,
)
HTTP_METHOD_PATTERN = re.compile(r"\b(GET|POST|PUT|DELETE|PATCH|OPTIONS|HEAD)\b")
PATH_HINT_PATTERN = re.compile(r"(?:^|\s)/[A-Za-z0-9._~!$&'()*+,;=:@%/\-{}]+")
API_VALUE_HINT_PATTERN = re.compile(
    r"(base url|authorization|request body|response|path parameter|query parameter|status code|鉴权|请求体|响应|字段|参数)",
    re.IGNORECASE,
)
LOW_VALUE_API_TITLE_PATTERN = re.compile(r"(错误格式|通用错误|状态码|错误码|附录|error|status\s*code)", re.IGNORECASE)
LOW_VALUE_API_BODY_PATTERN = re.compile(
    r"(all errors|所有错误统一返回|validation_error|resource_not_found|internal_error|rate_limited|trace_id|\"error\"\s*:)",
    re.IGNORECASE,
)
DEFAULT_TARGET_SIZE = 700
DEFAULT_OVERLAP = 80
DEFAULT_MIN_SIZE = 200


def get_metadata_window(markdown_text: str, max_chars: int = 1500) -> str:
    """
    从文档开头截取元信息窗口文本（优先包含文档标题、前若干个 heading/段落、封面表格等）。
    尽量在自然段落或标题处截断，避免截断在句子中间。
    """
    if not markdown_text:
        return ""
    
    text = markdown_text.strip()
    if len(text) <= max_chars:
        return text

    # 在 max_chars 附近寻找一个较好的截断点，如换行符
    # 给一点 buffer (如 +200) 来找段落结束
    search_end = min(len(text), max_chars + 200)
    window = text[:search_end]
    
    # 尝试在 max_chars 以内的最后一个空行截断
    last_blank_line = window.rfind("\n\n", 0, max_chars)
    if last_blank_line > max_chars * 0.5:
        return window[:last_blank_line].strip()
        
    # 如果没找到空行，尝试找最后一个换行符
    last_newline = window.rfind("\n", 0, max_chars)
    if last_newline > max_chars * 0.5:
        return window[:last_newline].strip()
        
    # 如果都没有，硬截断
    return text[:max_chars].strip()


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


def _strip_markdown_noise(text: str) -> str:
    cleaned = text.strip()
    cleaned = re.sub(r"^\s*#{1,6}\s*", "", cleaned, flags=re.MULTILINE)
    cleaned = cleaned.replace("**", "").replace("__", "").replace("`", "")
    cleaned = re.sub(r"\[(.*?)\]\((.*?)\)", r"\1", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip()


def _is_low_value_chunk(display_text: str, title_path: list[str], chunk_type: str) -> bool:
    cleaned = display_text.strip()
    if not cleaned:
        return True

    normalized = _clean_embed_text(cleaned)
    semantic_text = _strip_markdown_noise(normalized)
    normalized_lower = semantic_text.lower()
    title_leaf = _strip_markdown_noise((title_path[-1] if title_path else "")).lower()

    if chunk_type == "paragraph":
        if title_leaf and normalized_lower == title_leaf:
            return True

        lines = [_strip_markdown_noise(line).lower() for line in normalized.splitlines() if line.strip()]
        if title_leaf and len(lines) == 1 and lines[0] == title_leaf:
            return True

        if len(semantic_text) < 40 and not FACT_PATTERN.search(semantic_text):
            return True

        if len(semantic_text) < 90 and not FACT_PATTERN.search(semantic_text):
            generic_prefixes = (
                "test report",
                "api documentation",
                "test summary",
                "summary",
                "overview",
                "introduction",
            )
            if normalized_lower.startswith(generic_prefixes):
                return True

    return False


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


def _section_title_text(title_path: list[str]) -> str:
    return " > ".join(part.strip() for part in title_path if part and part.strip())


def _looks_like_api_section(title_path: list[str], blocks: list[_Block]) -> bool:
    title_text = _section_title_text(title_path)
    body_text = "\n".join(block.text for block in blocks)
    combined_text = f"{title_text}\n{body_text}"
    return bool(
        HTTP_METHOD_PATTERN.search(combined_text)
        or PATH_HINT_PATTERN.search(combined_text)
        or API_VALUE_HINT_PATTERN.search(combined_text)
        or "api" in title_text.lower()
    )


def _is_low_value_api_section(title_path: list[str], blocks: list[_Block]) -> bool:
    title_text = _section_title_text(title_path)
    body_text = "\n".join(block.text for block in blocks)
    has_endpoint_signal = bool(HTTP_METHOD_PATTERN.search(body_text) or PATH_HINT_PATTERN.search(body_text))
    has_api_value_signal = bool(API_VALUE_HINT_PATTERN.search(body_text))
    if re.search(r"限流", title_text) and not has_endpoint_signal:
        return True
    if LOW_VALUE_API_TITLE_PATTERN.search(title_text) and not has_endpoint_signal:
        return True
    if LOW_VALUE_API_BODY_PATTERN.search(body_text) and not (has_endpoint_signal or has_api_value_signal):
        return True
    return False


def _merge_blocks_semantically(title_path: list[str], blocks: list[_Block], target_size: int) -> list[_Block]:
    if not blocks or not _looks_like_api_section(title_path, blocks):
        return blocks

    merged: list[_Block] = []
    buffer_parts: list[str] = []
    buffer_size = 0
    for block in blocks:
        text = block.text.strip()
        if not text:
            continue
        addition_size = len(text) + (2 if buffer_parts else 0)
        if buffer_parts and buffer_size + addition_size > target_size:
            merged.append(_Block(chunk_type="section", text="\n\n".join(buffer_parts)))
            buffer_parts = [text]
            buffer_size = len(text)
            continue
        buffer_parts.append(text)
        buffer_size += addition_size

    if buffer_parts:
        merged.append(_Block(chunk_type="section", text="\n\n".join(buffer_parts)))

    return merged or blocks


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
        if _is_low_value_chunk(display_text=display_text, title_path=title_path, chunk_type=block.chunk_type):
            previous_display = display_text
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
        if _is_low_value_api_section(section.title_path, blocks):
            continue
        prepared_blocks = _prepare_blocks(blocks, target_size=target_size, min_size=min_size)
        prepared_blocks = _merge_blocks_semantically(section.title_path, prepared_blocks, target_size=target_size)
        section_chunks = _build_chunks_from_blocks(
            title_path=section.title_path,
            blocks=prepared_blocks,
            target_size=target_size,
            overlap_chars=overlap_chars,
            start_index=next_index,
        )
        chunks.extend(section_chunks)
        next_index += len(section_chunks)

    return _merge_adjacent_api_chunks(chunks, target_size=target_size, overlap_chars=overlap_chars)


def _merge_adjacent_api_chunks(
    chunks: list[MarkdownChunk],
    *,
    target_size: int,
    overlap_chars: int,
) -> list[MarkdownChunk]:
    if not chunks:
        return chunks

    merged: list[MarkdownChunk] = []
    current = chunks[0]

    def can_merge(left: MarkdownChunk, right: MarkdownChunk) -> bool:
        if len(left.title_path) < 2 or len(right.title_path) < 2:
            return False
        if left.title_path[:-1] != right.title_path[:-1]:
            return False
        if not (_looks_like_api_section(left.title_path, [_Block(chunk_type="section", text=left.text)]) and _looks_like_api_section(right.title_path, [_Block(chunk_type="section", text=right.text)])):
            return False
        left_heading = left.title_path[-1]
        right_heading = right.title_path[-1]
        combined_text = f"{left_heading}\n{left.text}\n\n{right_heading}\n{right.text}"
        return len(combined_text) <= target_size

    def merge_two(left: MarkdownChunk, right: MarkdownChunk) -> MarkdownChunk:
        title_path = left.title_path[:-1] if len(left.title_path) > 1 else left.title_path
        display_text = f"{left.title_path[-1]}\n{left.text}\n\n{right.title_path[-1]}\n{right.text}".strip()
        return MarkdownChunk(
            index=left.index,
            title_path=title_path,
            section_title=title_path[-1] if title_path else left.section_title,
            chunk_type="section",
            order_index=left.order_index,
            embed_text=_build_embed_text(title_path=title_path, display_text=display_text, overlap_prefix=""),
            display_text=display_text,
        )

    for chunk in chunks[1:]:
        if can_merge(current, chunk):
            current = merge_two(current, chunk)
            continue
        merged.append(current)
        current = chunk

    merged.append(current)
    return merged


def _node_label(node: dict[str, Any]) -> str:
    for key in ("title", "name", "id"):
        value = str(node.get(key) or "").strip()
        if value:
            return value
    return ""


def _artifact_extra_value(artifact: dict[str, Any], key: str) -> str:
    extra = artifact.get("extra")
    if isinstance(extra, dict):
        value = extra.get(key)
        if value is not None:
            return str(value).strip()
    return ""


def _find_api_artifact(
    artifacts: list[dict[str, Any]],
    interface_id: str,
    method: str,
    path: str,
) -> dict[str, Any] | None:
    normalized_method = method.upper()

    for artifact in artifacts:
        artifact_id = str(artifact.get("id") or "").strip()
        artifact_method = _artifact_extra_value(artifact, "method").upper()
        artifact_path = _artifact_extra_value(artifact, "path")
        if interface_id and artifact_id and artifact_id == interface_id:
            return artifact
        if artifact_method and artifact_path and artifact_method == normalized_method and artifact_path == path:
            return artifact

    return None


def _api_structured_blocks(extracted_data: dict[str, Any]) -> list[tuple[list[str], list[_Block]]]:
    title = str(extracted_data.get("title") or "API Documentation").strip()
    version = extracted_data.get("version")
    base_url = extracted_data.get("base_url")
    interfaces = extracted_data.get("interfaces") or []
    artifacts = [
        artifact
        for artifact in (extracted_data.get("artifacts") or [])
        if isinstance(artifact, dict) and artifact.get("artifact_type") == "api_endpoint"
    ]

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

    for interface in interfaces:
        if not isinstance(interface, dict):
            continue
        method = str(interface.get("method") or "").strip().upper()
        path = str(interface.get("path") or "").strip()
        if not method or not path:
            continue

        interface_id = str(interface.get("id") or "").strip()
        summary = str(interface.get("description") or "").strip()
        target = str(interface.get("target") or "").strip()
        artifact = _find_api_artifact(artifacts, interface_id=interface_id, method=method, path=path)
        request = _artifact_extra_value(artifact or {}, "request")
        response = _artifact_extra_value(artifact or {}, "response")
        operation_id = _artifact_extra_value(artifact or {}, "operation_id")

        lines = [
            f"API endpoint: {method} {path}",
            f"Method: {method}",
            f"Path: {path}",
        ]
        if target:
            lines.append(f"Target: {target}")
        if summary:
            lines.append(f"Summary: {summary}")
        if operation_id:
            lines.append(f"Operation ID: {operation_id}")
        if request:
            lines.append(f"Request: {request}")
        if response:
            lines.append(f"Response: {response}")

        sections.append(
            (
                ["Structured Data", "Endpoints", f"{method} {path}"],
                [_Block(chunk_type="structured", text="\n".join(lines))],
            )
        )

    return sections


def _issue_structured_blocks(extracted_data: dict[str, Any]) -> list[tuple[list[str], list[_Block]]]:
    artifacts = [
        artifact
        for artifact in (extracted_data.get("artifacts") or [])
        if isinstance(artifact, dict) and artifact.get("artifact_type") == "issue"
    ]
    issue_artifact = artifacts[0] if artifacts else {}
    title = str(_node_label(issue_artifact) or extracted_data.get("title") or "Issue").strip()
    overview_lines = [f"问题标题: {title}"]

    for label, value in (
        ("Issue ID", _artifact_extra_value(issue_artifact, "issue_id")),
        ("状态", str(issue_artifact.get("status") or "").strip()),
        ("严重级别", _artifact_extra_value(issue_artifact, "severity")),
    ):
        if value:
            overview_lines.append(f"{label}: {value}")

    if extracted_data.get("summary"):
        overview_lines.append(f"摘要: {extracted_data['summary']}")

    description = str(issue_artifact.get("description") or "").strip()
    if description:
        overview_lines.append(f"问题描述: {description}")

    expected = _artifact_extra_value(issue_artifact, "expected")
    actual = _artifact_extra_value(issue_artifact, "actual")
    if expected:
        overview_lines.append(f"期望结果: {expected}")
    if actual:
        overview_lines.append(f"实际结果: {actual}")

    issue_id = str(issue_artifact.get("id") or "").strip()
    impacted_ids: list[str] = []
    for relation in extracted_data.get("relations") or []:
        if not isinstance(relation, dict):
            continue
        subject_id = str(relation.get("subject_id") or "").strip()
        object_id = str(relation.get("object_id") or "").strip()
        relation_name = str(relation.get("relation") or "").strip()
        if not issue_id:
            continue
        if subject_id == issue_id and object_id:
            impacted_ids.append(f"{relation_name}: {object_id}")
        elif object_id == issue_id and subject_id:
            impacted_ids.append(f"{relation_name}: {subject_id}")
    if impacted_ids:
        overview_lines.append(f"关联对象: {', '.join(dict.fromkeys(impacted_ids))}")

    sections: list[tuple[list[str], list[_Block]]] = [
        (
            ["Structured Data", "Overview"],
            [_Block(chunk_type="structured", text="\n".join(overview_lines))],
        )
    ]

    reproduction_process = None
    for process in extracted_data.get("processes") or []:
        if not isinstance(process, dict):
            continue
        steps = process.get("steps") or []
        if steps:
            reproduction_process = process
            break

    if reproduction_process:
        process_title = _node_label(reproduction_process) or "Reproduction Steps"
        step_lines = []
        for idx, step in enumerate(reproduction_process.get("steps") or [], start=1):
            if not isinstance(step, dict):
                continue
            step_name = str(step.get("name") or "").strip()
            step_description = str(step.get("description") or "").strip()
            if step_name and step_description:
                step_lines.append(f"{idx}. {step_name}: {step_description}")
            elif step_name:
                step_lines.append(f"{idx}. {step_name}")
            elif step_description:
                step_lines.append(f"{idx}. {step_description}")
        if step_lines:
            sections.append(
                (
                    ["Structured Data", process_title],
                    [_Block(chunk_type="structured", text="\n".join(step_lines))],
                )
            )

    for requirement in extracted_data.get("requirements") or []:
        if not isinstance(requirement, dict):
            continue
        if requirement.get("requirement_type") != "acceptance":
            continue
        requirement_text = str(requirement.get("description") or _node_label(requirement)).strip()
        if requirement_text:
            sections.append(
                (
                    ["Structured Data", "Expected Result"],
                    [_Block(chunk_type="structured", text=requirement_text)],
                )
            )
            break

    if extracted_data.get("metrics"):
        metric_lines = []
        for metric in extracted_data.get("metrics") or []:
            if not isinstance(metric, dict):
                continue
            metric_name = str(metric.get("metric_name") or "").strip()
            metric_value = str(metric.get("metric_value") or "").strip()
            if not metric_name or not metric_value:
                continue
            condition = str(metric.get("condition") or "").strip()
            line = f"{metric_name}: {metric_value}"
            if condition:
                line = f"{line} ({condition})"
            metric_lines.append(line)
        if metric_lines:
            sections.append(
                (
                    ["Structured Data", "Metrics"],
                    [_Block(chunk_type="structured", text="\n".join(metric_lines))],
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
    elif doc_type == "issue":
        sections = _issue_structured_blocks(extracted_data)

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


def split_parse_result_into_chunks(
    parse_result: ParseResult,
    max_chars: int = DEFAULT_TARGET_SIZE,
    overlap_chars: int = DEFAULT_OVERLAP,
    min_chars: int = DEFAULT_MIN_SIZE,
) -> list[MarkdownChunk]:
    """
    直接基于解析器输出的 block 结构切分，避免再次从 Markdown 反推结构。
    """
    target_size = max_chars or DEFAULT_TARGET_SIZE
    overlap = overlap_chars if overlap_chars is not None else DEFAULT_OVERLAP
    min_size = min_chars or DEFAULT_MIN_SIZE

    sections: list[tuple[list[str], list[_Block]]] = []
    current_path: list[str] = []
    current_blocks: list[_Block] = []

    def flush_section() -> None:
        if current_blocks:
            sections.append((list(current_path), list(current_blocks)))
            current_blocks.clear()

    for block in parse_result.blocks:
        if block.type == "title":
            flush_section()
            level = max(1, block.level or 1)
            title_text = block.text.strip()
            if not title_text:
                continue
            current_path[:] = current_path[: level - 1]
            current_path.append(title_text)
            continue

        if block.type == "section_break":
            flush_section()
            continue

        chunk_type = block.type if block.type in {"paragraph", "list", "table", "code", "quote"} else "paragraph"
        text = block.text.strip()
        if not text:
            continue
        current_blocks.append(_Block(chunk_type=chunk_type, text=text))

    flush_section()

    chunks: list[MarkdownChunk] = []
    next_index = 0
    for title_path, blocks in sections:
        prepared_blocks = _prepare_blocks(blocks, target_size=target_size, min_size=min_size)
        section_chunks = _build_chunks_from_blocks(
            title_path=title_path,
            blocks=prepared_blocks,
            target_size=target_size,
            overlap_chars=overlap,
            start_index=next_index,
        )
        chunks.extend(section_chunks)
        next_index += len(section_chunks)

    if chunks:
        return chunks

    return split_markdown_into_chunks(
        markdown_text=parse_result.markdown,
        max_chars=max_chars,
        overlap_chars=overlap_chars,
        min_chars=min_chars,
    )

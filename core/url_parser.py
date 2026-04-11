import re
from html.parser import HTMLParser
from urllib.parse import urlparse
from urllib.request import Request, urlopen


def validate_public_url(url: str) -> str:
    candidate = (url or "").strip()
    parsed = urlparse(candidate)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("仅支持 http/https 的公开网页地址")
    return candidate


class _HtmlToMarkdownParser(HTMLParser):
    BLOCK_TAGS = {
        "article", "section", "main", "div", "p", "ul", "ol", "li",
        "pre", "code", "blockquote", "table", "tr", "td", "th", "br",
        "h1", "h2", "h3", "h4", "h5", "h6",
    }
    SKIP_TAGS = {"script", "style", "noscript", "svg", "canvas", "iframe"}
    HEADING_TAGS = {"h1": "#", "h2": "##", "h3": "###", "h4": "####", "h5": "#####", "h6": "######"}

    def __init__(self) -> None:
        super().__init__()
        self._skip_depth = 0
        self._current_tag = ""
        self._title_parts: list[str] = []
        self._pieces: list[str] = []
        self._list_stack: list[str] = []

    @property
    def title(self) -> str:
        title = "".join(self._title_parts)
        return re.sub(r"\s+", " ", title).strip()

    @property
    def markdown(self) -> str:
        text = "".join(self._pieces)
        text = re.sub(r"\n{3,}", "\n\n", text)
        lines = [line.rstrip() for line in text.splitlines()]
        return "\n".join(lines).strip()

    def handle_starttag(self, tag: str, attrs) -> None:
        tag = tag.lower()
        self._current_tag = tag
        if tag in self.SKIP_TAGS:
            self._skip_depth += 1
            return
        if self._skip_depth:
            return
        if tag in {"ul", "ol"}:
            self._list_stack.append(tag)
        elif tag == "li":
            prefix = "1. " if self._list_stack and self._list_stack[-1] == "ol" else "- "
            self._pieces.append(f"\n{prefix}")
        elif tag in self.HEADING_TAGS:
            self._pieces.append(f"\n{self.HEADING_TAGS[tag]} ")
        elif tag == "br":
            self._pieces.append("\n")
        elif tag in {"p", "div", "section", "article", "main", "table", "tr", "pre", "blockquote"}:
            self._pieces.append("\n")

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in self.SKIP_TAGS:
            self._skip_depth = max(0, self._skip_depth - 1)
            return
        if self._skip_depth:
            return
        if tag in {"ul", "ol"} and self._list_stack:
            self._list_stack.pop()
        if tag in self.BLOCK_TAGS:
            self._pieces.append("\n")
        self._current_tag = ""

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        text = re.sub(r"\s+", " ", data)
        if not text.strip():
            return
        if self._current_tag == "title":
            self._title_parts.append(text)
            return
        self._pieces.append(text)


def parse_url_to_markdown(url: str, timeout: int = 15) -> tuple[str, str]:
    valid_url = validate_public_url(url)
    request = Request(
        valid_url,
        headers={
            "User-Agent": "DocStruct/1.0 (+https://localhost/docstruct)",
            "Accept": "text/html,application/xhtml+xml",
        },
    )

    try:
        with urlopen(request, timeout=timeout) as response:
            content_type = response.headers.get("Content-Type", "")
            if "html" not in content_type.lower():
                raise RuntimeError(f"URL 响应不是 HTML 页面: {content_type or 'unknown'}")

            raw = response.read()
            charset = response.headers.get_content_charset() or "utf-8"
    except Exception as exc:
        raise RuntimeError(f"抓取网页失败: {exc}") from exc

    try:
        html = raw.decode(charset, errors="ignore")
    except Exception as exc:
        raise RuntimeError(f"网页内容解码失败: {exc}") from exc

    parser = _HtmlToMarkdownParser()
    parser.feed(html)
    parser.close()

    title = parser.title or urlparse(valid_url).netloc
    body = parser.markdown
    if not body:
        raise RuntimeError("网页正文为空，无法提取有效内容")

    markdown = f"# {title}\n\n来源 URL: {valid_url}\n\n{body}".strip()
    return title, markdown

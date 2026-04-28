import re

JSON_FORMAT_INSTRUCTION = "只返回合法 JSON。不要 Markdown，不要注释。JSON key 必须使用 schema 中的英文 key。"

# 共享正则模式 —— parser.py 与 docling_parser.py 共用
HEADING_MARKDOWN_PATTERN = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
TABLE_ROW_PATTERN = re.compile(r"^\s*\|.*\|\s*$")
TABLE_SEPARATOR_PATTERN = re.compile(r"^\s*\|?\s*:?-{3,}:?\s*(?:\|\s*:?-{3,}:?\s*)+\|?\s*$")

SYSTEM_PROMPT = """
你是严谨的软件工程文档结构化抽取专家。
请严格遵循用户提供的 JSON Schema 和抽取上下文。
只返回一个合法 JSON 对象，不要输出 Markdown、注释或解释。
不要编造原文没有的信息，不要输出 schema 未定义的字段。
"""

MAP_USER_PROMPT_TEMPLATE = """
请根据给定 JSON Schema，从当前输入分块中抽取结构化信息。
当前分块包含 [ELEMENT: element_id page=n] 标记；只能使用当前分块元数据允许的元素 ID。
只抽取当前分块中明确出现的对象；没有内容的对象槽返回空列表。

输入:
{content}

Schema:
{schema}

{json_instruction}
"""


DEFAULT_EXTRACTION_THRESHOLD = 6000
DEFAULT_EXTRACTION_CHUNK_MAX_CHARS = 5000
DEFAULT_EXTRACTION_CHUNK_OVERLAP_CHARS = 200
DEFAULT_EXTRACTION_MAX_CHARS = 100000
DEFAULT_EXTRACTION_CONCURRENCY = 3

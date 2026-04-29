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
严格遵循输入文档的实际文本内容：不要根据领域知识推断或补充文档未提及的对象、编号、指标或特性。
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

# === Phase 0 Pre-scan Prompts ===

PHASE0_SYSTEM_PROMPT = """
你是文档预分析专家。快速扫描文档采样片段，输出 JSON 元信息。
只输出合法 JSON，不要 Markdown、注释或解释。
"""

PHASE0_USER_PROMPT_TEMPLATE = """
请分析以下文档采样（开头、中间、结尾片段），输出文档元信息。

文档采样：
{content}

输出 JSON 格式：
{{
  "doc_type": "srs|api|design|test|manual|issue|unknown",
  "doc_type_confidence": 0.0-1.0,
  "key_entities": ["文档中出现的系统/角色/数据名称"],
  "section_themes": {{"章节路径": "该章节主要讨论什么"}},
  "extraction_hints": ["针对本文档的提取注意事项"]
}}

规则：
- doc_type 基于文档标题和内容特征判断
- key_entities 只列文档明确提及的实体名
- section_themes 每个章节一句话概括
- extraction_hints 列出提取时需注意的特殊情况（如"本文档的接口定义在第3章"）
"""

DEFAULT_EXTRACTION_THRESHOLD = 6000
DEFAULT_EXTRACTION_CHUNK_MAX_CHARS = 5000
DEFAULT_EXTRACTION_CHUNK_OVERLAP_CHARS = 200
DEFAULT_EXTRACTION_MAX_CHARS = 100000
DEFAULT_EXTRACTION_CONCURRENCY = 3
DEFAULT_LLM_MAX_TOKENS = 16384

DEFAULT_PHASE0_MAX_SAMPLE_CHARS = 6000

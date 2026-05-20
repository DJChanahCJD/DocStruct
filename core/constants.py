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

SUMMARY_USER_PROMPT_TEMPLATE = """
请为以下软件工程文档生成“结构化抽取上下文摘要”，用于后续分块抽取时理解全局语境。

要求：
- 只概括原文明确出现的信息，不要补充外部知识。
- 覆盖文档目标、核心系统/模块/接口/数据对象、关键章节分布、术语/缩写/命名约定和主要约束。
- 不要输出结构化抽取结果，不要生成对象 ID，不要生成 evidence_element_ids。
- 摘要只作为背景上下文，不能作为后续结构化对象存在或证据引用的依据。
- 使用中文，控制在 300-500 字。
- 只输出摘要正文，不要 Markdown 标题或列表。

文档大纲:
{outline}

文档内容:
{content}
"""

DEFAULT_EXTRACTION_THRESHOLD = 6000
DEFAULT_EXTRACTION_CHUNK_MAX_CHARS = 5000
DEFAULT_EXTRACTION_CHUNK_OVERLAP_CHARS = 300
DEFAULT_EXTRACTION_MAX_CHARS = 100000
DEFAULT_EXTRACTION_CONCURRENCY = 3
DEFAULT_LLM_MAX_TOKENS = 16384

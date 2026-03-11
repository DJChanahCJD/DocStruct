import json
import ast
import re
from typing import Any, Dict

def clean_and_parse_json(text: str) -> Dict[str, Any]:
    """
    清洗并解析 LLM 返回的 JSON 字符串。
    能够处理标准 JSON、Markdown 代码块包裹的 JSON 以及 Python 字典格式（单引号）。
    """
    if not text:
        raise ValueError("Input text is empty")

    # 1. 去除 Markdown 代码块标记 (```json ... ```)
    # 匹配 ```json 或 ``` 开头，到 ``` 结尾的内容
    # 使用 re.DOTALL 使 . 匹配换行符
    markdown_pattern = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL | re.IGNORECASE)
    match = markdown_pattern.search(text)
    if match:
        text = match.group(1)

    text = text.strip()

    # 2. 尝试标准 JSON 解析
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # 3. 尝试解析 Python 字典格式 (处理单引号问题)
    try:
        # ast.literal_eval 安全地评估表达式节点或字符串
        # 它只能处理字面量结构 (strings, bytes, numbers, tuples, lists, dicts, sets, booleans, and None)
        parsed = ast.literal_eval(text)
        if isinstance(parsed, dict):
            return parsed
    except (ValueError, SyntaxError):
        pass

    # 4. 如果都失败了，抛出包含原始内容的异常，便于调试
    raise ValueError(f"Failed to parse JSON from text: {text[:200]}...")

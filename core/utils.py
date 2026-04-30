import json
import ast
import re
from typing import Any

from pydantic import BaseModel

def _repair_truncated_json(text: str) -> str:
    """尝试修复被截断的 JSON：删除不完整片段并补齐缺失的闭合括号。"""
    stripped = text.rstrip()

    # 检查是否在未闭合的字符串中
    in_string = False
    for i, ch in enumerate(stripped):
        if ch == '"' and (i == 0 or stripped[i - 1] != '\\'):
            in_string = not in_string

    if in_string:
        # 末尾字符串被截断，回溯到最后一个安全的结构边界
        last_comma = stripped.rfind(',')
        last_open = max(stripped.rfind('{'), stripped.rfind('['))
        if last_comma > last_open:
            stripped = stripped[:last_comma]
        else:
            stripped = stripped[:last_open + 1]

    # 遍历整个字符串追踪括号开启顺序，按 LIFO 顺序补齐闭合
    bracket_stack: list[str] = []
    in_string = False
    for i, ch in enumerate(stripped):
        if ch == '"' and (i == 0 or stripped[i - 1] != '\\'):
            in_string = not in_string
        elif not in_string:
            if ch == '{':
                bracket_stack.append('}')
            elif ch == '[':
                bracket_stack.append(']')
            elif ch in ('}', ']'):
                if bracket_stack and bracket_stack[-1] == ch:
                    bracket_stack.pop()

    stripped += ''.join(reversed(bracket_stack))
    return stripped


def clean_and_parse_json(text: str) -> dict[str, Any]:
    """
    清洗并解析 LLM 返回的 JSON 字符串。
    能够处理标准 JSON、Markdown 代码块包裹的 JSON、Python 字典格式（单引号）、以及截断的 JSON。
    """
    if not text:
        raise ValueError("Input text is empty")

    # 1. 去除 Markdown 代码块标记 (```json ... ```)
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

    # 3. 尝试修复截断的 JSON
    try:
        repaired = _repair_truncated_json(text)
        return json.loads(repaired)
    except (json.JSONDecodeError, ValueError):
        pass

    # 4. 尝试解析 Python 字典格式 (处理单引号问题)
    try:
        parsed = ast.literal_eval(text)
        if isinstance(parsed, dict):
            return parsed
    except (ValueError, SyntaxError, TypeError):
        pass

    # 5. 如果都失败了，抛出包含原始内容的异常，便于调试
    raise ValueError(f"Failed to parse JSON from text: {text[:200]}...")


def normalize_extracted_data(value: Any) -> Any:
    """
    递归归一化提取结果：
    - 字符串去首尾空白
    - 容器类型递归处理
    """
    if isinstance(value, str):
        return value.strip()

    if isinstance(value, list):
        return [normalize_extracted_data(item) for item in value]

    if isinstance(value, dict):
        result = {}
        for key, val in value.items():
            result[key] = normalize_extracted_data(val)
        return result

    return value


def dump_extracted_document(document: BaseModel) -> dict[str, Any]:
    """序列化结构化抽取结果，并统一把 evidence 放到 JSON 末尾。"""
    payload = document.model_dump(mode="json")
    evidence = payload.pop("evidence", None)
    if evidence is not None:
        payload["evidence"] = evidence
    return payload


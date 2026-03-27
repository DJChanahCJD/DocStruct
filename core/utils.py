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
        return {key: normalize_extracted_data(val) for key, val in value.items()}

    return value


def _merge_scalar_value(existing: Any, incoming: Any) -> Any:
    if existing in (None, "", [], {}):
        return incoming
    if incoming in (None, "", [], {}):
        return existing

    if isinstance(existing, str) and isinstance(incoming, str):
        return incoming if len(incoming.strip()) > len(existing.strip()) else existing

    return existing


def _dict_identity(item: Dict[str, Any]) -> str:
    method = item.get("method")
    path = item.get("path")
    if method and path:
        return f"method_path::{str(method).upper()}::{path}"

    for key in ("id", "path", "name", "title", "problem"):
        if item.get(key):
            return f"{key}::{item[key]}"

    return f"raw::{json.dumps(item, ensure_ascii=False, sort_keys=True)}"


def _merge_dicts(existing: Dict[str, Any], incoming: Dict[str, Any]) -> Dict[str, Any]:
    merged = dict(existing)
    for key, incoming_value in incoming.items():
        if key not in merged:
            merged[key] = incoming_value
            continue

        existing_value = merged[key]

        if isinstance(existing_value, dict) and isinstance(incoming_value, dict):
            merged[key] = _merge_dicts(existing_value, incoming_value)
        elif isinstance(existing_value, list) and isinstance(incoming_value, list):
            merged[key] = _merge_lists(existing_value, incoming_value)
        else:
            merged[key] = _merge_scalar_value(existing_value, incoming_value)

    return merged


def _merge_lists(existing: list[Any], incoming: list[Any]) -> list[Any]:
    if not existing:
        return incoming
    if not incoming:
        return existing

    # 字典列表按关键字段去重并合并
    if all(isinstance(item, dict) for item in existing + incoming):
        merged_map: Dict[str, Dict[str, Any]] = {}
        for item in existing + incoming:
            identity = _dict_identity(item)
            if identity in merged_map:
                merged_map[identity] = _merge_dicts(merged_map[identity], item)
            else:
                merged_map[identity] = dict(item)
        return list(merged_map.values())

    # 标量列表去重
    seen = set()
    result = []
    for item in existing + incoming:
        marker = json.dumps(item, ensure_ascii=False, sort_keys=True) if isinstance(item, (dict, list)) else str(item)
        if marker in seen:
            continue
        seen.add(marker)
        result.append(item)
    return result


def merge_extraction_results(results: list[Dict[str, Any]]) -> Dict[str, Any]:
    """
    合并多个 chunk 的抽取结果：
    - 列表字段拼接去重
    - 字典字段递归合并
    - 标量字段保留信息量更高的值（例如更长文本）
    """
    merged: Dict[str, Any] = {}

    for result in results:
        if not isinstance(result, dict):
            continue
        for key, incoming_value in result.items():
            if incoming_value in (None, "", [], {}):
                continue

            if key not in merged:
                merged[key] = incoming_value
                continue

            existing_value = merged[key]
            if isinstance(existing_value, dict) and isinstance(incoming_value, dict):
                merged[key] = _merge_dicts(existing_value, incoming_value)
            elif isinstance(existing_value, list) and isinstance(incoming_value, list):
                merged[key] = _merge_lists(existing_value, incoming_value)
            else:
                merged[key] = _merge_scalar_value(existing_value, incoming_value)

    return normalize_extracted_data(merged)

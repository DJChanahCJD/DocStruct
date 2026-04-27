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
    except (ValueError, SyntaxError, TypeError):
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
        result = {}
        for key, val in value.items():
            result[key] = normalize_extracted_data(val)
        return result

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


def _clean_empty_values(data: Any) -> Any:
    """
    清理空值：
    - ""、仅空白字符串转为 None
    - 空列表 [] 和 空字典 {} 会被删除
    我们只递归清理 dict 和 list，遇到空值直接删除该 key。
    """
    if isinstance(data, dict):
        cleaned = {}
        for k, v in data.items():
            val = _clean_empty_values(v)
            if val not in (None, "", [], {}):
                cleaned[k] = val
        return cleaned
    elif isinstance(data, list):
        cleaned = []
        for item in data:
            val = _clean_empty_values(item)
            if val not in (None, "", [], {}):
                cleaned.append(val)
        return cleaned
    elif isinstance(data, str):
        s = data.strip()
        return s if s else None
    return data


def _deduplicate_requirements(requirements: list[Dict[str, Any]]) -> list[Dict[str, Any]]:
    """优先按 source_id/id，无标识时按 name + description + requirement_type 归一。"""
    seen_ids = set()
    seen_texts = set()
    result = []
    
    for req in requirements:
        req_id = req.get("source_id") or req.get("id", "")
        if req_id:
            if req_id in seen_ids:
                continue
            seen_ids.add(req_id)
            result.append(req)
            continue
            
        # 无 id 情况
        name = req.get("name", "")
        desc = req.get("description", "")
        req_type = req.get("requirement_type", "other")
        
        # 用 name + desc + type 作为去重 key
        text_key = f"{name}::{desc}::{req_type}"
        if text_key in seen_texts:
            continue
        seen_texts.add(text_key)
        result.append(req)
        
    return result


def _filter_invalid_artifacts(artifacts: list[Dict[str, Any]]) -> list[Dict[str, Any]]:
    """过滤纯术语、缩写、普通名词表项；对无 artifact_type 且无明确文档/接口/测试产物特征的条目丢弃"""
    valid = []
    for art in artifacts:
        art_type = art.get("artifact_type", "other")
        name = art.get("name", "")
        desc = art.get("description", "")
        
        if art_type == "other" and len(name) < 20 and len(desc) < 30:
            # 可能是普通术语、缩写，丢弃
            continue
        valid.append(art)
    return valid


def _stabilize_requirement_type(req: Dict[str, Any]) -> str:
    """基于标题、措辞二次修正 requirement_type"""
    current_type = req.get("requirement_type", "other")
    if current_type != "other":
        return current_type
        
    name = req.get("name", "")
    desc = req.get("description", "")
    text = f"{name} {desc}".lower()
    
    if any(k in text for k in ("性能", "可靠性", "安全性", "并发", "响应时间", "performance", "security", "非功能")):
        return "non_functional"
    if any(k in text for k in ("应", "必须", "支持", "能够", "功能", "functional", "shall", "must", "should")):
        return "functional"
    
    return "other"


def finalize_merged_result(metadata: Dict[str, Any], chunk_results: list[Dict[str, Any]]) -> Dict[str, Any]:
    """
    统一做清洗、归一化、去重，再组装为最终的数据字典。
    """
    # 1. 组合 chunk 结果
    merged_chunks = merge_extraction_results(chunk_results)
    
    # 2. 空值处理
    cleaned = _clean_empty_values(merged_chunks) or {}
    
    # 3. 具体对象列表的清洗归一化
    if "requirements" in cleaned and isinstance(cleaned["requirements"], list):
        reqs = []
        for req in cleaned["requirements"]:
            req["requirement_type"] = _stabilize_requirement_type(req)
            reqs.append(req)
            
        cleaned["requirements"] = _deduplicate_requirements(reqs)
        
    if "artifacts" in cleaned and isinstance(cleaned["artifacts"], list):
        cleaned["artifacts"] = _filter_invalid_artifacts(cleaned["artifacts"])
        
    # 4. 覆盖 metadata 字段（文档级字段仅来自阶段 A）
    # metadata 中的字段如 title, doc_type 优先级最高
    for key, value in metadata.items():
        if value not in (None, "", [], {}):
            cleaned[key] = value
            
    return cleaned

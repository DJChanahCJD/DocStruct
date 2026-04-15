from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any

from openai import OpenAI

from core.config import get_settings


@dataclass(frozen=True)
class TextModelSpec:
    """描述一个受控文本模型及其透明调用参数。"""

    id: str
    label: str
    description: str
    extra_body: dict[str, Any] = field(default_factory=dict)
    is_default: bool = False


# 分类任务专用模型：固定低成本、文档理解专用，与用户选择的提取模型解耦
CLASSIFY_MODEL_ID = "qwen-doc-turbo"

_PREDEFINED_TEXT_MODELS: tuple[TextModelSpec, ...] = (
    TextModelSpec(
        id="qwen-doc-turbo",
        label="Qwen Doc Turbo",
        description="当前默认的文档理解模型，适合作为通用基线。",
    ),
    TextModelSpec(
        id="kimi-k2.5",
        label="Kimi K2.5",
        description="适合长文本理解与格式化输出的通用文本模型。",
    ),
    TextModelSpec(
        id="deepseek-v3.2",
        label="DeepSeek V3.2",
        description="DeepSeek V3.2 模型",
    ),
    TextModelSpec(
        id="glm-4.7",
        label="GLM-4.7",
        description="GLM-4.7 模型",
    ),
    TextModelSpec(
        id="MiniMax-M2.5",
        label="MiniMax-M2.5",
        description="MiniMax-M2.5 模型",
    ),
)


@lru_cache(maxsize=1)
def get_openai_client() -> OpenAI:
    """返回复用的 OpenAI 兼容客户端，避免重复初始化。"""
    settings = get_settings()
    return OpenAI(api_key=settings.llm_api_key, base_url=settings.llm_base_url)


@lru_cache(maxsize=1)
def get_text_model_catalog() -> tuple[TextModelSpec, ...]:
    """构建文本模型白名单，并标记当前默认模型。"""
    settings = get_settings()
    default_model_id = settings.llm_model
    catalog: list[TextModelSpec] = []
    matched_default = False

    for spec in _PREDEFINED_TEXT_MODELS:
        is_default = spec.id == default_model_id
        matched_default = matched_default or is_default
        catalog.append(
            TextModelSpec(
                id=spec.id,
                label=spec.label,
                description=spec.description,
                extra_body=dict(spec.extra_body),
                is_default=is_default,
            )
        )

    if not matched_default:
        catalog.insert(
            0,
            TextModelSpec(
                id=default_model_id,
                label=f"{default_model_id}（默认）",
                description="来自环境变量 LLM_MODEL 的默认文本模型。",
                is_default=True,
            ),
        )

    return tuple(catalog)


def get_default_text_model() -> TextModelSpec:
    """返回当前环境下的默认文本模型。"""
    return next(spec for spec in get_text_model_catalog() if spec.is_default)



def resolve_text_model(model_id: str | None) -> TextModelSpec:
    """解析活动文本模型；为空时回退到默认模型。"""
    normalized_model_id = (model_id or "").strip()
    if not normalized_model_id:
        return get_default_text_model()

    for spec in get_text_model_catalog():
        if spec.id == normalized_model_id:
            return spec

    raise ValueError(f"不支持的文本模型: {model_id}")



def list_text_models() -> list[dict[str, Any]]:
    """返回可直接暴露给前端的文本模型列表。"""
    return [
        {
            "id": spec.id,
            "label": spec.label,
            "description": spec.description,
            "is_default": spec.is_default,
        }
        for spec in get_text_model_catalog()
    ]



def build_chat_completion_kwargs(
    llm_model: str | None,
    *,
    messages: list[dict[str, Any]],
    temperature: float,
) -> dict[str, Any]:
    """根据模型注册表生成统一的 Chat Completion 参数。"""
    model_spec = resolve_text_model(llm_model)
    payload: dict[str, Any] = {
        "model": model_spec.id,
        "messages": messages,
        "temperature": temperature,
    }
    if model_spec.extra_body:
        payload["extra_body"] = dict(model_spec.extra_body)
    return payload

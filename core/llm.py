from __future__ import annotations

from functools import lru_cache
from typing import Any

from openai import OpenAI

from core.config import get_settings


@lru_cache(maxsize=1)
def get_openai_client() -> OpenAI:
    settings = get_settings()
    return OpenAI(api_key=settings.llm_api_key, base_url=settings.llm_base_url)


def build_chat_completion_kwargs(
    *,
    messages: list[dict[str, Any]],
    temperature: float,
) -> dict[str, Any]:
    settings = get_settings()
    return {
        "model": settings.llm_model,
        "messages": messages,
        "temperature": temperature,
    }

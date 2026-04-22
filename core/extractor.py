from __future__ import annotations

import asyncio
import json
import logging

from pydantic import BaseModel

from core.chunker import split_markdown_into_chunks
from core.config import get_settings
from core.constants import EXTRACT_PROMPT_TEMPLATE, JSON_FORMAT_INSTRUCTION
from core.llm import build_chat_completion_kwargs, get_openai_client
from core.utils import clean_and_parse_json, merge_extraction_results, normalize_extracted_data


logger = logging.getLogger(__name__)
settings = get_settings()
raw_client = get_openai_client()


def _json_schema_text(model: type[BaseModel]) -> str:
    return json.dumps(model.model_json_schema(), ensure_ascii=False, indent=2)


def _render_prompt(template: str, **kwargs: str) -> str:
    rendered = template
    for key, value in kwargs.items():
        rendered = rendered.replace(f"{{{key}}}", value)
    return rendered


def _create_text_completion(
    messages: list[dict[str, str]],
    *,
    temperature: float,
) -> str:
    response = raw_client.chat.completions.create(
        **build_chat_completion_kwargs(
            messages=messages,
            temperature=temperature,
        )
    )
    return response.choices[0].message.content or ""


def _extract_once(
    content: str,
    response_model: type[BaseModel],
    *,
    context_note: str | None = None,
) -> dict[str, object]:
    prompt_content = content
    if context_note:
        prompt_content = f"[Context]\n{context_note}\n\n[Document Chunk]\n{content}"

    prompt = _render_prompt(
        EXTRACT_PROMPT_TEMPLATE,
        content=prompt_content,
        schema=_json_schema_text(response_model),
        json_instruction=JSON_FORMAT_INSTRUCTION,
    )
    response_text = _create_text_completion(
        messages=[
            {"role": "system", "content": "你是一个严谨的文档提取专家，只输出符合 Schema 的 JSON 数据。"},
            {"role": "user", "content": prompt},
        ],
        temperature=0.0,
    )
    data = clean_and_parse_json(response_text)
    return normalize_extracted_data(data)


async def _extract_chunk(
    semaphore: asyncio.Semaphore,
    chunk_text: str,
    response_model: type[BaseModel],
    *,
    context_note: str | None = None,
) -> dict[str, object]:
    async with semaphore:
        return await asyncio.to_thread(
            _extract_once,
            chunk_text,
            response_model,
            context_note=context_note,
        )


async def extract_structure_with_meta(
    markdown_content: str,
    response_model: type[BaseModel],
) -> tuple[BaseModel, dict[str, object]]:
    logger.info("Extracting structure for %s", response_model.__name__)
    content_length = len(markdown_content)

    if content_length > settings.extraction_max_chars:
        raise ValueError(
            f"文档长度为 {content_length} 字符，超过系统上限 {settings.extraction_max_chars}。"
            "当前系统仅面向中短文档。"
        )

    if content_length <= settings.extraction_threshold:
        data = await asyncio.to_thread(_extract_once, markdown_content, response_model)
        validated = response_model.model_validate(data)
        return validated, {"mode": "single", "chunk_count": 1}

    chunks = split_markdown_into_chunks(
        markdown_text=markdown_content,
        max_chars=settings.extraction_chunk_max_chars,
        overlap_chars=settings.extraction_chunk_overlap_chars,
    )
    if not chunks:
        raise ValueError("文档分块失败，无法继续提取")

    semaphore = asyncio.Semaphore(max(1, settings.extraction_concurrency))
    tasks = [
        _extract_chunk(
            semaphore,
            chunk.text,
            response_model,
            context_note=f"title_path={' > '.join(chunk.title_path) if chunk.title_path else '(no-heading)'}",
        )
        for chunk in chunks
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    partial_results: list[dict[str, object]] = []
    failed_chunks = 0
    for result in results:
        if isinstance(result, Exception):
            failed_chunks += 1
            logger.warning("Chunk extraction failed: %s", result)
            continue
        partial_results.append(result)

    if failed_chunks > 0:
        raise RuntimeError(f"分块提取失败，失败块数: {failed_chunks}/{len(chunks)}")
    if not partial_results:
        raise RuntimeError("分块提取失败，未返回有效结果")

    merged = merge_extraction_results(partial_results)
    validated = response_model.model_validate(merged)
    return validated, {
        "mode": "chunked",
        "chunk_count": len(chunks),
        "failed_chunks": failed_chunks,
    }


def extract_structure(markdown_content: str, response_model: type[BaseModel]) -> BaseModel:
    extracted, _ = asyncio.run(extract_structure_with_meta(markdown_content, response_model))
    return extracted

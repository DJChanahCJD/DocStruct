import logging
import json

from pydantic import BaseModel

from core.chunker import split_markdown_into_chunks
from core.config import get_settings
from core.constants import (
    CLASSIFY_PROMPT_TEMPLATE,
    DOC_TYPE_DESCRIPTIONS,
    EXTRACT_PROMPT_TEMPLATE,
    JSON_FORMAT_INSTRUCTION,
)
from core.text_models import build_chat_completion_kwargs, get_openai_client, resolve_text_model, CLASSIFY_MODEL_ID
from core.utils import clean_and_parse_json, merge_extraction_results, normalize_extracted_data
from schemas.models import DocClassification, DocType

logger = logging.getLogger(__name__)
settings = get_settings()

if not settings.llm_api_key:
    logger.warning("Warning: LLM_API_KEY not found in environment variables.")

raw_client = get_openai_client()


def _json_schema_text(model: type[BaseModel]) -> str:
    """将 Pydantic JSON Schema 序列化为 prompt 可注入文本。"""
    return json.dumps(model.model_json_schema(), ensure_ascii=False, indent=2)


def _render_doc_type_categories() -> str:
    """渲染文档类型说明，避免分类 prompt 与 DocType 分散维护。"""
    return "\n".join(f"{doc_type}: {description}" for doc_type, description in DOC_TYPE_DESCRIPTIONS.items())


def _render_prompt(template: str, **kwargs) -> str:
    """仅替换显式占位符，避免 JSON 示例中的花括号被误解析。"""
    rendered = template
    for key, value in kwargs.items():
        rendered = rendered.replace(f"{{{key}}}", str(value))
    return rendered



def _create_text_completion(
    messages: list[dict[str, str]],
    *,
    temperature: float,
    llm_model: str | None = None,
) -> str:
    """按指定文本模型执行一次非流式补全，并返回文本内容。"""
    model_spec = resolve_text_model(llm_model)
    response = raw_client.chat.completions.create(
        **build_chat_completion_kwargs(
            llm_model=model_spec.id,
            messages=messages,
            temperature=temperature,
        )
    )
    return response.choices[0].message.content or ""



def _extract_once(
    content: str,
    response_model: type[BaseModel],
    context_note: str | None = None,
    llm_model: str | None = None,
    prompt_override: str | None = None,
) -> dict[str, object]:

    """执行单次结构化提取并返回归一化后的 JSON 数据。

    prompt_override: 若提供，则用该模板替换默认 EXTRACT_PROMPT_TEMPLATE，
    模板需包含 {content}、{schema}、{json_instruction} 占位符。
    """
    prompt_content = content
    if context_note:
        prompt_content = f"[Context]\n{context_note}\n\n[Document Chunk]\n{content}"

    template = prompt_override if prompt_override is not None else EXTRACT_PROMPT_TEMPLATE
    prompt = _render_prompt(
        template,
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
        llm_model=llm_model,
    )

    logger.info("--- Raw LLM Response (Extraction) ---\n%s\n----------------------------------", response_text)
    data = clean_and_parse_json(response_text)
    return normalize_extracted_data(data)



def classify_document(markdown_content: str, llm_model: str | None = None) -> DocClassification:
    """使用固定分类模型（qwen-doc-turbo）对文档进行快速分类。

    llm_model 参数保留以兼容调用方签名，但分类任务始终使用 CLASSIFY_MODEL_ID，
    原因：分类只需文档前 2000 字符，qwen-doc-turbo 性价比最高且专为文档理解设计。
    """
    model_spec = resolve_text_model(CLASSIFY_MODEL_ID)
    summary = markdown_content[:2000]
    prompt = _render_prompt(
        CLASSIFY_PROMPT_TEMPLATE,
        summary=summary,
        categories=_render_doc_type_categories(),
        schema=_json_schema_text(DocClassification),
        json_instruction=JSON_FORMAT_INSTRUCTION,
    )

    try:
        logger.info("--- Classifying document using %s ---", model_spec.id)
        response_text = _create_text_completion(
            messages=[
                {"role": "system", "content": "你是一个资深的软件文档分类专家。"},
                {"role": "user", "content": prompt},
            ],
            temperature=0.0,
            llm_model=model_spec.id,
        )
        logger.info("--- Raw LLM Response (Classification) ---\n%s\n--------------------------------------", response_text)
        data = clean_and_parse_json(response_text)
        return DocClassification.model_validate(data)
    except Exception as exc:
        logger.error("Classification failed: %s", exc, exc_info=True)
        return DocClassification(
            doc_type=DocType.UNKNOWN,
            confidence=0.0,
            reasoning=f"Error: {str(exc)}",
        )



def extract_structure(
    markdown_content: str,
    response_model: type[BaseModel],
    llm_model: str | None = None,
    prompt_override: str | None = None,
) -> BaseModel:
    """使用活动文本模型从 Markdown 内容中提取结构化数据。"""
    extracted, _ = extract_structure_with_meta(
        markdown_content, response_model, llm_model=llm_model, prompt_override=prompt_override
    )
    return extracted



def extract_structure_with_meta(
    markdown_content: str,
    response_model: type[BaseModel],
    llm_model: str | None = None,
    prompt_override: str | None = None,
) -> tuple[BaseModel, dict[str, object]]:

    """按指定文本模型执行结构化提取，并返回提取元信息。

    prompt_override: 若提供，则用该模板替换默认 EXTRACT_PROMPT_TEMPLATE。
    """
    logger.info("--- Extracting structure for %s ---", response_model.__name__)

    threshold = settings.extraction_threshold
    if len(markdown_content) <= threshold:
        try:
            data = _extract_once(
                markdown_content[: settings.extraction_single_max_chars],
                response_model,
                llm_model=llm_model,
                prompt_override=prompt_override,
            )
            validated = response_model.model_validate(data)
            return validated, {"mode": "single", "chunk_count": 1, "failed_chunks": 0, "fallback_used": False}
        except Exception as exc:
            logger.error("Single extraction failed: %s", exc, exc_info=True)
            raise RuntimeError(f"LLM Extraction failed: {str(exc)}")

    chunks = split_markdown_into_chunks(
        markdown_text=markdown_content,
        max_chars=settings.extraction_chunk_max_chars,
        overlap_chars=settings.extraction_chunk_overlap_chars,
    )
    if not chunks:
        try:
            data = _extract_once(
                markdown_content[: settings.extraction_single_max_chars],
                response_model,
                llm_model=llm_model,
                prompt_override=prompt_override,
            )
            validated = response_model.model_validate(data)
            return validated, {"mode": "single", "chunk_count": 1, "failed_chunks": 0, "fallback_used": False}
        except Exception as exc:
            logger.error("Extraction failed on empty chunk fallback: %s", exc, exc_info=True)
            raise RuntimeError(f"LLM Extraction failed: {str(exc)}")

    partial_results = []
    failed_chunks = 0

    for chunk in chunks:
        context_note = f"heading_path={' > '.join(chunk.heading_path) if chunk.heading_path else '(no-heading)'}"
        try:
            data = _extract_once(
                chunk.text,
                response_model,
                context_note=context_note,
                llm_model=llm_model,
                prompt_override=prompt_override,
            )
            partial_results.append(data)
        except Exception as exc:
            failed_chunks += 1
            logger.warning("Chunk extraction failed at index=%s: %s", chunk.index, exc)

    if partial_results:
        try:
            merged = merge_extraction_results(partial_results)
            validated = response_model.model_validate(merged)
            return validated, {
                "mode": "chunked",
                "chunk_count": len(chunks),
                "failed_chunks": failed_chunks,
                "fallback_used": False,
            }
        except Exception as exc:
            logger.warning("Merged chunk validation failed, fallback to single extraction: %s", exc)

    try:
        fallback_data = _extract_once(
            markdown_content[: settings.extraction_single_max_chars],
            response_model,
            llm_model=llm_model,
            prompt_override=prompt_override,
        )
        validated = response_model.model_validate(fallback_data)
        return validated, {
            "mode": "single_fallback",
            "chunk_count": len(chunks),
            "failed_chunks": failed_chunks,
            "fallback_used": True,
        }
    except Exception as exc:
        logger.error("Extraction failed after fallback: %s", exc, exc_info=True)
        raise RuntimeError(f"LLM Extraction failed: {str(exc)}")


def re_extract_with_instruction(
    parsed_content: str,
    response_model: type[BaseModel],
    scope: str,
    field_key: str | None = None,
    instruction: str | None = None,
    llm_model: str | None = None,
) -> dict[str, object]:
    """人在环中的重新提取入口。

    - scope='full'：在原 system prompt 末尾追加 instruction，复用完整提取流程。
    - scope='field'：构造轻量 prompt 仅提取目标字段，返回 {field_key: value}。

    两个分支均不写库，结果直接返回给调用方。
    """
    if scope == "full":
        # 在 system prompt 中追加补充指示，其余复用完整提取流程
        extra = f"\n\n# 用户补充指示\n{instruction}" if instruction else ""
        prompt = _render_prompt(
            EXTRACT_PROMPT_TEMPLATE,
            content=parsed_content[: settings.extraction_single_max_chars],
            schema=_json_schema_text(response_model),
            json_instruction=JSON_FORMAT_INSTRUCTION + extra,
        )
        system_msg = "你是一个严谨的文档提取专家，只输出符合 Schema 的 JSON 数据。"
        response_text = _create_text_completion(
            messages=[
                {"role": "system", "content": system_msg},
                {"role": "user", "content": prompt},
            ],
            temperature=0.0,
            llm_model=llm_model,
        )
        logger.info("--- Raw LLM Response (re-extract full) ---\n%s\n---", response_text)
        data = clean_and_parse_json(response_text)
        # 用 response_model 验证，确保结构合法，再返回 dict
        validated = response_model.model_validate(normalize_extracted_data(data))
        return validated.model_dump(mode="json")

    # scope == "field"
    instruction_part = f"\n{instruction}" if instruction else ""

    # 从完整 Schema 中提取目标字段的约束描述，注入 prompt 避免类型/枚举冲突
    import json as _json

    full_schema = response_model.model_json_schema()
    properties = full_schema.get("properties", {})
    field_schema_hint = ""
    if field_key and field_key in properties:
        hint_payload: dict = {field_key: properties[field_key]}
        defs = full_schema.get("$defs", {})
        if defs:
            hint_payload["$defs"] = defs  # 保留 $ref 展开所需的嵌套定义
        field_schema_hint = (
            f"\n\n# 字段 Schema 约束（必须严格遵守类型与枚举）\n"
            f"```json\n{_json.dumps(hint_payload, ensure_ascii=False, indent=2)}\n```"
        )

    field_prompt = (
        f"你是文档结构提取助手。\n"
        f"从以下文档中提取字段「{field_key}」的内容，"
        f'以 JSON 格式返回：{{"{field_key}": ...}}\n'
        f"{instruction_part}"
        f"{field_schema_hint}\n\n"
        f"{JSON_FORMAT_INSTRUCTION}\n\n"
        f"文档内容：\n{parsed_content[: settings.extraction_single_max_chars]}"
    )
    response_text = _create_text_completion(
        messages=[
            {"role": "system", "content": "你是一个严谨的文档提取专家，只输出 JSON 数据。"},
            {"role": "user", "content": field_prompt},
        ],
        temperature=0.0,
        llm_model=llm_model,
    )
    logger.info("--- Raw LLM Response (re-extract field=%s) ---\n%s\n---", field_key, response_text)
    data = clean_and_parse_json(response_text)
    if field_key not in data:
        raise ValueError(f"LLM 未返回字段 '{field_key}'，实际返回 keys: {list(data.keys())}")
    return {field_key: data[field_key]}


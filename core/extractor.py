import os
import instructor
import logging
from openai import OpenAI
from pydantic import BaseModel
from dotenv import load_dotenv
from schemas.models import DocClassification, DocType
from core.constants import CLASSIFY_PROMPT_TEMPLATE, EXTRACT_PROMPT_TEMPLATE, JSON_FORMAT_INSTRUCTION
from core.chunker import split_markdown_into_chunks
from core.utils import clean_and_parse_json, merge_extraction_results, normalize_extracted_data

# 加载环境变量
load_dotenv()

logger = logging.getLogger(__name__)

# 获取 LLM 配置
API_KEY = os.getenv("LLM_API_KEY")
BASE_URL = os.getenv("LLM_BASE_URL")
MODEL_NAME = os.getenv("LLM_MODEL", "qwen2.5-7b-instruct-1m") # 默认模型

if not API_KEY:
    # 仅作为警告，允许运行时再配置
    logger.warning("Warning: LLM_API_KEY not found in environment variables.")

# 初始化 OpenAI 客户端
# 分离原始客户端和 instructor 客户端，以便在需要时手动控制
raw_client = OpenAI(
    api_key=API_KEY,
    base_url=BASE_URL,
)

# 保留 instructor 客户端以便未来可能的高级用法
client = instructor.from_openai(
    raw_client,
    mode=instructor.Mode.JSON,
)


def _extract_once(content: str, response_model: type[BaseModel], context_note: str | None = None) -> dict:
    prompt_content = content
    if context_note:
        prompt_content = f"[Context]\n{context_note}\n\n[Document Chunk]\n{content}"

    prompt = EXTRACT_PROMPT_TEMPLATE.format(
        content=prompt_content,
        schema=response_model.model_json_schema(),
        json_instruction=JSON_FORMAT_INSTRUCTION
    )

    resp = raw_client.chat.completions.create(
        model=MODEL_NAME,
        messages=[
            {"role": "system", "content": "你是一个严谨的文档提取专家，只输出符合 Schema 的 JSON 数据。"},
            {"role": "user", "content": prompt},
        ],
        temperature=0.0,
    )

    content = resp.choices[0].message.content
    logger.info(f"--- Raw LLM Response (Extraction) ---\n{content}\n----------------------------------")
    data = clean_and_parse_json(content)
    return normalize_extracted_data(data)

def classify_document(markdown_content: str) -> DocClassification:
    """
    第一阶段：对文档进行分类。
    仅使用前 2000 个字符进行快速判断。
    
    Args:
        markdown_content (str): 文档全文 Markdown
        
    Returns:
        DocClassification: 分类结果
    """
    summary = markdown_content[:2000]
    
    # 使用常量构建提示词
    prompt = CLASSIFY_PROMPT_TEMPLATE.format(
        summary=summary,
        json_instruction=JSON_FORMAT_INSTRUCTION
    )
    
    try:
        # 使用原始 client 获取文本响应，配合 clean_and_parse_json 进行鲁棒解析
        logger.info(f"--- Classifying document using {MODEL_NAME} ---")
        resp = raw_client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": "你是一个资深的软件文档分类专家。"},
                {"role": "user", "content": prompt},
            ],
            temperature=0.0,
        )
        
        content = resp.choices[0].message.content
        logger.info(f"--- Raw LLM Response (Classification) ---\n{content}\n--------------------------------------")
        
        # 自定义数据清洗与解析
        data = clean_and_parse_json(content)
        # Pydantic 验证
        return DocClassification.model_validate(data)
        
    except Exception as e:
        logger.error(f"Classification failed: {e}", exc_info=True)
        # 降级处理：返回 unknown
        return DocClassification(
            doc_type=DocType.UNKNOWN, 
            confidence=0.0, 
            reasoning=f"Error: {str(e)}"
        )

def extract_structure(markdown_content: str, response_model: type[BaseModel]) -> BaseModel:
    """
    使用 LLM 从 Markdown 内容中提取结构化数据。
    
    Args:
        markdown_content (str): PDF 解析后的 Markdown 文本
        response_model (type[BaseModel]): 目标 Pydantic 模型类
        
    Returns:
        BaseModel: 填充好数据的模型实例
    """
    
    extracted, _ = extract_structure_with_meta(markdown_content, response_model)
    return extracted


def extract_structure_with_meta(markdown_content: str, response_model: type[BaseModel]) -> tuple[BaseModel, dict]:
    """
    分块抽取 + 合并校验。
    对短文档保持单次抽取；对长文档采用分块抽取，并在必要时回退到单次抽取。
    """
    logger.info(f"--- Extracting structure for {response_model.__name__} ---")

    threshold = 6000
    if len(markdown_content) <= threshold:
        try:
            data = _extract_once(markdown_content[:30000], response_model)
            validated = response_model.model_validate(data)
            return validated, {"mode": "single", "chunk_count": 1, "failed_chunks": 0, "fallback_used": False}
        except Exception as e:
            logger.error(f"Single extraction failed: {e}", exc_info=True)
            raise RuntimeError(f"LLM Extraction failed: {str(e)}")

    chunks = split_markdown_into_chunks(markdown_content, max_chars=5000, overlap_chars=200)
    if not chunks:
        try:
            data = _extract_once(markdown_content[:30000], response_model)
            validated = response_model.model_validate(data)
            return validated, {"mode": "single", "chunk_count": 1, "failed_chunks": 0, "fallback_used": False}
        except Exception as e:
            logger.error(f"Extraction failed on empty chunk fallback: {e}", exc_info=True)
            raise RuntimeError(f"LLM Extraction failed: {str(e)}")

    partial_results = []
    failed_chunks = 0

    for chunk in chunks:
        context_note = f"heading_path={' > '.join(chunk.heading_path) if chunk.heading_path else '(no-heading)'}"
        try:
            data = _extract_once(chunk.text, response_model, context_note=context_note)
            partial_results.append(data)
        except Exception as e:
            failed_chunks += 1
            logger.warning(f"Chunk extraction failed at index={chunk.index}: {e}")

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
        except Exception as e:
            logger.warning(f"Merged chunk validation failed, fallback to single extraction: {e}")

    try:
        fallback_data = _extract_once(markdown_content[:30000], response_model)
        validated = response_model.model_validate(fallback_data)
        return validated, {
            "mode": "single_fallback",
            "chunk_count": len(chunks),
            "failed_chunks": failed_chunks,
            "fallback_used": True,
        }
    except Exception as e:
        logger.error(f"Extraction failed after fallback: {e}", exc_info=True)
        raise RuntimeError(f"LLM Extraction failed: {str(e)}")

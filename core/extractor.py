import os
import instructor
import traceback
import logging
from openai import OpenAI
from pydantic import BaseModel
from dotenv import load_dotenv
from schemas.models import DocClassification, DocType
from core.constants import CLASSIFY_PROMPT_TEMPLATE, EXTRACT_PROMPT_TEMPLATE, JSON_FORMAT_INSTRUCTION
from core.utils import clean_and_parse_json

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
    
    # 使用常量构建提示词
    prompt = EXTRACT_PROMPT_TEMPLATE.format(
        content=markdown_content[:30000],
        schema=response_model.model_json_schema(),
        json_instruction=JSON_FORMAT_INSTRUCTION
    )
    
    try:
        # 使用原始 client 获取文本响应
        logger.info(f"--- Extracting structure for {response_model.__name__} ---")
        resp = raw_client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": "你是一个严谨的文档提取专家，只输出符合 Schema 的 JSON 数据。"},
                {"role": "user", "content": prompt},
            ],
            temperature=0.0, # 降低随机性
        )
        
        content = resp.choices[0].message.content
        logger.info(f"--- Raw LLM Response (Extraction) ---\n{content}\n----------------------------------")

        # 自定义数据清洗与解析
        data = clean_and_parse_json(content)
        # Pydantic 验证
        return response_model.model_validate(data)
        
    except Exception as e:
        logger.error(f"Extraction failed: {e}", exc_info=True)
        # 记录详细错误信息以便调试
        raise RuntimeError(f"LLM Extraction failed: {str(e)}")

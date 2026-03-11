import os
import instructor
from openai import OpenAI
from pydantic import BaseModel
from dotenv import load_dotenv
from schemas.models import DocClassification

# 加载环境变量
load_dotenv()

# 获取 LLM 配置
API_KEY = os.getenv("LLM_API_KEY")
BASE_URL = os.getenv("LLM_BASE_URL")
MODEL_NAME = os.getenv("LLM_MODEL", "qwen2.5-7b-instruct-1m") # 默认模型

if not API_KEY:
    # 仅作为警告，允许运行时再配置
    print("Warning: LLM_API_KEY not found in environment variables.")

# 初始化 OpenAI 客户端并集成 Instructor
# 注意：新版 Instructor 推荐使用 from_openai 而非 patch
client = instructor.from_openai(
    OpenAI(
        api_key=API_KEY,
        base_url=BASE_URL,
    ),
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
    
    prompt = f"""
    请根据以下文档摘要，判断该文档属于哪种软件工程文档类型。
    
    文档摘要:
    ---
    {summary}
    ---
    
    可选类型：
    - srs: 软件需求规格说明书 (包含需求列表、功能描述)
    - api: API 接口文档 (包含 HTTP 方法、路径、参数)
    - test: 测试报告 (包含测试用例、通过率、失败原因)
    - unknown: 无法识别或不属于上述类型
    
    请给出判断结果和简短理由。
    **重要：请直接返回纯 JSON 字符串，不要使用 markdown 代码块（如 ```json）包裹。**
    """
    
    try:
        resp = client.chat.completions.create(
            model=MODEL_NAME,
            response_model=DocClassification,
            messages=[
                {"role": "system", "content": "你是一个资深的软件文档分类专家。"},
                {"role": "user", "content": prompt},
            ],
            temperature=0.0,
        )
        return resp
    except Exception as e:
        print(f"Classification failed: {e}")
        # 降级处理：返回 unknown
        from schemas.models import DocType
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
    
    prompt = f"""
    你是一个专业的软件工程文档分析助手。
    请分析以下 Markdown 格式的文档内容，并提取出结构化的信息。
    
    文档内容:
    ---
    {markdown_content[:30000]} 
    ---
    
    (注意：如果文档过长，仅截取了前 30000 字符。请尽量基于可见内容提取。)
    请严格按照 JSON 格式输出，符合定义的 Schema。
    **重要：请直接返回纯 JSON 字符串，不要使用 markdown 代码块（如 ```json）包裹。**
    """
    
    try:
        resp = client.chat.completions.create(
            model=MODEL_NAME,
            response_model=response_model,
            messages=[
                {"role": "system", "content": "你是一个严谨的文档提取专家，只输出符合 Schema 的 JSON 数据。"},
                {"role": "user", "content": prompt},
            ],
            temperature=0.0, # 降低随机性
        )
        return resp
    except Exception as e:
        raise RuntimeError(f"LLM Extraction failed: {str(e)}")

import pymupdf4llm
import os

def parse_pdf_to_markdown(file_path: str) -> str:
    """
    使用 PyMuPDF4LLM 将 PDF 解析为 Markdown 格式。
    pymupdf4llm 是一个轻量级且高效的 PDF 转 Markdown 工具，适合 MVP 快速实现。
    相比 marker-pdf，它不需要下载大型模型，运行速度更快。

    Args:
        file_path (str): PDF 文件路径

    Returns:
        str: 解析后的 Markdown 内容
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")
    
    try:
        # pymupdf4llm.to_markdown 直接返回 markdown 字符串
        md_text = pymupdf4llm.to_markdown(file_path)
        return md_text
    except Exception as e:
        raise RuntimeError(f"Failed to parse PDF: {str(e)}")

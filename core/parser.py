import os
from abc import ABC, abstractmethod
import pymupdf4llm
import fitz  # PyMuPDF
from docx import Document

# --- Abstract Base Class (Strategy Interface) ---

class BaseParser(ABC):
    """
    文档解析器抽象基类 (Strategy Interface)
    """
    @abstractmethod
    def parse(self, file_path: str) -> str:
        """
        解析文档并返回 Markdown 格式的文本内容
        """
        pass

# --- Concrete Strategies ---

class PdfParser(BaseParser):
    """
    PDF 解析策略：使用 pymupdf4llm，支持自动 OCR 检测
    """
    # 文本层检测阈值：少于此字符数认为需要 OCR
    OCR_TEXT_THRESHOLD = 100
    
    def parse(self, file_path: str, force_ocr: bool = False) -> str:
        """
        解析 PDF，支持自动检测图片型 PDF 并启用 OCR
        
        Args:
            file_path: PDF 文件路径
            force_ocr: 强制启用 OCR，无视文本层检测
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")
        
        try:
            # 自动检测是否需要 OCR
            use_ocr = force_ocr if force_ocr else self._needs_ocr(file_path)
            
            return pymupdf4llm.to_markdown(file_path, use_ocr=use_ocr)
        except Exception as e:
            raise RuntimeError(f"Failed to parse PDF: {str(e)}")
    
    def _needs_ocr(self, file_path: str) -> bool:
        """
        检测 PDF 是否需要 OCR（基于文本层检测）
        
        原理：打开 PDF 检测文本层字符数，如果过少（如扫描件、图片 PDF）
        则启用 OCR。这样可以避免对纯文本 PDF 进行不必要的 OCR 处理。
        """
        try:
            doc = fitz.open(file_path)
            total_chars = 0
            
            for page in doc:
                text = page.get_text()
                total_chars += len(text.strip())
            
            doc.close()
            
            # 如果整个文档少于阈值字符数，认为需要 OCR
            return total_chars < self.OCR_TEXT_THRESHOLD
        except Exception:
            # 检测失败时，保守起见启用 OCR
            return True

class DocxParser(BaseParser):
    """
    DOCX 解析策略：使用 python-docx 手动转换为 Markdown
    """
    def parse(self, file_path: str) -> str:
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")
        
        try:
            doc = Document(file_path)
            md_lines = []

            for para in doc.paragraphs:
                text = para.text.strip()
                if not text:
                    continue
                
                # 简单样式映射
                style_name = para.style.name.lower()
                if 'heading 1' in style_name:
                    md_lines.append(f"# {text}")
                elif 'heading 2' in style_name:
                    md_lines.append(f"## {text}")
                elif 'heading 3' in style_name:
                    md_lines.append(f"### {text}")
                elif 'list bullet' in style_name:
                    md_lines.append(f"- {text}")
                elif 'list number' in style_name:
                    md_lines.append(f"1. {text}")
                else:
                    md_lines.append(text)
                
                md_lines.append("") # 空行分隔

            # 简单表格处理
            for table in doc.tables:
                rows = []
                for row in table.rows:
                    cells = [cell.text.strip().replace("\n", " ") for cell in row.cells]
                    rows.append(f"| {' | '.join(cells)} |")
                
                if rows:
                    md_lines.append(rows[0])
                    # 添加表头分隔符
                    cols = len(rows[0].split('|')) - 2
                    if cols > 0:
                        md_lines.append(f"| {' | '.join(['---'] * cols)} |")
                    md_lines.extend(rows[1:])
                    md_lines.append("")

            return "\n".join(md_lines)

        except Exception as e:
            raise RuntimeError(f"Failed to parse DOCX: {str(e)}")

class PlainTextParser(BaseParser):
    """
    纯文本/Markdown 解析策略
    """
    def parse(self, file_path: str) -> str:
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read()
        except UnicodeDecodeError:
            # 尝试 GBK (针对 Windows 用户)
            try:
                with open(file_path, 'r', encoding='gbk') as f:
                    return f.read()
            except Exception as e:
                raise RuntimeError(f"Failed to read text file (encoding issue?): {str(e)}")
        except Exception as e:
            raise RuntimeError(f"Failed to parse text file: {str(e)}")

# --- Factory ---

class ParserFactory:
    """
    解析器工厂 (Simple Factory)
    """
    @staticmethod
    def get_parser(file_path: str) -> BaseParser:
        ext = os.path.splitext(file_path)[1].lower()
        
        if ext == '.pdf':
            return PdfParser()
        elif ext in ['.docx']: # python-docx 只支持 .docx, .doc 不支持
             return DocxParser()
        elif ext in ['.md', '.markdown', '.txt']:
            return PlainTextParser()
        else:
            raise ValueError(f"Unsupported file extension: {ext}")

# --- Helper function for backward compatibility ---
def parse_pdf_to_markdown(file_path: str) -> str:
    return ParserFactory.get_parser(file_path).parse(file_path)

import os
from dataclasses import dataclass
from functools import lru_cache
from core.constants import (
    DEFAULT_EXTRACTION_CHUNK_MAX_CHARS,
    DEFAULT_EXTRACTION_CHUNK_OVERLAP_CHARS,
    DEFAULT_EXTRACTION_CONCURRENCY,
    DEFAULT_EXTRACTION_MAX_CHARS,
    DEFAULT_EXTRACTION_THRESHOLD,
    DEFAULT_LLM_MAX_TOKENS,
)

from dotenv import load_dotenv


_ = load_dotenv()


def _get_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None or value == "":
        return default
    try:
        return int(value)
    except ValueError:
        return default


def _get_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None or value == "":
        return default
    return value.lower() in ("true", "1", "yes", "on")


@dataclass(frozen=True)
class RuntimeSettings:
    llm_api_key: str | None
    llm_base_url: str | None
    llm_model: str
    upload_dir: str
    db_path: str
    extraction_threshold: int
    extraction_chunk_max_chars: int
    extraction_chunk_overlap_chars: int
    extraction_max_chars: int
    extraction_concurrency: int
    llm_max_tokens: int
    parser_backend: str
    docling_enable_ocr: bool
    docling_enable_table_structure: bool
    docling_force_backend_text: bool


@lru_cache(maxsize=1)
def get_settings() -> RuntimeSettings:
    return RuntimeSettings(
        llm_api_key=os.getenv("LLM_API_KEY") or os.getenv("DASHSCOPE_API_KEY"),
        llm_base_url=os.getenv("LLM_BASE_URL"),
        llm_model=os.getenv("LLM_MODEL", "deepseek-v4-flash"),
        upload_dir=os.getenv("UPLOAD_DIR", os.path.join("db", "uploads")),
        db_path=os.getenv("DB_PATH", os.path.join("db", "db.sqlite3")),
        extraction_threshold=_get_int("EXTRACTION_THRESHOLD", DEFAULT_EXTRACTION_THRESHOLD),
        extraction_chunk_max_chars=_get_int("EXTRACTION_CHUNK_MAX_CHARS", DEFAULT_EXTRACTION_CHUNK_MAX_CHARS),
        extraction_chunk_overlap_chars=_get_int("EXTRACTION_CHUNK_OVERLAP_CHARS", DEFAULT_EXTRACTION_CHUNK_OVERLAP_CHARS),
        extraction_max_chars=_get_int("EXTRACTION_MAX_CHARS", DEFAULT_EXTRACTION_MAX_CHARS),
        extraction_concurrency=_get_int("EXTRACTION_CONCURRENCY", DEFAULT_EXTRACTION_CONCURRENCY),
        llm_max_tokens=_get_int("LLM_MAX_TOKENS", DEFAULT_LLM_MAX_TOKENS),
        parser_backend=os.getenv("PARSER_BACKEND", "basic"),
        docling_enable_ocr=_get_bool("DOCLING_ENABLE_OCR", False),
        docling_enable_table_structure=_get_bool("DOCLING_ENABLE_TABLE_STRUCTURE", True),
        docling_force_backend_text=_get_bool("DOCLING_FORCE_BACKEND_TEXT", True),
    )

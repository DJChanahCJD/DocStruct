import os
from dataclasses import dataclass
from functools import lru_cache

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


@lru_cache(maxsize=1)
def get_settings() -> RuntimeSettings:
    return RuntimeSettings(
        llm_api_key=os.getenv("LLM_API_KEY") or os.getenv("DASHSCOPE_API_KEY"),
        llm_base_url=os.getenv("LLM_BASE_URL"),
        llm_model=os.getenv("LLM_MODEL", "qwen-doc-turbo"),
        upload_dir=os.getenv("UPLOAD_DIR", os.path.join("db", "uploads")),
        db_path=os.getenv("DB_PATH", os.path.join("db", "db.sqlite3")),
        extraction_threshold=_get_int("EXTRACTION_THRESHOLD", 6000),
        extraction_chunk_max_chars=_get_int("EXTRACTION_CHUNK_MAX_CHARS", 5000),
        extraction_chunk_overlap_chars=_get_int("EXTRACTION_CHUNK_OVERLAP_CHARS", 200),
        extraction_max_chars=_get_int("EXTRACTION_MAX_CHARS", 100000),
        extraction_concurrency=_get_int("EXTRACTION_CONCURRENCY", 5),
    )

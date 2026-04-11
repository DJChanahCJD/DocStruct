import os
from dataclasses import dataclass
from functools import lru_cache

from dotenv import load_dotenv


load_dotenv()


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
    embedding_model: str
    upload_dir: str
    db_path: str
    vector_dir: str
    extraction_threshold: int
    extraction_chunk_max_chars: int
    extraction_chunk_overlap_chars: int
    extraction_single_max_chars: int
    retrieval_chunk_max_chars: int
    retrieval_chunk_overlap_chars: int
    retrieval_chunk_min_chars: int
    embedding_batch_size: int
    qa_top_k: int


@lru_cache(maxsize=1)
def get_settings() -> RuntimeSettings:
    vector_dir = os.path.join("db", "vector")
    return RuntimeSettings(
        llm_api_key=os.getenv("LLM_API_KEY"),
        llm_base_url=os.getenv("LLM_BASE_URL"),
        llm_model=os.getenv("LLM_MODEL", "qwen2.5-7b-instruct-1m"),
        embedding_model=os.getenv("EMBEDDING_MODEL") or os.getenv("LLM_EMBED_MODEL") or "text-embedding-v4",
        upload_dir=os.getenv("UPLOAD_DIR", os.path.join("db", "uploads")),
        db_path=os.getenv("DB_PATH", os.path.join("db", "db.sqlite3")),
        vector_dir=os.getenv("VECTOR_DIR", vector_dir),
        extraction_threshold=_get_int("EXTRACTION_THRESHOLD", 6000),
        extraction_chunk_max_chars=_get_int("EXTRACTION_CHUNK_MAX_CHARS", 5000),
        extraction_chunk_overlap_chars=_get_int("EXTRACTION_CHUNK_OVERLAP_CHARS", 200),
        extraction_single_max_chars=_get_int("EXTRACTION_SINGLE_MAX_CHARS", 30000),
        retrieval_chunk_max_chars=_get_int("RETRIEVAL_CHUNK_MAX_CHARS", 700),
        retrieval_chunk_overlap_chars=_get_int("RETRIEVAL_CHUNK_OVERLAP_CHARS", 80),
        retrieval_chunk_min_chars=_get_int("RETRIEVAL_CHUNK_MIN_CHARS", 200),
        embedding_batch_size=_get_int("EMBEDDING_BATCH_SIZE", 32),
        qa_top_k=_get_int("QA_TOP_K", 5),
    )

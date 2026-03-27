import logging


logger = logging.getLogger(__name__)


def build_retrieval_corpus(record_id: int) -> None:
    """
    预留检索语料构建入口（当前阶段仅保留接口，不做向量化实现）。
    """
    logger.debug("Retrieval corpus build is skipped for record_id=%s (stub).", record_id)

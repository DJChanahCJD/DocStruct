"""
DocStruct extraction models — contract and metadata for the extraction pipeline.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from schemas.constants import DocType


class ExtractionContract(BaseModel):
    """抽取契约。定义「抽取什么对象、遵守什么规则、忽略哪些章节」，约束每次 LLM 调用的输出。"""
    doc_type: DocType
    document_fields: list[str] = Field(default_factory=list, description="需要抽取的文档级字段")
    target_slots: list[str] = Field(description="需要抽取的对象槽")
    rules: list[str] = Field(default_factory=list, description="抽取规则")
    ignore_sections: list[str] = Field(default_factory=list, description="忽略的章节或标题模式")


class ExtractionMeta(BaseModel):
    """抽取元信息。记录抽取过程的关键统计和模型信息。"""
    llm_model: str = Field(default="", description="抽取所使用的 LLM 模型名称")
    confidence: float = Field(default=0.0, description="置信度，基于证据覆盖率计算，0~1")
    chunk_count: int = Field(default=0, description="文档分块总数")
    failed_chunks: int = Field(default=0, description="抽取失败的分块数，0=全成功")
    element_count: int = Field(default=0, description="IR 元素总数")
    section_count: int = Field(default=0, description="IR 章节数")

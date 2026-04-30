"""
DocStruct Test Case document type — test case specification extraction + document model.
"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

from schemas.docs.base import BaseExtractedDocument, BaseNode
from schemas.constants import DocType


class TestStepItem(BaseModel):
    """测试步骤。"""
    step_no: int = Field(default=0, description="步骤序号")
    action: str = Field(default="", description="操作描述")
    expected_result: str = Field(default="", description="预期结果")


class TestCaseItem(BaseNode):
    """测试用例。"""
    priority: str = Field(default="medium", description="优先级")
    preconditions: list[str] = Field(default_factory=list, description="前置条件")
    steps: list[TestStepItem] = Field(default_factory=list, description="测试步骤")
    expected_result: str = Field(default="", description="预期结果")


class TestCaseExtraction(BaseModel):
    """测试用例文档。"""
    test_scope: str = Field(default="", description="测试范围")
    test_cases: list[TestCaseItem] = Field(default_factory=list, description="测试用例列表")


class TestCaseExtractedDocument(TestCaseExtraction, BaseExtractedDocument):
    doc_type: Literal[DocType.TC] = Field(default=DocType.TC)

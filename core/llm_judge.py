from __future__ import annotations

import json
from typing import Any, Literal

from pydantic import BaseModel, Field

from core.llm import build_chat_completion_kwargs, get_openai_client
from core.utils import clean_and_parse_json


JUDGE_PROMPT_TEMPLATE = """
你是一名严格的软件工程文档结构化抽取评审员。
请基于以下 4 份输入，对“生成答案”做整体质量评审：

1. 文档类型：{doc_type}
2. 原始文档 Markdown：
{markdown_content}

3. 标准答案（Gold JSON）：
{golden_json}

4. 生成答案（Predicted JSON）：
{predicted_json}

评审要求：
- 重点关注关键信息覆盖、明显遗漏、错误字段、幻觉内容，以及与标准答案的一致性
- 输出一个总分 `score`，范围 0 到 100
- 输出 `decision`，只能是 `pass`、`partial`、`fail`
- 输出 `summary`，用简洁中文总结该文档抽取的整体效果和主要问题
- 输出 `issues`，列出 2 到 5 条简短问题；若问题很少，也至少给出 1 条最主要问题
- 输出 `confidence`，只能是 `low`、`medium`、`high`

评分参考：
- 90-100：总体正确，仅有轻微缺失或表达差异
- 70-89：主体正确，但有明显遗漏或局部错误
- 40-69：部分命中，但关键字段缺失较多
- 0-39：结构或内容明显错误，参考价值低

只输出 JSON，不要输出 Markdown，不要补充解释。
""".strip()


class LlmJudgeResult(BaseModel):
    score: float = Field(..., ge=0, le=100)
    decision: Literal["pass", "partial", "fail"]
    summary: str
    issues: list[str] = Field(default_factory=list)
    confidence: Literal["low", "medium", "high"] = "medium"


def judge_extraction(
    *,
    doc_type: str,
    markdown_content: str,
    golden_payload: dict[str, Any],
    predicted_payload: dict[str, Any],
    model_name: str | None = None,
    prompt_template: str | None = None,
    temperature: float = 0.0,
) -> LlmJudgeResult:
    client = get_openai_client()
    prompt = (prompt_template or JUDGE_PROMPT_TEMPLATE).format(
        doc_type=doc_type,
        markdown_content=markdown_content,
        golden_json=json.dumps(golden_payload, ensure_ascii=False, indent=2),
        predicted_json=json.dumps(predicted_payload, ensure_ascii=False, indent=2),
    )
    response = client.chat.completions.create(
        **build_chat_completion_kwargs(
            messages=[
                {"role": "system", "content": "你是一个严谨的评审模型，只输出合法 JSON。"},
                {"role": "user", "content": prompt},
            ],
            temperature=temperature,
            model_name=model_name,
        )
    )
    content = response.choices[0].message.content or ""
    parsed = clean_and_parse_json(content)
    return LlmJudgeResult.model_validate(parsed)

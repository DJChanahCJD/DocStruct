# JSON Format Instructions
JSON_FORMAT_INSTRUCTION = """
Return valid JSON only. No markdown, no comments. Keys must be in English.
"""

# Document Classification Prompt Template (Role: Expert Software Architect)
CLASSIFY_PROMPT_TEMPLATE = """
You are an expert in software engineering documentation.

Classify the following document summary into one category.

Document Summary:
{summary}

Categories:
srs: Software Requirements Specification
api: API documentation
design: System or architecture design
test_plan: Test planning document
test_case: Test case definitions
test_report: Test execution report
user_manual: User guide or manual
bug_report: Bug report, issue ticket, defect report, incident report
adr: Architecture Decision Record (design decisions, trade-off analysis, ADR log)
unknown: None of the above

{json_instruction}

Return JSON:
{{
  "doc_type": "srs | api | design | test_plan | test_case | test_report | user_manual | bug_report | adr | unknown",
  "confidence": 0.0-1.0
}}
"""

# Structure Extraction Prompt Template (Role: Senior Technical Writer / Data Engineer)
EXTRACT_PROMPT_TEMPLATE = """
Extract structured information from the following Markdown document using the provided JSON Schema.

Document:
{content}

Schema:
{schema}

{json_instruction}
"""

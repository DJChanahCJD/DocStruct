# JSON Format Instructions
JSON_FORMAT_INSTRUCTION = """
Return valid JSON only. No markdown, no comments. Keys must be in English.
"""

DOC_TYPE_DESCRIPTIONS = {
    "srs": "Software Requirements Specification",
    "api": "API documentation",
    "design": "System or architecture design",
    "test": "Test plan, test case, or test report",
    "manual": "User guide or manual",
    "issue": "Bug report, issue ticket, defect report, or incident report",
    "unknown": "None of the above",
}

# Document Classification Prompt Template (Role: Expert Software Architect)
CLASSIFY_PROMPT_TEMPLATE = """
You are an expert in software engineering documentation.

Classify the following document summary into one category.

Document Summary:
{summary}

Categories:
{categories}

Schema:
{schema}

{json_instruction}
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

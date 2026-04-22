JSON_FORMAT_INSTRUCTION = "Return valid JSON only. No markdown, no comments. Keys must be in English."

EXTRACT_PROMPT_TEMPLATE = """
You are an expert Software Engineering Document Analyst.
Extract structured information from the following Markdown document using the provided JSON Schema with high precision.

Document:
{content}

Schema:
{schema}

{json_instruction}
"""

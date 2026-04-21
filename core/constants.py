# JSON Format Instructions
JSON_FORMAT_INSTRUCTION = """
Return valid JSON only. No markdown, no comments. Keys must be in English.
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

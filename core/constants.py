JSON_FORMAT_INSTRUCTION = "Return valid JSON only. No markdown, no comments. Keys must be in English."

EXTRACT_PROMPT_TEMPLATE = """
You are an expert Software Engineering Document Analyst.
Extract structured information from the following Markdown document using the provided JSON Schema with high precision.
Return one top-level JSON object only.
Use the document as evidence, but do not copy request examples, response examples, error payloads, tables, or code blocks as the final output.
Map document evidence into the target schema. If this chunk does not contain enough information for a field, leave that field empty instead of inventing data or echoing source snippets.
Do not output any top-level keys that are not defined by the schema.

Document:
{content}

Schema:
{schema}

{json_instruction}
"""

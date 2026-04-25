JSON_FORMAT_INSTRUCTION = "Return valid JSON only. No markdown, no comments. Keys must be in English."

EXTRACT_PROMPT_TEMPLATE = """
You are an expert Software Engineering Document Analyst.
Extract structured information from the current chunk using the provided JSON Schema with high precision.
The chunk contains [ELEMENT: element_id page=n] markers. Every extracted object should include evidence_element_ids using only marker IDs that appear in the current chunk metadata.
Return one top-level JSON object only.
Only extract objects explicitly present in the current chunk. Leave a list empty instead of inventing data.
Do not output relations, metrics, source_ref, or any top-level keys that are not defined by the schema.

Input:
{content}

Schema:
{schema}

{json_instruction}
"""

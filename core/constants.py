# JSON Format Instructions
JSON_FORMAT_INSTRUCTION = """
Return a valid JSON object. No Markdown blocks (```json). No comments. All keys must be in English.
"""

# Document Classification Prompt Template (Role: Expert Software Architect)
CLASSIFY_PROMPT_TEMPLATE = """
Role: You are an Expert Software Architect specializing in technical documentation analysis.

Task: Analyze the following Markdown document summary and classify it into one of the predefined categories.

Document Summary:
---
{summary}
---

Categories:
- srs: Software Requirements Specification (Functional requirements, user stories)
- api: API Documentation (Endpoints, HTTP methods, parameters, responses)
- test: Test Report (Test cases, execution status, pass/fail rates)
- sdd: System Design Document (Architecture, modules, database schema)
- user_manual: User Manual (Installation, usage guide, troubleshooting)
- unknown: Cannot be classified into the above categories

{json_instruction}

Output Format:
{{
  "doc_type": "srs|api|test|sdd|user_manual|unknown",
  "confidence": 0.95,
  "reasoning": "Based on the presence of HTTP methods and endpoint paths..."
}}
"""

# Structure Extraction Prompt Template (Role: Senior Technical Writer / Data Engineer)
EXTRACT_PROMPT_TEMPLATE = """
Role: You are a Senior Technical Writer and Data Engineer.

Task: Extract structured data from the following Markdown document strictly adhering to the provided JSON Schema.

Context: The input is a technical document converted to Markdown. Use the headers (#, ##) and list structures to identify relevant sections.

Document Content:
---
{content}
---

(Note: Content may be truncated if too long. Focus on visible sections.)

Schema Definition:
{schema}

{json_instruction}
"""

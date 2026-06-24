from __future__ import annotations

import json

from fastmcp.exceptions import ToolError

from clients.ollama import chat_with_ollama

REQUIRED_CV_JSON_KEYS = (
    "anagraphical_data",
    "experience",
    "education",
    "skills",
    "certifications",
    "hobby",
)

SECTION_TITLES = {
    "anagraphical_data": "Anagraphical data",
    "experience": "Experience",
    "education": "Education",
    "skills": "Skills",
    "certifications": "Certifications",
    "hobby": "Hobby",
}

CV_ANONYMIZATION_PROMPT_TEMPLATE = """You anonymize CV content for PDF export and return structured JSON only.

Return only valid JSON using only these CV section keys:
{{
  "anagraphical_data": [],
  "experience": [],
  "education": [],
  "skills": [],
  "certifications": [],
  "hobby": []
}}

Privacy rules:
- Keep only the candidate first/given name; remove surnames/family names.
- Remove phone numbers.
- Remove email addresses.
- Remove URLs.
- Remove street addresses.
- Remove street names.
- Remove house numbers.
- Remove postal codes.
- Keep only the city from any address, for example "Via Roma 10, 6900 Lugano, Switzerland" becomes "Lugano".
- Remove or transform all personally identifiable information other than the candidate first/given name.

Classification and preservation rules:
- Classify all remaining CV information into the correct JSON arrays.
- Do not summarize professional content.
- Do not remove professional experience, education, skills, certifications, languages, projects, technical competencies, hobbies, or professional summary.
- Put languages, projects, technical competencies, and professional summary in the most appropriate array.
- If a field has no content in the source CV, omit that field or return an empty array.
- Every included field must be an array of non-empty strings.

Output rules:
- Return only JSON.
- Do not add introductions, explanations, comments, notes, markdown fences, or extra text.

CV content:
{cv_text}
"""

CV_JSON_REPAIR_PROMPT_TEMPLATE = """Repair this anonymized CV response into valid JSON only.

It must use only these CV section keys, each with an array of strings:
- anagraphical_data
- experience
- education
- skills
- certifications
- hobby

If a field has no content in the source CV, omit that field or use an empty array. Preserve all professional content from the source CV. Continue applying privacy rules: keep only first/given name; remove surnames, phone numbers, emails, URLs, street names, house numbers, and postal codes; keep only city from addresses.

Source CV content:
{cv_text}

Invalid response:
{invalid_response}
"""

OLLAMA_JSON_FORMAT = {
    "type": "object",
    "properties": {
        key: {"type": "array", "items": {"type": "string"}}
        for key in REQUIRED_CV_JSON_KEYS
    },
}


async def anonymize_cv_text(cv_text: str) -> str:
    cleaned_text = cv_text.strip()

    if not cleaned_text:
        raise ToolError("Extracted CV text is empty and cannot be anonymized.")

    prompt = CV_ANONYMIZATION_PROMPT_TEMPLATE.format(cv_text=cleaned_text)

    response = await chat_with_ollama(
        prompt,
        response_format=OLLAMA_JSON_FORMAT,
        options={"temperature": 0},
    )

    try:
        cv_json = _parse_cv_json(response)
    except ToolError:
        repair_response = await chat_with_ollama(
            CV_JSON_REPAIR_PROMPT_TEMPLATE.format(
                cv_text=cleaned_text,
                invalid_response=response,
            ),
            response_format=OLLAMA_JSON_FORMAT,
            options={"temperature": 0},
        )
        cv_json = _parse_cv_json(repair_response)

    return _format_cv_json_as_text(cv_json)


def _parse_cv_json(response: str) -> dict[str, list[str]]:
    stripped_response = response.strip()

    if not stripped_response:
        raise ToolError("Ollama returned an empty response.")

    try:
        parsed = json.loads(stripped_response)
    except json.JSONDecodeError as exc:
        raise ToolError(f"Ollama returned invalid JSON: {exc.msg}.") from exc

    if not isinstance(parsed, dict):
        raise ToolError("Ollama returned JSON with an unexpected shape.")

    return {
        key: parsed.get(key, [])
        for key in REQUIRED_CV_JSON_KEYS
    }


def _format_cv_json_as_text(cv_json: dict[str, list[str]]) -> str:
    sections: list[str] = []

    for key in REQUIRED_CV_JSON_KEYS:
        items = cv_json.get(key, [])

        if not items:
            continue

        lines = [f"**{SECTION_TITLES[key]}**"]
        lines.extend(f"• {item}" for item in items)
        sections.append("\n".join(lines))

    return "\n\n".join(sections)
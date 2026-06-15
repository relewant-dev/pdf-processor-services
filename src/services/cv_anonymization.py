from __future__ import annotations

from fastmcp.exceptions import ToolError

from clients.ollama import chat_with_ollama

CV_ANONYMIZATION_PROMPT_TEMPLATE = """You anonymize CV content for PDF export.

Privacy rules:
- Remove phone numbers.
- Remove email addresses.
- Remove street names and house numbers.
- Remove the candidate's first name and surname completely; do not leave, replace, initialize, or pseudonymize any part of the candidate name.
- Keep only the city from any address, for example "Via Roma 10, 6900 Lugano, Switzerland" becomes "Lugano".
- Preserve professional experience, education, skills, certifications, languages, projects, technical competencies, and professional summary.
- Remove or transform only personally identifiable information.

Output rules:
- Return only the anonymized CV content.
- The response must start directly with the CV content.
- Do not include any introductory text before the CV content.
- Do not add commentary, explanations, notes, markdown, or extra text.

CV content:
{cv_text}
"""


async def anonymize_cv_text(cv_text: str) -> str:
    cleaned_text = cv_text.strip()
    if not cleaned_text:
        raise ToolError("Extracted CV text is empty and cannot be anonymized.")

    response = await chat_with_ollama(
        CV_ANONYMIZATION_PROMPT_TEMPLATE.format(cv_text=cleaned_text)
    )
    anonymized_text = _remove_introductory_sentence(response.strip())
    if not anonymized_text:
        raise ToolError("Ollama returned an empty anonymized CV response.")
    return anonymized_text


def _remove_introductory_sentence(anonymized_text: str) -> str:
    intro = "Here is the anonymized CV content for PDF export:"
    if anonymized_text.startswith(intro):
        return anonymized_text.removeprefix(intro).lstrip()
    return anonymized_text

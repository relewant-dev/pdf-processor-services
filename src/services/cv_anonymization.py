from __future__ import annotations

from fastmcp.exceptions import ToolError

from clients.ollama import chat_with_ollama

CV_ANONYMIZATION_PROMPT_TEMPLATE = """You anonymize CV content for PDF export.

Privacy rules:
- Remove phone numbers.
- Remove email addresses.
- Remove street names and house numbers.
- Replace the candidate's full name with initials only, for example "Gabriele Di Somma" becomes "G. D. S." and "Mario Rossi" becomes "M. R.".
- Keep only the city from any address, for example "Via Roma 10, 6900 Lugano, Switzerland" becomes "Lugano".
- Preserve professional experience, education, skills, certifications, languages, projects, technical competencies, and professional summary.
- Remove or transform only personally identifiable information.

Output rules:
- Return only the anonymized CV content.
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
    anonymized_text = response.strip()
    if not anonymized_text:
        raise ToolError("Ollama returned an empty anonymized CV response.")
    return anonymized_text

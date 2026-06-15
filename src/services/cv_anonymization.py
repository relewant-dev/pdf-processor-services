from __future__ import annotations

from fastmcp.exceptions import ToolError

from clients.ollama import chat_with_ollama

CV_ANONYMIZATION_PROMPT_TEMPLATE = """You anonymize and format CV content for PDF export.

Privacy rules:
- Keep the candidate name.
- Remove phone numbers.
- Remove email addresses.
- Remove street addresses.
- Remove street names.
- Remove house numbers.
- Remove postal codes.
- Keep only the city from any address, for example "Via Roma 10, 6900 Lugano, Switzerland" becomes "Lugano".
- Preserve professional experience, education, skills, certifications, languages, projects, technical competencies, hobbies, and professional summary when present.
- Remove or transform only personally identifiable information other than the candidate name.

Formatting rules:
- Return the anonymized CV using exactly these sections and this order:
  1. Anagraphical data
  2. Experience
  3. Education
  4. Skills
  5. Certifications
  6. Hobby
- Section titles must be bold, for example **Anagraphical data**.
- Use round bullet points for lists.
- If a section has no supported content in the CV, include the bold section title and write a round bullet point with "Not specified".

Output rules:
- Return only the formatted anonymized CV content.
- Do not start with an introductory sentence such as "Here is the anonymized CV content for PDF export:".
- Do not add introductions, explanations, comments, notes, markdown fences, or extra text.

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

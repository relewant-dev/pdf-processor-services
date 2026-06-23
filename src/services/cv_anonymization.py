from __future__ import annotations

import re

from fastmcp.exceptions import ToolError

from clients.ollama import chat_with_ollama

REQUIRED_CV_SECTIONS = (
    "Personal data",
    "Experience",
    "Education",
    "Skills",
    "Certifications",
    "Hobby",
)

_SECTION_ALIASES = {
    "personal data": "Personal data",
    "anagraphical data": "Personal data",
    "anagrafical data": "Personal data",
    "contact": "Personal data",
    "contact information": "Personal data",
    "profile": "Personal data",
    "summary": "Personal data",
    "professional summary": "Personal data",
    "experience": "Experience",
    "work experience": "Experience",
    "professional experience": "Experience",
    "employment history": "Experience",
    "work history": "Experience",
    "career history": "Experience",
    "education": "Education",
    "academic background": "Education",
    "academic history": "Education",
    "qualifications": "Education",
    "skills": "Skills",
    "technical skills": "Skills",
    "competences": "Skills",
    "competencies": "Skills",
    "certifications": "Certifications",
    "certificates": "Certifications",
    "licenses": "Certifications",
    "licences": "Certifications",
    "hobby": "Hobby",
    "hobbies": "Hobby",
    "interests": "Hobby",
}

CV_ANONYMIZATION_PROMPT_TEMPLATE = """You anonymize and format CV content for PDF export.

Privacy rules:
- Keep only the candidate first/given name; remove surnames/family names.
- Remove phone numbers.
- Remove email addresses.
- Remove street addresses.
- Remove street names.
- Remove house numbers.
- Remove postal codes.
- Keep only the city from any address, for example "Via Roma 10, 6900 Lugano, Switzerland" becomes "Lugano".
- Preserve all non-sensitive professional information: professional summary, experience, job titles, employers, dates, responsibilities, achievements, education, skills, certifications, languages, projects, technical competencies, and hobbies.
- Anonymize personal/sensitive data only. Do not remove professional content unless it contains personal identifying data.
- Never invent missing information.

Classification rules:
- Classify all CV content into the most appropriate required section.
- Treat alternative headings such as "Work History" as Experience, "Academic Background" as Education, "Technical Skills" as Skills, and "Interests" as Hobby.
- Keep certifications and licenses in Certifications, not Education or Skills.
- Keep hobbies, interests, and extracurricular non-professional activities in Hobby.

Formatting rules:
- You must output exactly these sections and in this order:
  1. Personal data
  2. Experience
  3. Education
  4. Skills
  5. Certifications
  6. Hobby
- Never drop a section heading. Do not duplicate section headings.
- Section titles must be bold in the exported PDF. Mark each section title with markdown bold delimiters, for example **Personal data**, so the renderer can draw real bold text without showing the delimiters.
- Use only round bullet points for lists; never use square bullet points.
- For each section, include all relevant anonymized content found in the input CV.
- If no relevant content exists for a section, include the bold section title and write a round bullet point with "Not specified".

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
    return normalize_cv_sections(anonymized_text)


def normalize_cv_sections(anonymized_text: str) -> str:
    """Return anonymized CV text with one complete, ordered section set."""
    section_content = {section: [] for section in REQUIRED_CV_SECTIONS}
    current_section: str | None = None
    preamble: list[str] = []

    for raw_line in anonymized_text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        section = _section_from_heading(line)
        if section:
            current_section = section
            continue
        if current_section is None:
            preamble.append(_normalize_content_line(line))
            continue
        section_content[current_section].append(_normalize_content_line(line))

    if preamble:
        section_content["Personal data"] = preamble + section_content["Personal data"]

    normalized_lines: list[str] = []
    for section in REQUIRED_CV_SECTIONS:
        if normalized_lines:
            normalized_lines.append("")
        normalized_lines.append(f"**{section}**")
        content = _dedupe_content(section_content[section])
        if not content:
            normalized_lines.append("• Not specified")
            continue
        normalized_lines.extend(content)

    return "\n".join(normalized_lines)


def _section_from_heading(line: str) -> str | None:
    normalized = _normalize_heading_text(line)
    return _SECTION_ALIASES.get(normalized)


def _normalize_heading_text(line: str) -> str:
    heading = line.strip()
    heading = re.sub(r"\*\*([^*]+)\*\*", r"\1", heading).strip()
    heading = heading.strip("#:")
    heading = re.sub(r"^[-*•▪■□\s]+", "", heading).strip()
    heading = heading.rstrip(":").strip()
    return re.sub(r"\s+", " ", heading).casefold()


def _normalize_content_line(line: str) -> str:
    text = re.sub(r"^[▪■□]\s*", "• ", line.strip())
    text = re.sub(r"^[-*]\s+", "• ", text)
    if not text.startswith("•"):
        return f"• {text}"
    return re.sub(r"^•\s*", "• ", text)


def _dedupe_content(lines: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for line in lines:
        key = line.casefold()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(line)
    return deduped


def _remove_introductory_sentence(anonymized_text: str) -> str:
    intro = "Here is the anonymized CV content for PDF export:"
    if anonymized_text.startswith(intro):
        return anonymized_text.removeprefix(intro).lstrip()
    return anonymized_text

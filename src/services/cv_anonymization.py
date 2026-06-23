from __future__ import annotations

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

CV_ANONYMIZATION_PROMPT_TEMPLATE = """You anonymize and format CV content for PDF export.

Primary objective:
- This workflow must not rewrite, shorten, summarize, evaluate relevance, or remove professional content.
- Your only tasks are to anonymize private/personal identifying data and reorganize the remaining CV text into the required sections.
- Preserve as much original professional information as possible, including the original level of detail and bullet granularity.

Critical source-of-truth rule:
- After this PDF text has been converted to plain text, you are the only component allowed to classify CV content into sections.
- All section classification must be based only on the converted CV text below.
- Do not use assumptions.
- Do not infer content outside the given CV text.
- Do not invent information.

Privacy rules:
- Only anonymize personal identifying data such as name, email, phone, LinkedIn, address, precise personal location, and other private identifiers.
- Keep only the candidate first/given name when a name is present; remove surnames/family names.
- Remove phone numbers.
- Remove email addresses.
- Remove LinkedIn and personal profile URLs.
- Remove street addresses.
- Remove street names.
- Remove house numbers.
- Remove postal codes.
- Keep only the city from any address, for example "Via Roma 10, 6900 Lugano, Switzerland" becomes "Lugano".
- Company names, client names, technologies, project descriptions, dates, roles, education, and professional achievements must be preserved unless the application explicitly requires them to be anonymized.
- Preserve all non-sensitive professional information: professional summary, all work experiences, projects, responsibilities, achievements, teaching/training activities, technical stacks, education, skills, certifications, languages, technical competencies, and hobbies.
- Anonymize personal/sensitive data only. Do not remove professional content unless that exact content contains personal identifying data.

Classification rules:
- Classify all CV content into the most appropriate required section yourself, using only the converted CV text.
- Always classify content into these exact sections in this exact order:
  1. Personal data
  2. Experience
  3. Education
  4. Skills
  5. Certifications
  6. Hobby
- Skills may appear under headings such as Core Competencies, Technical Skills, Stack, Technologies, Tools, Frameworks, Methodologies, or inside experience descriptions.
- If skill-related information exists anywhere in the CV text, the Skills section must contain it.
- If information belongs to skills, place it in Skills.
- If information belongs to experience, place it in Experience.
- If information belongs to education, place it in Education.
- Keep certifications and licenses in Certifications, not Education or Skills.
- Keep hobbies, interests, and extracurricular non-professional activities in Hobby.
- Do not invent information.
- Do not use assumptions.
- Do not infer content outside the given CV text.

Professional preservation rules:
- Do not summarize the CV.
- Do not shorten the CV.
- Do not remove professional information.
- Do not judge whether an experience is relevant or not.
- Do not delete jobs, projects, bullet points, skills, education, training, languages, or technical stacks unless the specific text contains private data.
- Keep all work experiences, projects, responsibilities, achievements, teaching/training activities, technical stacks, education, languages, and skills.
- Preserve detailed bullet points instead of replacing them with short summaries.
- Keep technical skills from Core Competencies, Technical Skills, Stack, Technologies, Tools, Frameworks, Methodologies, and similar source lines.

Formatting rules:
- You must output exactly these sections and in this order:
  1. Personal data
  2. Experience
  3. Education
  4. Skills
  5. Certifications
  6. Hobby
- Never omit a section heading.
- Never leave a section empty.
- If no information is available for a section, write `Not specified`.
- Never drop a section heading. Do not duplicate section headings.
- Section titles must be bold in the exported PDF. Mark each section title with markdown bold delimiters, for example **Personal data**, so the renderer can draw real bold text without showing the delimiters.
- Use only round bullet points for lists; never use square bullet points.
- For each section, include all relevant anonymized content found in the input CV.
- If no relevant content exists for a section, include the bold section title and write a round bullet point with "Not specified".

Output rules:
- Return only the formatted anonymized CV content.
- Do not start with an introductory sentence such as "Here is the anonymized CV content for PDF export:".
- Do not add introductions, explanations, comments, notes, markdown fences, or extra text.
- Do not write comments such as "I removed this section because..." or any explanation of removed content.

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
    """Return Ollama-provided CV sections once, ordered, and structurally complete."""
    section_content = {section: [] for section in REQUIRED_CV_SECTIONS}
    current_section: str | None = None

    for raw_line in anonymized_text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        section = _required_section_heading(line)
        if section is not None:
            current_section = section
            continue
        if current_section is None:
            continue
        section_content[current_section].append(_normalize_content_line(line))

    normalized_lines: list[str] = []
    for section in REQUIRED_CV_SECTIONS:
        if normalized_lines:
            normalized_lines.append("")
        normalized_lines.append(f"**{section}**")
        content = section_content[section]
        if not content or _content_is_empty(content):
            normalized_lines.append("• Not specified")
            continue
        normalized_lines.extend(content)

    return "\n".join(normalized_lines)


def _required_section_heading(line: str) -> str | None:
    normalized = _normalize_heading_text(line)
    for section in REQUIRED_CV_SECTIONS:
        if normalized == section.casefold():
            return section
    return None


def _normalize_heading_text(line: str) -> str:
    heading = line.strip()
    if heading.startswith("**") and heading.endswith("**") and len(heading) > 4:
        heading = heading[2:-2].strip()
    heading = heading.strip("#:").strip().removesuffix(":").strip()
    return " ".join(heading.split()).casefold()


def _normalize_content_line(line: str) -> str:
    text = line.strip()
    if text.startswith(("▪", "■", "□")):
        text = f"• {text[1:].strip()}"
    elif text.startswith(("- ", "* ")):
        text = f"• {text[2:].strip()}"
    if not text.startswith("•"):
        return f"• {text}"
    return f"• {text[1:].strip()}"


def _content_is_empty(lines: list[str]) -> bool:
    return all(line.removeprefix("•").strip() == "" for line in lines)


def _remove_introductory_sentence(anonymized_text: str) -> str:
    intro = "Here is the anonymized CV content for PDF export:"
    if anonymized_text.startswith(intro):
        return anonymized_text.removeprefix(intro).lstrip()
    return anonymized_text

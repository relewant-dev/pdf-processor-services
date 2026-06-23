from __future__ import annotations

import logging

from fastmcp.exceptions import ToolError

from clients.ollama import chat_with_ollama

logger = logging.getLogger(__name__)

REQUIRED_CV_SECTIONS = (
    "Personal data",
    "Experience",
    "Education",
    "Skills",
    "Certifications",
    "Hobby",
)

CV_ANONYMIZATION_PROMPT_TEMPLATE = """You are anonymizing and reorganizing a CV.

Your task is NOT to summarize.
Your task is NOT to shorten.
Your task is NOT to evaluate relevance.
Your task is NOT to remove professional content.

Your only tasks are:

1. remove or anonymize private personal identifiers;
2. place the remaining text into the required sections.

You must preserve the original amount of professional detail. Keep all jobs, projects, bullets, technical stacks, skills, education, languages, training, achievements, dates, companies, clients, and technologies unless the specific text is private personal identifying data.

Required sections, exactly in this order:
**Personal data**
**Experience**
**Education**
**Skills**
**Certifications**
**Hobby**

Rules:

* Copy professional content as faithfully as possible.
* Do not compress multiple bullet points into one.
* Do not replace detailed experience with a short summary.
* Do not output `Not specified` for Experience if the CV contains work experience.
* Do not output `Not specified` for Skills if the CV contains Core Competencies, Technical Skills, Stack, technologies, tools, languages, frameworks, methodologies, cloud platforms, databases, or testing tools.
* Professional Summary belongs in Personal data or Experience, depending on the content.
* Professional Experience, Teaching & Training, jobs, projects, responsibilities, and achievements belong in Experience.
* Education belongs in Education.
* Core Competencies, Technical Skills, Stack lines, programming languages, frameworks, tools, cloud/devops, databases, methodologies, and spoken languages belong in Skills.
* Certifications and licenses belong in Certifications.
* Hobbies and interests belong in Hobby.
* If a section has no information in the source CV, write one bullet: `• Not specified`.
* Never write explanations, notes, or comments.
* Never say that content was removed because it was not relevant.
* Return only the formatted anonymized CV.

Privacy:

* Remove surname/family name.
* Keep only the given first name if present.
* Remove email, phone number, LinkedIn/profile URLs, street address, street name, house number, and postal code.
* Keep city only from addresses.
* Do not remove company names, client names, roles, projects, technologies, dates, education, professional achievements, or technical details.

Formatting:

* Section titles must be bold in the exported PDF. Mark each section title with markdown bold delimiters exactly as listed above.
* Use only round bullet points for lists; never use square bullet points.

CV content:
{cv_text}
"""

CV_REPAIR_PROMPT_TEMPLATE = """The previous answer incorrectly omitted professional content. Reprocess the same CV text. Preserve all professional details and populate Experience and Skills from the CV text. Do not summarize. Do not output `Not specified` for sections that have content in the source CV.

Validation error:
{validation_error}

Previous answer:
{previous_answer}

CV content:
{cv_text}
"""

CV_OLLAMA_OPTIONS = {"temperature": 0, "num_ctx": 32768, "num_predict": 12000}



async def anonymize_cv_text(cv_text: str) -> str:
    cleaned_text = cv_text.strip()
    if not cleaned_text:
        raise ToolError("Extracted CV text is empty and cannot be anonymized.")

    prompt = CV_ANONYMIZATION_PROMPT_TEMPLATE.format(cv_text=cleaned_text)
    logger.info("cv_anonymization_ollama_request cv_text_chars=%s prompt_chars=%s", len(cleaned_text), len(prompt))
    response = await chat_with_ollama(prompt, options=CV_OLLAMA_OPTIONS)
    logger.info("cv_anonymization_ollama_response output_chars=%s", len(response))
    anonymized_text = _clean_model_response(response)
    validation_error = validate_anonymized_cv(anonymized_text, cleaned_text)
    if validation_error is not None:
        repair_prompt = CV_REPAIR_PROMPT_TEMPLATE.format(
            validation_error=validation_error,
            previous_answer=anonymized_text,
            cv_text=cleaned_text,
        )
        logger.warning("cv_anonymization_validation_failed error=%s repair_prompt_chars=%s", validation_error, len(repair_prompt))
        repair_response = await chat_with_ollama(repair_prompt, options=CV_OLLAMA_OPTIONS)
        logger.info("cv_anonymization_repair_response output_chars=%s", len(repair_response))
        anonymized_text = _clean_model_response(repair_response)
        validation_error = validate_anonymized_cv(anonymized_text, cleaned_text)
        if validation_error is not None:
            raise ToolError(f"Ollama returned an invalid anonymized CV: {validation_error}")
    return normalize_cv_sections(anonymized_text)


def validate_anonymized_cv(anonymized_text: str, source_text: str) -> str | None:
    for section in REQUIRED_CV_SECTIONS:
        heading = f"**{section}**"
        if anonymized_text.count(heading) != 1:
            return f"section heading {heading} must exist exactly once"
    normalized = normalize_cv_sections(anonymized_text)
    for section in REQUIRED_CV_SECTIONS:
        content = _section_lines(normalized, section)
        if not content or _content_is_empty(content):
            return f"section {section} is empty"
    if _source_contains_experience(source_text) and _section_is_not_specified(normalized, "Experience"):
        return "Experience is Not specified even though the source CV contains professional experience"
    if _source_contains_skills(source_text) and _section_is_not_specified(normalized, "Skills"):
        return "Skills is Not specified even though the source CV contains technical skills"
    return None


def _clean_model_response(response: str) -> str:
    anonymized_text = _remove_introductory_sentence(response.strip())
    if not anonymized_text:
        raise ToolError("Ollama returned an empty anonymized CV response.")
    return anonymized_text


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


def _section_lines(normalized_text: str, section: str) -> list[str]:
    lines = normalized_text.splitlines()
    heading = f"**{section}**"
    try:
        start = lines.index(heading) + 1
    except ValueError:
        return []
    content: list[str] = []
    for line in lines[start:]:
        if line.startswith("**") and line.endswith("**"):
            break
        if line.strip():
            content.append(line.strip())
    return content


def _section_is_not_specified(normalized_text: str, section: str) -> bool:
    content = [line.removeprefix("•").strip().casefold() for line in _section_lines(normalized_text, section)]
    return content == ["not specified"]


def _source_contains_experience(source_text: str) -> bool:
    lowered = source_text.casefold()
    indicators = ("professional experience", "work experience", "experience", "developer", "engineer", "consultant", "manager", "architect", "analyst", "trainer", "teacher")
    return any(indicator in lowered for indicator in indicators)


def _source_contains_skills(source_text: str) -> bool:
    lowered = source_text.casefold()
    indicators = ("skills", "core competencies", "technical", "stack", "java", "spring boot", "python", "docker", "aws", "kafka", "react", "sql", "kubernetes", "gitlab ci/cd", "agile", "safe")
    return any(indicator in lowered for indicator in indicators)

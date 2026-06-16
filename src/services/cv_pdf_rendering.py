from __future__ import annotations

import copy
import hashlib
import logging
import textwrap
from pathlib import Path

from fastmcp.exceptions import ToolError

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_TEMPLATE_PATH = REPOSITORY_ROOT / "stationery" / "relewant-sa-letterhead.pdf"
logger = logging.getLogger(__name__)


def render_anonymized_cv_pdf(
    anonymized_text: str,
    output_path: Path,
    *,
    template_path: Path = DEFAULT_TEMPLATE_PATH,
) -> Path:
    """Render anonymized CV text onto the ReleWant letterhead template."""
    cleaned_text = anonymized_text.strip()
    if not cleaned_text:
        raise ToolError("Anonymized CV content is empty and cannot be rendered.")
    if not template_path.is_file():
        raise ToolError(f"ReleWant letterhead template not found: {template_path}")

    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        from pypdf import PdfReader, PdfWriter

        template_reader = PdfReader(str(template_path))
        template_page_count = len(template_reader.pages)
        logger.debug("CV PDF template page count: %s", template_page_count)
        if not template_reader.pages:
            raise ToolError("ReleWant letterhead template does not contain any pages.")

        page_width = float(template_reader.pages[0].mediabox.width or 595.2755905511812)
        page_height = float(template_reader.pages[0].mediabox.height or 841.8897637795277)
        overlay_path = output_path.with_suffix(".overlay.pdf")
        _write_text_overlay(cleaned_text, overlay_path, page_width, page_height)

        overlay_reader = PdfReader(str(overlay_path))
        overlay_pages = list(overlay_reader.pages)
        generated_content_page_count = len(overlay_pages)
        logger.debug("CV PDF generated content page count: %s", generated_content_page_count)
        output_pages = _remove_duplicate_pdf_pages(overlay_pages)
        if len(output_pages) != generated_content_page_count:
            logger.debug(
                "CV PDF removed %s duplicate generated content page(s).",
                generated_content_page_count - len(output_pages),
            )
        if not output_pages:
            raise ToolError("Generated anonymized CV overlay does not contain any pages.")

        writer = PdfWriter()
        for page_number, overlay_page in enumerate(output_pages, start=1):
            logger.debug("CV PDF merging generated content page %s onto template page 1.", page_number)
            base_page = copy.deepcopy(template_reader.pages[0])
            base_page.merge_page(overlay_page)
            writer.add_page(base_page)
            logger.debug("CV PDF added output page %s.", page_number)

        writer_pages = getattr(writer, "pages", output_pages)
        final_output_page_count = len(writer_pages)
        logger.debug("CV PDF final output page count before saving: %s", final_output_page_count)
        with output_path.open("wb") as output_file:
            writer.write(output_file)
        return output_path
    except ToolError:
        raise
    except Exception as exc:
        raise ToolError(f"Failed to render anonymized CV PDF: {exc}") from exc
    finally:
        if "overlay_path" in locals():
            overlay_path.unlink(missing_ok=True)


def _remove_duplicate_pdf_pages(pages: list[object]) -> list[object]:
    """Remove generated pages that contain exactly the same information."""
    unique_pages: list[object] = []
    seen_fingerprints: set[str] = set()

    for page in pages:
        fingerprint = _pdf_page_fingerprint(page)
        if fingerprint and fingerprint in seen_fingerprints:
            continue
        unique_pages.append(page)
        if fingerprint:
            seen_fingerprints.add(fingerprint)

    return unique_pages


def _pdf_page_fingerprint(page: object) -> str:
    contents = getattr(page, "get_contents", None)
    if callable(contents):
        page_contents = contents()
        if page_contents is not None:
            streams = page_contents if isinstance(page_contents, list) else [page_contents]
            stream_data = b"".join(
                stream.get_data() for stream in streams if hasattr(stream, "get_data")
            )
            if stream_data:
                return hashlib.sha256(stream_data).hexdigest()

    extract_text = getattr(page, "extract_text", None)
    if callable(extract_text):
        page_text = extract_text() or ""
        normalized_text = "\n".join(line.strip() for line in page_text.splitlines() if line.strip())
        if normalized_text:
            return hashlib.sha256(normalized_text.encode("utf-8")).hexdigest()
    return ""


def _write_text_overlay(
    text: str, overlay_path: Path, page_width: float, page_height: float
) -> None:
    from reportlab.lib.colors import HexColor
    from reportlab.lib.units import mm
    from reportlab.pdfgen import canvas

    pdf = canvas.Canvas(str(overlay_path), pagesize=(page_width, page_height))
    pdf.setTitle("Anonymized CV")

    left_margin = 22 * mm
    right_margin = 22 * mm
    top_margin = 42 * mm
    bottom_margin = 22 * mm
    font_name = "Helvetica"
    bold_font_name = "Helvetica-Bold"
    font_size = 10
    line_height = 14
    section_gap = 8
    chars_per_line = max(
        40, int((page_width - left_margin - right_margin) / (font_size * 0.52))
    )

    y = page_height - top_margin
    pdf.setFillColor(HexColor("#222222"))
    pdf.setFont(font_name, font_size)

    for flow_line in _build_cv_flow_lines(text):
        wrapped_lines = textwrap.wrap(flow_line.text, width=chars_per_line) or [flow_line.text]
        required_height = len(wrapped_lines) * line_height
        if flow_line.starts_section:
            required_height += section_gap
        if y - required_height < bottom_margin:
            pdf.showPage()
            pdf.setFillColor(HexColor("#222222"))
            pdf.setFont(font_name, font_size)
            y = page_height - top_margin
        elif flow_line.starts_section:
            y -= section_gap

        for line in wrapped_lines:
            line_font_name, drawable_line = _pdf_line_style(line, font_name, bold_font_name)
            pdf.setFont(line_font_name, font_size)
            pdf.drawString(left_margin, y, drawable_line)
            y -= line_height
    pdf.save()


class _CvFlowLine:
    def __init__(self, text: str, starts_section: bool = False) -> None:
        self.text = text
        self.starts_section = starts_section


def _build_cv_flow_lines(text: str) -> list[_CvFlowLine]:
    """Build drawable CV lines with spacing only before distinct sections."""
    flow_lines: list[_CvFlowLine] = []
    previous_was_section = False

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        is_section = _is_section_heading(line)
        starts_section = bool(flow_lines) and is_section and not previous_was_section
        flow_lines.append(_CvFlowLine(line, starts_section=starts_section))
        previous_was_section = is_section

    return flow_lines


def _is_section_heading(line: str) -> bool:
    stripped_line = line.strip()
    if stripped_line.startswith("**") and stripped_line.endswith("**") and len(stripped_line) > 4:
        return True
    normalized = stripped_line.rstrip(":").lower()
    return normalized in {
        "anagraphical data",
        "experience",
        "education",
        "skills",
        "certifications",
        "hobby",
    }


def _pdf_line_style(line: str, font_name: str, bold_font_name: str) -> tuple[str, str]:
    stripped_line = line.strip()
    if stripped_line.startswith("**") and stripped_line.endswith("**") and len(stripped_line) > 4:
        return bold_font_name, stripped_line.removeprefix("**").removesuffix("**")
    return font_name, line

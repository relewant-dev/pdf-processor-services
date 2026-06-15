from __future__ import annotations

import copy
import textwrap
from pathlib import Path

from fastmcp.exceptions import ToolError

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_TEMPLATE_PATH = REPOSITORY_ROOT / "stationery" / "relewant-sa-letterhead.pdf"


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
        if not template_reader.pages:
            raise ToolError("ReleWant letterhead template does not contain any pages.")

        page_width = float(template_reader.pages[0].mediabox.width or 595.2755905511812)
        page_height = float(template_reader.pages[0].mediabox.height or 841.8897637795277)
        overlay_path = output_path.with_suffix(".overlay.pdf")
        _write_text_overlay(cleaned_text, overlay_path, page_width, page_height)

        overlay_reader = PdfReader(str(overlay_path))
        writer = PdfWriter()
        for overlay_page in overlay_reader.pages:
            base_page = copy.deepcopy(template_reader.pages[0])
            base_page.merge_page(overlay_page)
            writer.add_page(base_page)

        with output_path.open("wb") as output_file:
            writer.write(output_file)
        overlay_path.unlink(missing_ok=True)
        return output_path
    except ToolError:
        raise
    except Exception as exc:
        raise ToolError(f"Failed to render anonymized CV PDF: {exc}") from exc


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
    font_size = 10
    line_height = 14
    chars_per_line = max(
        40, int((page_width - left_margin - right_margin) / (font_size * 0.52))
    )

    y = page_height - top_margin
    pdf.setFillColor(HexColor("#222222"))
    pdf.setFont(font_name, font_size)

    for paragraph in text.splitlines():
        wrapped_lines = textwrap.wrap(paragraph, width=chars_per_line) if paragraph.strip() else [""]
        for line in wrapped_lines:
            if y <= bottom_margin:
                pdf.showPage()
                pdf.setFillColor(HexColor("#222222"))
                pdf.setFont(font_name, font_size)
                y = page_height - top_margin
            pdf.drawString(left_margin, y, line)
            y -= line_height
    pdf.save()

from __future__ import annotations

import io
import os
import re
import textwrap
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from xml.etree import ElementTree

from pypdf import PdfReader
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFError, TTFont
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import (
    CondPageBreak,
    HRFlowable,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from .schemas import Artifact, ProfileFact


@dataclass(slots=True)
class ExtractionResult:
    text: str
    method: str
    warnings: list[str] = field(default_factory=list)
    pages: list[str] = field(default_factory=list)


class UnsupportedDocument(ValueError):
    pass


def extract_document_text(
    filename: str, content: bytes, *, allow_ocr: bool = True
) -> ExtractionResult:
    suffix = Path(filename).suffix.casefold()
    if suffix in {".txt", ".md"}:
        return ExtractionResult(
            content.decode("utf-8", errors="replace").strip(), "plain_text"
        )
    if suffix == ".docx":
        return ExtractionResult(_extract_docx(content), "docx_xml")
    if suffix == ".pdf":
        result = _extract_pdf(content)
        if result.text or not allow_ocr:
            return result
        return _extract_pdf_ocr(content, result.warnings)
    raise UnsupportedDocument("Supported formats: .txt, .md, .docx and text-layer .pdf")


def _extract_docx(content: bytes) -> str:
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            info = archive.getinfo("word/document.xml")
            if info.file_size > 10 * 1024 * 1024:
                raise UnsupportedDocument("DOCX document XML exceeds 10 MB")
            xml = archive.read("word/document.xml")
    except (zipfile.BadZipFile, KeyError) as exc:
        raise UnsupportedDocument("Invalid DOCX document") from exc
    root = ElementTree.fromstring(xml)
    paragraphs: list[str] = []
    for paragraph in (node for node in root.iter() if node.tag.endswith("}p")):
        text = "".join(
            node.text or "" for node in paragraph.iter() if node.tag.endswith("}t")
        )
        cleaned = " ".join(text.split())
        if cleaned:
            paragraphs.append(cleaned)
    return "\n".join(paragraphs)


def _extract_pdf(content: bytes) -> ExtractionResult:
    try:
        reader = PdfReader(io.BytesIO(content))
        if len(reader.pages) > 50:
            raise UnsupportedDocument("PDF exceeds the 50-page import limit")
        pages = [(page.extract_text() or "").strip() for page in reader.pages]
    except UnsupportedDocument:
        raise
    except Exception as exc:
        raise UnsupportedDocument("Invalid or encrypted PDF") from exc
    text = "\n\n".join(page for page in pages if page).strip()
    warnings: list[str] = []
    if not text:
        warnings.append("No text layer detected.")
    return ExtractionResult(text, "pypdf", warnings, pages)


def _extract_pdf_ocr(content: bytes, warnings: list[str]) -> ExtractionResult:
    """Best-effort local OCR; no document bytes leave the machine."""
    try:
        import fitz  # type: ignore[import-not-found]
        import pytesseract  # type: ignore[import-not-found]
        from PIL import Image  # type: ignore[import-not-found]
    except ImportError:
        return ExtractionResult(
            "",
            "pypdf",
            [
                *warnings,
                "No text layer detected. Install the optional [ocr] dependencies and local Tesseract.",
            ],
        )

    pages: list[str] = []
    try:
        with fitz.open(stream=content, filetype="pdf") as document:
            if document.page_count > 20:
                raise UnsupportedDocument("OCR is limited to 20 scanned pages")
            for page in document:
                pixmap = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
                if pixmap.width * pixmap.height > 20_000_000:
                    raise UnsupportedDocument("OCR page exceeds the pixel limit")
                image = Image.frombytes(
                    "RGB", [pixmap.width, pixmap.height], pixmap.samples
                )
                pages.append(pytesseract.image_to_string(image, timeout=30).strip())
    except UnsupportedDocument:
        raise
    except (OSError, RuntimeError) as exc:
        return ExtractionResult(
            "", "pypdf", [*warnings, f"Local OCR unavailable: {exc}"]
        )
    text = "\n\n".join(page for page in pages if page).strip()
    if not text:
        warnings.append("Local OCR completed but produced no text.")
    return ExtractionResult(
        text,
        "pytesseract" if text else "pypdf",
        warnings,
        pages,
    )


def facts_from_text(
    text: str,
    *,
    source_document_id: str | None = None,
    language: str | None = None,
    source_page: int | None = None,
) -> list[ProfileFact]:
    """Extract reviewable evidence instead of treating every PDF line as a fact."""
    injection_markers = (
        "ignore previous",
        "ignore all previous",
        "system prompt",
        "developer message",
        "call this tool",
    )
    headings = {
        "perfil profesional",
        "professional summary",
        "experiencia profesional",
        "professional experience",
        "proyectos seleccionados",
        "selected projects",
        "habilidades técnicas",
        "technical skills",
        "educación y formación especializada",
        "education and specialized training",
        "educación",
        "education",
        "habilidades",
        "skills",
        "certificaciones",
        "certifications",
    }

    raw_lines = text.splitlines()
    if len(raw_lines) <= 2:
        raw_lines = re.split(r"(?<=[.!?])\s+", text)

    prepared: list[tuple[int, str, bool]] = []
    for line_number, raw_line in enumerate(raw_lines, start=1):
        bullet = bool(re.match(r"^\s*[•●▪◦*-]\s+", raw_line))
        line = re.sub(r"\s+", " ", raw_line).strip(" •●▪◦*-\t")
        line = re.sub(r"\[redacted-(?:email|phone)\]", "", line, flags=re.IGNORECASE)
        line = re.sub(r"\s*\|\s*(?=\||$)", " ", line).strip(" |,-")
        lowered = line.casefold()
        if len(line) < 12 or any(marker in lowered for marker in injection_markers):
            continue
        if lowered in headings or re.fullmatch(r"(?:page|página)\s+\d+", lowered):
            continue
        if re.match(r"^(?:linkedin|github|portfolio|portafolio)\s*:", lowered):
            continue
        if not re.search(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ]{3}", line):
            continue
        prepared.append((line_number, line, bullet))

    grouped: list[tuple[int, int, str]] = []
    current_text = ""
    current_start = 0
    current_end = 0
    current_bullet = False

    def flush() -> None:
        nonlocal current_text, current_start, current_end, current_bullet
        if 12 <= len(current_text) <= 700:
            grouped.append((current_start, current_end, current_text.strip()))
        current_text = ""
        current_start = current_end = 0
        current_bullet = False

    for line_number, line, bullet in prepared:
        starts_distinct_record = bool(
            bullet
            or (" | " in line and not current_bullet)
            or re.match(
                r"^(?:stack|automation|automatización|development|desarrollo|data|datos)\s*:",
                line,
                re.IGNORECASE,
            )
        )
        if not current_text:
            current_text, current_start, current_end, current_bullet = (
                line,
                line_number,
                line_number,
                bullet,
            )
            continue
        previous_complete = bool(re.search(r"[.!?]$", current_text))
        if starts_distinct_record or previous_complete or len(current_text) + len(line) > 680:
            flush()
            current_text, current_start, current_end, current_bullet = (
                line,
                line_number,
                line_number,
                bullet,
            )
        else:
            current_text = f"{current_text} {line}"
            current_end = line_number
    flush()

    facts: list[ProfileFact] = []
    seen: set[str] = set()
    for start_line, end_line, line in grouped:
        normalized = re.sub(r"\W+", " ", line.casefold()).strip()
        if normalized in seen:
            continue
        seen.add(normalized)
        lowered = line.casefold()
        category = "experience"
        if any(
            marker in lowered
            for marker in (
                "degree",
                "university",
                "bachelor",
                "master",
                "universidad",
                "licenciatura",
                "bachillerato",
                "maestría",
                "maestria",
                "educación",
                "educacion",
            )
        ):
            category = "education"
        elif any(
            marker in lowered
            for marker in (
                "achievement",
                "award",
                "logro",
                "premio",
                "reconocimiento",
                "reducing",
                "reduced",
                "reduciendo",
                "logrando",
            )
        ) or re.search(r"\b\d+(?:[.,]\d+)?\s*%", line):
            category = "achievement"
        elif any(
            marker in lowered
            for marker in (
                "python",
                "javascript",
                "sql",
                "skill",
                "skills",
                "habilidad",
                "habilidades",
                "tecnología",
                "tecnologia",
                "aws",
                "playwright",
                "selenium",
                "react",
                "docker",
                "postman",
            )
        ):
            category = "skill"
        facts.append(
            ProfileFact(
                category=category,
                text=line,
                evidence=line,
                source_document_id=source_document_id,
                source_page=source_page,
                source_span=(
                    f"line:{start_line}"
                    if start_line == end_line
                    else f"lines:{start_line}-{end_line}"
                ),
                language=language,
                verified=False,
            )
        )
    return facts


def render_artifact_pdf(
    artifact: Artifact,
    output_path: str | Path,
    *,
    styled: bool = False,
) -> Path:
    if artifact.kind == "interview_guide":
        return _render_interview_guide_pdf(artifact, output_path)

    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    styles = getSampleStyleSheet()
    body = ParagraphStyle(
        "Body",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=10.5,
        leading=14,
        textColor=colors.HexColor("#273142") if styled else colors.black,
        alignment=TA_LEFT,
        spaceAfter=7,
    )
    title = ParagraphStyle(
        "Title",
        parent=styles["Title"],
        fontName="Helvetica-Bold",
        fontSize=20 if styled else 17,
        leading=21,
        spaceAfter=14,
        textColor=colors.HexColor("#0F6F70") if styled else colors.black,
    )
    section = ParagraphStyle(
        "Section",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=12,
        leading=15,
        spaceBefore=8,
        spaceAfter=6,
        textColor=colors.HexColor("#147D7A") if styled else colors.black,
    )
    bullet = ParagraphStyle(
        "Bullet",
        parent=body,
        leftIndent=13,
        firstLineIndent=-8,
        spaceAfter=4,
    )
    document = SimpleDocTemplate(
        str(path),
        pagesize=LETTER,
        leftMargin=0.8 * inch,
        rightMargin=0.8 * inch,
        topMargin=0.7 * inch,
        bottomMargin=0.7 * inch,
        title=artifact.title,
        author="Job Orchestrator",
    )
    story = [Paragraph(_xml_escape(artifact.title), title)]
    for raw_line in artifact.content.splitlines():
        line = raw_line.strip()
        if not line:
            story.append(Spacer(1, 4))
            continue
        if line.startswith("## "):
            story.append(Paragraph(_xml_escape(line[3:]), section))
            continue
        style = bullet if line.startswith("- ") else body
        display_line = f"- {line[2:]}" if line.startswith("- ") else line
        display_line = re.sub(r"[*`]+", "", display_line)
        for chunk in textwrap.wrap(display_line, width=800, break_long_words=False) or [
            display_line
        ]:
            story.append(Paragraph(_xml_escape(chunk), style))

    spanish_document = "## Puesto" in artifact.content

    def draw_footer(canvas: Canvas, _document: SimpleDocTemplate) -> None:
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.HexColor("#596273"))
        footer = (
            "Borrador local - requiere revisión humana"
            if spanish_document
            else "Local draft - human review required"
        )
        page_label = "Página" if spanish_document else "Page"
        canvas.drawString(0.8 * inch, 0.38 * inch, footer)
        canvas.drawRightString(
            LETTER[0] - 0.8 * inch,
            0.38 * inch,
            f"{page_label} {canvas.getPageNumber()}",
        )
        canvas.restoreState()

    document.build(story, onFirstPage=draw_footer, onLaterPages=draw_footer)
    return path


_URL_RE = re.compile(r"https://[^\s<>]+")
_FACT_REF_RE = re.compile(
    r"\[\s*fact_id\s*:\s*[^\]]+\]|\b(?:fact|about)_[A-Za-z0-9_-]+\b",
    re.IGNORECASE,
)


def register_unicode_document_fonts() -> tuple[str, str]:
    """Register a Unicode family when the host provides one, with a safe fallback."""

    registered_fonts = set(pdfmetrics.getRegisteredFontNames())
    if {"AmeWorkUI", "AmeWorkUI-Bold"} <= registered_fonts:
        return "AmeWorkUI", "AmeWorkUI-Bold"
    windows_root = Path(os.environ.get("WINDIR", "C:/Windows"))
    candidates = [
        (
            windows_root / "Fonts" / "segoeui.ttf",
            windows_root / "Fonts" / "segoeuib.ttf",
        ),
        (
            Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
            Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
        ),
        (
            Path("/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf"),
            Path("/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf"),
        ),
        (
            Path("/System/Library/Fonts/Supplemental/Arial.ttf"),
            Path("/System/Library/Fonts/Supplemental/Arial Bold.ttf"),
        ),
    ]
    for regular_path, bold_path in candidates:
        if not regular_path.is_file() or not bold_path.is_file():
            continue
        try:
            pdfmetrics.registerFont(TTFont("AmeWorkUI", str(regular_path)))
            pdfmetrics.registerFont(TTFont("AmeWorkUI-Bold", str(bold_path)))
            pdfmetrics.registerFontFamily(
                "AmeWorkUI",
                normal="AmeWorkUI",
                bold="AmeWorkUI-Bold",
                italic="AmeWorkUI",
                boldItalic="AmeWorkUI-Bold",
            )
            return "AmeWorkUI", "AmeWorkUI-Bold"
        except (
            OSError,
            TTFError,
        ):  # pragma: no cover - host font corruption is non-fatal.
            return "Helvetica", "Helvetica-Bold"
    return "Helvetica", "Helvetica-Bold"


def _guide_markup(value: str) -> str:
    """Escape untrusted text while preserving safe HTTPS links and simple fact references."""

    cleaned = re.sub(r"[*`]+", "", value.strip())
    parts: list[str] = []
    cursor = 0
    for match in _URL_RE.finditer(cleaned):
        parts.append(_xml_escape(cleaned[cursor : match.start()]))
        url = match.group(0).rstrip(".,;)")
        trailing = match.group(0)[len(url) :]
        escaped_url = _xml_escape(url)
        parts.append(
            f'<link href="{escaped_url}" color="#086A72"><u>{escaped_url}</u></link>'
        )
        parts.append(_xml_escape(trailing))
        cursor = match.end()
    parts.append(_xml_escape(cleaned[cursor:]))
    return "".join(parts)


def _guide_labeled_markup(value: str) -> str:
    labels = (
        "Perfil profesional",
        "Professional profile",
        "Puesto",
        "Role",
        "Empresa",
        "Company",
        "Idioma del CV",
        "Resume language",
        "Encaje estimado",
        "Estimated fit",
        "Ubicación y modalidad",
        "Location and work mode",
        "Fecha de publicación",
        "Published",
        "Procedencia",
        "Source",
        "Enlace final de la empresa",
        "Final company link",
        "Enlace del portal",
        "Portal link",
        "Requisito",
        "Requirement",
        "Estado",
        "Status",
        "Evidencia confirmada",
        "Confirmed evidence",
        "Pregunta",
        "Question",
        "Respuesta técnica de referencia",
        "Technical reference answer",
        "Respuesta de referencia",
        "Reference answer",
        "Cómo conectarlo con tu experiencia",
        "How to connect it to your experience",
        "Tema para estudiar",
        "Study topic",
        "Consigna",
        "Prompt",
        "Criterios de evaluación",
        "Evaluation criteria",
        "Preparación sugerida",
        "Suggested preparation",
        "Situación",
        "Situation",
        "Tarea",
        "Task",
        "Acción personal",
        "Personal action",
        "Resultado verificable",
        "Verifiable result",
    )
    for label in labels:
        prefix = f"{label}:"
        if value.startswith(prefix):
            remainder = value[len(prefix) :].strip()
            return f"<b>{_xml_escape(label)}:</b> {_guide_markup(remainder)}"
    return _guide_markup(value)


def _guide_callout_kind(line: str) -> str | None:
    folded = line.casefold()
    if folded.startswith(
        (
            "respuesta técnica de referencia:",
            "technical reference answer:",
            "respuesta de referencia:",
            "reference answer:",
        )
    ):
        return "reference"
    if folded.startswith(
        ("cómo conectarlo con tu experiencia:", "how to connect it to your experience:")
    ):
        return "evidence"
    if folded.startswith(("tema para estudiar:", "study topic:")):
        return "study"
    if folded.startswith(("estado: respaldado", "status: supported")):
        return "evidence"
    if folded.startswith(("estado: brecha", "status: identified gap")):
        return "study"
    if folded.startswith(("estado: evidencia desconocida", "status: evidence unknown")):
        return "unknown"
    if folded.startswith(
        (
            "aviso:",
            "notice:",
            "nota de alcance:",
            "scope note:",
            "revisión humana",
            "human review",
        )
    ):
        return "notice"
    return None


def _guide_callout(
    text: str,
    style: ParagraphStyle,
    kind: str,
) -> Table:
    palette = {
        "reference": ("#E6F5F3", "#0B7773"),
        "evidence": ("#E9F6DF", "#4D7D32"),
        "study": ("#FFF2CE", "#AD7415"),
        "unknown": ("#EEF1F0", "#66706B"),
        "notice": ("#F7EEE3", "#A35F42"),
    }
    background, accent = palette[kind]
    table = Table(
        [[Paragraph(_guide_labeled_markup(text), style)]],
        colWidths=[6.72 * inch],
        hAlign="LEFT",
    )
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor(background)),
                ("BOX", (0, 0), (-1, -1), 0.8, colors.HexColor(accent)),
                ("LINEBEFORE", (0, 0), (0, -1), 4, colors.HexColor(accent)),
                ("LEFTPADDING", (0, 0), (-1, -1), 12),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    return table


def _validate_interview_guide_artifact(artifact: Artifact) -> None:
    # The model's structured response already constrains the requested section and
    # question counts. Headings themselves are presentation text: requiring one exact
    # sentence rejected otherwise complete guides such as "Role overview". Validate
    # semantic structure and safety here instead of literal wording.
    visible_content = re.sub(r"[#*_`>-]", "", artifact.content).strip()
    if len(visible_content) < 1_000:
        raise ValueError("Interview guide content is incomplete")
    referenced_ids = set(_FACT_REF_RE.findall(artifact.content))
    if referenced_ids:
        raise ValueError("Interview guide must not expose internal fact identifiers")
    if any(not claim.text.strip() or not claim.fact_ids for claim in artifact.claims):
        raise ValueError(
            "Every interview guide claim must contain text and fact evidence"
        )
    insecure_links = re.findall(r"(?<!s)http://[^\s<>]+", artifact.content)
    if insecure_links:
        raise ValueError("Interview guide contains an insecure external link")


def _render_interview_guide_pdf(
    artifact: Artifact,
    output_path: str | Path,
) -> Path:
    _validate_interview_guide_artifact(artifact)
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    font_regular, font_bold = register_unicode_document_fonts()
    spanish = bool(
        (artifact.language or "").casefold().startswith("es")
        or "## 1. De qué trata el puesto" in artifact.content
    )

    body = ParagraphStyle(
        "GuideBody",
        fontName=font_regular,
        fontSize=9.25,
        leading=13,
        textColor=colors.HexColor("#263936"),
        spaceAfter=6,
        allowWidows=0,
        allowOrphans=0,
    )
    body_small = ParagraphStyle(
        "GuideBodySmall",
        parent=body,
        fontSize=8.4,
        leading=11.5,
        textColor=colors.HexColor("#42544F"),
    )
    cover_title = ParagraphStyle(
        "GuideCoverTitle",
        parent=body,
        fontName=font_bold,
        fontSize=23,
        leading=28,
        textColor=colors.HexColor("#103F43"),
        spaceBefore=18,
        spaceAfter=16,
    )
    section_style = ParagraphStyle(
        "GuideSection",
        parent=body,
        fontName=font_bold,
        fontSize=13,
        leading=16,
        textColor=colors.white,
    )
    subsection_style = ParagraphStyle(
        "GuideSubsection",
        parent=body,
        fontName=font_bold,
        fontSize=10.4,
        leading=13,
        textColor=colors.HexColor("#153E3B"),
        spaceAfter=0,
    )
    bullet_style = ParagraphStyle(
        "GuideBullet",
        parent=body,
        leftIndent=15,
        firstLineIndent=-10,
        bulletIndent=2,
        spaceAfter=4,
    )
    cover_meta_style = ParagraphStyle(
        "GuideCoverMeta",
        parent=body,
        fontSize=10,
        leading=14,
        textColor=colors.HexColor("#344D49"),
    )

    document = SimpleDocTemplate(
        str(path),
        pagesize=LETTER,
        leftMargin=0.65 * inch,
        rightMargin=0.65 * inch,
        topMargin=0.78 * inch,
        bottomMargin=0.7 * inch,
        title=artifact.title,
        author="Workspace",
        subject="Professional interview preparation guide",
        creator="Workspace",
    )
    story: list[object] = []
    brand = Table(
        [
            [
                Paragraph("<b>WORKSPACE</b>", section_style),
                Paragraph(
                    "CAREER BRIEF  /  02" if not spanish else "GUÍA PROFESIONAL  /  02",
                    ParagraphStyle(
                        "GuideBrandRight",
                        parent=body_small,
                        alignment=TA_CENTER,
                        textColor=colors.white,
                    ),
                ),
            ]
        ],
        colWidths=[3.7 * inch, 3.02 * inch],
    )
    brand.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#0B7773")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 14),
                ("RIGHTPADDING", (0, 0), (-1, -1), 14),
                ("TOPPADDING", (0, 0), (-1, -1), 11),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 11),
                ("LINEBELOW", (0, 0), (-1, -1), 4, colors.HexColor("#9BCB57")),
            ]
        )
    )
    story.extend(
        [
            brand,
            Paragraph(_guide_markup(artifact.title), cover_title),
            HRFlowable(
                width="100%",
                thickness=1,
                color=colors.HexColor("#B8C8BD"),
                spaceBefore=2,
                spaceAfter=14,
            ),
        ]
    )

    for raw_line in artifact.content.split("\n"):
        if raw_line.strip(" \t\r") == "\f":
            story.append(PageBreak())
            continue
        line = raw_line.strip()
        if not line:
            story.append(Spacer(1, 3))
            continue
        if line.startswith("# "):
            # The title is already rendered on the cover; avoid duplicating a model's
            # Markdown H1 as ordinary body text.
            continue
        if line.startswith("## "):
            story.append(CondPageBreak(0.7 * inch))
            section_table = Table(
                [[Paragraph(_guide_markup(line[3:]), section_style)]],
                colWidths=[6.72 * inch],
                hAlign="LEFT",
            )
            section_table.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#0B7773")),
                        ("LINEBELOW", (0, 0), (-1, -1), 3, colors.HexColor("#9BCB57")),
                        ("LEFTPADDING", (0, 0), (-1, -1), 12),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                        ("TOPPADDING", (0, 0), (-1, -1), 9),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                    ]
                )
            )
            story.extend([section_table, Spacer(1, 8)])
            continue
        question_heading = re.match(
            r"^(?:Q|P|Question|Pregunta)\s*\d{1,2}\s*[.):\-]\s*",
            line,
            re.IGNORECASE,
        )
        if line.startswith("### ") or question_heading:
            story.append(CondPageBreak(0.62 * inch))
            heading_text = line.removeprefix("### ")
            heading = Table(
                [[Paragraph(_guide_markup(heading_text), subsection_style)]],
                colWidths=[6.72 * inch],
                hAlign="LEFT",
            )
            heading.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#EDF5E8")),
                        ("LINEBEFORE", (0, 0), (0, -1), 4, colors.HexColor("#9BCB57")),
                        ("LEFTPADDING", (0, 0), (-1, -1), 10),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                        ("TOPPADDING", (0, 0), (-1, -1), 6),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                    ]
                )
            )
            story.extend([heading, Spacer(1, 5)])
            continue
        if line.startswith("- "):
            story.append(
                Paragraph(
                    _guide_markup(line[2:]),
                    bullet_style,
                    bulletText="-",
                )
            )
            continue
        kind = _guide_callout_kind(line)
        if kind:
            story.extend([_guide_callout(line, body, kind), Spacer(1, 6)])
            continue
        style = (
            cover_meta_style
            if not any(isinstance(item, PageBreak) for item in story)
            else body
        )
        story.append(Paragraph(_guide_labeled_markup(line), style))

    def draw_page(canvas: Canvas, _document: SimpleDocTemplate) -> None:
        canvas.saveState()
        width, height = LETTER
        canvas.setFillColor(colors.HexColor("#F8F4E8"))
        canvas.rect(0, 0, width, height, fill=1, stroke=0)
        canvas.setFillColor(colors.HexColor("#0B7773"))
        canvas.rect(0, 0, 0.12 * inch, height, fill=1, stroke=0)
        canvas.setStrokeColor(colors.HexColor("#AFC3B6"))
        canvas.setLineWidth(0.6)
        canvas.line(
            0.65 * inch, height - 0.48 * inch, width - 0.65 * inch, height - 0.48 * inch
        )
        canvas.setFont(font_bold, 7.5)
        canvas.setFillColor(colors.HexColor("#0B7773"))
        canvas.drawString(
            0.65 * inch, height - 0.36 * inch, "WORKSPACE // CAREER PREPARATION"
        )
        canvas.setFont(font_regular, 7.2)
        canvas.setFillColor(colors.HexColor("#5B6965"))
        short_title = (
            artifact.title if len(artifact.title) <= 72 else f"{artifact.title[:69]}..."
        )
        canvas.drawRightString(width - 0.65 * inch, height - 0.36 * inch, short_title)
        canvas.setStrokeColor(colors.HexColor("#AFC3B6"))
        canvas.line(0.65 * inch, 0.48 * inch, width - 0.65 * inch, 0.48 * inch)
        footer = (
            "Borrador local - revisión humana obligatoria"
            if spanish
            else "Local draft - human review required"
        )
        canvas.setFont(font_regular, 7.5)
        canvas.drawString(0.65 * inch, 0.31 * inch, footer)
        page_label = "PÁGINA" if spanish else "PAGE"
        canvas.drawRightString(
            width - 0.65 * inch,
            0.31 * inch,
            f"{page_label} {canvas.getPageNumber():02d}",
        )
        canvas.restoreState()

    document.build(story, onFirstPage=draw_page, onLaterPages=draw_page)
    _validate_rendered_guide_pdf(path, artifact)
    return path


def _validate_rendered_guide_pdf(path: Path, artifact: Artifact) -> None:
    try:
        reader = PdfReader(path)
    except Exception as exc:  # pragma: no cover - pypdf exposes many parser errors.
        raise ValueError("Rendered interview guide is not a readable PDF") from exc
    # A complete guide may paginate differently depending on the language and the
    # length of vacancy-specific answers. Readability matters more than an arbitrary
    # minimum page count.
    if not 3 <= len(reader.pages) <= 30:
        raise ValueError(
            f"Rendered interview guide has an unexpected page count: {len(reader.pages)}"
        )
    page_texts = [(page.extract_text() or "").strip() for page in reader.pages]
    if any(len(text) < 24 for text in page_texts):
        raise ValueError(
            "Rendered interview guide contains an empty or incomplete page"
        )
    full_text = "\n".join(page_texts)
    # Some PDF extractors substitute typography such as an en dash even when it
    # renders correctly. Validate the stable leading words instead of comparing
    # the model title byte-for-byte.
    title_words = re.findall(r"[a-z0-9]+", artifact.title.casefold())[:5]
    extracted_words = " ".join(re.findall(r"[a-z0-9]+", full_text.casefold()))
    if not title_words or " ".join(title_words) not in extracted_words:
        raise ValueError("Rendered interview guide is missing its title")
    expected_questions = len(
        re.findall(
            r"^### (?:Pregunta técnica|Technical question) \d+",
            artifact.content,
            re.MULTILINE,
        )
    )
    extracted_questions = len(
        re.findall(r"(?:Pregunta técnica|Technical question)\s+\d+", full_text)
    )
    if extracted_questions < expected_questions:
        raise ValueError(
            "Rendered interview guide lost one or more technical questions"
        )
    if _URL_RE.search(artifact.content):
        link_annotations = 0
        for page in reader.pages:
            for annotation in page.get("/Annots", []):
                resolved = annotation.get_object()
                if resolved.get("/Subtype") == "/Link":
                    link_annotations += 1
        if link_annotations == 0:
            raise ValueError(
                "Rendered interview guide is missing its clickable posting link"
            )


def _xml_escape(value: str) -> str:
    return value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

from __future__ import annotations

import io
import re
import textwrap
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from uuid import uuid4
from xml.etree import ElementTree

from pypdf import PdfReader
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

from .schemas import Artifact, JobRecord, Profile, ProfileFact


@dataclass(slots=True)
class ExtractionResult:
    text: str
    method: str
    warnings: list[str] = field(default_factory=list)


class UnsupportedDocument(ValueError):
    pass


def extract_document_text(filename: str, content: bytes, *, allow_ocr: bool = True) -> ExtractionResult:
    suffix = Path(filename).suffix.casefold()
    if suffix in {".txt", ".md"}:
        return ExtractionResult(content.decode("utf-8", errors="replace").strip(), "plain_text")
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
        text = "".join(node.text or "" for node in paragraph.iter() if node.tag.endswith("}t"))
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
    return ExtractionResult(text, "pypdf", warnings)


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
                pages.append(
                    pytesseract.image_to_string(image, timeout=30).strip()
                )
    except UnsupportedDocument:
        raise
    except (OSError, RuntimeError) as exc:
        return ExtractionResult("", "pypdf", [*warnings, f"Local OCR unavailable: {exc}"])
    text = "\n\n".join(page for page in pages if page).strip()
    if not text:
        warnings.append("Local OCR completed but produced no text.")
    return ExtractionResult(text, "pytesseract" if text else "pypdf", warnings)


def facts_from_text(
    text: str,
    *,
    source_document_id: str | None = None,
    language: str | None = None,
) -> list[ProfileFact]:
    """Extract conservative candidate facts; the user still has to verify them."""
    facts: list[ProfileFact] = []
    candidates = text.splitlines()
    if len(candidates) <= 2:
        candidates = re.split(r"(?<=[.!?])\s+", text)
    for line in (item.strip(" -\t") for item in candidates):
        if len(line) < 12 or len(line) > 300:
            continue
        lowered = line.casefold()
        if any(
            marker in lowered
            for marker in (
                "ignore previous",
                "ignore all previous",
                "system prompt",
                "developer message",
                "call this tool",
            )
        ):
            continue
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
            )
        ):
            category = "skill"
        elif any(
            marker in lowered
            for marker in ("achievement", "award", "logro", "premio", "reconocimiento")
        ):
            category = "achievement"
        facts.append(
            ProfileFact(
                category=category,
                text=line,
                evidence=line,
                source_document_id=source_document_id,
                source_span=line[:120],
                language=language if language in {"es", "en"} else None,
                verified=False,
            )
        )
        if len(facts) >= 40:
            break
    return facts


def render_artifact_pdf(
    artifact: Artifact,
    output_path: str | Path,
    *,
    styled: bool = False,
) -> Path:
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
        for chunk in textwrap.wrap(display_line, width=800, break_long_words=False) or [display_line]:
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


@dataclass(slots=True)
class PackageRenderResult:
    zip_path: Path
    files: list[Path]


def render_application_package(
    artifact: Artifact,
    profile: Profile,
    job: JobRecord,
    output_dir: str | Path,
    *,
    include_cover_letter: bool = True,
) -> PackageRenderResult:
    """Render an immutable PDF-only package from verified, claim-linked facts."""
    directory = Path(output_dir) / _safe_slug(f"{job.company}-{job.title}-{artifact.artifact_id}")
    directory.mkdir(parents=True, exist_ok=True)
    verified_by_id = {fact.fact_id: fact for fact in profile.facts if fact.verified}
    claim_fact_ids = {
        fact_id for claim in artifact.claims for fact_id in claim.fact_ids
    }
    facts = [
        fact
        for fact in profile.facts
        if fact.fact_id in claim_fact_ids and fact.fact_id in verified_by_id
    ]
    evidence = "\n".join(f"- {fact.text} [fact_id: {fact.fact_id}]" for fact in facts)
    if not evidence:
        evidence = "No verified facts were selected. Export requires manual review."

    requirements = _job_requirements(job)
    matrix_lines: list[str] = []
    gaps: list[str] = []
    for requirement in requirements:
        matched = _best_evidence(requirement, facts)
        if matched is None:
            matrix_lines.append(f"- Requirement: {requirement}\n  Evidence: unknown")
            gaps.append(f"- {requirement}")
        else:
            matrix_lines.append(
                f"- Requirement: {requirement}\n"
                f"  Evidence: {matched.text} [fact_id: {matched.fact_id}]"
            )
    matrix = "\n".join(matrix_lines) or "- No explicit requirements were supplied by the source."
    gap_text = "\n".join(gaps) or "- No unmapped requirement in the available source text."
    interview_questions = "\n".join(
        f"- Explain a confirmed example relevant to: {requirement}"
        for requirement in requirements[:3]
    ) or "- Ask the employer to clarify the role's top three outcomes."
    source_url = str(job.url) if job.url else "not supplied"
    posted = job.posted_at.date().isoformat() if job.posted_at else "unknown"
    company_info = (
        f"- Company: {job.company}\n"
        f"- Role: {job.title}\n"
        f"- Location: {job.location or 'unknown'}\n"
        f"- Source: {job.source}\n"
        f"- Canonical URL: {source_url}\n"
        f"- Posted date: {posted}\n"
        f"- Retrieved: {job.retrieved_at.date().isoformat()}"
    )

    common = (
        f"Candidate: {profile.name}\n\nTarget role: {job.title}\nCompany: {job.company}\n\n"
        f"## Verified professional evidence\n\n{evidence}"
    )
    documents = [
        (
            "cv_ats.pdf",
            Artifact(
                run_id=artifact.run_id,
                job_id=job.job_id,
                profile_id=profile.profile_id,
                kind="cv_ats",
                title=f"{profile.name} - {job.title}",
                content=common,
                claims=artifact.claims,
            ),
            False,
        ),
        (
            "cv_styled.pdf",
            Artifact(
                run_id=artifact.run_id,
                job_id=job.job_id,
                profile_id=profile.profile_id,
                kind="cv_styled",
                title=f"{profile.name} - {job.title}",
                content=common,
                claims=artifact.claims,
            ),
            True,
        ),
        (
            "application_brief.pdf",
            Artifact(
                run_id=artifact.run_id,
                job_id=job.job_id,
                profile_id=profile.profile_id,
                kind="application_brief",
                title=f"Application brief - {job.company}",
                content=(
                    f"{artifact.content}\n\n"
                    f"## Verified company and vacancy information\n\n{company_info}\n\n"
                    f"## Requirement-to-evidence matrix\n\n{matrix}\n\n"
                    f"## Gaps and unknowns\n\n{gap_text}\n\n"
                    f"## Interview preparation\n\n{interview_questions}\n\n"
                    "Open questions must be resolved by the candidate before applying."
                ),
                claims=artifact.claims,
            ),
            False,
        ),
    ]
    if include_cover_letter:
        documents.append(
            (
                "cover_letter.pdf",
                Artifact(
                    run_id=artifact.run_id,
                    job_id=job.job_id,
                    profile_id=profile.profile_id,
                    kind="cover_letter",
                    title=f"Cover letter - {job.company}",
                    content=(
                        f"Dear {job.company} hiring team,\n\n"
                        f"I am interested in the {job.title} role. The evidence below is drawn "
                        f"only from facts I confirmed in my career profile.\n\n{evidence}\n\n"
                        "Thank you for considering my application."
                    ),
                    claims=artifact.claims,
                ),
                False,
            )
        )

    rendered: list[Path] = []
    for filename, document_artifact, styled in documents:
        rendered.append(
            render_artifact_pdf(document_artifact, directory / filename, styled=styled)
        )
    zip_path = directory.parent / f"{directory.name}.zip"
    temporary_zip = directory.parent / f".{directory.name}.{uuid4().hex}.tmp"
    try:
        with zipfile.ZipFile(
            temporary_zip, "w", compression=zipfile.ZIP_DEFLATED
        ) as archive:
            for path in rendered:
                archive.write(path, arcname=path.name)
        temporary_zip.replace(zip_path)
    finally:
        temporary_zip.unlink(missing_ok=True)
    return PackageRenderResult(zip_path=zip_path, files=rendered)


def _xml_escape(value: str) -> str:
    return value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _safe_slug(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9._-]+", "-", value).strip("-.")
    return slug[:120] or "application-package"


def _job_requirements(job: JobRecord) -> list[str]:
    explicit = [item.strip() for item in job.requirements if item.strip()]
    if explicit:
        return explicit[:10]
    sentences = [
        " ".join(item.split())
        for item in re.split(r"(?<=[.!?])\s+", job.description)
        if 18 <= len(" ".join(item.split())) <= 240
    ]
    return sentences[:6]


def _best_evidence(requirement: str, facts: list[ProfileFact]) -> ProfileFact | None:
    ignored = {"about", "and", "build", "for", "from", "that", "the", "this", "with"}
    requirement_tokens = {
        token.casefold()
        for token in re.findall(r"[A-Za-z0-9+#.]+", requirement)
        if len(token) > 2 and token.casefold() not in ignored
    }
    best: tuple[int, ProfileFact] | None = None
    for fact in facts:
        fact_tokens = {
            token.casefold() for token in re.findall(r"[A-Za-z0-9+#.]+", fact.text)
        }
        overlap = len(requirement_tokens & fact_tokens)
        if overlap and (best is None or overlap > best[0]):
            best = (overlap, fact)
    return best[1] if best else None

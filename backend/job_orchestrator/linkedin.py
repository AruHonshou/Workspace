from __future__ import annotations

import re
from collections.abc import Mapping

SECTION_KEYS = (
    "headline",
    "about",
    "experience",
    "education",
    "skills",
    "certifications",
)

_SECTION_ALIASES: Mapping[str, str] = {
    "headline": "headline",
    "titular": "headline",
    "about": "about",
    "acerca de": "about",
    "extracto": "about",
    "resumen": "about",
    "summary": "about",
    "experience": "experience",
    "experiencia": "experience",
    "education": "education",
    "educación": "education",
    "educacion": "education",
    "skills": "skills",
    "top skills": "skills",
    "aptitudes": "skills",
    "aptitudes principales": "skills",
    "habilidades": "skills",
    "licenses & certifications": "certifications",
    "licencias y certificaciones": "certifications",
    "certifications": "certifications",
    "certificaciones": "certifications",
}

_PAGE_MARKER_RE = re.compile(r"(?i)^(?:page|p[aá]gina)\s+\d+\s+(?:of|de)\s+\d+$")
_ROLE_HINT_RE = re.compile(
    r"(?i)\b(?:qa|quality|engineer|engineering|developer|development|software|"
    r"analyst|manager|architect|designer|scientist|ingenier[oa]|desarrollador|"
    r"analista|gerente|arquitect[oa]|diseñador|científic[oa])\b"
)
_LANGUAGE_LINE_RE = re.compile(
    r"(?i)^(?:english|spanish|español|ingl[eé]s|portuguese|portugu[eé]s|french|franc[eé]s)\b"
)

_EMAIL_RE = re.compile(r"(?i)\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b")
_PHONE_RE = re.compile(r"(?<!\w)(?:\+?\d[\d\s().-]{7,}\d)(?!\w)")
_CONTACT_LABEL_RE = re.compile(
    r"(?i)^\s*(?:contact|contacto|email|correo|phone|tel[eé]fono|address|direcci[oó]n)\s*:"
)


def extract_contact_values(value: str) -> dict[str, list[str]]:
    """Extract private contact values locally before professional redaction."""

    return {
        "emails": list(dict.fromkeys(_EMAIL_RE.findall(value))),
        "phones": list(
            dict.fromkeys(" ".join(match.split()) for match in _PHONE_RE.findall(value))
        ),
    }


def redact_contact_text(value: str) -> str:
    """Remove contact details before professional text can reach a model."""

    safe_lines: list[str] = []
    for raw_line in value.splitlines():
        line = raw_line.strip()
        if not line or _CONTACT_LABEL_RE.match(line):
            continue
        line = _EMAIL_RE.sub("[redacted-email]", line)
        line = _PHONE_RE.sub("[redacted-phone]", line)
        safe_lines.append(line)
    return "\n".join(safe_lines).strip()


def parse_linkedin_sections(value: str) -> dict[str, str]:
    """Parse LinkedIn's PDF/text export conservatively into editable sections."""

    sections: dict[str, list[str]] = {key: [] for key in SECTION_KEYS}
    current: str | None = None
    preamble: list[str] = []
    lines: list[str] = []
    for raw_line in value.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        line = " ".join(raw_line.strip().split())
        if not line or _PAGE_MARKER_RE.fullmatch(line):
            continue
        lines.append(line)

    # LinkedIn's own PDF exporter may interleave the first page with a narrow
    # certifications/languages column. Resolve the headline independently from
    # the lines immediately preceding About/Extracto instead of trusting PDF order.
    about_positions = [
        index
        for index, line in enumerate(lines)
        if _SECTION_ALIASES.get(line.casefold().rstrip(":")) == "about"
    ]
    headline_candidate = ""
    if about_positions:
        before_about = lines[max(0, about_positions[0] - 14) : about_positions[0]]
        scored: list[tuple[int, int, str]] = []
        for position, line in enumerate(before_about):
            lowered = line.casefold().rstrip(":")
            if (
                lowered in _SECTION_ALIASES
                or _CONTACT_LABEL_RE.match(line)
                or _LANGUAGE_LINE_RE.match(line)
                or _EMAIL_RE.search(line)
                or _PHONE_RE.search(line)
            ):
                continue
            score = (8 if _ROLE_HINT_RE.search(line) else 0) + (4 if "|" in line else 0)
            score += 2 if 8 <= len(line) <= 180 else -2
            scored.append((score, position, line))
        if scored:
            best = max(scored)
            if best[0] >= 2:
                headline_candidate = best[2]

    for line in lines:
        normalized = line.casefold().rstrip(":")
        heading = _SECTION_ALIASES.get(normalized)
        if heading:
            current = heading
            continue
        if current is None:
            preamble.append(line)
        else:
            sections[current].append(line)

    if headline_candidate:
        sections["headline"] = [headline_candidate]
    elif preamble:
        # LinkedIn exports usually begin with name followed by headline. The user's
        # name and contact block are not useful to the optimizer. Select the last
        # non-contact, non-redacted line so a trailing contact line cannot erase it.
        safe_preamble = [
            redacted
            for line in preamble
            if (redacted := redact_contact_text(line)) and "[redacted-" not in redacted
        ]
        if safe_preamble:
            role_lines = [line for line in safe_preamble if _ROLE_HINT_RE.search(line)]
            sections["headline"].append(
                role_lines[-1] if role_lines else safe_preamble[-1]
            )

    return {
        key: redact_contact_text("\n".join(lines)) for key, lines in sections.items()
    }


__all__ = [
    "SECTION_KEYS",
    "extract_contact_values",
    "parse_linkedin_sections",
    "redact_contact_text",
]

from __future__ import annotations

import re
import unicodedata
from collections.abc import Awaitable, Callable
from datetime import timedelta
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlparse, urlsplit, urlunsplit

from .ranking import clean_text, rank_job
from .schemas import (
    Artifact,
    CareerJobResult,
    Claim,
    DeepFitAnalysis,
    DeepFitAnalysisV2,
    FitSummary,
    InterviewGuide,
    JobRecord,
    JobSourceEvidence,
    Profile,
    RequirementAnalysis,
    SearchRequest,
    TechnologyFit,
    normalize_bcp47,
)

ConnectorSearch = Callable[
    [SearchRequest], Awaitable[tuple[list[JobRecord], dict[str, str]]]
]

ROLE_ALIASES: dict[str, list[str]] = {
    "qa": [
        "QA",
        "QA Engineer",
        "Analista de calidad",
        "Ingeniero de calidad",
        "Quality Assurance",
        "Quality Analyst",
        "Software Tester",
        "Test Engineer",
        "SDET",
    ],
    "quality assurance": [
        "Quality Assurance",
        "QA Engineer",
        "Analista de calidad",
        "Ingeniero de calidad",
        "Quality Analyst",
        "Software Tester",
        "Test Engineer",
        "SDET",
    ],
    "analista de calidad": [
        "Analista de calidad",
        "Ingeniero de calidad",
        "QA Engineer",
        "Quality Assurance",
        "Software Tester",
    ],
    "desarrollador": [
        "Software Developer",
        "Software Engineer",
        "Backend Developer",
        "Frontend Developer",
        "Full Stack Developer",
        "Application Developer",
    ],
    "developer": [
        "Software Developer",
        "Software Engineer",
        "Desarrollador de software",
        "Ingeniero de software",
        "Backend Developer",
        "Frontend Developer",
        "Full Stack Developer",
    ],
    "software developer": [
        "Software Developer",
        "Software Engineer",
        "Desarrollador de software",
        "Ingeniero de software",
        "Backend Developer",
        "Frontend Developer",
        "Full Stack Developer",
    ],
    "software engineer": [
        "Software Engineer",
        "Software Developer",
        "Ingeniero de software",
        "Desarrollador de software",
    ],
    "data": [
        "Data Analyst",
        "Data Engineer",
        "Analytics Engineer",
        "Business Intelligence Analyst",
    ],
    "analista de datos": [
        "Data Analyst",
        "Business Intelligence Analyst",
        "Analytics Analyst",
    ],
    "data analyst": [
        "Data Analyst",
        "Analista de datos",
        "Business Intelligence Analyst",
        "Analytics Analyst",
    ],
    "soporte": [
        "Technical Support",
        "IT Support",
        "Help Desk",
        "Service Desk Analyst",
    ],
    "devops": [
        "DevOps Engineer",
        "Platform Engineer",
        "Site Reliability Engineer",
        "Cloud Engineer",
    ],
    "ciberseguridad": [
        "Cybersecurity Analyst",
        "Security Engineer",
        "Information Security Analyst",
        "SOC Analyst",
    ],
    "gerente de producto": ["Product Manager", "Product Owner"],
    "gerente de proyecto": ["Project Manager", "Program Manager"],
    "marketing": ["Marketing Specialist", "Digital Marketing", "Growth Marketing"],
    "ventas": ["Sales Representative", "Account Executive", "Business Development"],
    "recursos humanos": ["Human Resources", "HR Generalist", "Talent Acquisition"],
    "servicio al cliente": ["Customer Support", "Customer Service", "Customer Success"],
}

TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9+#.-]{1,}", re.IGNORECASE)
SPANISH_MARKERS = {
    "experiencia",
    "requisitos",
    "responsabilidades",
    "conocimientos",
    "habilidades",
    "puesto",
    "empresa",
}
EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
PHONE_RE = re.compile(r"(?<!\w)(?:\+?\d[\d ()-]{7,}\d)(?!\w)")
CONTACT_MARKERS = (
    "linkedin.com",
    "github.com",
    "http://",
    "https://",
    ".com/",
    ".io/",
    "portfolio:",
    "teléfono",
    "telefono",
    "phone:",
    "address:",
    "dirección:",
    "direccion:",
)

REQUIREMENT_MARKERS = (
    "experience",
    "required",
    "requirement",
    "must",
    "knowledge",
    "proficient",
    "skill",
    "degree",
    "bachelor",
    "education",
    "certification",
    "years",
    "experiencia",
    "requisito",
    "conocimiento",
    "dominio",
    "habilidad",
    "título",
    "titulo",
    "bachiller",
    "licenciatura",
    "certificación",
    "certificacion",
    "años",
    "manejo",
)

NON_REQUIREMENT_MARKERS = (
    "about the company",
    "about us",
    "company overview",
    "equal opportunity",
    "excellent opportunity",
    "join our team",
    "why join",
    "what we offer",
    "we offer",
    "we provide",
    "you will receive",
    "you'll receive",
    "our benefits",
    "employee benefits",
    "benefits include",
    "compensation package",
    "salary range",
    "acerca de la empresa",
    "sobre la empresa",
    "quienes somos",
    "quiénes somos",
    "excelente oportunidad",
    "unete a nuestro",
    "únete a nuestro",
    "por que trabajar",
    "por qué trabajar",
    "que ofrecemos",
    "qué ofrecemos",
    "te ofrecemos",
    "ofrecemos beneficios",
    "te proporcionaremos",
    "nuestros beneficios",
    "beneficios incluyen",
    "rango salarial",
)

RESPONSIBILITY_MARKERS = (
    "responsible for",
    "responsibilities include",
    "you will",
    "you'll",
    "ability to",
    "demonstrated ability",
    "hands-on",
    "proven experience",
    "familiarity with",
    "understanding of",
    "experience with",
    "knowledge of",
    "proficiency in",
    "responsable de",
    "responsabilidades incluyen",
    "seras responsable",
    "serás responsable",
    "capacidad para",
    "experiencia comprobada",
    "experiencia con",
    "conocimiento de",
    "dominio de",
)

GENERIC_MATCH_TOKENS = {
    "ability",
    "advanced",
    "best",
    "candidate",
    "experience",
    "experiencia",
    "general",
    "good",
    "knowledge",
    "conocimiento",
    "plus",
    "preferred",
    "proficient",
    "quality",
    "required",
    "requirement",
    "requirements",
    "requisito",
    "requisitos",
    "skill",
    "skills",
    "habilidad",
    "habilidades",
    "strong",
    "work",
    "working",
    "years",
    "year",
    "anos",
    "años",
}

SINGLE_TOKEN_SKILLS = {
    "sdet",
    "playwright",
    "selenium",
    "postman",
    "python",
    "typescript",
    "javascript",
    "react",
    "fastapi",
    "docker",
    "terraform",
    "jira",
    "scrum",
    "sql",
    "aws",
    "appium",
    "minitab",
    "sap",
    "haccp",
    "brcgs",
}


def _fold(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value.casefold())
    return "".join(char for char in normalized if not unicodedata.combining(char))


def _plain_job_text(value: str) -> str:
    return clean_text(re.sub(r"[*`]+", "", value)).lstrip("- ")


def expand_role(role: str) -> list[str]:
    cleaned = clean_text(role)
    key = _fold(cleaned)
    aliases = ROLE_ALIASES.get(key, [cleaned])
    result: list[str] = []
    for alias in [cleaned, *aliases]:
        if alias and alias.casefold() not in {item.casefold() for item in result}:
            result.append(alias)
    return result[:8]


def _tokens(value: str) -> set[str]:
    ignored = {
        "and",
        "the",
        "with",
        "for",
        "from",
        "that",
        "this",
        "you",
        "your",
        "para",
        "con",
        "las",
        "los",
        "del",
        "una",
        "por",
        "de",
        "en",
        "el",
        "la",
        "al",
        "se",
        "es",
        "un",
        "que",
        "como",
        "sus",
        "más",
        "mas",
        "todos",
        "cada",
        "our",
        "we",
        "are",
        "is",
        "be",
        "to",
        "of",
        "in",
        "on",
        "at",
        "an",
        "or",
        "as",
    }
    tokens: set[str] = set()
    for token in TOKEN_RE.findall(value):
        cleaned = token.casefold().strip(".-")
        if cleaned and cleaned not in ignored:
            tokens.add(cleaned)
    return tokens


def facts_for_language(profile: Profile, language: str) -> list[Any]:
    """Use the matching résumé plus the user's cross-language dossier evidence."""

    normalized = normalize_bcp47(language)
    language_base = normalized.split("-", 1)[0]
    matching = [
        fact
        for fact in profile.facts
        if fact.source_type == "about_me"
        or (
            fact.language
            and (
                fact.language == normalized
                or normalize_bcp47(fact.language).split("-", 1)[0] == language_base
            )
        )
    ]
    if matching:
        return matching
    legacy = [fact for fact in profile.facts if fact.language is None]
    return legacy if legacy else list(profile.facts)


def cloud_safe_verified_facts(
    profile: Profile,
    limit: int = 20,
    *,
    language: str | None = None,
    include_all: bool = False,
) -> list[dict[str, str]]:
    """Return confirmed professional facts without obvious contact identifiers.

    Most workflows benefit from ranking out very short fragments.  LinkedIn
    generation is different: a skill such as ``SQL`` or a certification name
    can be the complete fact, so that workflow opts into ``include_all`` and
    receives every confirmed, non-contact fact in the selected language.
    """

    safe: list[tuple[int, dict[str, str]]] = []
    profile_name = clean_text(profile.name).casefold()
    profile_name_tokens = _tokens(profile.name)
    source_facts = facts_for_language(profile, language) if language else profile.facts
    for fact in source_facts:
        text = clean_text(fact.text).lstrip("•- ")
        folded = text.casefold()
        if not fact.verified or not text:
            continue
        if EMAIL_RE.search(text) or PHONE_RE.search(text):
            continue
        if any(marker in folded for marker in CONTACT_MARKERS):
            continue
        if profile_name and folded == profile_name:
            continue
        fact_tokens = _tokens(text)
        if (
            profile_name_tokens
            and len(fact_tokens & profile_name_tokens)
            >= min(2, len(profile_name_tokens))
            and len(text) < 100
        ):
            continue
        if not include_all and (len(text) < 24 or (text.isupper() and len(text) < 120)):
            continue
        score = 0
        if fact.category in {"achievement", "experience"}:
            score += 4
        if re.search(r"\b\d+(?:[.,]\d+)?%?\b", text):
            score += 3
        if any(
            marker in _fold(text)
            for marker in (
                "disene",
                "implemente",
                "construi",
                "desarrolle",
                "automatic",
                "lidere",
                "reduje",
                "designed",
                "implemented",
                "built",
                "developed",
                "automated",
                "led",
                "reduced",
            )
        ):
            score += 3
        safe.append(
            (score, {"fact_id": fact.fact_id, "text": text, "category": fact.category})
        )
    safe.sort(key=lambda item: item[0], reverse=True)
    return [item for _, item in safe[:limit]]


def _is_requirement_candidate(value: str) -> bool:
    folded = _fold(value)
    if not folded or any(marker in folded for marker in NON_REQUIREMENT_MARKERS):
        return False
    if any(marker in folded for marker in REQUIREMENT_MARKERS):
        return True
    if any(marker in folded for marker in RESPONSIBILITY_MARKERS):
        return True
    return bool(_technology_mentions(value))


def extract_requirements(job: JobRecord, limit: int = 80) -> list[str]:
    if job.requirements:
        provided = _unique_text(
            [
                _plain_job_text(value)
                for value in job.requirements
                if clean_text(value)
                and _is_requirement_candidate(_plain_job_text(value))
            ],
            limit=limit,
        )
        if provided:
            return provided
    fragments = re.split(r"(?<=[.!?;])\s+|\s+[•|]\s+", clean_text(job.description))
    return _unique_text(
        [
            _plain_job_text(fragment)
            for fragment in fragments
            if 18 <= len(fragment.strip()) <= 320
            and _is_requirement_candidate(fragment)
        ],
        limit=limit,
    )


def _fit_level(score: float) -> str:
    if score >= 70:
        return "high"
    if score >= 45:
        return "medium"
    return "low"


def _matching_facts(
    profile: Profile, requirement: str, *, language: str | None = None
) -> list[tuple[str, str, int]]:
    requirement_tokens = _tokens(requirement) - GENERIC_MATCH_TOKENS
    requirement_folded = _fold(requirement)
    duration_match = re.search(
        r"\b(\d+)\+?\s*(?:years?|anos?)\b", requirement_folded
    )
    duration_required = bool(duration_match)
    required_years = int(duration_match.group(1)) if duration_match else None
    degree_required = any(
        marker in requirement_folded
        for marker in ("degree", "bachelor", "licenciatura", "bachiller", "titulo")
    )
    education_or_experience = degree_required and duration_required and any(
        marker in requirement_folded for marker in (" and/or ", " or ", " o ")
    )
    requirement_technologies = _technology_mentions(requirement)
    matches: list[tuple[str, str, int]] = []
    source_facts = facts_for_language(profile, language) if language else profile.facts
    for fact in source_facts:
        if not fact.verified:
            continue
        fact_text = clean_text(fact.text).lstrip("•- ")
        fact_folded = _fold(fact_text)
        if (
            len(fact_text) < 20
            or (fact_text.isupper() and len(fact_text) < 120)
            or EMAIL_RE.search(fact_text)
            or PHONE_RE.search(fact_text)
            or any(marker in fact_folded for marker in CONTACT_MARKERS)
        ):
            continue
        fact_duration_matches = [
            int(value)
            for value in re.findall(
                r"\b(\d+)\+?\s*(?:years?|anos?)\b", fact_folded
            )
        ]
        duration_supported = bool(
            required_years is not None
            and fact_duration_matches
            and max(fact_duration_matches) >= required_years
        )
        degree_supported = bool(
            fact.category == "education"
            or any(
                marker in fact_folded
                for marker in (
                    "degree",
                    "bachelor",
                    "licenciatura",
                    "bachiller",
                    "titulo",
                )
            )
        )
        if education_or_experience and not (duration_supported or degree_supported):
            continue
        if not education_or_experience and duration_required and not duration_supported:
            continue
        if not education_or_experience and degree_required and not degree_supported:
            continue
        fact_technologies = _technology_mentions(fact_text)
        if requirement_technologies and not (
            requirement_technologies & fact_technologies
        ):
            continue
        shared = requirement_tokens & (_tokens(fact_text) - GENERIC_MATCH_TOKENS)
        overlap = len(shared)
        threshold = 2 if len(requirement_tokens) <= 8 else 3
        if (
            overlap >= threshold
            or bool(requirement_technologies & fact_technologies)
            or any(token in SINGLE_TOKEN_SKILLS for token in shared)
            or (degree_required and degree_supported)
            or (duration_required and duration_supported)
        ):
            evidence_bonus = (
                2
                if any(
                    marker in fact_folded
                    for marker in (
                        "disene",
                        "implemente",
                        "construi",
                        "desarrolle",
                        "ejecute",
                        "automatic",
                        "lidere",
                        "reduje",
                        "designed",
                        "implemented",
                        "built",
                        "developed",
                        "executed",
                        "automated",
                        "led",
                        "reduced",
                    )
                )
                else 0
            )
            matches.append((fact.fact_id, fact_text, (overlap * 10) + evidence_bonus))
    return sorted(matches, key=lambda item: item[2], reverse=True)


def build_quick_result(job: JobRecord, profile: Profile) -> CareerJobResult:
    language = detect_job_language(job)
    selected_facts = facts_for_language(profile, language)
    ranked = rank_job(job, profile.model_copy(update={"facts": selected_facts}))
    requirements = extract_requirements(job)
    supported: list[str] = []
    unsupported: list[str] = []
    for requirement in requirements:
        if _matching_facts(profile, requirement, language=language):
            supported.append(requirement)
        else:
            unsupported.append(requirement)
    strengths = supported[:3] or ranked.reasons[:3]
    gaps = unsupported[:3] or ranked.gaps[:3]
    summary = clean_text(job.description)
    if len(summary) > 420:
        summary = f"{summary[:417].rstrip()}..."
    compatibility_status, filter_reasons, warnings = classify_job_compatibility(
        job, profile
    )
    return CareerJobResult(
        job_id=job.job_id,
        title=job.title,
        company=job.company,
        location=job.location or ("Remote" if job.remote else "Not specified"),
        remote=job.remote,
        source=job.source,
        sources=job.sources or [job.source],
        published_at=job.posted_at,  # type: ignore[arg-type]
        official_apply_url=job.url,  # type: ignore[arg-type]
        apply_url=job.url,
        apply_url_type=job.apply_url_type,
        remote_eligibility=job.remote_eligibility,
        source_evidence=job.source_evidence,
        provider=job.provider,
        source_portal=job.source_portal,
        source_url=job.source_url,
        description_summary=summary,
        requirements=requirements,
        fit_summary=FitSummary(
            score=ranked.score,
            level=_fit_level(ranked.score),
            strengths=strengths,
            gaps=gaps,
            confidence=ranked.breakdown.confidence,
        ),
        verification_level=job.verification_level,
        profile_id=profile.profile_id,
        compatibility_status=compatibility_status,
        filter_reasons=filter_reasons,
        warnings=warnings,
    )


SENIORITY_MARKERS: dict[str, tuple[str, ...]] = {
    "internship": ("intern", "internship", "pasant", "practicante"),
    "entry": ("entry level", "entry-level", "sin experiencia", "graduate"),
    "junior": ("junior", " jr", "jr.", "nivel inicial"),
    "mid": ("mid level", "mid-level", "intermediate", "intermedio", "semi senior"),
    "senior": ("senior", " sr", "sr."),
    "lead": (
        " tech lead",
        "team lead",
        "lead engineer",
        "líder técnico",
        "lider tecnico",
    ),
    "manager": ("manager", "gerente", "jefatura"),
    "director": ("director", "head of"),
    "executive": ("vice president", " vp", "chief ", "c-level"),
}


def _detect_seniority(job: JobRecord) -> str | None:
    text = f" {_fold(job.title)} {_fold(job.description[:1_500])} "
    for level in (
        "executive",
        "director",
        "manager",
        "lead",
        "senior",
        "mid",
        "junior",
        "entry",
        "internship",
    ):
        if any(marker in text for marker in SENIORITY_MARKERS[level]):
            return level
    return None


def _detect_work_mode(job: JobRecord) -> str | None:
    location = _fold(job.location)
    if any(marker in location for marker in ("hybrid", "hibrid")):
        return "hybrid"
    if job.remote is True or any(marker in location for marker in ("remote", "remoto")):
        return "remote"
    if job.remote is False or any(
        marker in location for marker in ("onsite", "on-site", "presencial", "office")
    ):
        return "onsite"
    return None


def classify_job_compatibility(
    job: JobRecord, profile: Profile
) -> tuple[str, list[str], list[str]]:
    """Separate only explicit preference conflicts; unknowns remain visible."""

    preferences = profile.preferences
    reasons: list[str] = []
    warnings: list[str] = []
    text = _fold(f"{job.title} {job.company} {job.location} {job.description}")
    seniority = _detect_seniority(job)
    allowed_seniorities = {str(value) for value in preferences.target_seniorities}
    if allowed_seniorities:
        if seniority is None:
            warnings.append("El nivel de seniority no está indicado con claridad.")
        elif seniority not in allowed_seniorities:
            reasons.append(
                f"Seniority explícito “{seniority}” fuera de las preferencias del perfil."
            )
    work_mode = _detect_work_mode(job)
    allowed_modes = {str(value) for value in preferences.allowed_work_modes}
    if allowed_modes:
        if work_mode is None:
            warnings.append("La modalidad de trabajo no está indicada con claridad.")
        elif work_mode not in allowed_modes:
            reasons.append(
                f"Modalidad explícita “{work_mode}” fuera de las preferencias del perfil."
            )
    if preferences.desired_locations and work_mode != "remote":
        location = _fold(job.location)
        if not location:
            warnings.append("La ubicación exacta no está indicada.")
        elif not any(
            _fold(value) in location for value in preferences.desired_locations
        ):
            reasons.append(
                f"Ubicación explícita “{job.location}” fuera de las preferencias del perfil."
            )
    for keyword in preferences.excluded_keywords:
        if _fold(keyword) in text:
            reasons.append(f"Coincide con la exclusión configurada “{keyword}”.")
    for sector in preferences.excluded_sectors:
        if _fold(sector) in text:
            reasons.append(f"Coincide con el sector excluido “{sector}”.")
    return (
        "review" if reasons else "compatible",
        list(dict.fromkeys(reasons)),
        list(dict.fromkeys(warnings)),
    )


TECHNOLOGY_NAMES: tuple[str, ...] = (
    "Adobe Analytics",
    "Adobe Experience Manager",
    "Adobe Journey Optimizer",
    "Adobe Experience Platform Debugger",
    "Adobe Sites",
    "Adobe Assets",
    "Playwright",
    "Selenium",
    "Cypress",
    "Appium",
    "Tosca",
    "Postman",
    "Python",
    "Java",
    "JavaScript",
    "TypeScript",
    "React",
    "Angular",
    "Vue",
    "SQL",
    "NoSQL",
    "REST",
    "GraphQL",
    "Docker",
    "Kubernetes",
    "AWS",
    "Azure",
    "GCP",
    "Jenkins",
    "GitHub Actions",
    "Jira",
    "Confluence",
    "WCAG",
    "Lighthouse",
    "OneTrust",
    "Data Layer",
    "Git",
    "Linux",
    "FastAPI",
    "Django",
    "Spring",
    ".NET",
    "C#",
    "Node.js",
    "PHP",
    "Ruby",
)


def _technology_mentions(value: str) -> set[str]:
    folded = _fold(value)
    return {
        technology
        for technology in TECHNOLOGY_NAMES
        if re.search(
            rf"(?<![a-z0-9]){re.escape(_fold(technology))}(?![a-z0-9])",
            folded,
            re.IGNORECASE,
        )
    }


def technology_mentions(value: str) -> set[str]:
    """Return normalized technology names recognized in untrusted job or CV text."""

    return _technology_mentions(value)


def _requirement_category(requirement: str) -> str:
    folded = _fold(requirement)
    if any(_fold(name) in folded for name in TECHNOLOGY_NAMES):
        return "technology"
    if any(
        marker in folded
        for marker in (
            "degree",
            "bachelor",
            "university",
            "titulo",
            "licenciatura",
            "bachiller",
        )
    ):
        return "education"
    if any(
        marker in folded
        for marker in ("english", "spanish", "idioma", "language", "bilingual")
    ):
        return "language"
    if any(
        marker in folded
        for marker in (
            "remote",
            "hybrid",
            "onsite",
            "location",
            "relocation",
            "remoto",
            "hibrid",
            "presencial",
        )
    ):
        return "logistics"
    if any(
        marker in folded
        for marker in ("experience", "years", "experiencia", "anos", "años")
    ):
        return "experience"
    return "other"


def _requirement_priority(requirement: str, job: JobRecord) -> str:
    folded = _fold(requirement)
    preferred = {_fold(value) for value in job.preferred_requirements}
    if folded in preferred or any(
        marker in folded
        for marker in ("preferred", "nice to have", "plus", "deseable", "preferible")
    ):
        return "preferred"
    if any(
        marker in folded
        for marker in (
            "must",
            "required",
            "requirement",
            "requisito",
            "indispensable",
            "se requiere",
        )
    ):
        return "required"
    return "unknown"


def build_deep_analysis(job: JobRecord, profile: Profile) -> DeepFitAnalysis:
    quick = build_quick_result(job, profile)
    language = detect_job_language(job)
    matched: list[dict[str, str]] = []
    missing: list[str] = []
    recommendations: list[str] = []
    requirement_analysis: list[RequirementAnalysis] = []
    technology_summary: dict[str, TechnologyFit] = {}
    for requirement in quick.requirements:
        matches = _matching_facts(profile, requirement, language=language)
        if matches:
            fact_id, fact_text, _ = matches[0]
            matched.append(
                {"requirement": requirement, "fact_id": fact_id, "evidence": fact_text}
            )
            requirement_analysis.append(
                RequirementAnalysis(
                    requirement=requirement,
                    category=_requirement_category(requirement),
                    priority=_requirement_priority(requirement, job),
                    status="supported",
                    fact_ids=[fact_id],
                    evidence=[fact_text],
                )
            )
        else:
            missing.append(requirement)
            requirement_analysis.append(
                RequirementAnalysis(
                    requirement=requirement,
                    category=_requirement_category(requirement),
                    priority=_requirement_priority(requirement, job),
                    status="gap",
                )
            )
            recommendations.append(
                "Si realmente cuentas con esta experiencia, descríbela en el CV con un "
                "ejemplo concreto y verificable. Si no cuentas con ella, no la añadas y "
                "trátala como un tema de aprendizaje: "
                f"{requirement}"
            )
        requirement_folded = _fold(requirement)
        for technology in TECHNOLOGY_NAMES:
            if _fold(technology) not in requirement_folded:
                continue
            supporting_ids = [
                item["fact_id"]
                for item in matched
                if item["requirement"] == requirement
            ]
            technology_summary[technology] = TechnologyFit(
                technology=technology,
                status="supported" if supporting_ids else "gap",
                fact_ids=supporting_ids,
            )
    for match in matched[:3]:
        recommendations.append(
            "Da mayor visibilidad a esta evidencia real y relaciónala claramente con el "
            f"requisito, sin cambiar su significado: {match['evidence']}"
        )
    if not recommendations:
        recommendations.append(
            "Reordena tus experiencias para que las evidencias más relacionadas con este puesto aparezcan primero."
        )
    cautions = [
        "No añadas habilidades, métricas ni responsabilidades que no puedas demostrar.",
        "Este análisis estima afinidad; no es un puntaje ATS ni garantiza una entrevista.",
    ]
    evidence_coverage = (
        (len(matched) / len(quick.requirements)) * 100 if quick.requirements else 0
    )
    evidence_score = round((evidence_coverage * 0.7) + (quick.fit_summary.score * 0.3))
    supported_keywords = sorted(
        {
            technology.technology
            for technology in technology_summary.values()
            if technology.status == "supported"
        }
    )
    confidence = min(
        1.0,
        max(
            0.2,
            0.35
            + (0.55 * (len(quick.requirements) / max(1, len(quick.requirements) + 2))),
        ),
    )
    return DeepFitAnalysis(
        job_id=job.job_id,
        profile_id=profile.profile_id,
        score=evidence_score,
        level=_fit_level(evidence_score),
        resume_language=language,
        matched_requirements=matched,
        missing_requirements=missing,
        cv_recommendations=recommendations,
        cautions=cautions,
        requirement_analysis=requirement_analysis,
        technology_summary=list(technology_summary.values()),
        supported_keywords=supported_keywords,
        confidence=round(confidence, 2),
    )


def build_deep_analysis_v2(job: JobRecord, profile: Profile) -> DeepFitAnalysisV2:
    """Create a complete, gap-first analysis without model-authored claims.

    V2 evaluates every recoverable requirement and every confirmed fact for the
    selected résumé language. The model may later improve phrasing, but scores,
    evidence links and gap classification remain deterministic.
    """

    language = detect_job_language(job)
    spanish = language.casefold().split("-", 1)[0] == "es"
    requirements = extract_requirements(job, limit=200)
    analyses: list[RequirementAnalysis] = []
    priority_gaps: list[str] = []
    strengths: list[str] = []
    cv_actions: list[str] = []
    supported_keywords: set[str] = set()
    missing_technologies: set[str] = set()
    uncertain_requirements: list[str] = []

    for requirement in requirements:
        matches = _matching_facts(profile, requirement, language=language)
        evidence_matches = matches[:3]
        category = _requirement_category(requirement)
        priority = _requirement_priority(requirement, job)
        required_technologies = _technology_mentions(requirement)
        evidenced_technologies = {
            technology
            for _fact_id, evidence, _score in evidence_matches
            for technology in _technology_mentions(evidence)
        }
        partial_technology_match = bool(
            evidence_matches
            and len(required_technologies) > 1
            and not required_technologies.issubset(evidenced_technologies)
        )
        if evidence_matches:
            status = "unknown" if partial_technology_match else "supported"
            analyses.append(
                RequirementAnalysis(
                    requirement=requirement,
                    category=category,
                    priority=priority,
                    status=status,
                    fact_ids=[item[0] for item in evidence_matches],
                    evidence=[item[1] for item in evidence_matches],
                    explanation=(
                        (
                            "Existe evidencia relacionada, pero sólo cubre parte de las "
                            "tecnologías mencionadas; requiere validación humana."
                            if spanish
                            else "Related evidence exists, but it covers only some of the "
                            "listed technologies; human validation is required."
                        )
                        if partial_technology_match
                        else (
                            "El perfil contiene evidencia confirmada directamente relacionada."
                            if spanish
                            else "The profile contains directly related confirmed evidence."
                        )
                    ),
                )
            )
            if status == "supported":
                strengths.append(evidence_matches[0][1])
            else:
                uncertain_requirements.append(requirement)
            cv_actions.append(
                (
                    "Da mayor visibilidad a esta evidencia en la sección más relevante: "
                    if spanish
                    else "Give this evidence more visibility in the most relevant section: "
                )
                + evidence_matches[0][1]
            )
        else:
            analyses.append(
                RequirementAnalysis(
                    requirement=requirement,
                    category=category,
                    priority=priority,
                    status="gap",
                    explanation=(
                        "No se encontró evidencia confirmada directa; debe tratarse como "
                        "brecha de preparación o validación."
                        if spanish
                        else "No direct confirmed evidence was found; treat this as a "
                        "preparation or validation gap."
                    ),
                )
            )
            if priority == "required":
                priority_gaps.append(requirement)
            action_prefixes = {
                "technology": (
                    "Prioriza práctica verificable o formación en: "
                    if spanish
                    else "Prioritize verifiable practice or training in: "
                ),
                "experience": (
                    "Identifica experiencia transferible relacionada con: "
                    if spanish
                    else "Identify transferable experience related to: "
                ),
                "education": (
                    "Aclara formación o equivalencias relacionadas con: "
                    if spanish
                    else "Clarify related education or equivalent training for: "
                ),
                "language": (
                    "Documenta de forma verificable tu nivel para: "
                    if spanish
                    else "Document your level with verifiable evidence for: "
                ),
                "logistics": (
                    "Confirma antes de postular la compatibilidad con: "
                    if spanish
                    else "Confirm compatibility before applying regarding: "
                ),
                "other": (
                    "Revisa y prepara evidencia para: "
                    if spanish
                    else "Review and prepare evidence for: "
                ),
            }
            cv_actions.append(f"{action_prefixes[category]}{requirement}")

        folded = _fold(requirement)
        for technology in TECHNOLOGY_NAMES:
            if _fold(technology) not in folded:
                continue
            if technology in evidenced_technologies:
                supported_keywords.add(technology)
            else:
                missing_technologies.add(technology)

    supported_count = sum(item.status == "supported" for item in analyses)
    requirement_score = (supported_count / len(analyses)) * 100 if analyses else 0.0
    quick_score = build_quick_result(job, profile).fit_summary.score
    score = round((requirement_score * 0.75) + (quick_score * 0.25), 1)
    confidence = round(min(0.95, 0.35 + min(len(analyses), 20) * 0.03), 2)
    unique_strengths = list(dict.fromkeys(strengths))[:8]
    unique_actions = list(dict.fromkeys(cv_actions))[:12]
    unique_gaps = list(dict.fromkeys(priority_gaps))[:12]
    if analyses:
        executive_summary = (
            f"El perfil respalda {supported_count} de {len(analyses)} requisitos "
            f"identificados. La preparación debe centrarse en {len(unique_gaps)} "
            "brechas obligatorias y en hacer más visible la evidencia confirmada."
            if spanish
            else (
                f"The profile supports {supported_count} of {len(analyses)} identified "
                f"requirements. Preparation should focus on {len(unique_gaps)} required "
                "gaps and on making confirmed evidence more visible."
            )
        )
    else:
        executive_summary = (
            "La publicación no contiene requisitos suficientemente estructurados; "
            "el encaje tiene una confianza limitada y requiere revisión humana."
            if spanish
            else (
                "The posting does not contain sufficiently structured requirements; "
                "the fit estimate has limited confidence and needs human review."
            )
        )
    uncertainties = list(dict.fromkeys(uncertain_requirements))[:12]
    if not analyses:
        uncertainties = [
            (
                "No fue posible separar requisitos verificables de la descripción publicada."
                if spanish
                else "Verifiable requirements could not be separated from the posting."
            )
        ]
    return DeepFitAnalysisV2(
        job_id=job.job_id,
        profile_id=profile.profile_id,
        profile_revision=profile.revision,
        resume_language=language,
        executive_summary=executive_summary,
        score=score,
        level=_fit_level(score),
        requirement_analysis=analyses,
        priority_gaps=unique_gaps,
        transferable_strengths=unique_strengths,
        cv_actions=unique_actions,
        supported_keywords=sorted(supported_keywords),
        missing_technologies=sorted(missing_technologies),
        uncertainties=uncertainties,
        integrity_notice=(
            "Revisa las recomendaciones antes de modificar tu CV."
            if spanish
            else "Review the recommendations before changing your résumé."
        ),
        confidence=confidence,
    )


def detect_job_language(job: JobRecord) -> str:
    raw_language = job.raw.get("language") or job.raw.get("job_language")
    if isinstance(raw_language, str) and raw_language.strip():
        language_names = {
            "english": "en",
            "spanish": "es",
            "español": "es",
            "portuguese": "pt",
            "português": "pt",
            "french": "fr",
            "français": "fr",
            "german": "de",
            "deutsch": "de",
            "italian": "it",
            "italiano": "it",
            "dutch": "nl",
            "nederlands": "nl",
        }
        candidate = language_names.get(raw_language.strip().casefold(), raw_language)
        try:
            detected = normalize_bcp47(candidate)
            return "es" if detected.split("-", 1)[0] == "es" else "en"
        except ValueError:
            pass
    tokens = _tokens(f"{job.title} {job.description}")
    markers = {
        "es": SPANISH_MARKERS,
        "pt": {
            "vaga",
            "requisitos",
            "experiencia",
            "trabalho",
            "conhecimento",
            "desejavel",
            "responsabilidades",
        },
        "fr": {
            "poste",
            "profil",
            "experience",
            "competences",
            "missions",
            "requis",
            "entreprise",
        },
        "de": {
            "stelle",
            "anforderungen",
            "erfahrung",
            "kenntnisse",
            "aufgaben",
            "unternehmen",
            "bewerbung",
        },
        "it": {
            "posizione",
            "requisiti",
            "esperienza",
            "competenze",
            "responsabilita",
            "azienda",
            "lavoro",
        },
        "nl": {
            "vacature",
            "vereisten",
            "ervaring",
            "vaardigheden",
            "werkzaamheden",
            "bedrijf",
            "functie",
        },
    }
    scores = {language: len(tokens & values) for language, values in markers.items()}
    language, score = max(scores.items(), key=lambda item: item[1])
    return "es" if language == "es" and score >= 2 else "en"


TECHNICAL_QUESTION_LIBRARY: dict[str, dict[str, str]] = {
    "playwright": {
        "label_es": "Playwright",
        "label_en": "Playwright",
        "question_es": "¿Cómo diseñarías una prueba estable con Playwright para un flujo crítico?",
        "question_en": "How would you design a stable Playwright test for a critical user flow?",
        "answer_es": (
            "Usaría localizadores orientados al usuario, esperas automáticas y datos de prueba "
            "controlados. Separaría preparación, acción y verificación; conservaría trazas, video "
            "o capturas sólo cuando ayuden a diagnosticar un fallo."
        ),
        "answer_en": (
            "Use user-facing locators, automatic waiting, and controlled test data. Separate setup, "
            "action, and assertion, and retain traces, video, or screenshots only when they improve "
            "failure diagnosis."
        ),
        "exercise_es": "Automatiza un inicio de sesión válido y uno inválido; añade aserciones de estado y una traza útil para depuración.",
        "exercise_en": "Automate one valid and one invalid sign-in path, with state assertions and a useful debugging trace.",
    },
    "manual_testing": {
        "label_es": "Pruebas manuales",
        "label_en": "Manual testing",
        "question_es": "¿Cómo convertirías una historia de usuario ambigua en casos de prueba útiles?",
        "question_en": "How would you turn an ambiguous user story into useful test cases?",
        "answer_es": (
            "Aclararía objetivo, actores, reglas y criterios de aceptación. Luego cubriría el flujo feliz, "
            "límites, errores, permisos y datos representativos, indicando precondiciones, pasos, resultado "
            "esperado y prioridad."
        ),
        "answer_en": (
            "Clarify the goal, actors, rules, and acceptance criteria. Then cover the happy path, boundaries, "
            "errors, permissions, and representative data, documenting preconditions, steps, expected result, "
            "and priority."
        ),
        "exercise_es": "Diseña una tabla de casos para un formulario de registro con reglas de correo, contraseña y consentimiento.",
        "exercise_en": "Design a test-case table for a registration form with email, password, and consent rules.",
    },
    "test_strategy": {
        "label_es": "Estrategia de pruebas",
        "label_en": "Test strategy",
        "question_es": "¿Cómo priorizarías las pruebas cuando el tiempo de una entrega es limitado?",
        "question_en": "How would you prioritize testing when release time is limited?",
        "answer_es": (
            "Aplicaría un enfoque basado en riesgo: impacto para el usuario o negocio, probabilidad de fallo, "
            "cambios recientes y capacidad de detección. Probaría primero rutas críticas e integraciones y "
            "documentaría explícitamente el riesgo residual."
        ),
        "answer_en": (
            "Use risk-based testing: user or business impact, failure likelihood, recent change, and detectability. "
            "Test critical paths and integrations first, and document residual risk explicitly."
        ),
        "exercise_es": "Prioriza diez casos de una tienda en línea para una ventana de pruebas de dos horas y justifica el riesgo de cada elección.",
        "exercise_en": "Prioritize ten online-store scenarios for a two-hour test window and justify the risk behind each choice.",
    },
    "defect_management": {
        "label_es": "Gestión de defectos",
        "label_en": "Defect management",
        "question_es": "¿Qué información debe contener un reporte de defecto que permita actuar al equipo?",
        "question_en": "What should an actionable defect report contain?",
        "answer_es": (
            "Debe incluir título preciso, entorno y versión, precondiciones, pasos mínimos, resultado esperado y "
            "real, evidencia, frecuencia, severidad e impacto. La prioridad se acuerda considerando riesgo y urgencia."
        ),
        "answer_en": (
            "Include a precise title, environment and build, preconditions, minimal reproduction steps, expected "
            "and actual behavior, evidence, frequency, severity, and impact. Agree priority from risk and urgency."
        ),
        "exercise_es": "Redacta un defecto reproducible para un pago duplicado e indica qué evidencia adjuntarías.",
        "exercise_en": "Write a reproducible defect for a duplicate payment and identify the evidence you would attach.",
    },
    "exploratory_testing": {
        "label_es": "Pruebas exploratorias",
        "label_en": "Exploratory testing",
        "question_es": "¿Cómo ejecutarías y documentarías una sesión de pruebas exploratorias?",
        "question_en": "How would you run and document an exploratory testing session?",
        "answer_es": (
            "Definiría una misión, alcance y tiempo. Durante la sesión registraría datos, recorridos, observaciones "
            "y preguntas; al finalizar resumiría cobertura, riesgos, defectos y próximos experimentos."
        ),
        "answer_en": (
            "Define a charter, scope, and timebox. Record data, paths, observations, and questions during the "
            "session, then summarize coverage, risks, defects, and next experiments."
        ),
        "exercise_es": "Crea una misión exploratoria de 30 minutos para el buscador y los filtros de una bolsa de empleo.",
        "exercise_en": "Create a 30-minute exploratory charter for the search and filters of a job board.",
    },
    "api_testing": {
        "label_es": "Pruebas de API",
        "label_en": "API testing",
        "question_es": "¿Qué validarías en una API además del código de estado HTTP?",
        "question_en": "What would you validate in an API beyond the HTTP status code?",
        "answer_es": (
            "Validaría contrato y tipos, reglas de negocio, autorizaciones, cabeceras, idempotencia, paginación, "
            "errores, límites y tiempos de respuesta. También comprobaría efectos persistidos y ausencia de datos sensibles."
        ),
        "answer_en": (
            "Validate schema and types, business rules, authorization, headers, idempotency, pagination, error "
            "behavior, limits, and response time, plus persisted side effects and absence of sensitive data."
        ),
        "exercise_es": "Diseña pruebas positivas, negativas y de autorización para un endpoint que crea solicitudes de empleo.",
        "exercise_en": "Design positive, negative, and authorization tests for an endpoint that creates job applications.",
    },
    "sql": {
        "label_es": "SQL y validación de datos",
        "label_en": "SQL and data validation",
        "question_es": "¿Cómo comprobarías con SQL que un proceso no creó registros duplicados?",
        "question_en": "How would you use SQL to verify that a process created no duplicate records?",
        "answer_es": (
            "Agruparía por la clave de negocio y buscaría conteos mayores que uno; después inspeccionaría los casos, "
            "las restricciones únicas y la transacción que los produjo. La consulta debe distinguir duplicado real "
            "de versiones históricas válidas."
        ),
        "answer_en": (
            "Group by the business key and identify counts above one, then inspect the cases, unique constraints, "
            "and producing transaction. The query must distinguish true duplicates from valid historical versions."
        ),
        "exercise_es": "Escribe una consulta para detectar correos repetidos por empresa y explicar cómo validarías el resultado.",
        "exercise_en": "Write a query to detect repeated email addresses per company and explain how you would validate the result.",
    },
    "automation": {
        "label_es": "Automatización de pruebas",
        "label_en": "Test automation",
        "question_es": "¿Qué pruebas automatizarías primero y cuáles mantendrías manuales?",
        "question_en": "Which tests would you automate first, and which would you keep manual?",
        "answer_es": (
            "Priorizaría pruebas repetibles, estables, de alto riesgo y ejecutadas con frecuencia. Mantendría manuales "
            "las evaluaciones nuevas, muy cambiantes, subjetivas o de baja repetición hasta entender mejor su valor."
        ),
        "answer_en": (
            "Prioritize repeatable, stable, high-risk tests that run frequently. Keep new, highly volatile, subjective, "
            "or rarely repeated evaluations manual until their value and behavior are understood."
        ),
        "exercise_es": "Clasifica una lista de pruebas de regresión por valor de automatización, costo de mantenimiento y riesgo.",
        "exercise_en": "Classify a regression suite by automation value, maintenance cost, and risk.",
    },
    "flaky_tests": {
        "label_es": "Estabilidad de pruebas",
        "label_en": "Test reliability",
        "question_es": "¿Cómo investigarías una prueba automática intermitente?",
        "question_en": "How would you investigate an intermittent automated test?",
        "answer_es": (
            "Reuniría frecuencia, entorno, traza y artefactos; aislaría dependencias, tiempo, datos y concurrencia. "
            "Eliminaría esperas fijas, controlaría el estado y corregiría la causa antes de aplicar reintentos limitados."
        ),
        "answer_en": (
            "Collect frequency, environment, traces, and artifacts, then isolate dependencies, timing, data, and "
            "concurrency. Remove fixed sleeps, control state, and fix the cause before considering bounded retries."
        ),
        "exercise_es": "Diagnostica una prueba que falla sólo en CI y plantea un experimento para cada hipótesis.",
        "exercise_en": "Diagnose a test that fails only in CI and propose one experiment for each hypothesis.",
    },
    "ci_cd": {
        "label_es": "Integración continua",
        "label_en": "Continuous integration",
        "question_es": "¿Cómo integrarías controles de calidad en un pipeline de CI sin volverlo demasiado lento?",
        "question_en": "How would you add quality gates to CI without making the pipeline too slow?",
        "answer_es": (
            "Separaría controles rápidos por cambio de suites amplias programadas, ejecutaría en paralelo cuando sea "
            "seguro y usaría caché. El bloqueo debe depender de señales confiables, con tiempos y responsables visibles."
        ),
        "answer_en": (
            "Separate fast change-level checks from broader scheduled suites, parallelize safely, and use caching. "
            "Blocking gates should rely on trustworthy signals with visible timing and ownership."
        ),
        "exercise_es": "Diseña etapas de CI para lint, unitarias, API, UI y seguridad indicando cuáles bloquean el despliegue.",
        "exercise_en": "Design CI stages for lint, unit, API, UI, and security checks, identifying which ones block deployment.",
    },
    "api_design": {
        "label_es": "Diseño de API",
        "label_en": "API design",
        "question_es": "¿Qué decisiones tomarías al diseñar un endpoint de creación idempotente?",
        "question_en": "What decisions would you make when designing an idempotent create endpoint?",
        "answer_es": (
            "Definiría contrato, autenticación, validación y semántica de errores; aceptaría una clave de idempotencia, "
            "guardaría su resultado durante una ventana y devolvería la misma respuesta para reintentos equivalentes."
        ),
        "answer_en": (
            "Define the contract, authentication, validation, and error semantics. Accept an idempotency key, retain "
            "its result for a bounded window, and return the same outcome for equivalent retries."
        ),
        "exercise_es": "Diseña el contrato de una API para guardar una vacante como interés sin crear duplicados.",
        "exercise_en": "Design an API contract that saves an interested job without creating duplicates.",
    },
    "debugging": {
        "label_es": "Diagnóstico",
        "label_en": "Debugging",
        "question_es": "¿Cómo abordarías un fallo de producción que no puedes reproducir localmente?",
        "question_en": "How would you approach a production failure that you cannot reproduce locally?",
        "answer_es": (
            "Delimitaría impacto y línea de tiempo, revisaría cambios y telemetría redactada, formularía hipótesis y "
            "compararía entornos. Aplicaría mitigación reversible antes de corregir la causa y añadir una prueba preventiva."
        ),
        "answer_en": (
            "Bound the impact and timeline, review recent changes and redacted telemetry, form hypotheses, and compare "
            "environments. Apply a reversible mitigation before fixing the cause and adding a regression test."
        ),
        "exercise_es": "Propón un árbol de diagnóstico para respuestas 500 que sólo aparecen bajo carga.",
        "exercise_en": "Propose a diagnostic tree for HTTP 500 responses that appear only under load.",
    },
    "security": {
        "label_es": "Seguridad de aplicaciones",
        "label_en": "Application security",
        "question_es": "¿Qué controles mínimos aplicarías al procesar datos enviados por un usuario?",
        "question_en": "What minimum controls would you apply when processing user-supplied data?",
        "answer_es": (
            "Validaría estructura y límites, codificaría salidas, aplicaría autorización por recurso y consultas "
            "parametrizadas, limitaría tasa y tamaño, protegería secretos y evitaría registrar datos sensibles."
        ),
        "answer_en": (
            "Validate structure and bounds, encode output, enforce resource-level authorization and parameterized "
            "queries, limit rate and size, protect secrets, and avoid logging sensitive data."
        ),
        "exercise_es": "Revisa un formulario de carga de CV e identifica amenazas, controles y pruebas de seguridad.",
        "exercise_en": "Review a resume upload form and identify threats, controls, and security tests.",
    },
    "performance": {
        "label_es": "Rendimiento",
        "label_en": "Performance",
        "question_es": "¿Cómo investigarías una operación que se volvió lenta después de una entrega?",
        "question_en": "How would you investigate an operation that became slow after a release?",
        "answer_es": (
            "Compararía métricas antes y después, segmentaría latencia por componente y revisaría consultas, llamadas "
            "externas, volumen y contención. Optimizaría el cuello medido y verificaría resultado y regresiones."
        ),
        "answer_en": (
            "Compare before-and-after metrics, split latency by component, and inspect queries, external calls, volume, "
            "and contention. Optimize the measured bottleneck and verify both improvement and regressions."
        ),
        "exercise_es": "Diseña una prueba para determinar si una API cumple un objetivo de latencia p95 bajo carga.",
        "exercise_en": "Design a test to determine whether an API meets a p95 latency target under load.",
    },
    "git": {
        "label_es": "Colaboración con Git",
        "label_en": "Git collaboration",
        "question_es": "¿Cómo mantendrías una solicitud de cambios fácil de revisar y segura de integrar?",
        "question_en": "How would you keep a change request easy to review and safe to merge?",
        "answer_es": (
            "Limitaría el alcance, separaría cambios mecánicos de comportamiento, explicaría intención y riesgos, "
            "añadiría pruebas y evidencias, respondería observaciones y evitaría reescribir historial compartido."
        ),
        "answer_en": (
            "Keep scope focused, separate mechanical from behavioral changes, explain intent and risks, add tests and "
            "evidence, address feedback, and avoid rewriting shared history."
        ),
        "exercise_es": "Divide una funcionalidad grande en una secuencia de cambios pequeños que puedan revisarse de forma independiente.",
        "exercise_en": "Break a large feature into a sequence of small changes that can be reviewed independently.",
    },
    "general_problem": {
        "label_es": "Resolución de problemas",
        "label_en": "Problem solving",
        "question_es": "¿Cómo resolverías un problema técnico o de dominio con información incompleta?",
        "question_en": "How would you solve a technical or domain problem with incomplete information?",
        "answer_es": (
            "Aclararía el resultado esperado y las restricciones, separaría hechos de supuestos, priorizaría las "
            "incógnitas de mayor riesgo y ejecutaría experimentos pequeños. Documentaría decisiones y validaría con interesados."
        ),
        "answer_en": (
            "Clarify the expected outcome and constraints, separate facts from assumptions, prioritize the highest-risk "
            "unknowns, and run small experiments. Document decisions and validate them with stakeholders."
        ),
        "exercise_es": "Define preguntas, hipótesis y un experimento mínimo para una solicitud de negocio ambigua.",
        "exercise_en": "Define questions, hypotheses, and a minimum experiment for an ambiguous business request.",
    },
}


TOPIC_MARKERS: dict[str, tuple[str, ...]] = {
    "playwright": ("playwright",),
    "manual_testing": ("manual test", "manual qa", "pruebas manual", "casos de prueba"),
    "api_testing": ("api test", "postman", "rest assured", "pruebas de api"),
    "sql": (" sql", "database", "base de datos", "query", "consulta"),
    "automation": ("automation", "automatiz", "selenium", "cypress", "appium", "sdet"),
    "flaky_tests": ("flaky", "intermittent", "inestable", "estabilidad"),
    "ci_cd": (
        "ci/cd",
        "continuous integration",
        "pipeline",
        "integración continua",
        "github actions",
        "jenkins",
    ),
    "api_design": (
        "api design",
        "rest api",
        "backend",
        "fastapi",
        "endpoint",
        "microservice",
    ),
    "debugging": ("debug", "troubleshoot", "diagnos", "support"),
    "security": ("security", "seguridad", "owasp", "authentication", "authorization"),
    "performance": (
        "performance",
        "rendimiento",
        "latency",
        "load test",
        "k6",
        "jmeter",
    ),
    "git": (" git", "github", "gitlab", "version control", "control de versiones"),
    "defect_management": ("defect", "bug", "jira", "incidencia"),
    "exploratory_testing": ("exploratory", "exploratoria"),
    "test_strategy": ("quality", " qa", "test", "calidad", "prueba"),
}


def _unique_text(values: list[str], *, limit: int) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        cleaned = _plain_job_text(value)
        key = _fold(cleaned)
        if cleaned and key not in seen:
            seen.add(key)
            result.append(cleaned)
        if len(result) >= limit:
            break
    return result


def _guide_requirements(job: JobRecord) -> list[tuple[str, bool]]:
    required = _unique_text(
        [*job.requirements, *extract_requirements(job, limit=12)], limit=10
    )
    preferred = _unique_text(list(job.preferred_requirements), limit=4)
    result = [(item, True) for item in required]
    required_keys = {_fold(item) for item in required}
    result.extend(
        (item, False) for item in preferred if _fold(item) not in required_keys
    )
    return result[:12]


def _job_overview(job: JobRecord, *, spanish: bool) -> str:
    cleaned = _plain_job_text(job.description)
    fragments = [
        clean_text(item)
        for item in re.split(r"(?<=[.!?])\s+|\n+", cleaned)
        if 35 <= len(clean_text(item)) <= 420
    ]
    summary = " ".join(fragments[:3]).strip()
    if summary:
        return summary[:1_100]
    return (
        f"La vacante corresponde a {job.title} en {job.company}. La fuente no incluyó un resumen suficientemente detallado."
        if spanish
        else f"This opening is for {job.title} at {job.company}. The source did not include a sufficiently detailed summary."
    )


def _question_topics(job: JobRecord) -> list[str]:
    haystack = f" {_fold(job.title)} {_fold(job.description)} "
    haystack += " " + " ".join(
        _fold(value) for value in [*job.requirements, *job.preferred_requirements]
    )
    selected = [
        topic
        for topic, markers in TOPIC_MARKERS.items()
        if any(marker in haystack for marker in markers)
    ]
    title = _fold(job.title)
    qa_role = any(
        marker in haystack
        for marker in (" qa ", "quality assurance", "tester", "sdet", "pruebas")
    )
    developer_role = any(
        marker in haystack
        for marker in (
            "developer",
            "engineer",
            "desarrollador",
            "software",
            "backend",
            "frontend",
        )
    )
    if qa_role:
        defaults = [
            "test_strategy",
            "manual_testing",
            "defect_management",
            "exploratory_testing",
            "automation",
            "api_testing",
            "flaky_tests",
            "ci_cd",
            "sql",
            "general_problem",
        ]
    elif developer_role or any(
        marker in title for marker in ("ingeniero", "programador")
    ):
        defaults = [
            "api_design",
            "debugging",
            "security",
            "performance",
            "sql",
            "git",
            "ci_cd",
            "automation",
            "api_testing",
            "general_problem",
        ]
    else:
        defaults = [
            "general_problem",
            "test_strategy",
            "defect_management",
            "debugging",
            "security",
            "performance",
            "sql",
            "git",
            "ci_cd",
            "api_design",
        ]
    return list(dict.fromkeys([*selected, *defaults]))[:10]


def _guide_fact_map(profile: Profile, language: str) -> dict[str, dict[str, str]]:
    facts = cloud_safe_verified_facts(
        profile,
        limit=max(20, len(profile.facts)),
        language=language,
        include_all=True,
    )
    return {item["fact_id"]: item for item in facts}


def _matched_evidence(
    analysis: DeepFitAnalysis, safe_facts: dict[str, dict[str, str]]
) -> list[dict[str, str]]:
    matched: list[dict[str, str]] = []
    for item in analysis.matched_requirements:
        fact_id = item.get("fact_id", "")
        requirement = _plain_job_text(item.get("requirement", ""))
        fact = safe_facts.get(fact_id)
        if requirement and fact:
            matched.append(
                {
                    "requirement": requirement,
                    "fact_id": fact_id,
                    "evidence": fact["text"],
                }
            )
    return matched


def _evidence_for_topic(
    topic: str, matched: list[dict[str, str]]
) -> dict[str, str] | None:
    markers = TOPIC_MARKERS.get(topic, ())
    for item in matched:
        haystack = f" {_fold(item['requirement'])} {_fold(item['evidence'])} "
        if any(marker in haystack for marker in markers):
            return item
    return None


def build_interview_guide(
    *, guide: InterviewGuide, job: JobRecord, profile: Profile
) -> Artifact:
    language = guide.language
    spanish = language == "es"
    analysis = guide.analysis
    safe_facts = _guide_fact_map(profile, language)
    matched = _matched_evidence(analysis, safe_facts)
    used_fact_ids = {
        item["fact_id"] for item in matched if item["fact_id"] in safe_facts
    }
    matched_by_requirement = {_fold(item["requirement"]): item for item in matched}
    gaps = _unique_text(
        [
            *analysis.missing_requirements,
            *(
                item.get("requirement", "")
                for item in analysis.matched_requirements
                if item.get("fact_id", "") not in safe_facts
            ),
        ],
        limit=10,
    )
    gap_keys = {_fold(item) for item in gaps}
    requirements = _guide_requirements(job)
    topics = _question_topics(job)
    display_name = clean_text(str(getattr(profile, "display_name", "") or profile.name))
    fit_label = {
        "high": "alto" if spanish else "high",
        "medium": "medio" if spanish else "medium",
        "low": "bajo" if spanish else "low",
    }.get(analysis.level, analysis.level)
    posted = (
        job.posted_at.isoformat()
        if job.posted_at
        else ("No indicada" if spanish else "Not specified")
    )
    location = job.location or ("No indicada" if spanish else "Not specified")
    link = str(job.final_url or job.url or job.source_url or "")
    link_type = (
        (
            "Enlace final de la empresa"
            if job.apply_url_type == "company"
            else "Enlace del portal"
        )
        if spanish
        else (
            "Final company link" if job.apply_url_type == "company" else "Portal link"
        )
    )

    pages: list[str] = []
    if spanish:
        pages.append(
            "\n".join(
                [
                    "WORKSPACE CAREER BRIEF - PLANTILLA 2.0",
                    f"Perfil profesional: {display_name}",
                    f"Puesto: {job.title}",
                    f"Empresa: {job.company}",
                    f"Idioma del CV: {language.upper()}",
                    f"Encaje estimado: {fit_label} ({analysis.score:.0f}/100)",
                    "Aviso: material de preparación sujeto a revisión humana. No sustituye la descripción oficial.",
                ]
            )
        )
        pages.append(
            "\n".join(
                [
                    "## 1. De qué trata el puesto",
                    _job_overview(job, spanish=True),
                    "",
                    "### Datos de la vacante",
                    f"Puesto: {job.title}",
                    f"Empresa: {job.company}",
                    f"Ubicación y modalidad: {location}",
                    f"Fecha de publicación: {posted}",
                    f"Procedencia: {job.provider or str(job.source)} / {job.source_portal or 'fuente registrada'}",
                    f"{link_type}: {link or 'No disponible'}",
                    "",
                    "Nota de alcance: el encaje es una estimación basada en la descripción disponible y los hechos confirmados del perfil.",
                ]
            )
        )
        matrix = ["## 2. Requisitos y matriz de evidencia"]
        if not requirements:
            matrix.append(
                "- La fuente no proporcionó requisitos suficientemente específicos; confirma el alcance con la empresa."
            )
        for index, (requirement, mandatory) in enumerate(requirements, start=1):
            evidence = matched_by_requirement.get(_fold(requirement))
            requirement_key = _fold(requirement)
            matrix.extend(
                [
                    "",
                    f"### Requisito {index} - {'Obligatorio' if mandatory else 'Deseable'}",
                    f"Requisito: {requirement}",
                ]
            )
            if evidence:
                matrix.extend(
                    [
                        "Estado: Respaldado por el CV confirmado",
                        f"Evidencia profesional confirmada: {evidence['evidence']}",
                    ]
                )
            elif requirement_key in gap_keys:
                matrix.extend(
                    [
                        "Estado: Brecha detectada",
                        "Tema para estudiar: No hay evidencia confirmada en el perfil. No afirmes esta experiencia; prepara aprendizaje y preguntas de aclaración.",
                    ]
                )
            else:
                matrix.extend(
                    [
                        "Estado: Evidencia desconocida",
                        "Tema para estudiar: Revisa si existe un ejemplo verificable antes de mencionarlo; si no existe, trátalo como aprendizaje.",
                    ]
                )
        pages.append("\n".join(matrix))
        strengths = ["## 3. Fortalezas, brechas y recomendaciones honestas"]
        strengths.append("### Fortalezas que puedes demostrar")
        if matched:
            strengths.extend(f"- {item['evidence']}" for item in matched[:6])
        else:
            strengths.append(
                "- No se encontró evidencia confirmada suficiente para afirmar una fortaleza específica del puesto."
            )
        strengths.append("### Brechas y temas prioritarios")
        strengths.extend(f"- {item}" for item in gaps[:6])
        if not gaps:
            strengths.append(
                "- No se detectó una brecha explícita; valida los detalles con el entrevistador."
            )
        strengths.append("### Recomendaciones para mejorar el CV existente")
        for item in matched[:4]:
            strengths.append(
                f"- Da mayor visibilidad a esta evidencia sin cambiar su significado: {item['evidence']}"
            )
        for item in gaps[:4]:
            strengths.append(
                f"- Si realmente tienes experiencia con '{item}', añade un ejemplo verificable. Si no la tienes, no la incluyas y conviértela en un objetivo de aprendizaje."
            )
        strengths.append(
            "- Mantén empresas, fechas, métricas, herramientas y responsabilidades exactamente como puedas demostrarlas."
        )
        pages.append("\n".join(strengths))
    else:
        pages.append(
            "\n".join(
                [
                    "WORKSPACE CAREER BRIEF - TEMPLATE 2.0",
                    f"Professional profile: {display_name}",
                    f"Role: {job.title}",
                    f"Company: {job.company}",
                    f"Resume language: {language.upper()}",
                    f"Estimated fit: {fit_label} ({analysis.score:.0f}/100)",
                    "Notice: preparation material requiring human review. It does not replace the official posting.",
                ]
            )
        )
        pages.append(
            "\n".join(
                [
                    "## 1. What this role is about",
                    _job_overview(job, spanish=False),
                    "",
                    "### Vacancy details",
                    f"Role: {job.title}",
                    f"Company: {job.company}",
                    f"Location and work mode: {location}",
                    f"Published: {posted}",
                    f"Source: {job.provider or str(job.source)} / {job.source_portal or 'registered source'}",
                    f"{link_type}: {link or 'Not available'}",
                    "",
                    "Scope note: fit is an estimate based on the available posting and confirmed profile facts.",
                ]
            )
        )
        matrix = ["## 2. Requirements and evidence matrix"]
        if not requirements:
            matrix.append(
                "- The source did not provide sufficiently specific requirements; confirm scope with the employer."
            )
        for index, (requirement, mandatory) in enumerate(requirements, start=1):
            evidence = matched_by_requirement.get(_fold(requirement))
            requirement_key = _fold(requirement)
            matrix.extend(
                [
                    "",
                    f"### Requirement {index} - {'Required' if mandatory else 'Preferred'}",
                    f"Requirement: {requirement}",
                ]
            )
            if evidence:
                matrix.extend(
                    [
                        "Status: Supported by the confirmed resume",
                        f"Confirmed professional evidence: {evidence['evidence']}",
                    ]
                )
            elif requirement_key in gap_keys:
                matrix.extend(
                    [
                        "Status: Identified gap",
                        "Study topic: The profile contains no confirmed evidence. Do not claim this experience; prepare learning and clarification questions.",
                    ]
                )
            else:
                matrix.extend(
                    [
                        "Status: Evidence unknown",
                        "Study topic: Check for a verifiable example before mentioning it; otherwise treat it as a learning goal.",
                    ]
                )
        pages.append("\n".join(matrix))
        strengths = ["## 3. Strengths, gaps, and honest recommendations"]
        strengths.append("### Strengths you can demonstrate")
        if matched:
            strengths.extend(f"- {item['evidence']}" for item in matched[:6])
        else:
            strengths.append(
                "- There is not enough confirmed evidence to claim a role-specific strength."
            )
        strengths.append("### Priority gaps and study topics")
        strengths.extend(f"- {item}" for item in gaps[:6])
        if not gaps:
            strengths.append(
                "- No explicit gap was detected; validate the details with the interviewer."
            )
        strengths.append("### Recommendations for the existing resume")
        for item in matched[:4]:
            strengths.append(
                f"- Give this evidence more visibility without changing its meaning: {item['evidence']}"
            )
        for item in gaps[:4]:
            strengths.append(
                f"- If you truly have experience with '{item}', add a verifiable example. Otherwise do not add it; make it a learning objective."
            )
        strengths.append(
            "- Keep employers, dates, metrics, tools, and responsibilities exactly as you can substantiate them."
        )
        pages.append("\n".join(strengths))

    question_pages: list[list[str]] = []
    for index, topic in enumerate(topics, start=1):
        template = TECHNICAL_QUESTION_LIBRARY[topic]
        evidence = _evidence_for_topic(topic, matched)
        if (index - 1) % 2 == 0:
            question_pages.append(
                [
                    (
                        f"## 4. Preguntas técnicas y respuestas - bloque {len(question_pages) + 1}"
                        if spanish
                        else f"## 4. Technical questions and reference answers - set {len(question_pages) + 1}"
                    )
                ]
            )
        page = question_pages[-1]
        page.extend(
            [
                "",
                f"### {'Pregunta técnica' if spanish else 'Technical question'} {index} - {template['label_es' if spanish else 'label_en']}",
                f"{'Pregunta' if spanish else 'Question'}: {template['question_es' if spanish else 'question_en']}",
                f"{'Respuesta técnica de referencia' if spanish else 'Technical reference answer'}: {template['answer_es' if spanish else 'answer_en']}",
            ]
        )
        if evidence:
            page.append(
                f"Cómo conectarlo con tu experiencia: Usa únicamente esta experiencia profesional confirmada y explica el contexto con tus propias palabras: {evidence['evidence']}"
                if spanish
                else f"How to connect it to your experience: Use only this confirmed professional experience and explain its context in your own words: {evidence['evidence']}"
            )
        else:
            page.append(
                "Tema para estudiar: No hay un hecho confirmado que demuestre esta competencia. Practica la respuesta de referencia, pero no la presentes como experiencia personal."
                if spanish
                else "Study topic: No confirmed fact demonstrates this competency. Practice the reference answer, but do not present it as personal experience."
            )
    pages.extend("\n".join(page) for page in question_pages)

    exercises = [
        "## 5. Ejercicios prácticos probables"
        if spanish
        else "## 5. Likely practical exercises"
    ]
    for index, topic in enumerate(topics[:3], start=1):
        template = TECHNICAL_QUESTION_LIBRARY[topic]
        exercises.extend(
            [
                "",
                f"### {'Ejercicio' if spanish else 'Exercise'} {index} - {template['label_es' if spanish else 'label_en']}",
                f"{'Consigna' if spanish else 'Prompt'}: {template['exercise_es' if spanish else 'exercise_en']}",
                (
                    "Criterios de evaluación: claridad de supuestos, cobertura de riesgos, solución verificable, comunicación de decisiones y reconocimiento de límites."
                    if spanish
                    else "Evaluation criteria: clear assumptions, risk coverage, verifiable solution, decision communication, and recognition of limits."
                ),
                (
                    "Preparación sugerida: resuelve primero sin ayuda, registra decisiones y luego compara el resultado con documentación oficial."
                    if spanish
                    else "Suggested preparation: solve it without assistance first, record decisions, and then compare the outcome with official documentation."
                ),
            ]
        )
    pages.append("\n".join(exercises))

    employer_questions = (
        [
            "¿Cómo se medirá el éxito durante los primeros 30, 60 y 90 días?",
            "¿Cuáles son los riesgos o retos más importantes que heredará esta persona?",
            "¿Qué resultados distinguen a alguien que tiene un desempeño excelente en el puesto?",
            "¿Cómo se organizan la revisión, mentoría y retroalimentación del equipo?",
            "¿Qué herramientas y procesos son esenciales en el trabajo cotidiano?",
            "¿Cómo se deciden prioridades cuando calidad, alcance y fecha entran en tensión?",
            "¿Qué parte de la descripción podría cambiar durante los próximos seis meses?",
            "¿Cómo es el proceso restante y qué debería preparar para la siguiente etapa?",
        ]
        if spanish
        else [
            "How will success be measured during the first 30, 60, and 90 days?",
            "What are the most important risks or challenges this person will inherit?",
            "What outcomes distinguish excellent performance in this role?",
            "How are review, mentoring, and feedback organized within the team?",
            "Which tools and processes are essential in day-to-day work?",
            "How are priorities decided when quality, scope, and timing conflict?",
            "Which part of this role might change during the next six months?",
            "What remains in the hiring process, and what should I prepare next?",
        ]
    )
    pages.append(
        "\n".join(
            [
                "## 6. Preguntas para la empresa"
                if spanish
                else "## 6. Questions for the employer",
                *[f"- {item}" for item in employer_questions],
                "",
                (
                    "Elige de tres a cinco preguntas según el momento; no es necesario formularlas todas."
                    if spanish
                    else "Choose three to five questions that fit the conversation; you do not need to ask all of them."
                ),
            ]
        )
    )

    study_items = gaps[:5] or [
        template["label_es" if spanish else "label_en"]
        for template in (TECHNICAL_QUESTION_LIBRARY[topic] for topic in topics[:3])
    ]
    final_page = [
        "## 7. Plan de estudio y lista final"
        if spanish
        else "## 7. Study plan and final checklist",
        "### Plan de preparación" if spanish else "### Preparation plan",
    ]
    for index, item in enumerate(study_items, start=1):
        final_page.append(
            f"- Prioridad {index}: {item}. Estudia la base, practica un ejemplo y registra qué aún no puedes demostrar."
            if spanish
            else f"- Priority {index}: {item}. Study the foundation, practice one example, and record what you still cannot demonstrate."
        )
    final_page.extend(
        [
            "### Lista previa" if spanish else "### Final checklist",
            *(
                [
                    "- Releer la publicación y comprobar que el enlace siga activo.",
                    "- Practicar las preguntas técnicas en voz alta.",
                    "- Resolver al menos un ejercicio sin consultar la respuesta.",
                    "- Investigar producto, clientes y noticias desde fuentes verificables.",
                    "- Confirmar modalidad, horario, zona, idioma y elegibilidad laboral para el país seleccionado.",
                    "- Preparar preguntas para la empresa.",
                    "- Probar cámara, micrófono, conexión y entorno si la entrevista es remota.",
                    "- Llevar el CV utilizado y no afirmar conocimientos que no puedas demostrar.",
                    "- Anotar aprendizajes inmediatamente después de la entrevista.",
                ]
                if spanish
                else [
                    "- Re-read the posting and confirm that its link is still active.",
                    "- Practice the technical questions aloud.",
                    "- Complete at least one exercise without consulting the answer.",
                    "- Research the product, customers, and news through verifiable sources.",
                    "- Confirm work mode, hours, time zone, language, and eligibility for the selected country.",
                    "- Prepare questions for the employer.",
                    "- Test camera, microphone, connection, and environment for a remote interview.",
                    "- Bring the resume used here and do not claim knowledge you cannot demonstrate.",
                    "- Record lessons immediately after the interview.",
                ]
            ),
            "### Fuente y trazabilidad" if spanish else "### Source and traceability",
            f"{'Publicación' if spanish else 'Posting'}: {job.title} - {job.company}",
            f"{'Fecha' if spanish else 'Published'}: {posted}",
            f"{link_type}: {link or ('No disponible' if spanish else 'Not available')}",
            (
                "Revisión humana obligatoria: verifica siempre la publicación oficial antes de usar esta guía."
                if spanish
                else "Human review required: always verify the official posting before using this guide."
            ),
        ]
    )
    pages.append("\n".join(final_page))

    content = "\n\f\n".join(pages)
    title = (
        f"Guía de entrevista - {job.title} - {job.company}"
        if spanish
        else f"Interview guide - {job.title} - {job.company}"
    )
    return Artifact(
        run_id=guide.guide_id,
        job_id=job.job_id,
        profile_id=profile.profile_id,
        kind="interview_guide",
        title=title,
        content=content,
        language=language,
        claims=[
            Claim(text=safe_facts[fact_id]["text"], fact_ids=[fact_id])
            for fact_id in sorted(used_fact_ids)
            if fact_id in safe_facts
        ],
    )


def _is_valid_official_url(job: JobRecord) -> bool:
    if not job.url:
        return False
    parsed = urlparse(str(job.url))
    return parsed.scheme == "https" and bool(parsed.hostname)


TRACKING_QUERY_KEYS = {
    "fbclid",
    "gclid",
    "ref",
    "referrer",
    "source",
    "trk",
}


def _canonical_url(value: object) -> str | None:
    if not value:
        return None
    try:
        parsed = urlsplit(str(value))
    except ValueError:
        return None
    if parsed.scheme.casefold() not in {"http", "https"} or not parsed.hostname:
        return None
    query = urlencode(
        [
            (key, item)
            for key, item in parse_qsl(parsed.query, keep_blank_values=True)
            if not key.casefold().startswith("utm_")
            and key.casefold() not in TRACKING_QUERY_KEYS
        ]
    )
    path = re.sub(r"/{2,}", "/", parsed.path or "/")
    if path != "/":
        path = path.rstrip("/")
    port = f":{parsed.port}" if parsed.port else ""
    return urlunsplit(("https", f"{parsed.hostname.casefold()}{port}", path, query, ""))


def _source_evidence(job: JobRecord) -> list[dict[str, object]]:
    evidence = [item.model_dump(mode="json") for item in job.source_evidence]
    existing = job.raw.get("source_evidence")
    if isinstance(existing, list):
        evidence.extend(dict(item) for item in existing if isinstance(item, dict))
    evidence.append(
        {
            "provider": job.provider or str(job.source),
            "source_portal": job.source_portal,
            "source_url": str(job.source_url) if job.source_url else None,
            "final_url": str(job.final_url) if job.final_url else None,
            "apply_url_type": str(job.apply_url_type),
            "external_id": job.external_id,
        }
    )
    unique: dict[str, dict[str, object]] = {}
    for item in evidence:
        key = "|".join(
            str(item.get(field) or "")
            for field in (
                "provider",
                "source",
                "source_url",
                "final_url",
                "external_id",
            )
        )
        unique[key] = item
    return list(unique.values())


def _typed_source_evidence(item: dict[str, object]) -> JobSourceEvidence:
    payload = {
        key: value
        for key, value in item.items()
        if key in JobSourceEvidence.model_fields
    }
    if payload.get("apply_url_type") == "company":
        payload["apply_url_type"] = "official"
    return JobSourceEvidence.model_validate(payload)


def _deduplication_keys(job: JobRecord) -> list[tuple[str, ...]]:
    urls = [
        _canonical_url(job.final_url),
        _canonical_url(job.url),
        _canonical_url(job.source_url),
    ]
    result: list[tuple[str, ...]] = [("url", url) for url in urls if url]
    if job.provider and job.external_id:
        result.append(
            ("provider_id", job.provider.casefold(), job.external_id.casefold())
        )
    elif job.external_id:
        result.append(("source_id", str(job.source), job.external_id.casefold()))
    raw_country = job.raw.get("_search_country_code") or job.raw.get("country_code")
    country = str(raw_country or "").strip().upper()
    title = clean_text(job.title).casefold()
    company = clean_text(job.company).casefold()
    location = clean_text(job.location).casefold()
    if title and company:
        result.append(("identity", company, title, country, location))
    if job.content_hash:
        result.append(("content", job.content_hash))
    return result


def _job_link_priority(job: JobRecord) -> tuple[int, int, int]:
    apply_type = str(job.apply_url_type)
    link = 3 if job.final_url else 2 if apply_type != "portal" else 1
    verification = {"official": 3, "authorized_feed": 2, "manual_portal": 1}.get(
        str(job.verification_level), 0
    )
    return (link, verification, len(job.description))


def deduplicate_canonical_jobs(jobs: list[JobRecord]) -> list[JobRecord]:
    """Deduplicate using stable identities while retaining every provenance."""

    result: list[JobRecord] = []
    indexes: dict[tuple[str, ...], int] = {}
    for job in jobs:
        keys = _deduplication_keys(job)
        existing_indexes = {indexes[key] for key in keys if key in indexes}
        if existing_indexes:
            index = min(existing_indexes)
            candidates = [*(result[item] for item in sorted(existing_indexes)), job]
            preferred = max(candidates, key=_job_link_priority)
            raw = dict(preferred.raw)
            combined_evidence = [
                evidence
                for candidate in candidates
                for evidence in _source_evidence(candidate)
            ]
            raw["source_evidence"] = list(
                {
                    "|".join(
                        str(item.get(field) or "")
                        for field in (
                            "provider",
                            "source",
                            "source_url",
                            "final_url",
                            "external_id",
                        )
                    ): item
                    for item in combined_evidence
                }.values()
            )
            sources = list(
                dict.fromkeys(
                    [
                        source
                        for candidate in candidates
                        for source in [*candidate.sources, candidate.source]
                    ]
                )
            )
            typed_evidence = [
                _typed_source_evidence(item) for item in raw["source_evidence"]
            ]
            result[index] = preferred.model_copy(
                update={
                    "sources": sources,
                    "source_evidence": typed_evidence,
                    "raw": raw,
                }
            )
            for duplicate_index in sorted(existing_indexes - {index}, reverse=True):
                del result[duplicate_index]
            indexes.clear()
            for current_index, current in enumerate(result):
                for key in _deduplication_keys(current):
                    indexes[key] = current_index
            continue
        index = len(result)
        raw = dict(job.raw)
        raw["source_evidence"] = _source_evidence(job)
        sources = list(dict.fromkeys([*job.sources, job.source]))
        typed_evidence = [
            _typed_source_evidence(item) for item in raw["source_evidence"]
        ]
        result.append(
            job.model_copy(
                update={
                    "sources": sources,
                    "source_evidence": typed_evidence,
                    "raw": raw,
                }
            )
        )
        for key in keys:
            indexes[key] = index
    return result


def _raw_country_codes(job: JobRecord) -> set[str]:
    values: list[object] = []
    for key in ("country_codes", "job_country_codes"):
        raw_value = job.raw.get(key)
        values.extend(raw_value if isinstance(raw_value, list) else [raw_value])
    values.extend(
        [
            job.raw.get("country_code"),
            job.raw.get("job_country_code"),
            job.raw.get("_search_country_code"),
        ]
    )
    return {
        str(value).strip().upper()
        for value in values
        if value and re.fullmatch(r"[A-Za-z]{2}", str(value).strip())
    }


def _work_mode(job: JobRecord) -> str | None:
    values = job.raw.get("workplace_types") or job.raw.get("workplace_type")
    if isinstance(values, str):
        values = [values]
    normalized = (
        {str(value).casefold().replace("-", "_") for value in values}
        if isinstance(values, list)
        else set()
    )
    if job.remote is True or "remote" in normalized:
        return "remote"
    if "hybrid" in normalized or "hybrid" in _fold(job.location):
        return "hybrid"
    if job.remote is False or normalized & {"on_site", "onsite"}:
        return "onsite"
    return None


def _remote_eligibility(
    job: JobRecord,
    *,
    country_code: str | None,
    include_global_remote: bool,
) -> str:
    codes = _raw_country_codes(job)
    selected = country_code.upper() if country_code else None
    location = _fold(job.location)
    worldwide = any(
        marker in location for marker in ("worldwide", "anywhere", "global")
    )
    if selected and codes:
        return "eligible_for_country" if selected in codes else "ineligible"
    if worldwide:
        return "worldwide" if include_global_remote else "eligible_for_country"
    if job.remote is not True:
        return "unknown"
    return "unknown"


def filter_verified_recent_jobs(
    jobs: list[JobRecord],
    *,
    search_started_at: Any,
    window_days: int = 7,
    country_code: str | None = None,
    city_or_region: str | None = None,
    modalities: list[str] | tuple[str, ...] | None = None,
    include_global_remote: bool = False,
) -> tuple[list[JobRecord], dict[str, int]]:
    if window_days != 7:
        raise ValueError("New career searches use a fixed seven-day window")
    lower = search_started_at - timedelta(days=window_days)
    upper = search_started_at
    accepted: list[JobRecord] = []
    rejected = {
        "missing_date": 0,
        "outside_7d": 0,
        "invalid_url": 0,
        "outside_scope": 0,
        "outside_region": 0,
        "modality_mismatch": 0,
    }
    selected_country = country_code.strip().upper() if country_code else None
    selected_region = _fold(city_or_region or "")
    selected_modalities = {
        "onsite" if str(value).casefold() == "on_site" else str(value).casefold()
        for value in (modalities or ())
    }
    # Validate before deduplication so an old copy cannot hide a fresh one.
    for job in jobs:
        if job.posted_at is None:
            rejected["missing_date"] += 1
            continue
        if not lower <= job.posted_at <= upper:
            rejected["outside_7d"] += 1
            continue
        if not _is_valid_official_url(job):
            rejected["invalid_url"] += 1
            continue
        eligibility = _remote_eligibility(
            job,
            country_code=selected_country,
            include_global_remote=include_global_remote,
        )
        codes = _raw_country_codes(job)
        if (
            selected_country
            and codes
            and selected_country not in codes
            and eligibility != "worldwide"
        ):
            rejected["outside_scope"] += 1
            continue
        mode = _work_mode(job)
        if selected_modalities and mode is not None and mode not in selected_modalities:
            rejected["modality_mismatch"] += 1
            continue
        if (
            selected_region
            and mode != "remote"
            and clean_text(job.location)
            and selected_region not in _fold(job.location)
        ):
            rejected["outside_region"] += 1
            continue
        raw = dict(job.raw)
        raw["remote_eligibility"] = eligibility
        if mode:
            raw["work_mode"] = mode
        job = job.model_copy(update={"raw": raw, "remote_eligibility": eligibility})
        job.date_confidence = "exact"
        job.official_url_verified = True
        accepted.append(job)
    return deduplicate_canonical_jobs(accepted), rejected


__all__ = [
    "build_deep_analysis",
    "build_deep_analysis_v2",
    "build_interview_guide",
    "build_quick_result",
    "deduplicate_canonical_jobs",
    "detect_job_language",
    "expand_role",
    "filter_verified_recent_jobs",
]

from __future__ import annotations

import asyncio
import re
import unicodedata
from collections.abc import Awaitable, Callable
from datetime import timedelta
from typing import Any
from urllib.parse import urlparse

from .agents import DeepSeekAgentRegistry, ScoutProposal
from .ranking import clean_text, deduplicate_jobs, rank_job
from .replay import PUBLIC_RUN_FAILURE, EventEmitter
from .schemas import (
    AgentRole,
    Artifact,
    CareerJobResult,
    CareerSearchCreate,
    Claim,
    DeepFitAnalysis,
    FitSummary,
    Interest,
    JobRecord,
    Profile,
    RunStatus,
    SearchRequest,
    SourceKind,
)
from .storage import SQLiteStore
from .theirstack import TheirStackClient, TheirStackError

ConnectorSearch = Callable[
    [SearchRequest], Awaitable[tuple[list[JobRecord], dict[str, str]]]
]

ROLE_ALIASES: dict[str, list[str]] = {
    "qa": [
        "QA",
        "QA Engineer",
        "Quality Assurance",
        "Quality Analyst",
        "Software Tester",
        "Test Engineer",
        "SDET",
    ],
    "quality assurance": [
        "Quality Assurance",
        "QA Engineer",
        "Quality Analyst",
        "Software Tester",
        "Test Engineer",
        "SDET",
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
        "Backend Developer",
        "Frontend Developer",
        "Full Stack Developer",
    ],
    "data": [
        "Data Analyst",
        "Data Engineer",
        "Analytics Engineer",
        "Business Intelligence Analyst",
    ],
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

SINGLE_TOKEN_SKILLS = {
    "qa",
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
    """Prefer the matching résumé while preserving legacy single-résumé profiles."""

    matching = [fact for fact in profile.facts if fact.language == language]
    if matching:
        return matching
    legacy = [fact for fact in profile.facts if fact.language is None]
    return legacy if legacy else list(profile.facts)


def cloud_safe_verified_facts(
    profile: Profile, limit: int = 20, *, language: str | None = None
) -> list[dict[str, str]]:
    """Return confirmed professional facts without obvious contact identifiers."""

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
            and len(fact_tokens & profile_name_tokens) >= min(2, len(profile_name_tokens))
            and len(text) < 100
        ):
            continue
        if len(text) < 24 or (text.isupper() and len(text) < 120):
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


def extract_requirements(job: JobRecord, limit: int = 8) -> list[str]:
    if job.requirements:
        provided = [_plain_job_text(value) for value in job.requirements if clean_text(value)]
        specific = [
            value
            for value in provided
            if any(marker in value.casefold() for marker in REQUIREMENT_MARKERS)
        ]
        if specific:
            return specific[:limit]
    fragments = re.split(r"(?<=[.!?;])\s+|\s+[•|]\s+", clean_text(job.description))
    selected = [
        _plain_job_text(fragment)
        for fragment in fragments
        if 18 <= len(fragment.strip()) <= 260
        and any(marker in fragment.casefold() for marker in REQUIREMENT_MARKERS)
    ]
    if not selected:
        selected = [
            _plain_job_text(fragment)
            for fragment in fragments
            if 18 <= len(fragment.strip()) <= 260
        ]
    return selected[:limit]


def _fit_level(score: float) -> str:
    if score >= 70:
        return "high"
    if score >= 45:
        return "medium"
    return "low"


def _matching_facts(
    profile: Profile, requirement: str, *, language: str | None = None
) -> list[tuple[str, str, int]]:
    requirement_tokens = _tokens(requirement)
    requirement_folded = _fold(requirement)
    duration_required = bool(
        re.search(r"\b\d+\+?\s*(?:years?|anos?)\b", requirement_folded)
    )
    degree_required = any(
        marker in requirement_folded
        for marker in ("degree", "bachelor", "licenciatura", "bachiller", "titulo")
    )
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
        if duration_required and not re.search(
            r"\b\d+\+?\s*(?:years?|anos?)\b", fact_folded
        ):
            continue
        if degree_required and not (
            fact.category == "education"
            or any(
                marker in fact_folded
                for marker in ("degree", "bachelor", "licenciatura", "bachiller", "titulo")
            )
        ):
            continue
        shared = requirement_tokens & _tokens(fact_text)
        overlap = len(shared)
        if overlap >= 2 or any(token in SINGLE_TOKEN_SKILLS for token in shared):
            evidence_bonus = 2 if any(
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
            ) else 0
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
    )


def build_deep_analysis(job: JobRecord, profile: Profile) -> DeepFitAnalysis:
    quick = build_quick_result(job, profile)
    language = detect_job_language(job)
    matched: list[dict[str, str]] = []
    missing: list[str] = []
    recommendations: list[str] = []
    for requirement in quick.requirements:
        matches = _matching_facts(profile, requirement, language=language)
        if matches:
            fact_id, fact_text, _ = matches[0]
            matched.append(
                {"requirement": requirement, "fact_id": fact_id, "evidence": fact_text}
            )
        else:
            missing.append(requirement)
            recommendations.append(
                "Si realmente cuentas con esta experiencia, descríbela en el CV con un "
                "ejemplo concreto y verificable. Si no cuentas con ella, no la añadas y "
                "trátala como un tema de aprendizaje: "
                f"{requirement}"
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
    )


def detect_job_language(job: JobRecord) -> str:
    tokens = _tokens(f"{job.title} {job.description}")
    return "es" if len(tokens & SPANISH_MARKERS) >= 2 else "en"


def build_interview_guide(
    *, interest: Interest, job: JobRecord, profile: Profile
) -> Artifact:
    spanish = interest.guide_language == "es"
    analysis = interest.analysis
    verified_facts = cloud_safe_verified_facts(
        profile, language=interest.guide_language
    )
    evidence_lines = [
        (
            f"- {item['requirement']} - Evidencia confirmada: {item['evidence']}"
            if spanish
            else f"- {item['requirement']} - Confirmed evidence: {item['evidence']}"
        )
        for item in analysis.matched_requirements
    ] or [
        "- No hay evidencia confirmada suficiente; prepara ejemplos reales antes de la entrevista."
        if spanish
        else "- There is not enough confirmed evidence; prepare real examples before the interview."
    ]
    gaps = [f"- {item}" for item in analysis.missing_requirements] or [
        "- No se detectaron brechas claras en la descripción disponible."
        if spanish
        else "- No clear gaps were detected in the available description."
    ]
    questions = [
        f"- ¿Cómo aplicarías tu experiencia a este requisito: {requirement}?"
        if spanish
        else f"- How would you apply your experience to this requirement: {requirement}?"
        for requirement in extract_requirements(job, limit=6)
    ]
    star = [
        (
            f"- Evidencia confirmada: {fact['text']}\n"
            "  Situación: ____  Tarea: ____  Acción: ____  Resultado verificable: ____"
            if spanish
            else f"- Confirmed evidence: {fact['text']}\n"
            "  Situation: ____  Task: ____  Action: ____  Verifiable result: ____"
        )
        for fact in verified_facts[:4]
    ]
    if not star:
        star = ["- Completa un ejemplo real antes de practicar." if spanish else "- Complete a real example before practicing."]

    link_label = (
        "Enlace de la empresa"
        if job.apply_url_type == "company"
        else "Enlace de la publicación"
    )
    link_label_en = "Company link" if job.apply_url_type == "company" else "Posting link"

    if spanish:
        content = f"""## Puesto
{job.title} - {job.company}
Ubicación: {job.location or 'No indicada'}
Publicación: {job.posted_at.isoformat() if job.posted_at else 'No indicada'}
{link_label}: {job.url}

## Resumen y enfoque
Nivel de encaje estimado: {analysis.level} ({analysis.score:.0f}/100).
Usa esta guía para practicar; adapta cada respuesta a hechos que puedas demostrar.

## Requisitos respaldados por tu CV
{chr(10).join(evidence_lines)}

## Brechas y temas para estudiar
{chr(10).join(gaps)}

## Preguntas probables
{chr(10).join(questions) if questions else '- Explica por qué te interesa el puesto y qué experiencia relevante aportarías.'}

## Preparación de respuestas STAR
{chr(10).join(star)}

## Preguntas para la empresa
- ¿Cómo se mide el éxito durante los primeros 90 días?
- ¿Cuáles son los retos más importantes del equipo actualmente?
- ¿Cómo es el proceso de incorporación y acompañamiento?

## Lista previa
- Repasar la descripción y el sitio oficial de la empresa.
- Preparar ejemplos verificables y resultados concretos.
- Confirmar modalidad, horario y elegibilidad desde Costa Rica.
- Probar cámara, audio y conexión si la entrevista es remota.
"""
        title = f"Guía de entrevista - {job.title} - {job.company}"
    else:
        content = f"""## Role
{job.title} - {job.company}
Location: {job.location or 'Not specified'}
Published: {job.posted_at.isoformat() if job.posted_at else 'Not specified'}
{link_label_en}: {job.url}

## Summary and focus
Estimated fit: {analysis.level} ({analysis.score:.0f}/100).
Use this guide for practice and keep every answer grounded in facts you can demonstrate.

## Requirements supported by your résumé
{chr(10).join(evidence_lines)}

## Gaps and study topics
{chr(10).join(gaps)}

## Likely questions
{chr(10).join(questions) if questions else '- Explain why this role interests you and what relevant experience you bring.'}

## STAR answer preparation
{chr(10).join(star)}

## Questions for the employer
- How will success be measured during the first 90 days?
- What are the team's most important current challenges?
- What does onboarding and mentoring look like?

## Before the interview
- Review the job description and the employer's official site.
- Prepare verifiable examples and concrete outcomes.
- Confirm work mode, schedule, and Costa Rica eligibility.
- Test your camera, audio, and connection for a remote interview.
"""
        title = f"Interview guide - {job.title} - {job.company}"
    return Artifact(
        run_id=interest.guide_run_id or interest.run_id,
        job_id=job.job_id,
        profile_id=profile.profile_id,
        kind="interview_guide",
        title=title,
        content=content,
        claims=[
            Claim(text=fact["text"], fact_ids=[fact["fact_id"]])
            for fact in verified_facts[:4]
        ],
    )


def _is_valid_official_url(job: JobRecord) -> bool:
    if not job.url:
        return False
    parsed = urlparse(str(job.url))
    return parsed.scheme == "https" and bool(parsed.hostname)


def _is_costa_rica_or_remote(job: JobRecord) -> bool:
    location = _fold(job.location)
    if any(marker in location for marker in ("costa rica", "san jose", "heredia", "alajuela", "cartago")):
        return True
    if job.remote is not True and not any(marker in location for marker in ("remote", "worldwide", "anywhere", "global", "latam", "latin america")):
        return False
    excluded = ("us only", "united states only", "canada only", "europe only", "emea only")
    return not any(marker in location for marker in excluded)


def filter_verified_recent_jobs(
    jobs: list[JobRecord], *, search_started_at: Any, window_days: int = 30
) -> tuple[list[JobRecord], dict[str, int]]:
    lower = search_started_at - timedelta(days=window_days)
    upper = search_started_at + timedelta(minutes=5)
    accepted: list[JobRecord] = []
    rejected = {
        "missing_date": 0,
        "outside_30d": 0,
        "invalid_url": 0,
        "outside_scope": 0,
    }
    # Validate before deduplication so an old copy cannot hide a fresh one.
    for job in jobs:
        if job.posted_at is None:
            rejected["missing_date"] += 1
            continue
        if not lower <= job.posted_at <= upper:
            rejected["outside_30d"] += 1
            continue
        if not _is_valid_official_url(job):
            rejected["invalid_url"] += 1
            continue
        if not _is_costa_rica_or_remote(job):
            rejected["outside_scope"] += 1
            continue
        job.date_confidence = "exact"
        job.official_url_verified = True
        accepted.append(job)
    return deduplicate_jobs(accepted), rejected


async def run_career_search(
    store: SQLiteStore,
    run_id: str,
    payload: CareerSearchCreate,
    *,
    connector_search: ConnectorSearch,
    ats_boards: list[str] | None = None,
    agent_registry: DeepSeekAgentRegistry | None = None,
    theirstack_client: TheirStackClient | None = None,
    max_results: int = 2_000,
) -> None:
    run = store.get_run(run_id)
    if run is None:
        return
    emitter = EventEmitter(store, run_id)
    try:
        profile = store.get_profile(payload.profile_id)
        if profile is None or not profile.confirmed or not any(fact.verified for fact in profile.facts):
            raise ValueError("A confirmed résumé profile is required before searching")
        run.status = RunStatus.RUNNING
        store.save_run_if_not_terminal(run)
        aliases = expand_role(payload.role)
        model_warnings: list[str] = []
        if agent_registry is not None:
            try:
                await asyncio.to_thread(
                    agent_registry.invoke,
                    AgentRole.COORDINATOR,
                    {
                        "role": payload.role,
                        "profile_confirmed": True,
                        "search_window_days": 30,
                        "task": "Confirm that the bounded career search may start.",
                    },
                )
                proposal = await asyncio.to_thread(
                    agent_registry.invoke,
                    AgentRole.SCOUT,
                    {
                        "role": payload.role,
                        "region": "Costa Rica or remote available from Costa Rica",
                        "deterministic_aliases": aliases,
                        "task": "Return a concise summary and bilingual equivalent job titles.",
                    },
                )
                if isinstance(proposal.structured, ScoutProposal):
                    aliases = expand_role(payload.role)
                    for alias in proposal.structured.aliases:
                        normalized = clean_text(alias)
                        if (
                            1 < len(normalized) <= 80
                            and normalized.casefold()
                            not in {item.casefold() for item in aliases}
                        ):
                            aliases.append(normalized)
                    aliases = aliases[:12]
            except Exception:  # noqa: BLE001 - deterministic search must remain available
                model_warnings.append("role_expansion_unavailable")
        emitter.emit(
            "run_started",
            stage="search",
            actor_kind="agent",
            actor_id=AgentRole.COORDINATOR,
            template_key="career.search.started",
            template_args={"role": payload.role},
        )
        emitter.emit(
            "agent_started",
            stage="search",
            actor_kind="agent",
            actor_id=AgentRole.SCOUT,
            template_key="career.search.scouting",
            template_args={"aliases": ", ".join(aliases)},
            progress=0.15,
        )
        jobs: list[JobRecord] = []
        errors: dict[str, str] = {}
        theirstack_page = None
        theirstack_available = False
        if theirstack_client is not None:
            try:
                theirstack_page = await theirstack_client.search_page(
                    role=payload.role,
                    aliases=aliases,
                    page=0,
                )
                jobs.extend(theirstack_page.jobs)
                theirstack_available = True
            except TheirStackError as exc:
                errors["theirstack"] = str(exc)
            except ValueError:
                errors["theirstack"] = "TheirStack devolvió datos que no se pudieron validar"

        requests: list[tuple[str, SearchRequest]] = []
        if not theirstack_available:
            requests.append(("public_remote_sources", SearchRequest(
                query=payload.role,
                aliases=aliases,
                location=None,
                remote_only=False,
                sources=[
                    SourceKind.HIMALAYAS,
                    SourceKind.WWR,
                    SourceKind.JOBICY,
                    SourceKind.REMOTIVE,
                    SourceKind.REMOTE_OK,
                ],
                limit=max_results,
            )))
        allowed_ats = {SourceKind.GREENHOUSE, SourceKind.LEVER, SourceKind.ASHBY}
        for specification in (ats_boards or []) if not theirstack_available else []:
            source_value, separator, identifier = specification.partition(":")
            if not separator or not identifier.strip():
                continue
            try:
                source = SourceKind(source_value.strip())
            except ValueError:
                continue
            if source not in allowed_ats:
                continue
            label = f"{source}:{identifier.strip()}"
            requests.append((label, SearchRequest(
                query=payload.role,
                aliases=aliases,
                sources=[source],
                source_identifiers={str(source): identifier.strip()},
                limit=max_results,
            )))
        batches = await asyncio.gather(
            *(connector_search(search_request) for _, search_request in requests),
            return_exceptions=True,
        ) if requests else []
        for (label, _), batch in zip(requests, batches, strict=True):
            if isinstance(batch, BaseException):
                errors[label] = "Source unavailable during this search"
                continue
            batch_jobs, batch_errors = batch
            jobs.extend(batch_jobs)
            errors.update({f"{label}:{source}": message for source, message in batch_errors.items()})
        portal_sources = {
            SourceKind.MANUAL,
            SourceKind.LINKEDIN,
            SourceKind.INDEED,
            SourceKind.GLASSDOOR,
            SourceKind.COMPUTRABAJO,
        }
        for stored_job in store.list_jobs(limit=max_results):
            haystack = f"{stored_job.title} {stored_job.description}".casefold()
            if stored_job.source in portal_sources and any(
                alias.casefold() in haystack for alias in aliases
            ):
                jobs.append(stored_job)
        emitter.emit(
            "agent_completed",
            stage="search",
            actor_kind="agent",
            actor_id=AgentRole.SCOUT,
            template_key="career.search.found",
            template_args={"jobs": len(jobs)},
            progress=1,
        )
        emitter.emit(
            "agent_started",
            stage="verification",
            actor_kind="agent",
            actor_id=AgentRole.REVIEWER,
            template_key="career.search.verifying",
            progress=0.55,
        )
        valid_jobs, rejected = filter_verified_recent_jobs(
            jobs, search_started_at=run.created_at, window_days=30
        )
        emitter.emit(
            "agent_completed",
            stage="verification",
            actor_kind="agent",
            actor_id=AgentRole.REVIEWER,
            template_key="career.search.verified",
            template_args={"jobs": len(valid_jobs)},
            progress=1,
        )
        valid_jobs = [store.save_job(job) for job in valid_jobs]
        emitter.emit(
            "agent_started",
            stage="analysis",
            actor_kind="agent",
            actor_id=AgentRole.FIT_ANALYST,
            template_key="career.search.comparing",
            template_args={"jobs": len(valid_jobs)},
            progress=0.72,
        )
        results = [build_quick_result(job, profile) for job in valid_jobs]
        results.sort(
            key=lambda item: (item.fit_summary.score, item.published_at), reverse=True
        )
        emitter.emit(
            "agent_completed",
            stage="analysis",
            actor_kind="agent",
            actor_id=AgentRole.FIT_ANALYST,
            template_key="career.search.compared",
            template_args={"jobs": len(results)},
            progress=1,
        )
        run.result = {
            "flow": "career_search",
            "role": payload.role,
            "aliases": aliases,
            "scope": "costa_rica_and_remote",
            "freshness_hours": 720,
            "window_started_at": (run.created_at - timedelta(days=30)).isoformat(),
            "window_ended_at": run.created_at.isoformat(),
            "career_results": [item.model_dump(mode="json") for item in results],
            "provider": "theirstack" if theirstack_available else "fallback",
            "total_available": (
                theirstack_page.total_available if theirstack_page is not None else len(results)
            ),
            "retrieved_count": len(results),
            "next_page": 1 if theirstack_page is not None and theirstack_page.can_load_more else None,
            "can_load_more": bool(theirstack_page and theirstack_page.can_load_more),
            "loaded_pages": [0] if theirstack_page is not None else [],
            "coverage": {
                "sources_requested": [
                    *(["theirstack"] if theirstack_client is not None else []),
                    *[label for label, _ in requests],
                ],
                "sources_failed": list(errors),
                "connector_errors": errors,
                "retrieved": len(jobs),
                "accepted": len(results),
                "rejected": rejected,
                "model_warnings": model_warnings,
            },
        }
        run.status = RunStatus.COMPLETED
        if store.save_run_if_not_terminal(run) is None:
            return
        emitter.emit(
            "run_completed",
            stage="completed",
            actor_kind="agent",
            actor_id=AgentRole.COORDINATOR,
            template_key="career.search.completed",
            template_args={"jobs": len(results)},
            severity="success",
            progress=1,
        )
    except Exception:  # noqa: BLE001 - the public event must never expose connector/model details
        current = store.get_run(run_id)
        if current is None or current.status == RunStatus.CANCELLED:
            return
        current.status = RunStatus.FAILED
        current.error = PUBLIC_RUN_FAILURE
        store.save_run_if_not_terminal(current)
        emitter.emit(
            "run_failed",
            stage="failed",
            actor_id=AgentRole.COORDINATOR,
            actor_kind="agent",
            template_key="career.search.failed",
            severity="error",
        )


__all__ = [
    "build_deep_analysis",
    "build_interview_guide",
    "build_quick_result",
    "detect_job_language",
    "expand_role",
    "filter_verified_recent_jobs",
    "run_career_search",
]

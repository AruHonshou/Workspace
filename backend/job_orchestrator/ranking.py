from __future__ import annotations

import hashlib
import html
import re
from collections.abc import Iterable
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import Any

from .schemas import (
    CriterionResult,
    JobRecord,
    ManualJobCreate,
    MatchStatus,
    Profile,
    RankedJob,
    RankingBreakdown,
    SourceKind,
)

TAG_RE = re.compile(r"<[^>]+>")
SPACE_RE = re.compile(r"\s+")
TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9+#.-]{1,}", re.IGNORECASE)


def clean_text(value: str | None) -> str:
    if not value:
        return ""
    return SPACE_RE.sub(" ", html.unescape(TAG_RE.sub(" ", value))).strip()


def content_hash(title: str, company: str, description: str) -> str:
    canonical = "|".join(clean_text(part).casefold() for part in (title, company, description))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def normalize_manual_job(data: ManualJobCreate) -> JobRecord:
    description = clean_text(data.description)
    digest = content_hash(data.title, data.company, description)
    return JobRecord(
        source=data.source,
        sources=[data.source],
        external_id=digest[:20],
        title=clean_text(data.title),
        company=clean_text(data.company),
        location=clean_text(data.location),
        remote=data.remote,
        salary_min=data.salary_min,
        salary_max=data.salary_max,
        salary_currency=data.salary_currency,
        description=description,
        url=data.url,
        posted_at=data.posted_at,
        date_confidence="exact" if data.posted_at else "unknown",
        verification_level=(
            "manual_portal"
            if data.source in {
                SourceKind.LINKEDIN,
                SourceKind.INDEED,
                SourceKind.GLASSDOOR,
                SourceKind.COMPUTRABAJO,
            }
            else "official"
        ),
        official_url_verified=bool(data.url),
        content_hash=digest,
        raw=data.model_dump(mode="json"),
    )


def normalize_job(
    *,
    source: SourceKind,
    external_id: str,
    title: str,
    company: str,
    description: str,
    location: str = "",
    remote: bool | None = None,
    url: str | None = None,
    posted_at: datetime | str | None = None,
    raw: dict[str, Any] | None = None,
) -> JobRecord:
    cleaned = clean_text(description)
    if isinstance(posted_at, str):
        try:
            posted_at = datetime.fromisoformat(posted_at)
        except ValueError:
            try:
                posted_at = parsedate_to_datetime(posted_at)
            except (TypeError, ValueError):
                posted_at = None
    if posted_at and posted_at.tzinfo is None:
        posted_at = posted_at.replace(tzinfo=UTC)
    return JobRecord(
        source=source,
        sources=[source],
        external_id=str(external_id),
        title=clean_text(title) or "Untitled role",
        company=clean_text(company) or "Unknown company",
        description=cleaned,
        location=clean_text(location),
        remote=remote,
        url=url,
        posted_at=posted_at,
        date_confidence="exact" if posted_at else "unknown",
        verification_level=(
            "authorized_feed"
            if source in {
                SourceKind.JOBICY,
                SourceKind.REMOTIVE,
                SourceKind.REMOTE_OK,
                SourceKind.HIMALAYAS,
                SourceKind.WWR,
            }
            else "official"
        ),
        official_url_verified=bool(url),
        content_hash=content_hash(title, company, cleaned),
        raw=raw or {},
    )


def deduplicate_jobs(jobs: Iterable[JobRecord]) -> list[JobRecord]:
    priority = {"official": 3, "authorized_feed": 2, "manual_portal": 1}
    result: list[JobRecord] = []
    by_hash: dict[str, int] = {}
    by_id: dict[tuple[str, str], int] = {}
    for job in jobs:
        source_id = (str(job.source), job.external_id)
        existing_index = by_hash.get(job.content_hash, by_id.get(source_id))
        if existing_index is not None:
            existing = result[existing_index]
            merged_sources = list(
                dict.fromkeys([*existing.sources, existing.source, *job.sources, job.source])
            )
            preferred = (
                job
                if priority.get(job.verification_level, 0)
                > priority.get(existing.verification_level, 0)
                else existing
            )
            result[existing_index] = preferred.model_copy(
                update={"sources": merged_sources}
            )
            continue
        job.sources = list(dict.fromkeys([*job.sources, job.source]))
        by_hash[job.content_hash] = len(result)
        by_id[source_id] = len(result)
        result.append(job)
    return result


def _tokens(value: str) -> set[str]:
    return {token.casefold() for token in TOKEN_RE.findall(value)}


def rank_job(job: JobRecord, profile: Profile) -> RankedJob:
    preferences = profile.preferences
    job_text = f"{job.title} {job.description} {job.location}".casefold()
    verified_facts = [fact for fact in profile.facts if fact.verified]
    verified_text = " ".join(fact.text for fact in verified_facts)
    profile_tokens = _tokens(verified_text)

    desired = [*preferences.keywords, *preferences.desired_titles]
    matches = [item for item in desired if item.casefold() in job_text]
    excluded = [item for item in preferences.excluded_keywords if item.casefold() in job_text]
    requirement_tokens = _tokens(job.description)
    overlap = profile_tokens & requirement_tokens

    raw_requirements = min(50.0, 10.0 + len(overlap) * 2.0 + len(matches) * 5.0)
    raw_experience = min(20.0, len(verified_facts) * 2.0)

    criteria: list[CriterionResult] = []
    eligible: bool | None = True
    logistics = 7.5
    if preferences.remote_required:
        if job.remote is True or "remote" in job.location.casefold():
            logistics = 15.0
            criteria.append(CriterionResult(name="remote", status=MatchStatus.MATCH))
        elif job.remote is False:
            logistics = 0.0
            eligible = False
            criteria.append(CriterionResult(name="remote", status=MatchStatus.GAP))
        else:
            eligible = None
            criteria.append(CriterionResult(name="remote", status=MatchStatus.UNKNOWN))
    elif preferences.desired_locations:
        if not job.location.strip():
            eligible = None
            criteria.append(CriterionResult(name="location", status=MatchStatus.UNKNOWN))
        elif any(
            location.casefold() in job.location.casefold()
            for location in preferences.desired_locations
        ):
            logistics = 15.0
            criteria.append(CriterionResult(name="location", status=MatchStatus.MATCH))
        elif any(
            marker in job.location.casefold()
            for marker in ("anywhere", "global", "remote", "worldwide")
        ):
            eligible = None
            criteria.append(CriterionResult(name="location", status=MatchStatus.UNKNOWN))
        else:
            logistics = 0.0
            eligible = False
            criteria.append(CriterionResult(name="location", status=MatchStatus.GAP))

    if preferences.minimum_salary is not None:
        if job.salary_max is None:
            if eligible is True:
                eligible = None
            criteria.append(CriterionResult(name="salary_floor", status=MatchStatus.UNKNOWN))
        elif (
            preferences.currency
            and job.salary_currency
            and preferences.currency.casefold() != job.salary_currency.casefold()
        ):
            if eligible is True:
                eligible = None
            criteria.append(
                CriterionResult(
                    name="salary_floor",
                    status=MatchStatus.UNKNOWN,
                    evidence="Currency conversion was not inferred.",
                )
            )
        elif job.salary_max < preferences.minimum_salary:
            eligible = False
            logistics = 0.0
            criteria.append(CriterionResult(name="salary_floor", status=MatchStatus.GAP))
        else:
            criteria.append(CriterionResult(name="salary_floor", status=MatchStatus.MATCH))

    if preferences.work_authorization:
        if eligible is True:
            eligible = None
        criteria.append(
            CriterionResult(
                name="work_authorization",
                status=MatchStatus.UNKNOWN,
                evidence="The vacancy source did not provide a normalized authorization field.",
            )
        )

    raw_preference_score = min(15.0, len(matches) * 3.0)
    if excluded:
        raw_preference_score = 0.0
        eligible = False
        criteria.append(
            CriterionResult(
                name="excluded_keywords",
                status=MatchStatus.GAP,
                evidence=", ".join(excluded),
            )
        )

    confidence = min(1.0, 0.20 + 0.08 * len(verified_facts) + 0.03 * len(desired))
    weights = preferences.ranking_weights
    breakdown = RankingBreakdown(
        requirements=round((raw_requirements / 50) * weights.requirements, 2),
        experience=round((raw_experience / 20) * weights.experience, 2),
        logistics=round((logistics / 15) * weights.logistics, 2),
        preferences=round((raw_preference_score / 15) * weights.preferences, 2),
        confidence=confidence,
    )
    reasons = [f"Matched keyword: {item}" for item in matches]
    if overlap:
        reasons.append(f"{len(overlap)} evidence tokens overlap with the posting")
    gaps = [f"Excluded keyword present: {item}" for item in excluded]
    return RankedJob(
        job=job,
        score=breakdown.total,
        eligible=eligible,
        breakdown=breakdown,
        criteria=criteria,
        reasons=reasons,
        gaps=gaps,
    )


def rank_jobs(jobs: Iterable[JobRecord], profile: Profile) -> list[RankedJob]:
    ranked = [rank_job(job, profile) for job in jobs]
    return sorted(
        ranked,
        key=lambda item: (item.eligible is not False, item.score, item.breakdown.confidence),
        reverse=True,
    )

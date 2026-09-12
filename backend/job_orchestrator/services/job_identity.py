from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import dataclass
from difflib import SequenceMatcher
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from ..schemas import ApplyUrlType, JobRecord, JobSourceEvidence

TRACKING_KEYS = {"fbclid", "gclid", "ref", "referrer", "source", "trk"}
TITLE_EQUIVALENTS = {
    "qa": ("quality", "assurance"),
    "sdet": ("software", "development", "engineer", "test"),
    "dev": ("developer",),
    "eng": ("engineer",),
    "sr": ("senior",),
    "jr": ("junior",),
}
COMPANY_SUFFIXES = {
    "inc",
    "incorporated",
    "llc",
    "ltd",
    "limited",
    "corp",
    "corporation",
    "company",
    "co",
    "sa",
    "srl",
}


def canonicalize_url(value: object) -> str | None:
    """Return a stable HTTPS URL without fragments or tracking parameters."""
    if not value:
        return None
    try:
        parsed = urlsplit(str(value))
        if parsed.scheme.casefold() not in {"http", "https"} or not parsed.hostname:
            return None
        query = urlencode(
            [
                (key, item)
                for key, item in parse_qsl(parsed.query, keep_blank_values=True)
                if not key.casefold().startswith("utm_")
                and key.casefold() not in TRACKING_KEYS
            ]
        )
        path = re.sub(r"/{2,}", "/", parsed.path or "/")
        if path != "/":
            path = path.rstrip("/")
        port = f":{parsed.port}" if parsed.port else ""
        return urlunsplit(
            ("https", f"{parsed.hostname.casefold()}{port}", path, query, "")
        )
    except ValueError:
        return None


def _words(value: str) -> str:
    folded = unicodedata.normalize("NFKD", value)
    ascii_text = "".join(char for char in folded if not unicodedata.combining(char))
    return " ".join(re.findall(r"[a-z0-9]+", ascii_text.casefold()))


def _canonical_title(value: str) -> str:
    tokens: list[str] = []
    for token in _words(value).split():
        tokens.extend(TITLE_EQUIVALENTS.get(token, (token,)))
    return " ".join(tokens)


def _canonical_company(value: str) -> str:
    tokens = _words(value).split()
    while tokens and tokens[-1] in COMPANY_SUFFIXES:
        tokens.pop()
    return " ".join(tokens)


def _description_similarity(left: str, right: str) -> float:
    """Compare substantial descriptions after removing markup and punctuation noise."""

    left_words = _words(left)
    right_words = _words(right)
    if min(len(left_words), len(right_words)) < 120:
        return 0.0
    left_tokens = set(left_words.split())
    right_tokens = set(right_words.split())
    token_union = left_tokens | right_tokens
    jaccard = len(left_tokens & right_tokens) / len(token_union) if token_union else 0.0
    sequence = SequenceMatcher(None, left_words, right_words).ratio()
    return max(jaccard, sequence)


def _probably_same_vacancy(left: JobRecord, right: JobRecord) -> bool:
    """Conservatively join cross-portal copies that differ only in presentation."""

    if _canonical_company(left.company) != _canonical_company(right.company):
        return False
    if _canonical_title(left.title) != _canonical_title(right.title):
        return False
    if left.country_code and right.country_code and left.country_code != right.country_code:
        return False
    left_location = _words(left.location)
    right_location = _words(right.location)
    left_location_tokens = set(left_location.split())
    right_location_tokens = set(right_location.split())
    location_union = left_location_tokens | right_location_tokens
    location_overlap = (
        len(left_location_tokens & right_location_tokens) / len(location_union)
        if location_union
        else 0.0
    )
    same_or_missing_location = bool(
        left_location == right_location
        or not left_location
        or not right_location
        or location_overlap >= 0.4
    )
    similarity = _description_similarity(left.description, right.description)
    if same_or_missing_location and similarity >= 0.76:
        return True
    # Different portal location labels may name a city, province, or country for
    # the same posting. Require near-identical substantial descriptions in that case.
    return similarity >= 0.93


def identity_keys(job: JobRecord) -> list[str]:
    """Return link and conservative vacancy identities for transitive matching."""
    urls = [
        canonicalize_url(job.final_url),
        canonicalize_url(job.url),
        canonicalize_url(job.source_url),
    ]
    keys = [f"url|{url}" for url in urls if url]
    title = _canonical_title(job.title)
    company = _canonical_company(job.company)
    location = _words(job.location)
    country = (job.country_code or "").upper()
    if title and company:
        keys.append(f"identity|{company}|{title}|{country}|{location}")
    keys.append(f"provider|{job.provider or job.source}|{job.external_id}")
    return list(dict.fromkeys(keys))


def _evidence(job: JobRecord) -> list[JobSourceEvidence]:
    items = [
        *job.source_evidence,
        JobSourceEvidence(
            provider=job.provider or str(job.source),
            source_portal=job.source_portal,
            source_url=job.source_url or job.url,
            final_url=job.final_url,
            apply_url_type=job.apply_url_type,
            external_id=job.external_id,
        ),
    ]
    unique: dict[str, JobSourceEvidence] = {}
    for item in items:
        key = "|".join(
            str(value or "")
            for value in (
                item.provider,
                item.source_portal,
                canonicalize_url(item.source_url),
                canonicalize_url(item.final_url),
                item.external_id,
            )
        )
        unique[key] = item
    return list(unique.values())


def _priority(job: JobRecord) -> tuple[int, int, int]:
    link = {
        ApplyUrlType.OFFICIAL: 3,
        ApplyUrlType.ATS: 2,
        ApplyUrlType.PORTAL: 1,
    }.get(job.apply_url_type, 0)
    verified = {"official": 3, "authorized_feed": 2, "manual_portal": 1}.get(
        str(job.verification_level), 0
    )
    return link, verified, len(job.description)


@dataclass(frozen=True)
class CanonicalJob:
    job: JobRecord
    identity: str


def merge_jobs(jobs: list[JobRecord]) -> list[CanonicalJob]:
    """Merge duplicates while retaining all observed portals and links."""
    groups: list[list[JobRecord]] = []
    group_keys: list[set[str]] = []
    for job in jobs:
        keys = set(identity_keys(job))
        matches = [
            index
            for index, known in enumerate(group_keys)
            if known & keys
            or any(_probably_same_vacancy(job, candidate) for candidate in groups[index])
        ]
        if not matches:
            groups.append([job])
            group_keys.append(keys)
            continue
        target = matches[0]
        groups[target].append(job)
        group_keys[target].update(keys)
        for index in reversed(matches[1:]):
            groups[target].extend(groups.pop(index))
            group_keys[target].update(group_keys.pop(index))

    merged: list[CanonicalJob] = []
    for group in groups:
        preferred = max(group, key=_priority)
        official_urls = [
            canonicalize_url(candidate.final_url or candidate.url)
            for candidate in group
            if candidate.apply_url_type != ApplyUrlType.PORTAL
        ]
        preferred_keys = identity_keys(preferred)
        key = next(
            (item for item in preferred_keys if item.startswith("identity|")),
            next((url for url in official_urls if url), preferred_keys[0]),
        )
        evidence = [item for candidate in group for item in _evidence(candidate)]
        unique: dict[str, JobSourceEvidence] = {}
        for item in evidence:
            evidence_key = "|".join(
                str(value or "")
                for value in (
                    item.provider,
                    item.source_portal,
                    canonicalize_url(item.source_url),
                    canonicalize_url(item.final_url),
                    item.external_id,
                )
            )
            unique[evidence_key] = item
        sources = list(
            dict.fromkeys(
                source
                for candidate in group
                for source in [*candidate.sources, candidate.source]
            )
        )
        stable_id = f"job_{hashlib.sha256(key.encode()).hexdigest()[:24]}"
        raw = dict(preferred.raw)
        raw["source_evidence"] = [
            item.model_dump(mode="json") for item in unique.values()
        ]
        raw["canonical_identity"] = key
        merged_job = preferred.model_copy(
            update={
                "job_id": stable_id,
                "sources": sources,
                "source_evidence": list(unique.values()),
                "raw": raw,
            }
        )
        merged.append(CanonicalJob(job=merged_job, identity=key))
    return merged

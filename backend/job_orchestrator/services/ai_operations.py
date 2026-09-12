from __future__ import annotations

"""Explicit AI operations with deterministic validation and no graph framework."""

import re
from collections.abc import Callable, Mapping
from typing import Any

from ..ai_contracts import (
    AIOperation,
    ATSResumeProposal,
    LinkedInOptimizationProposal,
    StructuredAIClient,
)
from ..ats_documents import ats_adaptation_issues, build_ats_document
from ..career import (
    build_deep_analysis_v2,
    cloud_safe_verified_facts,
    detect_job_language,
    extract_requirements,
)
from ..linkedin import SECTION_KEYS, redact_contact_text
from ..schemas import (
    DeepFitAnalysisV2,
    JobRecord,
    LinkedInOptimizationSection,
    LinkedInProfileSnapshot,
    Profile,
)


class SequentialOperation:
    """Small synchronous operation wrapper used by the service functions."""

    def __init__(self, operation: Callable[[dict[str, Any]], dict[str, Any]]):
        self._operation = operation

    def invoke(
        self,
        state: Mapping[str, Any],
        _config: Mapping[str, Any] | None = None,
        **_options: Any,
    ) -> dict[str, Any]:
        return self._operation(dict(state))


_REFERENCE_BLOCK_RE = re.compile(
    r"\s*\[\s*(?:fact|record)[ _-]?id\s*[:=]\s*[^\]\n]+\]\s*", re.IGNORECASE
)
_REFERENCE_TOKEN_RE = re.compile(
    r"\b(?:fact|record)[ _-]?id\s*[:=]\s*[A-Za-z0-9_-]+", re.IGNORECASE
)
_INTERNAL_ID_RE = re.compile(r"\b(?:fact|record)_[A-Za-z0-9]+\b", re.IGNORECASE)
_REDACTED_CONTACT_RE = re.compile(r"\[redacted-(?:email|phone)\]", re.IGNORECASE)


def _strip_internal_markers(value: str) -> str:
    cleaned = _REFERENCE_BLOCK_RE.sub(" ", value)
    cleaned = _REFERENCE_TOKEN_RE.sub("", cleaned)
    cleaned = _INTERNAL_ID_RE.sub("", cleaned)
    return " ".join(cleaned.split())


def _safe_visible_text(value: str) -> str:
    """Remove internal evidence identifiers from user-visible model prose."""

    return _strip_internal_markers(value).strip()


def _profile_context(
    profile: Profile, snapshot: LinkedInProfileSnapshot
) -> dict[str, Any]:
    preferences = profile.preferences.model_dump(mode="json")
    keys = (
        "desired_titles",
        "keywords",
        "desired_locations",
        "target_seniorities",
        "allowed_work_modes",
        "excluded_keywords",
        "excluded_sectors",
        "remote_required",
    )
    objectives = {
        key: preferences.get(key)
        for key in keys
        if preferences.get(key) not in (None, [], "")
    }
    roles = list(
        dict.fromkeys([*snapshot.target_roles, *profile.preferences.desired_titles])
    )
    summary = _REDACTED_CONTACT_RE.sub("", redact_contact_text(profile.summary)).strip()
    return {
        "output_language": snapshot.language,
        "target_roles": roles,
        "objectives": objectives,
        "professional_summary": summary,
    }


def _resume_export(profile: Profile, language: str) -> str:
    normalized = language.casefold()
    base = normalized.split("-", 1)[0]
    matches = [
        variant
        for key, variant in profile.resumes.items()
        if key.casefold() == normalized or key.casefold().split("-", 1)[0] == base
    ]
    source = matches[0].text if matches else profile.resume_text
    return _REDACTED_CONTACT_RE.sub("", redact_contact_text(source)).strip()


def _professional_record_export(
    profile: Profile, facts: list[dict[str, str]]
) -> dict[str, list[dict[str, Any]]]:
    """Export only records derived from the exact evidence offered in this call."""

    offered = {f"record_{item['fact_id']}" for item in facts}
    output: dict[str, list[dict[str, Any]]] = {}
    for field_name in (
        "employment",
        "projects",
        "skills",
        "achievements",
        "education",
        "certifications",
        "languages",
    ):
        output[field_name] = [
            record.model_dump(mode="json")
            for record in getattr(profile.professional_records, field_name)
            if record.record_id in offered
        ]
    return output


def build_fit_analysis_operation(
    ai_client: StructuredAIClient | None = None,
) -> SequentialOperation:
    def operation(state: dict[str, Any]) -> dict[str, Any]:
        job = JobRecord.model_validate(state["job"])
        profile = Profile.model_validate(state["profile"])
        analysis = build_deep_analysis_v2(job, profile)
        output_language = str(state.get("output_language") or "es")
        if output_language not in {"es", "en"}:
            output_language = "es"
        analysis.analysis_language = output_language
        reviewed = False
        if ai_client is not None:
            facts = cloud_safe_verified_facts(
                profile,
                limit=max(1, len(profile.facts)),
                language=detect_job_language(job),
                include_all=True,
            )
            try:
                response = ai_client.invoke(
                    AIOperation.FIT_ANALYSIS,
                    {
                        "verified_profile_facts": facts,
                        "jobs": [
                            {
                                "job_id": job.job_id,
                                "title": job.title,
                                "requirements": [
                                    {"index": index, "text": value}
                                    for index, value in enumerate(
                                        extract_requirements(job, limit=200)
                                    )
                                ],
                            }
                        ],
                        "output_language": output_language,
                        "task": (
                            "Audit every requirement, explain supported evidence and gaps, "
                            "and propose concise CV presentation actions in output_language. "
                            "Do not repeat integrity warnings in each action."
                        ),
                    },
                )
                offered = {item["fact_id"] for item in facts}
                proposal = response.structured
                mappings = getattr(proposal, "mappings", [])
                valid_mappings = all(
                    mapping.job_id == job.job_id
                    and set(mapping.fact_ids).issubset(offered)
                    for mapping in mappings
                )
                reviewed = valid_mappings and bool(
                    mappings
                    or getattr(proposal, "executive_summary", None)
                    or getattr(proposal, "requirement_notes", [])
                    or getattr(proposal, "cv_actions", [])
                )
                if state.get("require_model") and not reviewed:
                    raise RuntimeError(
                        "DeepSeek returned an unsafe fit-analysis mapping"
                    )
                requirements = extract_requirements(job, limit=200)
                notes = getattr(proposal, "requirement_notes", [])
                actions = getattr(proposal, "cv_actions", [])
                if any(
                    note.requirement_index >= len(requirements)
                    or not set(note.fact_ids).issubset(offered)
                    for note in notes
                ) or any(
                    not set(action.fact_ids).issubset(offered) for action in actions
                ):
                    raise RuntimeError("DeepSeek returned an unsafe analysis narrative")
                for note in notes:
                    target = analysis.requirement_analysis[note.requirement_index]
                    explanation = _safe_visible_text(note.explanation)
                    cited_deterministic_evidence = bool(note.fact_ids) and set(
                        note.fact_ids
                    ).issubset(set(target.fact_ids))
                    gap_explanation = not note.fact_ids and any(
                        marker in explanation.casefold()
                        for marker in (
                            "brecha",
                            "falta",
                            "no se encontr",
                            "no demuestra",
                            "gap",
                            "missing",
                            "not found",
                            "does not demonstrate",
                            "no evidence",
                        )
                    )
                    # Model prose may clarify a deterministic link, but it cannot attach
                    # a merely offered fact to an unrelated requirement. Unsupported
                    # citations are ignored instead of failing the whole analysis.
                    if explanation and (
                        cited_deterministic_evidence
                        or (target.status == "gap" and gap_explanation)
                    ):
                        target.explanation = explanation
                safe_actions = [_safe_visible_text(action.text) for action in actions]
                safe_actions = [
                    value
                    for value in safe_actions
                    if value
                    and not any(
                        marker in value.casefold()
                        for marker in (
                            "do not invent",
                            "don't invent",
                            "never invent",
                            "no inventes",
                            "sin inventar",
                        )
                    )
                ]
                if safe_actions:
                    analysis.cv_actions = list(dict.fromkeys(safe_actions))[:12]
            except RuntimeError:
                if state.get("require_model"):
                    raise
        elif state.get("require_model"):
            raise RuntimeError("DeepSeek is required for deep fit analysis")
        return {
            **state,
            "analysis": analysis.model_dump(mode="json"),
            "model_reviewed": reviewed,
            "stage": "reviewed" if reviewed else "evidence_mapped",
        }

    return SequentialOperation(operation)


def run_fit_analysis(
    job: JobRecord,
    profile: Profile,
    ai_client: StructuredAIClient | None,
    *,
    require_model: bool = False,
    output_language: str = "es",
) -> DeepFitAnalysisV2:
    state = build_fit_analysis_operation(ai_client).invoke(
        {
            "job": job.model_dump(mode="json"),
            "profile": profile.model_dump(mode="json"),
            "require_model": require_model,
            "output_language": output_language,
        }
    )
    return DeepFitAnalysisV2.model_validate(state["analysis"])


def build_ats_resume_operation(ai_client: StructuredAIClient) -> SequentialOperation:
    def operation(state: dict[str, Any]) -> dict[str, Any]:
        job = JobRecord.model_validate(state["job"])
        profile = Profile.model_validate(state["profile"])
        facts = cloud_safe_verified_facts(
            profile,
            limit=max(1, len(profile.facts)),
            language=detect_job_language(job),
            include_all=True,
        )
        analysis = build_deep_analysis_v2(job, profile)
        payload = {
            "job": {
                "job_id": job.job_id,
                "title": job.title,
                "company": job.company,
                "description": job.description,
                "requirements": extract_requirements(job, limit=200),
            },
            "targeting_context": {
                "supported_requirements": [
                    item.model_dump(mode="json")
                    for item in analysis.requirement_analysis
                    if item.status == "supported"
                ],
                "unsupported_or_uncertain_requirements": [
                    item.model_dump(mode="json")
                    for item in analysis.requirement_analysis
                    if item.status != "supported"
                ],
                "supported_keywords": analysis.supported_keywords,
                "instruction": (
                    "Use supported requirements to prioritize and rewrite evidence. "
                    "Never place unsupported or uncertain requirements in personal claims."
                ),
            },
            "confirmed_records": facts,
            "redacted_source_resume": _resume_export(
                profile, detect_job_language(job)
            ),
            "source_structure": _professional_record_export(profile, facts),
            "language": detect_job_language(job),
            "document_goal": (
                "Create a complete new ATS résumé for this exact vacancy. Preserve the "
                "candidate's chronology and every factual boundary, but choose a sharper "
                "headline, vacancy-specific summary, ordered skills, and rewritten bullets. "
                "Do not return advice or a comparison: return the finished résumé content."
            ),
        }
        response = ai_client.invoke(AIOperation.ATS_RESUME, payload)
        proposal = (
            response.structured
            if isinstance(response.structured, ATSResumeProposal)
            else None
        )
        if proposal is None:
            raise RuntimeError("DeepSeek did not return a structured ATS résumé")
        if proposal.language.split("-", 1)[0] != detect_job_language(job).split("-", 1)[0]:
            raise RuntimeError("DeepSeek returned the ATS résumé in the wrong language")
        document, issues = build_ats_document(profile, job, proposal)
        quality_issues = ats_adaptation_issues(document, job)
        if quality_issues:
            revision_response = ai_client.invoke(
                AIOperation.ATS_RESUME,
                {
                    **payload,
                    "previous_proposal": (
                        proposal.model_dump(mode="json")
                        if proposal is not None
                        else None
                    ),
                    "required_revision": {
                        "problems": quality_issues,
                        "instruction": (
                            "Return a substantially more targeted proposal now. Reorder "
                            "relevant evidence and rewrite it around the vacancy's supported "
                            "responsibilities and keywords while preserving every fact."
                        ),
                    },
                },
            )
            revision = (
                revision_response.structured
                if isinstance(revision_response.structured, ATSResumeProposal)
                else None
            )
            revised_document, revised_issues = build_ats_document(
                profile, job, revision
            )
            if len(ats_adaptation_issues(revised_document, job)) < len(quality_issues):
                document, issues = revised_document, revised_issues
        remaining_quality_issues = ats_adaptation_issues(document, job)
        if remaining_quality_issues:
            raise RuntimeError("DeepSeek did not produce a sufficiently tailored ATS résumé")
        if not document.experience and not document.projects:
            issues.append(
                "The ATS résumé has no confirmed experience or project evidence."
            )
        return {
            **state,
            "facts": facts,
            "document": document.model_dump(mode="json"),
            "review_issues": list(dict.fromkeys(issues)),
            "stage": "awaiting_approval",
        }

    return SequentialOperation(operation)


def build_linkedin_optimization_operation(
    ai_client: StructuredAIClient,
) -> SequentialOperation:
    def operation(state: dict[str, Any]) -> dict[str, Any]:
        snapshot = LinkedInProfileSnapshot.model_validate(state["snapshot"])
        profile = Profile.model_validate(state["profile"])
        facts = cloud_safe_verified_facts(
            profile,
            limit=max(1, len(profile.facts)),
            language=snapshot.language,
            include_all=True,
        )
        current = snapshot.sections.model_dump(mode="json")
        source_text = snapshot.source_text or "\n\n".join(
            f"{key.upper()}\n{current.get(key, '')}"
            for key in SECTION_KEYS
            if current.get(key)
        )
        response = ai_client.invoke(
            AIOperation.LINKEDIN_OPTIMIZATION,
            {
                "current_sections": current,
                "linkedin_export_text": source_text,
                "resume_export_text": _resume_export(profile, snapshot.language),
                "target_roles": snapshot.target_roles,
                "profile_context": _profile_context(profile, snapshot),
                "confirmed_records": facts,
                "language": snapshot.language,
            },
        )
        proposal = (
            response.structured
            if isinstance(response.structured, LinkedInOptimizationProposal)
            else None
        )
        if proposal is None:
            raise RuntimeError("DeepSeek did not return a structured LinkedIn profile")
        offered = {item["fact_id"] for item in facts}
        evidence_by_id = {item["fact_id"]: item["text"] for item in facts}
        by_key: dict[str, LinkedInOptimizationSection] = {}
        issues: list[str] = []
        for item in proposal.sections:
            if item.section in by_key or not set(item.record_ids).issubset(offered):
                issues.append(f"Unsafe or repeated proposal for {item.section}.")
                continue
            proposed = _strip_internal_markers(item.proposed_text)
            rationale = _strip_internal_markers(item.rationale)
            current_text = str(current.get(item.section, ""))
            by_key[item.section] = LinkedInOptimizationSection(
                section=item.section,
                current_text=current_text,
                proposed_text=proposed or current_text,
                rationale=rationale or "Uses only confirmed profile evidence.",
                keywords=[
                    value
                    for value in item.keywords
                    if not _REFERENCE_TOKEN_RE.search(value)
                    and not _INTERNAL_ID_RE.search(value)
                ],
                record_ids=item.record_ids,
                evidence=[
                    evidence_by_id[value]
                    for value in item.record_ids
                    if value in evidence_by_id
                ],
            )
        sections: list[LinkedInOptimizationSection] = []
        for key in SECTION_KEYS:
            if key in by_key:
                sections.append(by_key[key])
            else:
                raise RuntimeError(
                    f"DeepSeek did not produce a safe {key} LinkedIn section"
                )
        return {
            **state,
            "sections": [item.model_dump(mode="json") for item in sections],
            "review_issues": list(dict.fromkeys(issues)),
            "stage": "completed",
        }

    return SequentialOperation(operation)


__all__ = [
    "SequentialOperation",
    "build_ats_resume_operation",
    "build_fit_analysis_operation",
    "build_linkedin_optimization_operation",
    "run_fit_analysis",
]

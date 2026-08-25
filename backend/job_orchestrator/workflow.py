from __future__ import annotations

import re
from collections.abc import Callable
from typing import TYPE_CHECKING, Any, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from .agents import (
    CoordinatorProposal,
    FitAnalystProposal,
    ReviewerProposal,
    ScoutProposal,
    TailorProposal,
    parse_role_output,
)
from .ranking import normalize_job, rank_jobs
from .schemas import (
    AgentRole,
    ApprovalKind,
    Artifact,
    Claim,
    JobRecord,
    Profile,
    RankedJob,
    ReviewIssue,
    ReviewReport,
    SourceKind,
)

if TYPE_CHECKING:
    from .agents import DeepSeekAgentRegistry


class WorkflowState(TypedDict, total=False):
    run_id: str
    mode: str
    query: str
    auto_approve: bool
    profile: dict[str, Any]
    jobs: list[dict[str, Any]]
    ranked_jobs: list[dict[str, Any]]
    selected_job_ids: list[str]
    artifacts: list[dict[str, Any]]
    review: dict[str, Any]
    approvals: list[dict[str, Any]]
    active_role: str
    stage: str
    revision_count: int
    use_model: bool
    agent_summaries: dict[str, str]
    agent_models: dict[str, str]


def _approval(state: WorkflowState, kind: ApprovalKind, payload: dict[str, Any]) -> dict[str, Any]:
    if state.get("auto_approve", False):
        decision: dict[str, Any] = {"decision": "approved", "automatic": True}
    else:
        decision = interrupt({"kind": str(kind), "payload": payload})
    return {
        "approvals": [*state.get("approvals", []), {"kind": str(kind), **decision}],
    }


def coordinator(state: WorkflowState) -> dict[str, Any]:
    return {"active_role": AgentRole.COORDINATOR, "stage": "profile"}


def profile_gate(state: WorkflowState) -> dict[str, Any]:
    profile = Profile.model_validate(state["profile"])
    result = _approval(
        state,
        ApprovalKind.PROFILE_CONFIRMATION,
        {"profile_id": profile.profile_id, "version": profile.version},
    )
    profile.confirmed = True
    return {**result, "profile": profile.model_dump(mode="json"), "stage": "search"}


def scout(state: WorkflowState) -> dict[str, Any]:
    jobs = state.get("jobs") or [job.model_dump(mode="json") for job in synthetic_jobs()]
    return {"active_role": AgentRole.SCOUT, "jobs": jobs, "stage": "search"}


def fit_analyst(state: WorkflowState) -> dict[str, Any]:
    profile = Profile.model_validate(state["profile"])
    jobs = [JobRecord.model_validate(job) for job in state.get("jobs", [])]
    ranked = rank_jobs(jobs, profile)
    return {
        "active_role": AgentRole.FIT_ANALYST,
        "ranked_jobs": [item.model_dump(mode="json") for item in ranked],
        "stage": "analysis",
    }


def _requirement_options(job: JobRecord) -> list[str]:
    """Return deterministic posting excerpts that a model may reference by index."""

    candidates = [*job.requirements, *job.preferred_requirements]
    if not candidates:
        candidates = re.split(r"(?<=[.!?])\s+|[\r\n]+", job.description)
    options: list[str] = []
    for raw in candidates:
        normalized = " ".join(raw.split()).strip()
        if normalized and normalized not in options:
            options.append(normalized)
        if len(options) >= 12:
            break
    return options


def _artifact_content(
    profile: Profile,
    ranked_job: RankedJob,
    fact_ids: list[str],
) -> tuple[str, list[Claim]]:
    facts_by_id = {fact.fact_id: fact for fact in profile.facts if fact.verified}
    evidence = [facts_by_id[fact_id] for fact_id in fact_ids]
    claims = [Claim(text=fact.text, fact_ids=[fact.fact_id]) for fact in evidence]
    fact_text = "\n".join(f"- {fact.text}" for fact in evidence)
    if not fact_text:
        fact_text = "- No verified facts selected."
    content = (
        f"Application brief for {ranked_job.job.title} at {ranked_job.job.company}.\n\n"
        f"Verified candidate evidence:\n{fact_text}\n\n"
        f"Fit score: {ranked_job.score:.1f}/100. Review all wording before export."
    )
    return content, claims


def shortlist_gate(state: WorkflowState) -> dict[str, Any]:
    ranked = [RankedJob.model_validate(item) for item in state.get("ranked_jobs", [])]
    suggested = [item.job.job_id for item in ranked if item.eligible is not False][:3]
    result = _approval(
        state,
        ApprovalKind.SHORTLIST_SELECTION,
        {"suggested_job_ids": suggested},
    )
    return {
        **result,
        "selected_job_ids": state.get("selected_job_ids") or suggested,
        "stage": "drafting",
    }


def tailor(state: WorkflowState) -> dict[str, Any]:
    profile = Profile.model_validate(state["profile"])
    ranked = [RankedJob.model_validate(item) for item in state.get("ranked_jobs", [])]
    selected = set(state.get("selected_job_ids", []))
    artifacts: list[Artifact] = []
    facts = [fact for fact in profile.facts if fact.verified]
    for item in ranked:
        if item.job.job_id not in selected:
            continue
        evidence = facts[:5]
        content, claims = _artifact_content(
            profile, item, [fact.fact_id for fact in evidence]
        )
        artifacts.append(
            Artifact(
                run_id=state["run_id"],
                job_id=item.job.job_id,
                profile_id=profile.profile_id,
                kind="application_brief",
                title=f"{profile.name} - {item.job.title}",
                content=content,
                claims=claims,
            )
        )
    return {
        "active_role": AgentRole.TAILOR,
        "artifacts": [item.model_dump(mode="json") for item in artifacts],
        "stage": "reviewing",
        "revision_count": state.get("revision_count", 0)
        + (1 if state.get("artifacts") else 0),
    }


def reviewer(state: WorkflowState) -> dict[str, Any]:
    profile = Profile.model_validate(state["profile"])
    valid_fact_ids = {fact.fact_id for fact in profile.facts if fact.verified}
    verified_text_by_id = {
        fact.fact_id: " ".join(fact.text.casefold().split())
        for fact in profile.facts
        if fact.verified
    }
    issues: list[ReviewIssue] = []
    for raw in state.get("artifacts", []):
        artifact = Artifact.model_validate(raw)
        for claim in artifact.claims:
            if not claim.fact_ids or not set(claim.fact_ids).issubset(valid_fact_ids):
                issues.append(
                    ReviewIssue(
                        severity="error",
                        message="Claim is not fully supported by verified profile facts",
                        claim=claim.text,
                    )
                )
                continue
            normalized_claim = " ".join(claim.text.casefold().split())
            if normalized_claim not in {
                verified_text_by_id[fact_id] for fact_id in claim.fact_ids
            }:
                issues.append(
                    ReviewIssue(
                        severity="error",
                        message="Claim wording is stronger or different from its verified fact",
                        claim=claim.text,
                    )
                )
    report = ReviewReport(approved=not issues, issues=issues)
    return {
        "active_role": AgentRole.REVIEWER,
        "review": report.model_dump(mode="json"),
        "stage": "approval",
    }


def application_gate(state: WorkflowState) -> dict[str, Any]:
    artifacts = [Artifact.model_validate(item) for item in state.get("artifacts", [])]
    result = _approval(
        state,
        ApprovalKind.APPLICATION_APPROVAL,
        {
            "artifact_ids": [item.artifact_id for item in artifacts],
            "review": state.get("review", {}),
        },
    )
    return {**result, "active_role": AgentRole.COORDINATOR, "stage": "completed"}


def review_route(state: WorkflowState) -> str:
    report = ReviewReport.model_validate(state.get("review", {"approved": False}))
    if report.approved:
        return "application_approval"
    if state.get("revision_count", 0) < 1:
        return "application_tailor"
    return "review_blocked"


def review_blocked(_state: WorkflowState) -> dict[str, Any]:
    return {"stage": "failed", "active_role": AgentRole.REVIEWER}


def project_role_context(
    state: WorkflowState,
    role: AgentRole,
    result: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return the least-privilege payload allowed to leave deterministic nodes."""

    result = result or {}
    verified_facts = [
        {"fact_id": fact.get("fact_id"), "text": fact.get("text")}
        for fact in state.get("profile", {}).get("facts", [])
        if fact.get("verified")
    ][:20]
    raw_jobs = result.get("jobs") or state.get("jobs", [])
    jobs = [
        {
            "job_id": job.get("job_id"),
            "title": job.get("title"),
            "company": job.get("company"),
            "location": job.get("location"),
            "description": str(job.get("description", ""))[:4000],
            "requirement_options": [
                {"index": index, "text": text}
                for index, text in enumerate(
                    _requirement_options(JobRecord.model_validate(job))
                )
            ],
        }
        for job in raw_jobs
    ][:10]
    base = {"stage": result.get("stage", state.get("stage"))}
    if role == AgentRole.COORDINATOR:
        return {
            **base,
            "job_count": len(jobs),
            "artifact_count": len(state.get("artifacts", [])),
            "approval_count": len(state.get("approvals", [])),
        }
    if role == AgentRole.SCOUT:
        return {**base, "query": state.get("query", ""), "jobs": jobs}
    if role == AgentRole.FIT_ANALYST:
        offered_job_ids = {job["job_id"] for job in jobs}
        return {
            **base,
            "verified_profile_facts": verified_facts,
            "jobs": jobs,
            "ranked_summary": [
                {
                    "job_id": item.get("job", {}).get("job_id"),
                    "score": item.get("score"),
                    "eligible": item.get("eligible"),
                    "reasons": item.get("reasons", []),
                    "gaps": item.get("gaps", []),
                }
                for item in result.get("ranked_jobs", [])
                if item.get("job", {}).get("job_id") in offered_job_ids
            ],
        }
    if role == AgentRole.TAILOR:
        return {
            **base,
            "verified_profile_facts": verified_facts,
            "selected_jobs": [
                job for job in jobs if job["job_id"] in state.get("selected_job_ids", [])
            ],
        }
    return {
        **base,
        "verified_profile_facts": verified_facts,
        "drafts": [
            {
                "artifact_id": item.get("artifact_id"),
                "content": str(item.get("content", ""))[:6000],
                "claims": item.get("claims", []),
            }
            for item in state.get("artifacts", [])
        ],
    }


def _apply_fit_proposal(
    state: WorkflowState,
    result: dict[str, Any],
    proposal: FitAnalystProposal,
) -> tuple[dict[str, Any], str]:
    profile = Profile.model_validate(state["profile"])
    verified_facts = {
        fact.fact_id: fact for fact in profile.facts if fact.verified
    }
    verified_facts = dict(list(verified_facts.items())[:20])
    ranked = [RankedJob.model_validate(item) for item in result.get("ranked_jobs", [])]
    ranked_by_id = {item.job.job_id: item for item in ranked}
    offered_job_ids = {
        job.get("job_id") for job in state.get("jobs", [])[:10] if job.get("job_id")
    }
    seen_jobs: set[str] = set()

    for mapping in proposal.mappings:
        if (
            mapping.job_id not in ranked_by_id
            or mapping.job_id not in offered_job_ids
            or mapping.job_id in seen_jobs
        ):
            raise ValueError("Fit proposal contains an unavailable or duplicate job ID")
        seen_jobs.add(mapping.job_id)
        if len(set(mapping.fact_ids)) != len(mapping.fact_ids):
            raise ValueError("Fit proposal contains duplicate fact IDs")
        if not set(mapping.fact_ids).issubset(verified_facts):
            raise ValueError("Fit proposal contains an unavailable fact ID")
        options = _requirement_options(ranked_by_id[mapping.job_id].job)
        if len(set(mapping.gap_requirement_indices)) != len(
            mapping.gap_requirement_indices
        ) or any(
            index < 0 or index >= len(options)
            for index in mapping.gap_requirement_indices
        ):
            raise ValueError("Fit proposal contains an unavailable requirement index")

    for mapping in proposal.mappings:
        item = ranked_by_id[mapping.job_id]
        for fact_id in mapping.fact_ids:
            reason = (
                f"Verified evidence selected by analyst ({fact_id}): "
                f"{verified_facts[fact_id].text}"
            )
            if reason not in item.reasons:
                item.reasons.append(reason)
        options = _requirement_options(item.job)
        for index in mapping.gap_requirement_indices:
            gap = f"Posting requirement flagged as a gap: {options[index]}"
            if gap not in item.gaps:
                item.gaps.append(gap)

    result["ranked_jobs"] = [item.model_dump(mode="json") for item in ranked]
    count = sum(len(item.fact_ids) for item in proposal.mappings)
    return result, f"Applied {count} validated evidence mappings without changing scores."


def _apply_tailor_proposal(
    state: WorkflowState,
    result: dict[str, Any],
    proposal: TailorProposal,
) -> tuple[dict[str, Any], str]:
    profile = Profile.model_validate(state["profile"])
    verified_fact_ids = {
        fact.fact_id for fact in [item for item in profile.facts if item.verified][:20]
    }
    ranked = [RankedJob.model_validate(item) for item in state.get("ranked_jobs", [])]
    ranked_by_id = {item.job.job_id: item for item in ranked}
    artifacts = [Artifact.model_validate(item) for item in result.get("artifacts", [])]
    offered_job_ids = {
        job.get("job_id")
        for job in state.get("jobs", [])[:10]
        if job.get("job_id") in state.get("selected_job_ids", [])
    }
    artifact_job_ids = {item.job_id for item in artifacts} & offered_job_ids
    seen_jobs: set[str] = set()

    for selection in proposal.selections:
        if selection.job_id not in artifact_job_ids or selection.job_id in seen_jobs:
            raise ValueError("Tailor proposal contains an unavailable or duplicate job ID")
        seen_jobs.add(selection.job_id)
        if len(set(selection.ordered_fact_ids)) != len(selection.ordered_fact_ids):
            raise ValueError("Tailor proposal contains duplicate fact IDs")
        if not set(selection.ordered_fact_ids).issubset(verified_fact_ids):
            raise ValueError("Tailor proposal contains an unavailable fact ID")

    selections = {item.job_id: item.ordered_fact_ids for item in proposal.selections}
    for artifact in artifacts:
        fact_ids = selections.get(artifact.job_id)
        if fact_ids is None:
            continue
        content, claims = _artifact_content(
            profile,
            ranked_by_id[artifact.job_id],
            fact_ids,
        )
        artifact.content = content
        artifact.claims = claims

    result["artifacts"] = [item.model_dump(mode="json") for item in artifacts]
    return result, f"Applied validated fact ordering to {len(selections)} drafts."


_REVIEW_MESSAGES = {
    "clarity": "Model observation: review this claim for clarity.",
    "coverage": "Model observation: check whether this claim covers the target requirement.",
    "tone": "Model observation: review this claim's tone.",
    "unsupported": "Model observation: this claim requires an additional evidence check.",
}


def _apply_reviewer_proposal(
    state: WorkflowState,
    result: dict[str, Any],
    proposal: ReviewerProposal,
) -> tuple[dict[str, Any], str]:
    artifacts = {
        artifact.artifact_id: artifact
        for artifact in (
            Artifact.model_validate(item) for item in state.get("artifacts", [])
        )
    }
    seen: set[tuple[str, int, str]] = set()
    for observation in proposal.observations:
        artifact = artifacts.get(observation.artifact_id)
        key = (observation.artifact_id, observation.claim_index, observation.code)
        if (
            artifact is None
            or observation.claim_index >= len(artifact.claims)
            or key in seen
        ):
            raise ValueError("Reviewer proposal contains an unavailable or duplicate reference")
        seen.add(key)

    report = ReviewReport.model_validate(result.get("review", {"approved": False}))
    for observation in proposal.observations:
        claim = artifacts[observation.artifact_id].claims[observation.claim_index]
        report.issues.append(
            ReviewIssue(
                severity="error" if observation.code == "unsupported" else "warning",
                message=_REVIEW_MESSAGES[observation.code],
                claim=claim.text,
            )
        )
    # The model has no `approved` field and can only make this result stricter.
    report.approved = report.approved and not any(
        issue.severity == "error" for issue in report.issues
    )
    result["review"] = report.model_dump(mode="json")
    return result, f"Added {len(proposal.observations)} validated review observations."


def _apply_model_proposal(
    role: AgentRole,
    state: WorkflowState,
    result: dict[str, Any],
    proposal: object,
) -> tuple[dict[str, Any], str]:
    if role == AgentRole.COORDINATOR and isinstance(proposal, CoordinatorProposal):
        return result, " ".join(proposal.summary.split())
    if role == AgentRole.SCOUT and isinstance(proposal, ScoutProposal):
        return result, " ".join(proposal.summary.split())
    if role == AgentRole.FIT_ANALYST and isinstance(proposal, FitAnalystProposal):
        return _apply_fit_proposal(state, result, proposal)
    if role == AgentRole.TAILOR and isinstance(proposal, TailorProposal):
        return _apply_tailor_proposal(state, result, proposal)
    if role == AgentRole.REVIEWER and isinstance(proposal, ReviewerProposal):
        return _apply_reviewer_proposal(state, result, proposal)
    raise ValueError("Model proposal does not match the active role")


def _with_local_agent(
    role: AgentRole,
    node: Callable[[WorkflowState], dict[str, Any]],
    registry: DeepSeekAgentRegistry | None,
) -> Callable[[WorkflowState], dict[str, Any]]:
    if registry is None:
        return node

    def wrapped(state: WorkflowState) -> dict[str, Any]:
        result = node(state)
        if not state.get("use_model", False):
            return result
        safe_payload = project_role_context(state, role, result)
        invocation = registry.invoke(role, safe_payload)
        try:
            proposal = invocation.structured or parse_role_output(role, invocation.content)
            result, visible_summary = _apply_model_proposal(role, state, result, proposal)
        except (TypeError, ValueError):
            visible_summary = (
                "Model proposal rejected because it violated the schema or referenced "
                "unavailable data."
            )
        summaries = dict(state.get("agent_summaries", {}))
        summaries[str(role)] = visible_summary
        models = dict(state.get("agent_models", {}))
        models[str(role)] = invocation.model
        result["agent_summaries"] = summaries
        result["agent_models"] = models
        return result

    return wrapped


def build_graph(
    *,
    checkpointer: Any = None,
    agent_registry: DeepSeekAgentRegistry | None = None,
):
    graph = StateGraph(WorkflowState)
    graph.add_node(
        "career_coordinator",
        _with_local_agent(AgentRole.COORDINATOR, coordinator, agent_registry),
    )
    graph.add_node("profile_confirmation", profile_gate)
    graph.add_node(
        "opportunity_scout",
        _with_local_agent(AgentRole.SCOUT, scout, agent_registry),
    )
    graph.add_node(
        "fit_analyst",
        _with_local_agent(AgentRole.FIT_ANALYST, fit_analyst, agent_registry),
    )
    graph.add_node("shortlist_selection", shortlist_gate)
    graph.add_node(
        "application_tailor",
        _with_local_agent(AgentRole.TAILOR, tailor, agent_registry),
    )
    graph.add_node(
        "quality_reviewer",
        _with_local_agent(AgentRole.REVIEWER, reviewer, agent_registry),
    )
    graph.add_node("review_blocked", review_blocked)
    graph.add_node("application_approval", application_gate)
    graph.add_edge(START, "career_coordinator")
    graph.add_edge("career_coordinator", "profile_confirmation")
    graph.add_edge("profile_confirmation", "opportunity_scout")
    graph.add_edge("opportunity_scout", "fit_analyst")
    graph.add_edge("fit_analyst", "shortlist_selection")
    graph.add_edge("shortlist_selection", "application_tailor")
    graph.add_edge("application_tailor", "quality_reviewer")
    graph.add_conditional_edges("quality_reviewer", review_route)
    graph.add_edge("review_blocked", END)
    graph.add_edge("application_approval", END)
    return graph.compile(checkpointer=checkpointer)


def synthetic_jobs() -> list[JobRecord]:
    return [
        normalize_job(
            source=SourceKind.REPLAY,
            external_id="replay-1",
            title="Python Automation Engineer",
            company="Northstar Labs",
            location="Remote - Americas",
            remote=True,
            url="https://example.invalid/jobs/replay-1",
            description="Build Python services, SQL workflows, APIs, and reliable automation for a remote team.",
        ),
        normalize_job(
            source=SourceKind.REPLAY,
            external_id="replay-2",
            title="Data Operations Analyst",
            company="Atlas Works",
            location="San Jose, Costa Rica",
            remote=False,
            url="https://example.invalid/jobs/replay-2",
            description="Analyze operational data with SQL and Python. Communicate findings and improve processes.",
        ),
        normalize_job(
            source=SourceKind.REPLAY,
            external_id="replay-3",
            title="Technical Program Coordinator",
            company="Juniper Systems",
            location="Remote",
            remote=True,
            url="https://example.invalid/jobs/replay-3",
            description="Coordinate technical projects, document decisions, and collaborate with engineering teams.",
        ),
    ]


def synthetic_profile() -> Profile:
    from .schemas import ProfileFact, UserPreferences

    return Profile(
        profile_id="profile_replay",
        name="Alex Rivera",
        summary="Automation and data professional",
        facts=[
            ProfileFact(
                fact_id="fact_python",
                category="skill",
                text="Built Python automation for recurring operational reports.",
                evidence="Verified synthetic fixture",
                verified=True,
            ),
            ProfileFact(
                fact_id="fact_sql",
                category="skill",
                text="Uses SQL to analyze and validate business data.",
                evidence="Verified synthetic fixture",
                verified=True,
            ),
        ],
        preferences=UserPreferences(
            desired_titles=["Python", "Data"], keywords=["automation", "SQL"], remote_required=True
        ),
        confirmed=True,
    )

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Any

from langgraph.types import Command

from .connectors import CONNECTOR_TYPES, search_connectors
from .ranking import clean_text, deduplicate_jobs
from .replay import (
    EventEmitter,
    _set_pipeline_status,
    _set_ranked_analysis_statuses,
    _sync_ranked_pipeline_statuses,
)
from .schemas import (
    AgentRole,
    AgentStatus,
    Approval,
    ApprovalKind,
    ApprovalStatus,
    Artifact,
    JobRecord,
    PipelineStatus,
    RunCreate,
    RunStatus,
    SearchRequest,
    SourceKind,
    build_integrity_snapshot,
    utc_now,
)
from .storage import SQLiteStore
from .workflow import build_graph

if TYPE_CHECKING:
    from .agents import DeepSeekAgentRegistry


ConnectorSearch = Callable[
    [SearchRequest], Awaitable[tuple[list[JobRecord], dict[str, str]]]
]

logger = logging.getLogger(__name__)
PUBLIC_RUN_FAILURE = "The local run failed; inspect local logs"


def effective_search_request(payload: RunCreate) -> SearchRequest:
    """Prefer the explicit SearchRequest while keeping the flat UI contract compatible."""

    if payload.search is not None:
        return payload.search
    return SearchRequest(
        query=payload.query,
        location=payload.location,
        remote_only=payload.work_mode.casefold() == "remote",
        sources=payload.sources,
        source_identifiers=payload.source_identifiers,
        limit=payload.limit,
    )


def _matches_search(job: JobRecord, request: SearchRequest) -> bool:
    query = clean_text(request.query).casefold()
    location = clean_text(request.location).casefold()
    haystack = f"{job.title} {job.company} {job.description}".casefold()
    if query and query not in haystack:
        return False
    if location and location not in job.location.casefold():
        return False
    return not (request.remote_only and job.remote is False)


async def collect_live_jobs(
    store: SQLiteStore,
    payload: RunCreate,
    *,
    connector_search: ConnectorSearch = search_connectors,
) -> tuple[list[JobRecord], dict[str, str]]:
    """Collect only explicitly selected connectors plus local jobs in scope.

    An empty source list means local/manual-only. It never expands to every network
    connector, which keeps a live run honest and opt-in.
    """

    request = effective_search_request(payload)
    requested_source_list = list(
        dict.fromkeys(SourceKind(source) for source in request.sources)
    )
    requested_sources = set(requested_source_list)
    jobs: list[JobRecord] = []
    errors: dict[str, str] = {}

    for job_id in payload.job_ids:
        job = store.get_job(job_id)
        if job is None:
            errors[f"job:{job_id}"] = "Stored job was not found"
        else:
            jobs.append(job)

    include_manual = SourceKind.MANUAL in requested_sources or (
        not requested_sources and not payload.job_ids
    )
    if include_manual:
        jobs.extend(
            job
            for job in store.list_jobs(limit=max(100, request.limit))
            if job.source == SourceKind.MANUAL and _matches_search(job, request)
        )

    network_sources = [
        source for source in requested_source_list if source in CONNECTOR_TYPES
    ]
    if network_sources:
        network_request = request.model_copy(update={"sources": network_sources})
        fetched, connector_errors = await connector_search(network_request)
        jobs.extend(fetched)
        errors.update(connector_errors)

    if SourceKind.REPLAY in requested_sources:
        errors[str(SourceKind.REPLAY)] = "Synthetic replay jobs are unavailable in live mode"

    deduplicated = deduplicate_jobs(jobs)[: request.limit]
    for job in deduplicated:
        store.save_job(job)
    return deduplicated, errors


def _interrupt_kind(output: dict[str, Any]) -> str:
    interrupts = output.get("__interrupt__", [])
    if not interrupts:
        raise RuntimeError("LangGraph did not pause at the expected human gate")
    value = interrupts[0].value
    return str(value.get("kind", ""))


async def run_live_workflow(
    store: SQLiteStore,
    run_id: str,
    payload: RunCreate,
    *,
    connector_search: ConnectorSearch = search_connectors,
    agent_registry: DeepSeekAgentRegistry | None = None,
    checkpointer: Any = None,
    recovery: bool = False,
) -> None:
    """Run real stored/connector jobs through the same interruptible StateGraph."""

    run = store.get_run(run_id)
    profile = store.get_profile(payload.profile_id or "")
    if run is None:
        raise KeyError(run_id)
    if profile is None or not profile.confirmed:
        raise ValueError("A confirmed profile is required for live mode")

    emitter = EventEmitter(store, run_id)
    graph = build_graph(checkpointer=checkpointer, agent_registry=agent_registry)
    config = {"configurable": {"thread_id": run.thread_id or run_id}}

    async def invoke(value: Any) -> dict[str, Any]:
        return await asyncio.to_thread(graph.invoke, value, config)

    def was_cancelled() -> bool:
        current = store.get_run(run_id)
        return current is None or current.status == RunStatus.CANCELLED

    async def approval_gate(
        kind: ApprovalKind,
        *,
        stage: str,
        gate_payload: dict[str, Any],
        allowed_decisions: list[str],
        integrity_snapshot: dict[str, Any],
        existing_approval: Approval | None = None,
    ) -> Approval | None:
        if was_cancelled():
            return None
        is_new = existing_approval is None
        approval = existing_approval or store.save_approval(
            Approval(
                run_id=run_id,
                kind=kind,
                allowed_decisions=allowed_decisions,
                offered_entity_ids=[
                    str(item) for item in gate_payload.get("entity_ids", [])
                ],
                max_selected=3 if kind == ApprovalKind.SHORTLIST_SELECTION else None,
                integrity_snapshot=integrity_snapshot,
                artifact_version=gate_payload.get("artifact_version"),
                payload=gate_payload,
            )
        )
        was_pending = approval.status == ApprovalStatus.PENDING
        if was_pending:
            run.status = RunStatus.AWAITING_USER
            run.result = {
                **run.result,
                "phase": stage,
                "pending_approval_id": approval.approval_id,
            }
            if store.save_run_if_not_terminal(run) is None:
                return None
        if is_new:
            emitter.emit(
                "approval_requested",
                stage=stage,
                actor_kind="agent",
                actor_id=AgentRole.COORDINATOR,
                payload={
                    "approval": {
                        "approval_id": approval.approval_id,
                        "kind": str(kind),
                        "owner_agent_id": str(AgentRole.COORDINATOR),
                        "entity_ids": gate_payload.get("entity_ids", []),
                        "artifact_version": gate_payload.get("artifact_version"),
                        "allowed_decisions": allowed_decisions,
                        "summary": gate_payload.get("summary", ""),
                    }
                },
                template_key="approval.requested",
            )
        if was_pending and payload.auto_approve:
            approval.status = ApprovalStatus.APPROVED
            approval.decision_payload = {
                "automatic": True,
                "entity_ids": gate_payload.get("entity_ids", []),
                "decision": "approved",
            }
            approval.resolved_at = utc_now()
            store.save_approval(approval)
        elif was_pending:
            while True:
                current_run = store.get_run(run_id)
                if current_run is None or current_run.status == RunStatus.CANCELLED:
                    return None
                current = store.get_approval(approval.approval_id)
                if current is not None and current.status != ApprovalStatus.PENDING:
                    approval = current
                    break
                await asyncio.sleep(0.05)

        if was_pending:
            emitter.emit(
                "approval_resolved",
                stage=stage,
                actor_kind="user",
                actor_id="automatic_policy" if payload.auto_approve else "local_user",
                target_id=AgentRole.COORDINATOR,
                payload={
                    "approval_id": approval.approval_id,
                    "kind": str(kind),
                    "decision": str(approval.status),
                },
                template_key="approval.resolved",
                template_args={"decision": str(approval.status)},
                severity=(
                    "success"
                    if approval.status == ApprovalStatus.APPROVED
                    else "warning"
                ),
            )
        if was_cancelled():
            return None
        if approval.status != ApprovalStatus.APPROVED:
            run.status = RunStatus.CANCELLED
            if store.save_run_if_not_terminal(run) is None:
                return None
            emitter.emit(
                "run_cancelled",
                stage="cancelled",
                payload={"reason": f"{kind} rejected"},
                template_key="run.cancelled",
                severity="warning",
            )
            return None

        run.status = RunStatus.RUNNING
        run.result = {
            key: value
            for key, value in run.result.items()
            if key != "pending_approval_id"
        }
        if store.save_run_if_not_terminal(run) is None:
            return None
        return approval

    def initial_state(request: SearchRequest) -> dict[str, Any]:
        return {
            "run_id": run_id,
            "mode": "live",
            "query": request.query,
            "auto_approve": False,
            "profile": profile.model_dump(mode="json"),
            "jobs": [],
            "selected_job_ids": payload.selected_job_ids,
            "approvals": [],
            "artifacts": [],
            "revision_count": 0,
            "use_model": payload.use_model,
            "agent_summaries": {},
            "agent_models": {},
        }

    async def ensure_gate(
        target_node: str,
        request: SearchRequest,
        jobs: list[JobRecord],
        selected: list[str],
    ) -> dict[str, Any]:
        try:
            snapshot = await asyncio.to_thread(graph.get_state, config)
            if target_node in snapshot.next:
                return dict(snapshot.values)
        except (AttributeError, ValueError):
            pass
        output = await invoke(initial_state(request))
        if target_node == "profile_confirmation":
            return output
        output = await invoke(
            Command(
                resume={"decision": "approved"},
                update={"jobs": [job.model_dump(mode="json") for job in jobs]},
            )
        )
        if target_node == "shortlist_selection":
            return output
        return await invoke(
            Command(
                resume={"decision": "approved", "entity_ids": selected},
                update={"selected_job_ids": selected},
            )
        )

    def existing_approval(kind: ApprovalKind) -> Approval | None:
        if not recovery:
            return None
        approval_id = run.result.get("pending_approval_id")
        approval = store.get_approval(str(approval_id)) if approval_id else None
        if approval is not None and approval.kind == kind:
            return approval
        return next(
            (
                item
                for item in reversed(store.list_approvals(run_id))
                if item.kind == kind and item.status == ApprovalStatus.PENDING
            ),
            None,
        )

    try:
        request = effective_search_request(payload)
        phase = str(run.result.get("phase", "profile")) if recovery else "profile"
        if phase not in {"profile", "shortlist", "approval"}:
            raise RuntimeError(f"Cannot recover unknown live phase: {phase}")

        jobs: list[JobRecord] = []
        ranked: list[dict[str, Any]] = list(run.result.get("ranked_jobs", []))
        connector_errors: dict[str, str] = dict(
            run.result.get("connector_errors", {})
        )
        selected = [str(item) for item in run.result.get("selected_job_ids", [])]
        if recovery and phase in {"shortlist", "approval"}:
            job_ids = list(run.result.get("job_ids", [])) or [
                str(item.get("job", {}).get("job_id"))
                for item in ranked
                if item.get("job", {}).get("job_id")
            ]
            jobs = [job for job_id in job_ids if (job := store.get_job(job_id))]
            _sync_ranked_pipeline_statuses(store, jobs, ranked)

        if not recovery:
            run.status = RunStatus.RUNNING
            run.result = {
                "phase": "profile",
                "search": {
                    "query": request.query,
                    "location": request.location,
                    "remote_only": request.remote_only,
                    "sources": [str(source) for source in request.sources],
                    "limit": request.limit,
                    "job_ids": payload.job_ids,
                },
            }
            if store.save_run_if_not_terminal(run) is None:
                return
            emitter.emit("run_started", stage="profile", template_key="run.started")
            emitter.emit(
                "agent_started",
                stage="profile",
                actor_kind="agent",
                actor_id=AgentRole.COORDINATOR,
                payload={"status": AgentStatus.WORKING},
                template_key="profile.ready",
                template_args={"facts": len(profile.facts)},
            )

        if phase == "profile":
            output = await ensure_gate(
                "profile_confirmation", request, jobs=[], selected=[]
            )
            if was_cancelled():
                return
            if not recovery and _interrupt_kind(output) != str(
                ApprovalKind.PROFILE_CONFIRMATION
            ):
                raise RuntimeError("Unexpected first LangGraph gate")
            profile_approval = await approval_gate(
                ApprovalKind.PROFILE_CONFIRMATION,
                stage="profile",
                gate_payload={
                    "entity_ids": [profile.profile_id],
                    "artifact_version": profile.version,
                    "summary": "Confirm this stored profile may be used for the live search.",
                },
                allowed_decisions=["approve", "reject"],
                integrity_snapshot=build_integrity_snapshot(profile=profile),
                existing_approval=existing_approval(
                    ApprovalKind.PROFILE_CONFIRMATION
                ),
            )
            if profile_approval is None:
                return

            emitter.emit(
                "agent_started",
                stage="search",
                actor_kind="agent",
                actor_id=AgentRole.SCOUT,
                payload={"status": AgentStatus.WORKING},
                template_key="scout.started",
                template_args={"sources": len(request.sources) or 1},
            )
            jobs, connector_errors = await collect_live_jobs(
                store, payload, connector_search=connector_search
            )
            if was_cancelled():
                return
            emitter.emit(
                "agent_completed",
                stage="search",
                actor_kind="agent",
                actor_id=AgentRole.SCOUT,
                payload={
                    "found": len(jobs),
                    "connector_errors": {
                        source: "connector_failed" for source in connector_errors
                    },
                },
                template_key="scout.completed",
                template_args={"found": len(jobs), "duplicates": 0},
                severity="warning" if connector_errors else "info",
                progress=1,
            )
            emitter.emit(
                "agent_started",
                stage="analysis",
                actor_kind="agent",
                actor_id=AgentRole.FIT_ANALYST,
                payload={"status": AgentStatus.WORKING, "jobs": len(jobs)},
                template_key="fit.started",
                template_args={"jobs": len(jobs)},
            )
            output = await invoke(
                Command(
                    resume={"decision": "approved"},
                    update={"jobs": [job.model_dump(mode="json") for job in jobs]},
                )
            )
            if was_cancelled():
                return
            if _interrupt_kind(output) != str(ApprovalKind.SHORTLIST_SELECTION):
                raise RuntimeError("Unexpected shortlist LangGraph gate")
            ranked = output.get("ranked_jobs", [])
            _set_ranked_analysis_statuses(store, jobs, ranked)
            run.result = {
                **run.result,
                "job_ids": [job.job_id for job in jobs],
                "ranked_jobs": ranked,
                "connector_errors": connector_errors,
            }
            if store.save_run_if_not_terminal(run) is None:
                return
            emitter.emit(
                "agent_completed",
                stage="analysis",
                actor_kind="agent",
                actor_id=AgentRole.FIT_ANALYST,
                payload={"analyzed": len(ranked)},
                template_key="fit.completed",
                template_args={
                    "eligible": len(
                        [item for item in ranked if item.get("eligible") is not False]
                    )
                },
                progress=1,
            )
        elif phase == "shortlist":
            output = await ensure_gate(
                "shortlist_selection", request, jobs=jobs, selected=[]
            )

        if phase in {"profile", "shortlist"}:
            suggested = [
                item["job"]["job_id"]
                for item in ranked
                if item.get("eligible") is not False
            ][:3]
            shortlist = await approval_gate(
                ApprovalKind.SHORTLIST_SELECTION,
                stage="shortlist",
                gate_payload={
                    "entity_ids": suggested,
                    "summary": "Select up to three live vacancies to prepare.",
                },
                allowed_decisions=["select", "skip"],
                integrity_snapshot=build_integrity_snapshot(
                    profile=profile, jobs=jobs
                ),
                existing_approval=existing_approval(
                    ApprovalKind.SHORTLIST_SELECTION
                ),
            )
            if shortlist is None:
                return
            selected = [
                str(job_id)
                for job_id in (
                    shortlist.decision_payload.get("entity_ids")
                    or payload.selected_job_ids
                    or suggested
                )
                if str(job_id) in {job.job_id for job in jobs}
            ][:3]
            _set_pipeline_status(
                store,
                jobs,
                ranked,
                selected,
                PipelineStatus.SHORTLISTED,
            )
            run.result = {
                **run.result,
                "selected_job_ids": selected,
                "ranked_jobs": ranked,
            }
            if store.save_run_if_not_terminal(run) is None:
                return
            _set_pipeline_status(
                store,
                jobs,
                ranked,
                selected,
                PipelineStatus.DRAFTING,
            )
            run.result = {**run.result, "ranked_jobs": ranked}
            if store.save_run_if_not_terminal(run) is None:
                return
            emitter.emit(
                "agent_started",
                stage="drafting",
                actor_kind="agent",
                actor_id=AgentRole.TAILOR,
                template_key="tailor.started",
                template_args={"version": 1},
            )
            output = await invoke(
                Command(
                    resume={"decision": "approved", "entity_ids": selected},
                    update={"selected_job_ids": selected},
                )
            )
            if was_cancelled():
                return
            if _interrupt_kind(output) != str(ApprovalKind.APPLICATION_APPROVAL):
                raise RuntimeError("Unexpected application LangGraph gate")
            artifacts: list[Artifact] = []
            _set_pipeline_status(
                store,
                jobs,
                ranked,
                selected,
                PipelineStatus.REVIEWING,
            )
            run.result = {**run.result, "ranked_jobs": ranked}
            if store.save_run_if_not_terminal(run) is None:
                return
            for raw in output.get("artifacts", []):
                artifact = store.save_artifact_if_run_active(
                    Artifact.model_validate(raw)
                )
                if artifact is None:
                    return
                artifacts.append(artifact)
                emitter.emit(
                    "artifact_created",
                    stage="drafting",
                    actor_kind="agent",
                    actor_id=AgentRole.TAILOR,
                    entity_ref=artifact.artifact_id,
                    payload={
                        "artifact_id": artifact.artifact_id,
                        "kind": artifact.kind,
                        "artifact": {
                            "id": artifact.artifact_id,
                            "kind": artifact.kind,
                            "title": artifact.title,
                            "version": artifact.version,
                        },
                    },
                    template_key="tailor.completed",
                    template_args={"claims": len(artifact.claims)},
                )
            review = output.get("review", {})
            emitter.emit(
                "agent_started",
                stage="reviewing",
                actor_kind="agent",
                actor_id=AgentRole.REVIEWER,
                template_key="review.started",
            )
            emitter.emit(
                "agent_completed",
                stage="reviewing",
                actor_kind="agent",
                actor_id=AgentRole.REVIEWER,
                payload=review,
                template_key=(
                    "review.passed" if review.get("approved") else "review.issue"
                ),
                template_args={"issues": len(review.get("issues", []))},
                severity="success" if review.get("approved") else "warning",
            )
            if review.get("approved"):
                _set_pipeline_status(
                    store,
                    jobs,
                    ranked,
                    selected,
                    PipelineStatus.READY_FOR_APPROVAL,
                )
            run.result = {
                **run.result,
                "ranked_jobs": ranked,
                "artifact_ids": [artifact.artifact_id for artifact in artifacts],
                "review": review,
            }
            if store.save_run_if_not_terminal(run) is None:
                return
        else:
            artifacts = store.list_artifacts(run_id)
            review = dict(run.result.get("review", {}))
            output = await ensure_gate(
                "application_approval", request, jobs=jobs, selected=selected
            )

        application = await approval_gate(
            ApprovalKind.APPLICATION_APPROVAL,
            stage="approval",
            gate_payload={
                "entity_ids": [artifact.artifact_id for artifact in artifacts],
                "artifact_version": 1,
                "summary": "Approve the reviewed live package before PDF export.",
            },
            allowed_decisions=["approve", "reject"],
            integrity_snapshot=build_integrity_snapshot(
                profile=profile,
                jobs=[job for job in jobs if job.job_id in set(selected)],
                artifacts=artifacts,
            ),
            existing_approval=existing_approval(
                ApprovalKind.APPLICATION_APPROVAL
            ),
        )
        if application is None:
            return

        output = await invoke(Command(resume={"decision": "approved"}))
        if was_cancelled():
            return
        _set_pipeline_status(
            store,
            jobs,
            ranked,
            selected,
            PipelineStatus.APPROVED,
        )
        run.status = RunStatus.COMPLETED
        run.result = {
            **run.result,
            "phase": "completed",
            "profile_id": profile.profile_id,
            "job_ids": [job.job_id for job in jobs],
            "ranked_jobs": ranked,
            "artifact_ids": [artifact.artifact_id for artifact in artifacts],
            "review": review,
            "connector_errors": connector_errors,
            "agent_summaries": output.get("agent_summaries", {}),
            "agent_models": output.get("agent_models", {}),
        }
        if store.save_run_if_not_terminal(run) is None:
            return
        emitter.emit(
            "run_completed",
            stage="completed",
            payload={"artifact_count": len(artifacts), "job_count": len(jobs)},
            template_key="run.completed",
            template_args={"artifact_count": len(artifacts)},
            severity="success",
            progress=1,
        )
    # Background-task boundary: persist a sanitized terminal failure for any
    # connector, graph, renderer, or local-model exception.
    except Exception:
        if was_cancelled():
            return
        logger.exception("Live run %s failed", run_id)
        run.status = RunStatus.FAILED
        run.error = "run_failed"
        if store.save_run_if_not_terminal(run) is None:
            return
        emitter.emit(
            "run_failed",
            stage="failed",
            payload={
                "error_code": "run_failed",
                "message": PUBLIC_RUN_FAILURE,
            },
            template_key="run.failed",
            severity="error",
        )


__all__ = ["collect_live_jobs", "effective_search_request", "run_live_workflow"]

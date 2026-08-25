from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any

from .ranking import rank_jobs
from .schemas import (
    AgentRole,
    AgentStatus,
    Approval,
    ApprovalKind,
    ApprovalStatus,
    Artifact,
    EventUI,
    GraphEvent,
    JobRecord,
    PipelineStatus,
    RunStatus,
    build_integrity_snapshot,
)
from .storage import SQLiteStore
from .workflow import build_graph, synthetic_jobs, synthetic_profile

if TYPE_CHECKING:
    from .agents import DeepSeekAgentRegistry

logger = logging.getLogger(__name__)
PUBLIC_RUN_FAILURE = "The local run failed; inspect local logs"


def _sync_ranked_pipeline_statuses(
    store: SQLiteStore,
    jobs: list[JobRecord],
    ranked_jobs: list[dict[str, Any]],
) -> None:
    """Project persisted pipeline state into the ranked copies rendered by the UI."""

    statuses = {job.job_id: str(job.pipeline_status) for job in jobs}
    for item in ranked_jobs:
        raw_job = item.get("job", {})
        job_id = str(raw_job.get("job_id", ""))
        if job_id not in statuses:
            stored = store.get_job(job_id)
            if stored is not None:
                statuses[job_id] = str(stored.pipeline_status)
        if job_id in statuses:
            raw_job["pipeline_status"] = statuses[job_id]


def _set_pipeline_status(
    store: SQLiteStore,
    jobs: list[JobRecord],
    ranked_jobs: list[dict[str, Any]],
    job_ids: list[str] | set[str],
    status: PipelineStatus,
) -> None:
    """Persist a real pipeline transition and keep the run projection in sync."""

    target_ids = set(job_ids)
    by_id = {job.job_id: job for job in jobs}
    for job_id in target_ids:
        job = by_id.get(job_id) or store.get_job(job_id)
        if job is None:
            continue
        job.pipeline_status = status
        store.save_job(job)
        by_id[job_id] = job
    _sync_ranked_pipeline_statuses(store, list(by_id.values()), ranked_jobs)


def _set_ranked_analysis_statuses(
    store: SQLiteStore,
    jobs: list[JobRecord],
    ranked_jobs: list[dict[str, Any]],
) -> None:
    """Mark certain matches eligible and every other analyzed result analyzed."""

    status_by_id = {
        str(item.get("job", {}).get("job_id", "")): (
            PipelineStatus.ELIGIBLE
            if item.get("eligible") is True
            else PipelineStatus.ANALYZED
        )
        for item in ranked_jobs
    }
    by_id = {job.job_id: job for job in jobs}
    for job_id, status in status_by_id.items():
        job = by_id.get(job_id) or store.get_job(job_id)
        if job is None:
            continue
        job.pipeline_status = status
        store.save_job(job)
        by_id[job_id] = job
    _sync_ranked_pipeline_statuses(store, list(by_id.values()), ranked_jobs)


class EventEmitter:
    def __init__(self, store: SQLiteStore, run_id: str):
        self.store = store
        self.run_id = run_id

    def emit(
        self,
        event_type: str,
        *,
        stage: str,
        actor_id: str = "workflow",
        actor_kind: str = "workflow",
        target_id: str | None = None,
        entity_ref: str | None = None,
        payload: dict[str, Any] | None = None,
        template_key: str | None = None,
        template_args: dict[str, Any] | None = None,
        severity: str = "info",
        progress: float | None = None,
        causation_id: str | None = None,
    ) -> GraphEvent:
        event = GraphEvent(
            run_id=self.run_id,
            # SQLiteStore assigns the real sequence atomically with the insert.
            sequence=1,
            type=event_type,
            stage=stage,
            actor_id=actor_id,
            actor_kind=actor_kind,
            target_id=target_id,
            entity_ref=entity_ref,
            causation_id=causation_id,
            payload=payload or {},
            visibility="user",
            ui=EventUI(
                template_key=(
                    template_key
                    if template_key and template_key.startswith("event.")
                    else f"event.{template_key or event_type}"
                ),
                template_args=template_args or {},
                severity=severity,
                progress=progress,
            ),
        )
        return self.store.append_event(event)


async def run_synthetic_replay(
    store: SQLiteStore,
    run_id: str,
    *,
    delay_ms: int = 0,
    use_model: bool = False,
    agent_registry: DeepSeekAgentRegistry | None = None,
    auto_approve: bool = False,
    checkpointer: Any = None,
    recovery: bool = False,
) -> None:
    run = store.get_run(run_id)
    if run is None:
        raise KeyError(run_id)
    if recovery:
        await _recover_synthetic_replay(
            store,
            run_id,
            use_model=use_model,
            agent_registry=agent_registry,
            checkpointer=checkpointer,
        )
        return
    emitter = EventEmitter(store, run_id)
    delay = delay_ms / 1000

    async def pause() -> None:
        if delay:
            await asyncio.sleep(delay)

    def was_cancelled() -> bool:
        current = store.get_run(run_id)
        return current is None or current.status == RunStatus.CANCELLED

    async def approval_gate(
        kind: ApprovalKind,
        *,
        stage: str,
        payload: dict[str, Any],
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
                    str(item) for item in payload.get("entity_ids", [])
                ],
                max_selected=3 if kind == ApprovalKind.SHORTLIST_SELECTION else None,
                integrity_snapshot=integrity_snapshot,
                artifact_version=payload.get("artifact_version"),
                payload=payload,
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
                        "entity_ids": payload.get("entity_ids", []),
                        "artifact_version": payload.get("artifact_version"),
                        "allowed_decisions": allowed_decisions,
                        "summary": payload.get("summary", ""),
                    }
                },
                template_key="approval.requested",
            )
        if was_pending and auto_approve:
            approval.status = ApprovalStatus.APPROVED
            approval.decision_payload = {"automatic": True, **payload}
            from .schemas import utc_now

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
                await asyncio.sleep(0.1)
        if was_pending:
            emitter.emit(
                "approval_resolved",
                stage=stage,
                actor_kind="user",
                actor_id="replay_user" if auto_approve else "local_user",
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
        run.result = {key: value for key, value in run.result.items() if key != "pending_approval_id"}
        if store.save_run_if_not_terminal(run) is None:
            return None
        return approval

    try:
        run.status = RunStatus.RUNNING
        if store.save_run_if_not_terminal(run) is None:
            return
        emitter.emit("run_started", stage="profile", template_key="run.started")
        await pause()
        if was_cancelled():
            return

        profile = synthetic_profile()
        profile.confirmed = False
        store.save_profile(profile)
        emitter.emit(
            "agent_started",
            stage="profile",
            actor_kind="agent",
            actor_id=AgentRole.COORDINATOR,
            payload={"status": AgentStatus.WORKING},
            template_key="profile.ready",
            template_args={"facts": len(profile.facts)},
        )
        if not await approval_gate(
            ApprovalKind.PROFILE_CONFIRMATION,
            stage="profile",
            payload={
                "entity_ids": [profile.profile_id],
                "artifact_version": profile.version,
                "summary": "Confirm the extracted profile facts before they may be used.",
            },
            allowed_decisions=["approve", "reject"],
            integrity_snapshot=build_integrity_snapshot(profile=profile),
        ):
            return
        profile.confirmed = True
        store.save_profile(profile)
        await pause()
        if was_cancelled():
            return

        jobs = synthetic_jobs()
        for job in jobs:
            store.save_job(job)
        emitter.emit(
            "agent_started",
            stage="search",
            actor_kind="agent",
            actor_id=AgentRole.SCOUT,
            payload={"status": AgentStatus.WORKING},
            template_key="scout.started",
            template_args={"sources": 1},
        )
        emitter.emit(
            "agent_progress",
            stage="search",
            actor_kind="agent",
            actor_id=AgentRole.SCOUT,
            payload={"found": len(jobs)},
            template_key="scout.completed",
            template_args={"found": len(jobs), "duplicates": 0},
            progress=1,
        )
        emitter.emit(
            "agent_completed",
            stage="search",
            actor_kind="agent",
            actor_id=AgentRole.SCOUT,
            payload={"found": len(jobs)},
            template_key="scout.completed",
            template_args={"found": len(jobs), "duplicates": 0},
            progress=1,
        )
        await pause()
        if was_cancelled():
            return

        emitter.emit(
            "agent_started",
            stage="analysis",
            actor_kind="agent",
            actor_id=AgentRole.FIT_ANALYST,
            payload={"status": AgentStatus.WORKING},
            template_key="fit.started",
            template_args={"jobs": len(jobs)},
        )
        ranked_items = rank_jobs(jobs, profile)
        ranked = [item.model_dump(mode="json") for item in ranked_items]
        _set_ranked_analysis_statuses(store, jobs, ranked)
        suggested = [item.job.job_id for item in ranked_items if item.eligible is not False][:3]
        run.result = {
            **run.result,
            "profile_id": profile.profile_id,
            "job_ids": [job.job_id for job in jobs],
            "ranked_jobs": ranked,
        }
        if store.save_run_if_not_terminal(run) is None:
            return
        emitter.emit(
            "agent_progress",
            stage="analysis",
            actor_kind="agent",
            actor_id=AgentRole.FIT_ANALYST,
            payload={"analyzed": len(ranked)},
            template_key="fit.completed",
            template_args={"eligible": len([item for item in ranked_items if item.eligible is not False])},
            progress=1,
        )
        shortlist = await approval_gate(
            ApprovalKind.SHORTLIST_SELECTION,
            stage="shortlist",
            payload={
                "entity_ids": suggested,
                "summary": "Select up to three synthetic vacancies to prepare.",
            },
            allowed_decisions=["select", "skip"],
            integrity_snapshot=build_integrity_snapshot(
                profile=profile, jobs=jobs
            ),
        )
        if shortlist is None:
            return
        selected = shortlist.decision_payload.get("entity_ids") or suggested
        selected = [str(job_id) for job_id in selected][:3]
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
        graph = build_graph(checkpointer=checkpointer, agent_registry=agent_registry)
        invocation = {
            "run_id": run_id,
            "mode": "replay",
            "query": run.query,
            "auto_approve": True,
            "profile": profile.model_dump(mode="json"),
            "jobs": [job.model_dump(mode="json") for job in jobs],
            "ranked_jobs": ranked,
            "selected_job_ids": selected,
            "approvals": [],
            "artifacts": [],
            "revision_count": 0,
            "use_model": use_model,
            "agent_summaries": {},
            "agent_models": {},
        }
        config = {"configurable": {"thread_id": run_id}}
        output = await asyncio.to_thread(
            graph.invoke,
            invocation,
            config,
        )
        await pause()
        if was_cancelled():
            return

        artifacts = output.get("artifacts", [])
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
        emitter.emit(
            "agent_started",
            stage="drafting",
            actor_kind="agent",
            actor_id=AgentRole.TAILOR,
            template_key="tailor.started",
            template_args={"version": 1},
        )
        for raw in artifacts:
            artifact = Artifact.model_validate(raw)
            if store.save_artifact_if_run_active(artifact) is None:
                return
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
        await pause()
        if was_cancelled():
            return

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
            template_key="review.passed" if review.get("approved") else "review.issue",
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
            "artifact_ids": [item["artifact_id"] for item in artifacts],
            "review": review,
            "agent_summaries": output.get("agent_summaries", {}),
            "agent_models": output.get("agent_models", {}),
        }
        if store.save_run_if_not_terminal(run) is None:
            return
        application = await approval_gate(
            ApprovalKind.APPLICATION_APPROVAL,
            stage="approval",
            payload={
                "entity_ids": [item["artifact_id"] for item in artifacts],
                "artifact_version": 1,
                "summary": "Approve the reviewed package before PDF export.",
            },
            allowed_decisions=["approve", "reject"],
            integrity_snapshot=build_integrity_snapshot(
                profile=profile,
                jobs=[job for job in jobs if job.job_id in set(selected)],
                artifacts=[Artifact.model_validate(item) for item in artifacts],
            ),
        )
        if application is None:
            return

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
            "profile_id": profile.profile_id,
            "job_ids": [job.job_id for job in jobs],
            "ranked_jobs": ranked,
            "artifact_ids": [item["artifact_id"] for item in artifacts],
            "review": review,
            "agent_summaries": output.get("agent_summaries", {}),
            "agent_models": output.get("agent_models", {}),
        }
        if store.save_run_if_not_terminal(run) is None:
            return
        emitter.emit(
            "run_completed",
            stage="completed",
            payload={"artifact_count": len(artifacts)},
            template_key="run.completed",
            template_args={"artifact_count": len(artifacts)},
            severity="success",
            progress=1,
        )
    except Exception:
        if was_cancelled():
            return
        logger.exception("Synthetic replay %s failed", run_id)
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
        raise


async def _recover_synthetic_replay(
    store: SQLiteStore,
    run_id: str,
    *,
    use_model: bool,
    agent_registry: DeepSeekAgentRegistry | None,
    checkpointer: Any,
) -> None:
    """Continue an interrupted deterministic replay without duplicating its gate."""

    run = store.get_run(run_id)
    if run is None:
        return
    emitter = EventEmitter(store, run_id)

    def was_cancelled() -> bool:
        current = store.get_run(run_id)
        return current is None or current.status == RunStatus.CANCELLED

    async def gate(
        kind: ApprovalKind,
        *,
        stage: str,
        gate_payload: dict[str, Any],
        allowed_decisions: list[str],
        integrity_snapshot: dict[str, Any],
        existing: Approval | None = None,
    ) -> Approval | None:
        approval = existing or store.save_approval(
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
        run.status = RunStatus.AWAITING_USER
        run.result = {
            **run.result,
            "phase": stage,
            "pending_approval_id": approval.approval_id,
        }
        if store.save_run_if_not_terminal(run) is None:
            return None
        if existing is None:
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
        was_pending = approval.status == ApprovalStatus.PENDING
        while approval.status == ApprovalStatus.PENDING:
            if was_cancelled():
                return None
            await asyncio.sleep(0.05)
            approval = store.get_approval(approval.approval_id) or approval
        if was_pending:
            emitter.emit(
                "approval_resolved",
                stage=stage,
                actor_kind="user",
                actor_id="local_user",
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

    def interrupted_approval(kind: ApprovalKind) -> Approval | None:
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
        phase = str(run.result.get("phase", "profile"))
        if phase not in {"profile", "shortlist", "approval"}:
            raise RuntimeError(f"Cannot recover unknown replay phase: {phase}")
        profile = synthetic_profile()
        stored_job_ids = [str(item) for item in run.result.get("job_ids", [])]
        jobs = [
            job for job_id in stored_job_ids if (job := store.get_job(job_id))
        ]
        if not jobs:
            jobs = synthetic_jobs()
            for job in jobs:
                store.save_job(job)
        ranked_items = rank_jobs(jobs, profile)
        ranked = [item.model_dump(mode="json") for item in ranked_items]
        suggested = [
            item.job.job_id for item in ranked_items if item.eligible is not False
        ][:3]
        selected = [str(item) for item in run.result.get("selected_job_ids", [])]

        if phase == "profile":
            approved = await gate(
                ApprovalKind.PROFILE_CONFIRMATION,
                stage="profile",
                gate_payload={
                    "entity_ids": [profile.profile_id],
                    "artifact_version": profile.version,
                    "summary": "Confirm the extracted profile facts before they may be used.",
                },
                allowed_decisions=["approve", "reject"],
                integrity_snapshot=build_integrity_snapshot(profile=profile),
                existing=interrupted_approval(ApprovalKind.PROFILE_CONFIRMATION),
            )
            if approved is None:
                return
            profile.confirmed = True
            store.save_profile(profile)
            emitter.emit(
                "agent_completed",
                stage="search",
                actor_kind="agent",
                actor_id=AgentRole.SCOUT,
                payload={"found": len(jobs)},
                template_key="scout.completed",
                template_args={"found": len(jobs), "duplicates": 0},
                progress=1,
            )
            _set_ranked_analysis_statuses(store, jobs, ranked)
        else:
            _sync_ranked_pipeline_statuses(store, jobs, ranked)

        run.result = {
            **run.result,
            "profile_id": profile.profile_id,
            "job_ids": [job.job_id for job in jobs],
            "ranked_jobs": ranked,
        }
        if store.save_run_if_not_terminal(run) is None:
            return

        if phase in {"profile", "shortlist"}:
            shortlist = await gate(
                ApprovalKind.SHORTLIST_SELECTION,
                stage="shortlist",
                gate_payload={
                    "entity_ids": suggested,
                    "summary": "Select up to three synthetic vacancies to prepare.",
                },
                allowed_decisions=["select", "skip"],
                integrity_snapshot=build_integrity_snapshot(
                    profile=profile, jobs=jobs
                ),
                existing=(
                    interrupted_approval(ApprovalKind.SHORTLIST_SELECTION)
                    if phase == "shortlist"
                    else None
                ),
            )
            if shortlist is None:
                return
            selected = [
                str(job_id)
                for job_id in (
                    shortlist.decision_payload.get("entity_ids") or suggested
                )
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
            graph = build_graph(
                checkpointer=checkpointer, agent_registry=agent_registry
            )
            config = {"configurable": {"thread_id": run.thread_id or run_id}}
            output = await asyncio.to_thread(
                graph.invoke,
                {
                    "run_id": run_id,
                    "mode": "replay",
                    "query": run.query,
                    "auto_approve": True,
                    "profile": profile.model_dump(mode="json"),
                    "jobs": [job.model_dump(mode="json") for job in jobs],
                    "ranked_jobs": ranked,
                    "selected_job_ids": selected,
                    "approvals": [],
                    "artifacts": [],
                    "revision_count": 0,
                    "use_model": use_model,
                    "agent_summaries": {},
                    "agent_models": {},
                },
                config,
            )
            if was_cancelled():
                return
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
            artifacts: list[Artifact] = []
            for raw in output.get("artifacts", []):
                artifact = store.save_artifact_if_run_active(
                    Artifact.model_validate(raw)
                )
                if artifact is None:
                    return
                artifacts.append(artifact)
            review = output.get("review", {})
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
                "artifact_ids": [item.artifact_id for item in artifacts],
                "review": review,
                "agent_summaries": output.get("agent_summaries", {}),
                "agent_models": output.get("agent_models", {}),
            }
            if store.save_run_if_not_terminal(run) is None:
                return
        else:
            artifacts = store.list_artifacts(run_id)
            review = dict(run.result.get("review", {}))
            output = dict(run.result)
            if checkpointer is not None:
                try:
                    graph = build_graph(
                        checkpointer=checkpointer, agent_registry=agent_registry
                    )
                    snapshot = await asyncio.to_thread(
                        graph.get_state,
                        {"configurable": {"thread_id": run.thread_id or run_id}},
                    )
                    output = {**output, **dict(snapshot.values)}
                    review = output.get("review", review)
                except (AttributeError, ValueError):
                    pass

        application = await gate(
            ApprovalKind.APPLICATION_APPROVAL,
            stage="approval",
            gate_payload={
                "entity_ids": [item.artifact_id for item in artifacts],
                "artifact_version": 1,
                "summary": "Approve the reviewed package before PDF export.",
            },
            allowed_decisions=["approve", "reject"],
            integrity_snapshot=build_integrity_snapshot(
                profile=profile,
                jobs=[job for job in jobs if job.job_id in set(selected)],
                artifacts=artifacts,
            ),
            existing=(
                interrupted_approval(ApprovalKind.APPLICATION_APPROVAL)
                if phase == "approval"
                else None
            ),
        )
        if application is None or was_cancelled():
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
            "artifact_ids": [item.artifact_id for item in artifacts],
            "review": review,
            "agent_summaries": output.get("agent_summaries", {}),
            "agent_models": output.get("agent_models", {}),
        }
        if store.save_run_if_not_terminal(run) is None:
            return
        emitter.emit(
            "run_completed",
            stage="completed",
            payload={"artifact_count": len(artifacts)},
            template_key="run.completed",
            template_args={"artifact_count": len(artifacts)},
            severity="success",
            progress=1,
        )
    except Exception:
        if was_cancelled():
            return
        logger.exception("Recovered synthetic replay %s failed", run_id)
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

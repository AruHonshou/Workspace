from __future__ import annotations

import asyncio
import hashlib
import secrets
import sqlite3
from contextlib import asynccontextmanager, suppress
from pathlib import Path
from typing import Annotated, Any

import httpx
from fastapi import (
    Depends,
    FastAPI,
    File,
    Header,
    HTTPException,
    Query,
    Request,
    Response,
    UploadFile,
    status,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from langgraph.checkpoint.memory import InMemorySaver

try:
    from langgraph.checkpoint.sqlite import SqliteSaver
except ModuleNotFoundError:  # Optional fallback keeps offline/replay startup executable.
    SqliteSaver = None  # type: ignore[assignment,misc]

from .agents import (
    DeepSeekAgentRegistry,
    FitAnalystProposal,
)
from .career import (
    build_deep_analysis,
    build_interview_guide,
    build_quick_result,
    cloud_safe_verified_facts,
    detect_job_language,
    extract_requirements,
    filter_verified_recent_jobs,
    run_career_search,
)
from .config import Settings
from .connectors import CONNECTOR_TYPES, search_connectors
from .credentials import CredentialStore, CredentialStoreUnavailable
from .documents import (
    UnsupportedDocument,
    extract_document_text,
    facts_from_text,
    render_application_package,
    render_artifact_pdf,
)
from .live import effective_search_request, run_live_workflow
from .ranking import normalize_manual_job, rank_jobs
from .replay import EventEmitter, run_synthetic_replay
from .schemas import (
    AgentRole,
    Approval,
    ApprovalKind,
    ApprovalResolution,
    ApprovalStatus,
    Artifact,
    CareerSearchCreate,
    CareerSearchMoreCreate,
    DataDeleteConfirmation,
    DeepFitAnalysis,
    DeepSeekKeyInput,
    DeepSeekStatus,
    Health,
    Interest,
    InterestCreate,
    JobRecord,
    ManualJobCreate,
    PipelineStatusUpdate,
    Profile,
    ProfileCreate,
    ProfileFactUpdate,
    RankedJob,
    RankRequest,
    ResumeDocument,
    Run,
    RunCreate,
    RunMode,
    RunStatus,
    SearchRequest,
    SourceKind,
    TheirStackKeyInput,
    TheirStackStatus,
    build_integrity_snapshot,
    utc_now,
)
from .storage import ActiveRunsError, SQLiteStore
from .theirstack import TheirStackClient, TheirStackError


def get_store(request: Request) -> SQLiteStore:
    return request.app.state.store


StoreDep = Annotated[SQLiteStore, Depends(get_store)]

GATE_DECISIONS: dict[ApprovalKind, list[str]] = {
    ApprovalKind.PROFILE_CONFIRMATION: ["approve", "reject"],
    ApprovalKind.SHORTLIST_SELECTION: ["select", "skip"],
    ApprovalKind.APPLICATION_APPROVAL: ["approve", "reject"],
}


def _sanitize_public_value(value: Any) -> Any:
    if isinstance(value, list):
        return [_sanitize_public_value(item) for item in value]
    if not isinstance(value, dict):
        return value
    sanitized: dict[str, Any] = {}
    for key, item in value.items():
        normalized = key.casefold()
        if normalized in {"raw", "agent_summaries", "messages"} or "prompt" in normalized:
            continue
        if normalized == "connector_errors" and isinstance(item, dict):
            sanitized[key] = {str(source): "connector_failed" for source in item}
            continue
        sanitized[key] = _sanitize_public_value(item)
    return sanitized


def _public_run(run: Run) -> Run:
    return run.model_copy(
        update={
            "result": _sanitize_public_value(run.result),
            "error": (
                "The local run failed; inspect local logs" if run.error else None
            ),
        }
    )


def _integrity_mismatches(
    store: SQLiteStore, expected: dict[str, Any]
) -> list[str]:
    if not expected:
        return ["missing_integrity_snapshot"]
    profile = None
    profile_id = (expected.get("profile") or {}).get("id")
    if profile_id:
        profile = store.get_profile(str(profile_id))
        if profile is None:
            return [f"profile:{profile_id}:missing"]
    jobs: list[JobRecord] = []
    for job_id in (expected.get("jobs") or {}):
        job = store.get_job(str(job_id))
        if job is None:
            return [f"job:{job_id}:missing"]
        jobs.append(job)
    artifacts: list[Artifact] = []
    for artifact_id in (expected.get("artifacts") or {}):
        artifact = store.get_artifact(str(artifact_id))
        if artifact is None:
            return [f"artifact:{artifact_id}:missing"]
        artifacts.append(artifact)
    current = build_integrity_snapshot(
        profile=profile,
        jobs=jobs,
        artifacts=artifacts,
    )
    mismatches: list[str] = []
    for key in ("profile", "facts", "jobs", "artifacts"):
        if expected.get(key) != current.get(key):
            mismatches.append(key)
    return mismatches


def _validated_export_sources(
    store: SQLiteStore, artifact: Artifact
) -> tuple[Profile, JobRecord]:
    approvals = reversed(store.list_approvals(artifact.run_id))
    approved: Approval | None = None
    for approval in approvals:
        if (
            approval.kind != ApprovalKind.APPLICATION_APPROVAL
            or approval.status != ApprovalStatus.APPROVED
        ):
            continue
        entity_ids = (
            approval.decision_payload.get("entity_ids")
            or approval.payload.get("entity_ids")
            or []
        )
        approved_version = approval.decision_payload.get("artifact_version")
        if approved_version is None:
            approved_version = approval.artifact_version
        if approved_version is None:
            approved_version = approval.payload.get("artifact_version")
        if artifact.artifact_id in entity_ids and approved_version == artifact.version:
            approved = approval
            break
    if approved is None:
        raise HTTPException(
            status_code=409,
            detail="A final approval for this artifact version is required before export",
        )
    mismatches = _integrity_mismatches(store, approved.integrity_snapshot)
    if mismatches:
        raise HTTPException(
            status_code=409,
            detail={
                "message": "Approved inputs changed; create and approve a new package",
                "changed": mismatches,
            },
        )

    job = store.get_job(artifact.job_id)
    profile = store.get_profile(artifact.profile_id)
    if job is None or profile is None:
        raise HTTPException(status_code=409, detail="Package source data is missing")
    verified_fact_ids = {fact.fact_id for fact in profile.facts if fact.verified}
    unsupported = [
        claim.text
        for claim in artifact.claims
        if not claim.fact_ids or not set(claim.fact_ids).issubset(verified_fact_ids)
    ]
    if unsupported:
        raise HTTPException(
            status_code=409,
            detail={"message": "Unsupported claims block export", "claims": unsupported},
        )
    return profile, job


def _spawn(app: FastAPI, coroutine: Any) -> asyncio.Task[Any]:
    task = asyncio.create_task(coroutine)
    app.state.tasks.add(task)
    task.add_done_callback(app.state.tasks.discard)
    return task


def _open_checkpointer(
    settings: Settings,
) -> tuple[Any, sqlite3.Connection | None]:
    if SqliteSaver is None:
        return InMemorySaver(), None
    connection = sqlite3.connect(
        settings.checkpoints_path,
        check_same_thread=False,
    )
    checkpointer = SqliteSaver(connection)
    checkpointer.setup()
    return checkpointer, connection


def _configured_artifacts_root(settings: Settings) -> Path:
    configured_root = settings.artifacts_dir
    is_junction = getattr(configured_root, "is_junction", lambda: False)
    if configured_root.is_symlink() or is_junction():
        raise RuntimeError("Refusing to clear a linked artifacts_dir")
    root = configured_root.resolve(strict=False)
    if root == Path(root.anchor):
        raise RuntimeError("Refusing to clear a filesystem root as artifacts_dir")
    data_root = settings.data_dir.resolve(strict=False)
    if (
        not root.is_relative_to(data_root)
        and root.name.casefold() != "artifacts"
    ):
        raise RuntimeError(
            "Refusing to clear an external directory not explicitly named artifacts"
        )
    if root.parent == Path(root.anchor):
        raise RuntimeError("Refusing to clear an artifacts directory at drive root")
    return root


def _purge_configured_artifacts(settings: Settings) -> int:
    root = _configured_artifacts_root(settings)
    root.mkdir(parents=True, exist_ok=True)
    removed = 0

    def remove_entry(path: Path) -> None:
        nonlocal removed
        if path.is_symlink():
            path.unlink(missing_ok=True)
            removed += 1
            return
        is_junction = getattr(path, "is_junction", lambda: False)
        if is_junction():
            path.rmdir()
            removed += 1
            return
        if path.is_dir():
            for child in path.iterdir():
                remove_entry(child)
            path.rmdir()
            return
        path.unlink(missing_ok=True)
        removed += 1

    for child in list(root.iterdir()):
        remove_entry(child)
    return removed


def _configured_checkpoint_path(settings: Settings) -> Path:
    data_root = settings.data_dir.resolve(strict=False)
    checkpoint = settings.checkpoints_path.resolve(strict=False)
    if checkpoint == data_root or not checkpoint.is_relative_to(data_root):
        raise RuntimeError("Checkpoint path is outside the configured data directory")
    return checkpoint


def _remove_configured_checkpoints(settings: Settings) -> int:
    checkpoint = _configured_checkpoint_path(settings)
    removed = 0
    for suffix in ("", "-wal", "-shm"):
        candidate = Path(f"{checkpoint}{suffix}")
        if candidate.parent != checkpoint.parent:
            raise RuntimeError("Invalid checkpoint sidecar path")
        if candidate.exists():
            candidate.unlink()
            removed += 1
    return removed


def create_app(*, settings: Settings | None = None, database_path: str | Path | None = None) -> FastAPI:
    configured = settings or Settings()
    if database_path is not None:
        configured.database_path = Path(database_path)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        configured.ensure_directories()
        store = SQLiteStore(configured.resolved_database_path)
        store.migrate()
        checkpointer, checkpoint_connection = _open_checkpointer(configured)
        app.state.settings = configured
        app.state.store = store
        app.state.tasks = set()
        app.state.checkpointer = checkpointer
        app.state.checkpoint_connection = checkpoint_connection
        app.state.credential_store = CredentialStore(
            configured.credential_service, configured.credential_account
        )
        app.state.theirstack_credential_store = CredentialStore(
            configured.credential_service, configured.theirstack_credential_account
        )
        app.state.agent_registry = DeepSeekAgentRegistry(
            configured, app.state.credential_store
        )
        app.state.theirstack_client = TheirStackClient(
            configured, app.state.theirstack_credential_store
        )
        app.state.theirstack_page_locks = {}
        app.state.connector_search = search_connectors
        app.state.deepseek_last_verified_at = None
        app.state.theirstack_last_verified_at = None
        app.state.theirstack_api_credits = None
        for interrupted in store.list_runs():
            if (
                interrupted.request.get("flow") == "career_search"
                and interrupted.status in {RunStatus.QUEUED, RunStatus.RUNNING}
            ):
                try:
                    career_payload = CareerSearchCreate.model_validate(
                        interrupted.request.get("payload", {})
                    )
                except ValueError:
                    continue
                _spawn(
                    app,
                    run_career_search(
                        store,
                        interrupted.run_id,
                        career_payload,
                        connector_search=app.state.connector_search,
                        ats_boards=configured.career_ats_boards,
                        agent_registry=app.state.agent_registry,
                        theirstack_client=app.state.theirstack_client,
                        max_results=configured.max_connector_results,
                    ),
                )
                continue
            if interrupted.status != RunStatus.AWAITING_USER or not interrupted.request:
                continue
            try:
                interrupted_payload = RunCreate.model_validate(interrupted.request)
            except ValueError:
                continue
            if interrupted.mode == RunMode.LIVE:
                _spawn(
                    app,
                    run_live_workflow(
                        store,
                        interrupted.run_id,
                        interrupted_payload,
                        connector_search=app.state.connector_search,
                        agent_registry=app.state.agent_registry,
                        checkpointer=app.state.checkpointer,
                        recovery=True,
                    ),
                )
            elif interrupted.mode == RunMode.REPLAY:
                _spawn(
                    app,
                    run_synthetic_replay(
                        store,
                        interrupted.run_id,
                        delay_ms=app.state.settings.replay_delay_ms,
                        use_model=interrupted_payload.use_model,
                        agent_registry=app.state.agent_registry,
                        auto_approve=interrupted_payload.auto_approve,
                        checkpointer=app.state.checkpointer,
                        recovery=True,
                    ),
                )
        yield
        tasks = list(app.state.tasks)
        for task in tasks:
            task.cancel()
        for task in tasks:
            with suppress(asyncio.CancelledError):
                await task
        active_checkpoint_connection = app.state.checkpoint_connection
        if active_checkpoint_connection is not None:
            active_checkpoint_connection.close()

    app = FastAPI(
        title="Job Orchestrator API",
        version="0.1.0",
        description="Five-role LangGraph job-search backend powered by DeepSeek",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=configured.cors_origins,
        allow_credentials=True,
        allow_methods=["*"] ,
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def session_guard(request: Request, call_next):
        public_paths = {"/", "/health", "/api/session", "/openapi.json", "/docs", "/redoc"}
        public_prefixes = ("/docs/", "/redoc/")
        if (
            request.method != "OPTIONS"
            and request.url.path not in public_paths
            and not request.url.path.startswith(public_prefixes)
        ):
            supplied = (
                request.headers.get("x-session-token")
                or request.cookies.get("job_orchestrator_session")
                or request.headers.get("authorization", "").removeprefix("Bearer ")
            )
            if not supplied or not secrets.compare_digest(supplied, configured.session_token):
                return JSONResponse(status_code=401, content={"detail": "Invalid session token"})
        return await call_next(request)

    @app.get("/", include_in_schema=False)
    async def root() -> dict[str, str]:
        return {"name": "job-orchestrator", "docs": "/docs"}

    @app.get("/health", response_model=Health)
    async def health() -> Health:
        return Health()

    @app.get("/api/session")
    async def local_session(response: Response) -> dict[str, str]:
        response.set_cookie(
            "job_orchestrator_session",
            configured.session_token,
            httponly=True,
            samesite="strict",
            secure=False,
        )
        return {"status": "ready"}

    def deepseek_status_payload(request: Request) -> DeepSeekStatus:
        try:
            configured_key = bool(request.app.state.credential_store.get())
        except CredentialStoreUnavailable as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        return DeepSeekStatus(
            configured=configured_key,
            model=configured.deepseek_model,
            last_verified_at=request.app.state.deepseek_last_verified_at,
        )

    @app.get("/api/settings/deepseek", response_model=DeepSeekStatus)
    async def get_deepseek_settings(request: Request) -> DeepSeekStatus:
        return deepseek_status_payload(request)

    @app.put("/api/settings/deepseek", response_model=DeepSeekStatus)
    async def put_deepseek_settings(
        payload: DeepSeekKeyInput, request: Request
    ) -> DeepSeekStatus:
        api_key = payload.api_key.strip()
        try:
            async with httpx.AsyncClient(
                base_url="https://api.deepseek.com",
                timeout=min(configured.request_timeout_seconds, 30),
                follow_redirects=False,
            ) as client:
                response = await client.get(
                    "/models",
                    headers={"Authorization": f"Bearer {api_key}"},
                )
                response.raise_for_status()
                model_payload = response.json()
        except httpx.HTTPStatusError as exc:
            code = exc.response.status_code
            detail = (
                "DeepSeek rechazó la API key"
                if code in {401, 403}
                else "DeepSeek no pudo validar la clave; revisa el estado de la cuenta"
            )
            raise HTTPException(status_code=422, detail=detail) from exc
        except (httpx.HTTPError, ValueError) as exc:
            raise HTTPException(
                status_code=503,
                detail="No se pudo conectar con DeepSeek desde el backend",
            ) from exc
        model_items = model_payload.get("data", []) if isinstance(model_payload, dict) else []
        available_models = {
            item.get("id")
            for item in model_items
            if isinstance(item, dict)
        }
        if available_models and configured.deepseek_model not in available_models:
            raise HTTPException(
                status_code=422,
                detail=f"El modelo {configured.deepseek_model} no está disponible para esta cuenta",
            )
        try:
            request.app.state.credential_store.set(api_key)
        except CredentialStoreUnavailable as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        request.app.state.deepseek_last_verified_at = utc_now()
        return deepseek_status_payload(request)

    @app.delete("/api/settings/deepseek", response_model=DeepSeekStatus)
    async def delete_deepseek_settings(request: Request) -> DeepSeekStatus:
        try:
            request.app.state.credential_store.delete()
        except CredentialStoreUnavailable as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        request.app.state.deepseek_last_verified_at = None
        return deepseek_status_payload(request)

    def theirstack_status_payload(request: Request) -> TheirStackStatus:
        try:
            configured_key = bool(request.app.state.theirstack_credential_store.get())
        except CredentialStoreUnavailable as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        return TheirStackStatus(
            configured=configured_key,
            batch_size=configured.theirstack_batch_size,
            api_credits=request.app.state.theirstack_api_credits,
            last_verified_at=request.app.state.theirstack_last_verified_at,
        )

    @app.get("/api/settings/theirstack", response_model=TheirStackStatus)
    async def get_theirstack_settings(request: Request) -> TheirStackStatus:
        return theirstack_status_payload(request)

    @app.put("/api/settings/theirstack", response_model=TheirStackStatus)
    async def put_theirstack_settings(
        payload: TheirStackKeyInput, request: Request
    ) -> TheirStackStatus:
        api_key = payload.api_key.strip()
        try:
            api_credits = await request.app.state.theirstack_client.validate_key(api_key)
        except TheirStackError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        try:
            request.app.state.theirstack_credential_store.set(api_key)
        except CredentialStoreUnavailable as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        request.app.state.theirstack_last_verified_at = utc_now()
        request.app.state.theirstack_api_credits = api_credits
        return theirstack_status_payload(request)

    @app.delete("/api/settings/theirstack", response_model=TheirStackStatus)
    async def delete_theirstack_settings(request: Request) -> TheirStackStatus:
        try:
            request.app.state.theirstack_credential_store.delete()
        except CredentialStoreUnavailable as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        request.app.state.theirstack_last_verified_at = None
        request.app.state.theirstack_api_credits = None
        return theirstack_status_payload(request)

    @app.post("/profiles", response_model=Profile, status_code=status.HTTP_201_CREATED)
    @app.post("/api/profiles", response_model=Profile, status_code=status.HTTP_201_CREATED)
    async def create_profile(payload: ProfileCreate, store: StoreDep) -> Profile:
        return store.save_profile(Profile(**payload.model_dump()))

    @app.post("/api/profiles/import", response_model=dict[str, Any], status_code=status.HTTP_201_CREATED)
    @app.post("/profiles/import", response_model=dict[str, Any], status_code=status.HTTP_201_CREATED)
    async def import_profile(
        store: StoreDep,
        file: Annotated[UploadFile, File()],
        name: Annotated[str | None, Query()] = None,
        language: Annotated[str | None, Query(pattern="^(es|en)$")] = None,
        profile_id: Annotated[str | None, Query()] = None,
    ) -> dict[str, Any]:
        content = await file.read(10 * 1024 * 1024 + 1)
        if len(content) > 10 * 1024 * 1024:
            raise HTTPException(status_code=413, detail="Document exceeds 10 MB")
        try:
            extraction = await asyncio.to_thread(
                extract_document_text,
                file.filename or "resume.txt",
                content,
            )
        except UnsupportedDocument as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        document_id = f"document_{hashlib.sha256(content).hexdigest()}"
        filename = Path(file.filename or "resume.txt").name
        imported_facts = facts_from_text(
            extraction.text,
            source_document_id=document_id,
            language=language,
        )
        profile = store.get_profile(profile_id) if profile_id else None
        if profile_id and profile is None:
            raise HTTPException(status_code=404, detail="Profile not found")
        if profile is None:
            profile = Profile(
                name=name or Path(filename).stem,
                resume_text=extraction.text,
                facts=imported_facts,
                confirmed=False,
            )
        elif language:
            profile.facts = [
                fact for fact in profile.facts if fact.language != language
            ] + imported_facts
            profile.version += 1
            profile.updated_at = utc_now()
            profile.confirmed = False
        else:
            profile.resume_text = extraction.text
            profile.facts = imported_facts
            profile.version += 1
            profile.updated_at = utc_now()
            profile.confirmed = False
        if language:
            profile.resumes[language] = ResumeDocument(
                document_id=document_id,
                language=language,
                filename=filename,
                text=extraction.text,
                extraction_method=extraction.method,
                warnings=extraction.warnings,
            )
            profile.resume_text = "\n\n".join(
                item.text for item in profile.resumes.values() if item.text
            )
        store.save_profile(profile)
        return {
            "profile": profile.model_dump(mode="json"),
            "extraction_method": extraction.method,
            "warnings": extraction.warnings,
        }

    @app.get("/profiles", response_model=list[Profile])
    @app.get("/api/profiles", response_model=list[Profile])
    async def list_profiles(store: StoreDep) -> list[Profile]:
        return store.list_profiles()

    @app.get("/profiles/{profile_id}", response_model=Profile)
    @app.get("/api/profiles/{profile_id}", response_model=Profile)
    async def get_profile(profile_id: str, store: StoreDep) -> Profile:
        profile = store.get_profile(profile_id)
        if profile is None:
            raise HTTPException(status_code=404, detail="Profile not found")
        return profile

    @app.patch("/api/profile-facts/{fact_id}", response_model=Profile)
    async def patch_profile_fact(
        fact_id: str,
        payload: ProfileFactUpdate,
        store: StoreDep,
    ) -> Profile:
        for profile in store.list_profiles():
            for fact in profile.facts:
                if fact.fact_id != fact_id:
                    continue
                if payload.text is not None:
                    fact.text = payload.text.strip()
                    fact.version += 1
                    fact.verified = False
                    fact.verified_at = None
                if payload.verified is not None:
                    fact.verified = payload.verified
                    fact.verified_at = utc_now() if payload.verified else None
                profile.version += 1
                profile.updated_at = utc_now()
                variants_ready = not profile.resumes or {"es", "en"}.issubset(
                    profile.resumes
                )
                profile.confirmed = (
                    variants_ready
                    and bool(profile.facts)
                    and all(item.verified for item in profile.facts)
                )
                return store.save_profile(profile)
        raise HTTPException(status_code=404, detail="Profile fact not found")

    @app.post("/api/profiles/{profile_id}/confirm", response_model=Profile)
    async def confirm_profile(profile_id: str, store: StoreDep) -> Profile:
        profile = store.get_profile(profile_id)
        if profile is None:
            raise HTTPException(status_code=404, detail="Profile not found")
        if not profile.facts:
            raise HTTPException(status_code=409, detail="The résumé contains no reviewable facts")
        if profile.resumes and not {"es", "en"}.issubset(profile.resumes):
            raise HTTPException(
                status_code=409,
                detail="Upload both the Spanish and English résumé before confirming",
            )
        now = utc_now()
        for fact in profile.facts:
            fact.verified = True
            fact.verified_at = now
        profile.confirmed = True
        profile.version += 1
        profile.updated_at = now
        return store.save_profile(profile)

    @app.post("/api/jobs/manual", response_model=JobRecord, status_code=status.HTTP_201_CREATED)
    @app.post("/jobs/manual", response_model=JobRecord, status_code=status.HTTP_201_CREATED)
    async def create_manual_job(payload: ManualJobCreate, store: StoreDep) -> JobRecord:
        portal_sources = {
            SourceKind.LINKEDIN,
            SourceKind.INDEED,
            SourceKind.GLASSDOOR,
            SourceKind.COMPUTRABAJO,
        }
        if payload.source not in portal_sources | {SourceKind.MANUAL}:
            raise HTTPException(
                status_code=422,
                detail="Manual import accepts only an official page or a supported portal",
            )
        if payload.url is None or payload.posted_at is None:
            raise HTTPException(
                status_code=422,
                detail="Manual imports require the publication URL and exact publication time",
            )
        return store.save_job(normalize_manual_job(payload))

    @app.post("/api/jobs/search", response_model=dict[str, Any])
    @app.post("/jobs/search", response_model=dict[str, Any])
    async def search_jobs(payload: SearchRequest, request: Request, store: StoreDep) -> dict[str, Any]:
        if payload.sources == [SourceKind.REPLAY]:
            from .workflow import synthetic_jobs

            jobs, errors = synthetic_jobs()[: payload.limit], {}
        else:
            jobs, errors = await search_connectors(
                payload, timeout=request.app.state.settings.request_timeout_seconds
            )
        saved = [store.save_job(job) for job in jobs]
        return {
            "jobs": [job.model_dump(mode="json") for job in saved],
            "errors": errors,
        }

    @app.get("/jobs", response_model=list[JobRecord])
    @app.get("/api/jobs", response_model=list[JobRecord])
    async def list_jobs(
        store: StoreDep,
        limit: Annotated[int, Query(ge=1, le=500)] = 100,
        query: Annotated[str | None, Query(max_length=200)] = None,
    ) -> list[JobRecord]:
        return store.search_jobs_text(query, limit) if query else store.list_jobs(limit)

    @app.get("/api/jobs/{job_id}", response_model=JobRecord)
    @app.get("/jobs/{job_id}", response_model=JobRecord)
    async def get_job(job_id: str, store: StoreDep) -> JobRecord:
        job = store.get_job(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Job not found")
        return job

    @app.post("/api/career/searches", response_model=Run, status_code=status.HTTP_202_ACCEPTED)
    async def create_career_search(
        payload: CareerSearchCreate, request: Request, store: StoreDep
    ) -> Run:
        profile = store.get_profile(payload.profile_id)
        if profile is None:
            raise HTTPException(status_code=404, detail="Profile not found")
        if not profile.confirmed or not any(fact.verified for fact in profile.facts):
            raise HTTPException(
                status_code=409,
                detail="Review and confirm your résumé before searching",
            )
        if profile.resumes and not {"es", "en"}.issubset(profile.resumes):
            raise HTTPException(
                status_code=409,
                detail="Upload and confirm both résumé languages before searching",
            )
        try:
            if not request.app.state.credential_store.get():
                raise HTTPException(
                    status_code=409,
                    detail="Configure and validate your DeepSeek API key before searching",
                )
        except CredentialStoreUnavailable as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        run = Run(
            mode=RunMode.LIVE,
            status=RunStatus.QUEUED,
            profile_id=profile.profile_id,
            query=payload.role.strip(),
            request={"flow": "career_search", "payload": payload.model_dump(mode="json")},
        )
        store.save_run(run)
        _spawn(
            request.app,
            run_career_search(
                store,
                run.run_id,
                payload,
                connector_search=request.app.state.connector_search,
                ats_boards=request.app.state.settings.career_ats_boards,
                agent_registry=request.app.state.agent_registry,
                theirstack_client=request.app.state.theirstack_client,
                max_results=request.app.state.settings.max_connector_results,
            ),
        )
        return _public_run(run)

    @app.get("/api/career/searches/{run_id}", response_model=Run)
    async def get_career_search(run_id: str, store: StoreDep) -> Run:
        run = store.get_run(run_id)
        if run is None or run.request.get("flow") != "career_search":
            raise HTTPException(status_code=404, detail="Career search not found")
        return _public_run(run)

    @app.post("/api/career/searches/{run_id}/more", response_model=Run)
    async def load_more_career_results(
        run_id: str,
        payload: CareerSearchMoreCreate,
        request: Request,
        store: StoreDep,
    ) -> Run:
        locks: dict[str, asyncio.Lock] = request.app.state.theirstack_page_locks
        lock = locks.setdefault(run_id, asyncio.Lock())
        async with lock:
            run = store.get_run(run_id)
            if run is None or run.request.get("flow") != "career_search":
                raise HTTPException(status_code=404, detail="Career search not found")
            if run.status != RunStatus.COMPLETED:
                raise HTTPException(status_code=409, detail="The search is not complete")
            loaded_pages = [int(value) for value in run.result.get("loaded_pages", [])]
            if payload.page in loaded_pages:
                return _public_run(run)
            next_page = run.result.get("next_page")
            if run.result.get("provider") != "theirstack" or not run.result.get("can_load_more"):
                raise HTTPException(status_code=409, detail="There are no more TheirStack results")
            if next_page is None or payload.page != int(next_page):
                raise HTTPException(status_code=409, detail="Request the next available page")
            profile = store.get_profile(run.profile_id or "")
            if profile is None:
                raise HTTPException(status_code=404, detail="Profile not found")
            role = str(run.result.get("role") or run.query)
            aliases = [str(value) for value in run.result.get("aliases", [])]
            try:
                page_result = await request.app.state.theirstack_client.search_page(
                    role=role,
                    aliases=aliases,
                    page=payload.page,
                )
            except TheirStackError as exc:
                raise HTTPException(status_code=503, detail=str(exc)) from exc
            valid_jobs, rejected = filter_verified_recent_jobs(
                page_result.jobs,
                search_started_at=run.created_at,
                window_days=30,
            )
            valid_jobs = [store.save_job(job) for job in valid_jobs]
            incoming = [
                build_quick_result(job, profile).model_dump(mode="json")
                for job in valid_jobs
            ]
            merged_by_id = {
                str(item["job_id"]): item
                for item in [*run.result.get("career_results", []), *incoming]
                if isinstance(item, dict) and item.get("job_id")
            }
            merged = list(merged_by_id.values())
            merged.sort(
                key=lambda item: (
                    float((item.get("fit_summary") or {}).get("score", 0)),
                    str(item.get("published_at", "")),
                ),
                reverse=True,
            )
            coverage = dict(run.result.get("coverage") or {})
            coverage["retrieved"] = int(coverage.get("retrieved", 0)) + len(page_result.jobs)
            coverage["accepted"] = len(merged)
            aggregate_rejected = dict(coverage.get("rejected") or {})
            for reason, count in rejected.items():
                aggregate_rejected[reason] = int(aggregate_rejected.get(reason, 0)) + count
            coverage["rejected"] = aggregate_rejected
            loaded_pages.append(payload.page)
            run.result = {
                **run.result,
                "career_results": merged,
                "total_available": page_result.total_available or run.result.get("total_available"),
                "retrieved_count": len(merged),
                "next_page": payload.page + 1 if page_result.can_load_more else None,
                "can_load_more": page_result.can_load_more,
                "loaded_pages": sorted(set(loaded_pages)),
                "coverage": coverage,
            }
            store.save_run(run)
            return _public_run(run)

    @app.get("/api/jobs/{job_id}/analysis", response_model=DeepFitAnalysis)
    async def get_deep_fit_analysis(
        job_id: str,
        profile_id: Annotated[str, Query()],
        request: Request,
        store: StoreDep,
    ) -> DeepFitAnalysis:
        job = store.get_job(job_id)
        profile = store.get_profile(profile_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Job not found")
        if profile is None:
            raise HTTPException(status_code=404, detail="Profile not found")
        if not profile.confirmed:
            raise HTTPException(status_code=409, detail="Résumé profile is not confirmed")
        analysis = build_deep_analysis(job, profile)
        safe_facts = cloud_safe_verified_facts(
            profile,
            language=analysis.resume_language,
        )
        try:
            proposed = await asyncio.to_thread(
                request.app.state.agent_registry.invoke,
                AgentRole.FIT_ANALYST,
                {
                    "verified_profile_facts": safe_facts,
                    "jobs": [
                        {
                            "job_id": job.job_id,
                            "title": job.title,
                            "requirements": [
                                {"index": index, "text": requirement}
                                for index, requirement in enumerate(
                                    extract_requirements(job)
                                )
                            ],
                        }
                    ],
                    "task": "Review evidence mappings and gaps without changing the deterministic score.",
                },
            )
        except RuntimeError:
            # The evidence-based local analysis remains useful if the model provider
            # is briefly unavailable; no model-authored claim is merged silently.
            return analysis
        if isinstance(proposed.structured, FitAnalystProposal):
            offered_facts = {item["fact_id"] for item in safe_facts}
            for mapping in proposed.structured.mappings:
                if mapping.job_id != job.job_id:
                    return analysis
                if not set(mapping.fact_ids).issubset(offered_facts):
                    return analysis
                if any(
                    index >= len(extract_requirements(job))
                    for index in mapping.gap_requirement_indices
                ):
                    return analysis
        return analysis

    async def finish_interview_guide(
        *,
        interest_id: str,
        app: FastAPI,
        store: SQLiteStore,
    ) -> None:
        interest = store.get_interest(interest_id)
        if interest is None or not interest.guide_run_id:
            return
        guide_run = store.get_run(interest.guide_run_id)
        job = store.get_job(interest.job_id)
        profile = store.get_profile(interest.profile_id)
        if guide_run is None or job is None or profile is None:
            return
        emitter = EventEmitter(store, guide_run.run_id)
        try:
            emitter.emit(
                "stage_entered",
                stage="analysis",
                actor_kind="workflow",
                actor_id="career_assistant",
                template_key="career.guide.analyzing",
                progress=0.25,
            )
            interest.analysis = build_deep_analysis(job, profile)
            emitter.emit(
                "stage_entered",
                stage="writing",
                actor_kind="workflow",
                actor_id="career_assistant",
                template_key="career.guide.writing",
                template_args={"language": interest.guide_language.upper()},
                progress=0.5,
            )
            artifact = build_interview_guide(
                interest=interest,
                job=job,
                profile=profile,
            )
            output_path = (
                app.state.settings.artifacts_dir
                / "interview-guides"
                / f"{artifact.artifact_id}.pdf"
            )
            emitter.emit(
                "stage_entered",
                stage="rendering",
                actor_kind="workflow",
                actor_id="career_assistant",
                template_key="career.guide.rendering",
                progress=0.75,
            )
            await asyncio.to_thread(
                render_artifact_pdf,
                artifact,
                output_path,
                styled=True,
            )
            if (
                not output_path.is_file()
                or output_path.stat().st_size < 800
                or output_path.read_bytes()[:4] != b"%PDF"
            ):
                raise RuntimeError("PDF renderer did not produce a valid file")
            store.save_artifact(artifact)
            interest.guide_artifact_id = artifact.artifact_id
            interest.guide_status = "ready"
            interest.guide_error = None
            saved = store.save_interest(interest)
            guide_run.status = RunStatus.COMPLETED
            guide_run.result = {
                "interest_id": saved.interest_id,
                "guide_artifact_id": artifact.artifact_id,
            }
            store.save_run(guide_run)
            emitter.emit(
                "run_completed",
                stage="completed",
                actor_kind="workflow",
                actor_id="career_assistant",
                template_key="career.guide.ready",
                severity="success",
                progress=1,
            )
        except Exception:  # noqa: BLE001 - background failures become a safe visible state
            interest.guide_status = "failed"
            interest.guide_error = (
                "No se pudo crear el PDF. Puedes reintentar desde esta vacante."
            )
            store.save_interest(interest)
            guide_run.status = RunStatus.FAILED
            guide_run.result = {"error_code": "interview_guide_generation_failed"}
            store.save_run(guide_run)
            emitter.emit(
                "run_failed",
                stage="failed",
                actor_kind="workflow",
                actor_id="career_assistant",
                payload={"error": "interview_guide_generation_failed"},
                template_key="career.guide.failed",
                severity="error",
                progress=1,
            )

    @app.post(
        "/api/jobs/{job_id}/interests",
        response_model=Interest,
        status_code=status.HTTP_202_ACCEPTED,
    )
    async def create_interest(
        job_id: str,
        payload: InterestCreate,
        request: Request,
        store: StoreDep,
    ) -> Interest:
        existing = store.get_interest_for_job(payload.profile_id, job_id)
        if existing and existing.guide_status == "ready" and existing.guide_artifact_id:
            return existing
        job = store.get_job(job_id)
        profile = store.get_profile(payload.profile_id)
        run = store.get_run(payload.run_id)
        if job is None or profile is None or run is None:
            raise HTTPException(status_code=404, detail="Job, profile, or search not found")
        if run.profile_id != profile.profile_id:
            raise HTTPException(status_code=409, detail="Search and profile do not match")
        if not profile.confirmed:
            raise HTTPException(status_code=409, detail="Résumé profile is not confirmed")
        if job.url is None or job.posted_at is None:
            raise HTTPException(
                status_code=409,
                detail="The job needs a verified official URL and publication date",
            )
        if existing and existing.guide_status == "preparing" and existing.guide_run_id:
            active_guide_run = store.get_run(existing.guide_run_id)
            if active_guide_run and active_guide_run.status in {
                RunStatus.QUEUED,
                RunStatus.RUNNING,
            }:
                return existing
        guide_run = Run(
            mode=RunMode.LIVE,
            status=RunStatus.RUNNING,
            profile_id=profile.profile_id,
            query=job.title,
            request={"flow": "interview_guide", "job_id": job.job_id},
        )
        store.save_run(guide_run)
        interest = existing or Interest(
            profile_id=profile.profile_id,
            job_id=job.job_id,
            run_id=run.run_id,
            guide_run_id=guide_run.run_id,
            job_title=job.title,
            company=job.company,
            official_apply_url=job.url,
            published_at=job.posted_at,
            analysis=build_deep_analysis(job, profile),
            guide_language=detect_job_language(job),
        )
        interest.guide_run_id = guide_run.run_id
        interest.guide_artifact_id = None
        interest.guide_status = "preparing"
        interest.guide_error = None
        saved = store.save_interest(interest)
        emitter = EventEmitter(store, guide_run.run_id)
        emitter.emit(
            "run_started",
            stage="interview_guide",
            actor_kind="workflow",
            actor_id="career_assistant",
            template_key="career.guide.started",
            template_args={"role": job.title},
            progress=0.05,
        )
        _spawn(
            request.app,
            finish_interview_guide(
                interest_id=saved.interest_id,
                app=request.app,
                store=store,
            ),
        )
        return saved

    @app.get("/api/interests", response_model=list[Interest])
    async def list_interests(
        store: StoreDep,
        profile_id: Annotated[str | None, Query()] = None,
    ) -> list[Interest]:
        return store.list_interests(profile_id)

    @app.get("/api/interests/{interest_id}", response_model=Interest)
    async def get_interest(interest_id: str, store: StoreDep) -> Interest:
        interest = store.get_interest(interest_id)
        if interest is None:
            raise HTTPException(status_code=404, detail="Interest not found")
        return interest

    @app.delete("/api/interests/{interest_id}", status_code=status.HTTP_204_NO_CONTENT)
    async def delete_interest(interest_id: str, store: StoreDep) -> Response:
        if not store.delete_interest(interest_id):
            raise HTTPException(status_code=404, detail="Interest not found")
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    @app.get("/api/interests/{interest_id}/guide.pdf")
    async def download_interview_guide(
        interest_id: str, request: Request, store: StoreDep
    ) -> FileResponse:
        interest = store.get_interest(interest_id)
        if interest is None or not interest.guide_artifact_id:
            raise HTTPException(status_code=404, detail="Interview guide not found")
        path = (
            request.app.state.settings.artifacts_dir
            / "interview-guides"
            / f"{interest.guide_artifact_id}.pdf"
        )
        if not path.exists():
            raise HTTPException(status_code=404, detail="Interview guide file is missing")
        return FileResponse(
            path,
            media_type="application/pdf",
            filename=f"interview-guide-{interest.job_id}.pdf",
        )

    @app.post("/api/ranking", response_model=list[RankedJob])
    @app.post("/ranking", response_model=list[RankedJob])
    async def ranking(payload: RankRequest, store: StoreDep) -> list[RankedJob]:
        profile = store.get_profile(payload.profile_id)
        if profile is None:
            raise HTTPException(status_code=404, detail="Profile not found")
        jobs = (
            [job for job_id in payload.job_ids if (job := store.get_job(job_id)) is not None]
            if payload.job_ids
            else store.list_jobs()
        )
        return rank_jobs(jobs, profile)

    @app.post("/api/search-runs", response_model=Run, status_code=status.HTTP_202_ACCEPTED)
    @app.post("/runs", response_model=Run, status_code=status.HTTP_202_ACCEPTED)
    async def create_run(payload: RunCreate, request: Request, store: StoreDep) -> Run:
        profile: Profile | None = None
        if payload.mode == RunMode.LIVE:
            if payload.auto_approve:
                raise HTTPException(
                    status_code=422,
                    detail="auto_approve is allowed only for synthetic replay tests",
                )
            if not payload.profile_id:
                raise HTTPException(
                    status_code=422, detail="profile_id is required for live mode"
                )
            profile = store.get_profile(payload.profile_id)
            if profile is None:
                raise HTTPException(status_code=404, detail="Profile not found")
            if not profile.confirmed:
                raise HTTPException(
                    status_code=422,
                    detail="The profile must be confirmed before a live run",
                )
        elif payload.use_model:
            raise HTTPException(
                status_code=422,
                detail="Synthetic replay never calls DeepSeek; use_model must be false",
            )
        search_request = effective_search_request(payload)
        run = Run(
            mode=payload.mode,
            status=RunStatus.QUEUED,
            profile_id=payload.profile_id,
            query=search_request.query,
            request=payload.model_dump(mode="json"),
        )
        run.thread_id = run.run_id
        store.save_run(run)
        if payload.mode == RunMode.LIVE:
            _spawn(
                request.app,
                run_live_workflow(
                    store,
                    run.run_id,
                    payload,
                    connector_search=request.app.state.connector_search,
                    agent_registry=request.app.state.agent_registry,
                    checkpointer=request.app.state.checkpointer,
                ),
            )
        else:
            _spawn(
                request.app,
                run_synthetic_replay(
                    store,
                    run.run_id,
                    delay_ms=request.app.state.settings.replay_delay_ms,
                    use_model=payload.use_model,
                    agent_registry=request.app.state.agent_registry,
                    auto_approve=payload.auto_approve,
                    checkpointer=request.app.state.checkpointer,
                ),
            )
        return _public_run(run)

    @app.get("/api/search-runs", response_model=list[Run])
    @app.get("/runs", response_model=list[Run])
    async def list_runs(store: StoreDep) -> list[Run]:
        return [_public_run(run) for run in store.list_runs()]

    @app.get("/runs/{run_id}", response_model=Run)
    @app.get("/api/search-runs/{run_id}", response_model=Run)
    async def get_run(run_id: str, store: StoreDep) -> Run:
        run = store.get_run(run_id)
        if run is None:
            raise HTTPException(status_code=404, detail="Run not found")
        return _public_run(run)

    @app.post("/api/runs/{run_id}/cancel", response_model=Run)
    @app.post("/runs/{run_id}/cancel", response_model=Run)
    async def cancel_run(run_id: str, store: StoreDep) -> Run:
        run, changed = store.cancel_run_once(run_id)
        if run is None:
            raise HTTPException(status_code=404, detail="Run not found")
        if changed:
            EventEmitter(store, run_id).emit(
                "run_cancelled",
                stage="cancelled",
                payload={},
                template_key="run.cancelled",
                severity="warning",
            )
        return _public_run(run)

    @app.get("/runs/{run_id}/events")
    async def list_events(
        run_id: str,
        store: StoreDep,
        after: Annotated[int, Query(ge=0)] = 0,
    ) -> list[dict[str, Any]]:
        if store.get_run(run_id) is None:
            raise HTTPException(status_code=404, detail="Run not found")
        return [event.model_dump(mode="json") for event in store.list_events(run_id, after)]

    @app.get("/runs/{run_id}/events/stream")
    async def stream_events(
        run_id: str,
        request: Request,
        store: StoreDep,
        after: Annotated[int, Query(ge=0)] = 0,
    ) -> StreamingResponse:
        if store.get_run(run_id) is None:
            raise HTTPException(status_code=404, detail="Run not found")

        async def generator():
            cursor = after
            while True:
                events = store.list_events(run_id, cursor)
                for event in events:
                    cursor = event.sequence
                    data = event.model_dump_json()
                    yield f"id: {event.sequence}\nevent: {event.type}\ndata: {data}\n\n"
                run = store.get_run(run_id)
                if run is None or (run.status in {
                    RunStatus.COMPLETED,
                    RunStatus.FAILED,
                    RunStatus.CANCELLED,
                } and not events):
                    break
                if await request.is_disconnected():
                    break
                await asyncio.sleep(0.05)

        return StreamingResponse(
            generator(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    @app.get("/api/runs/{run_id}/events")
    async def api_stream_events(
        run_id: str,
        request: Request,
        store: StoreDep,
        after_sequence: Annotated[int, Query(ge=0)] = 0,
        last_event_id: Annotated[str | None, Header(alias="Last-Event-ID")] = None,
    ) -> StreamingResponse:
        if store.get_run(run_id) is None:
            raise HTTPException(status_code=404, detail="Run not found")
        cursor = after_sequence
        if last_event_id:
            try:
                cursor = max(cursor, int(last_event_id))
            except ValueError:
                raise HTTPException(status_code=400, detail="Last-Event-ID must be an integer")

        async def generator():
            nonlocal cursor
            while True:
                events = store.list_events(run_id, cursor)
                for event in events:
                    cursor = event.sequence
                    yield (
                        f"id: {event.sequence}\nevent: {event.type}\n"
                        f"data: {event.model_dump_json()}\n\n"
                    )
                run = store.get_run(run_id)
                if run is None or (
                    run.status in {RunStatus.COMPLETED, RunStatus.FAILED, RunStatus.CANCELLED}
                    and not events
                ):
                    break
                if await request.is_disconnected():
                    break
                await asyncio.sleep(0.05)

        return StreamingResponse(
            generator(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    @app.get("/runs/{run_id}/approvals", response_model=list[Approval])
    async def list_approvals(run_id: str, store: StoreDep) -> list[Approval]:
        return store.list_approvals(run_id)

    @app.post("/api/approvals/{approval_id}/decisions", response_model=Approval)
    @app.post("/approvals/{approval_id}/resolve", response_model=Approval)
    async def resolve_approval(
        approval_id: str, payload: ApprovalResolution, store: StoreDep
    ) -> Approval:
        approval = store.get_approval(approval_id)
        if approval is None:
            raise HTTPException(status_code=404, detail="Approval not found")
        if approval.status != ApprovalStatus.PENDING:
            raise HTTPException(status_code=409, detail="Approval already resolved")
        allowed_decisions = approval.allowed_decisions or GATE_DECISIONS[approval.kind]
        if payload.decision not in allowed_decisions:
            raise HTTPException(
                status_code=422,
                detail={
                    "message": "Decision is not allowed for this gate",
                    "allowed_decisions": allowed_decisions,
                },
            )
        mismatches = _integrity_mismatches(store, approval.integrity_snapshot)
        if approval.integrity_snapshot and mismatches:
            raise HTTPException(
                status_code=409,
                detail={
                    "message": "Approval inputs changed; restart this gate",
                    "changed": mismatches,
                },
            )
        try:
            approval.status = payload.normalized_status
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        offered = approval.offered_entity_ids or [
            str(item) for item in approval.payload.get("entity_ids", [])
        ]
        if approval.kind == ApprovalKind.SHORTLIST_SELECTION:
            selected = list(dict.fromkeys(str(item) for item in payload.entity_ids))
            if payload.decision == "select":
                maximum = approval.max_selected or 3
                if not selected or len(selected) > maximum:
                    raise HTTPException(
                        status_code=422,
                        detail=f"Select between 1 and {maximum} offered jobs",
                    )
                invalid = [item for item in selected if item not in offered]
                if invalid:
                    raise HTTPException(
                        status_code=422,
                        detail={
                            "message": "Selection contains jobs not offered by this gate",
                            "invalid_entity_ids": invalid,
                        },
                    )
            elif selected:
                raise HTTPException(
                    status_code=422, detail="skip may not include selected jobs"
                )
        elif approval.status == ApprovalStatus.APPROVED:
            selected = list(offered)
        else:
            selected = []
        approval.decision_payload = {
            **payload.payload,
            **payload.edits,
            "entity_ids": selected,
            "artifact_version": approval.artifact_version,
            "decision": payload.decision,
        }
        approval.resolved_at = utc_now()
        resolved = store.resolve_approval(approval)
        if resolved is None:
            raise HTTPException(status_code=409, detail="Approval already resolved")
        return resolved

    @app.get("/runs/{run_id}/artifacts", response_model=list[Artifact])
    @app.get("/api/search-runs/{run_id}/artifacts", response_model=list[Artifact])
    async def list_artifacts(run_id: str, store: StoreDep) -> list[Artifact]:
        return store.list_artifacts(run_id)

    @app.get("/artifacts/{artifact_id}.pdf")
    async def artifact_pdf(artifact_id: str, request: Request, store: StoreDep) -> FileResponse:
        artifact = store.get_artifact(artifact_id)
        if artifact is None:
            raise HTTPException(status_code=404, detail="Artifact not found")
        _validated_export_sources(store, artifact)
        path = request.app.state.settings.artifacts_dir / f"{artifact.artifact_id}.pdf"
        render_artifact_pdf(artifact, path)
        return FileResponse(path, media_type="application/pdf", filename=f"{artifact.title}.pdf")

    @app.get("/api/artifacts/{artifact_id}", response_model=Artifact)
    @app.get("/artifacts/{artifact_id}", response_model=Artifact)
    async def get_artifact(artifact_id: str, store: StoreDep) -> Artifact:
        artifact = store.get_artifact(artifact_id)
        if artifact is None:
            raise HTTPException(status_code=404, detail="Artifact not found")
        return artifact

    @app.get("/api/application-packs")
    async def list_application_packs(
        store: StoreDep,
        run_id: Annotated[str | None, Query()] = None,
    ) -> list[dict[str, Any]]:
        artifacts = store.list_artifacts(run_id) if run_id else [
            artifact
            for run in store.list_runs()
            for artifact in store.list_artifacts(run.run_id)
        ]
        return [
            {
                "id": item.artifact_id,
                "job_id": item.job_id,
                "run_id": item.run_id,
                "title": item.title,
                "version": item.version,
                "status": "ready_for_approval",
                "claims_verified": len(item.claims),
                "claims_total": len(item.claims),
                "created_at": item.created_at.isoformat(),
            }
            for item in artifacts
        ]

    @app.post("/api/application-packs/{artifact_id}/export")
    async def prepare_application_pack(
        artifact_id: str, request: Request, store: StoreDep
    ) -> dict[str, Any]:
        artifact = store.get_artifact(artifact_id)
        if artifact is None:
            raise HTTPException(status_code=404, detail="Application pack not found")
        profile, job = _validated_export_sources(store, artifact)
        rendered = render_application_package(
            artifact,
            profile,
            job,
            request.app.state.settings.artifacts_dir,
            include_cover_letter=True,
        )
        job.pipeline_status = "exported"
        store.save_job(job)
        return {
            "artifact_id": artifact.artifact_id,
            "download_url": str(
                request.url_for("download_application_pack", artifact_id=artifact.artifact_id)
            ),
            "files": [path.name for path in rendered.files],
        }

    @app.get("/api/application-packs/{artifact_id}/export", name="download_application_pack")
    async def download_application_pack(
        artifact_id: str, request: Request, store: StoreDep
    ) -> FileResponse:
        artifact = store.get_artifact(artifact_id)
        if artifact is None:
            raise HTTPException(status_code=404, detail="Application pack not found")
        profile, job = _validated_export_sources(store, artifact)
        rendered = render_application_package(
            artifact,
            profile,
            job,
            request.app.state.settings.artifacts_dir,
            include_cover_letter=True,
        )
        return FileResponse(
            rendered.zip_path,
            media_type="application/zip",
            filename=f"application-{artifact.artifact_id}.zip",
        )

    @app.get("/api/jobs/{job_id}/pipeline-status")
    async def get_pipeline_status(job_id: str, store: StoreDep) -> dict[str, str]:
        job = store.get_job(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Job not found")
        return {"job_id": job.job_id, "status": str(job.pipeline_status)}

    @app.patch("/api/jobs/{job_id}/pipeline-status")
    @app.post("/api/jobs/{job_id}/pipeline-status")
    async def set_pipeline_status(
        job_id: str, payload: PipelineStatusUpdate, store: StoreDep
    ) -> dict[str, str]:
        job = store.get_job(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Job not found")
        job.pipeline_status = payload.status
        store.save_job(job)
        return {"job_id": job.job_id, "status": str(job.pipeline_status)}

    @app.get("/connectors")
    async def connectors() -> dict[str, list[str]]:
        return {
            "network": [str(SourceKind.THEIRSTACK), *[str(source) for source in CONNECTOR_TYPES]],
            "offline": [str(SourceKind.MANUAL), str(SourceKind.REPLAY)],
        }

    @app.delete("/api/data")
    async def delete_local_data(
        payload: DataDeleteConfirmation,
        request: Request,
        store: StoreDep,
    ) -> dict[str, Any]:
        # Resolve and validate every destructive target before deleting database rows.
        try:
            _configured_artifacts_root(request.app.state.settings)
            _configured_checkpoint_path(request.app.state.settings)
        except RuntimeError as exc:
            raise HTTPException(
                status_code=409,
                detail="Configured deletion targets are unsafe; no data was deleted",
            ) from exc
        try:
            deleted = store.clear_all_data()
        except ActiveRunsError as exc:
            raise HTTPException(
                status_code=409,
                detail={
                    "message": "Local data cannot be deleted while a run is active",
                    "run_id": str(exc),
                },
            ) from exc

        checkpoint_connection = request.app.state.checkpoint_connection
        if checkpoint_connection is not None:
            checkpoint_connection.close()
            request.app.state.checkpoint_connection = None

        removed_artifact_entries = 0
        removed_checkpoint_files = 0
        try:
            removed_artifact_entries = _purge_configured_artifacts(
                request.app.state.settings
            )
            removed_checkpoint_files = _remove_configured_checkpoints(
                request.app.state.settings
            )
        finally:
            checkpointer, connection = _open_checkpointer(
                request.app.state.settings
            )
            request.app.state.checkpointer = checkpointer
            request.app.state.checkpoint_connection = connection

        return {
            "status": "deleted",
            "deleted": deleted,
            "removed_artifact_entries": removed_artifact_entries,
            "removed_checkpoint_files": removed_checkpoint_files,
        }

    @app.get("/api/data/export")
    @app.get("/export")
    async def export(store: StoreDep) -> dict[str, Any]:
        return store.export_snapshot()

    return app

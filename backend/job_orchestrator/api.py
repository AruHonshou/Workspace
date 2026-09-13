from __future__ import annotations

import asyncio
import hashlib
import logging
import os
import re
import secrets
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
from fastapi.responses import FileResponse, JSONResponse
from starlette.datastructures import UploadFile as StarletteUploadFile

from .ai_contracts import (
    AIOperation,
    ContentProposal,
    StructuredAIClient,
)
from .ats_documents import (
    render_ats_docx,
    render_ats_pdf,
)
from .career import (
    build_deep_analysis,
    build_interview_guide,
    cloud_safe_verified_facts,
    detect_job_language,
    extract_requirements,
)
from .config import Settings
from .connectors.providers import ProviderSearchQuery
from .countries import country_catalog, normalize_country_code
from .credentials import CredentialStore, CredentialStoreUnavailable
from .documents import (
    UnsupportedDocument,
    extract_document_text,
    facts_from_text,
    render_artifact_pdf,
)
from .linkedin import (
    extract_contact_values,
    parse_linkedin_sections,
    redact_contact_text,
)
from .providers.jobs import BreteProvider, JobProviderGroup
from .schemas import (
    AboutMeProfile,
    AboutMeUpdate,
    Artifact,
    ATSResume,
    ATSResumeApproval,
    ATSResumeDocument,
    ATSResumeVersion,
    Claim,
    CloudConsentDecision,
    CloudProcessingConsent,
    ConfirmationStatus,
    ConsentStatus,
    DataDeleteConfirmation,
    DeepFitAnalysisV2,
    DeepSeekKeyInput,
    DeepSeekStatus,
    GeneratedDocumentStatus,
    GuideVersionRecord,
    Health,
    InterviewGuide,
    JobApplication,
    JobApplicationCreate,
    JobApplicationEvent,
    JobApplicationUpdate,
    JobRecord,
    LinkedInManualImport,
    LinkedInOptimizationSection,
    LinkedInOptimizationVersion,
    LinkedInProfileSnapshot,
    LinkedInSectionInput,
    LinkedInSnapshotUpdate,
    PrivateContactBlock,
    Profile,
    ProfileCreate,
    ProfileDuplicateCreate,
    ProfileFact,
    ProfileFactUpdate,
    ProfileUpdate,
    RedactedProfessionalPreview,
    ResumeDocument,
    SavedJob,
    SavedJobCreate,
    TheirStackKeyInput,
    TheirStackStatus,
    normalize_bcp47,
    utc_now,
)
from .services.ai_operations import (
    build_ats_resume_operation,
    build_linkedin_optimization_operation,
    run_fit_analysis,
)
from .services.job_search import (
    JobSearchInput,
    JobSearchService,
    SearchConflict,
    SearchResult,
)
from .storage import (
    ActiveOperationsError,
    ProfileDisplayNameConflictError,
    ProfileHasActiveOperationsError,
    SQLiteStore,
)
from .theirstack import TheirStackClient, TheirStackError

logger = logging.getLogger(__name__)
_INTERNAL_EVIDENCE_ID_RE = re.compile(
    r"\[\s*fact_id\s*:\s*[^\]]+\]|\b(?:fact|about)_[A-Za-z0-9_-]+\b",
    re.IGNORECASE,
)


def _normalize_generated_guide_content(
    content: str,
    *,
    job: JobRecord,
    language: str,
) -> str:
    """Make model-authored guide prose safe and reliably renderable."""

    cleaned = _INTERNAL_EVIDENCE_ID_RE.sub("", content)
    cleaned = re.sub(
        r"\(?\s*fact ids? (?:are )?provided for traceability\s*\)?\.?",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(
        r"\s*\(\s*(?:fact\s*)?ids?\s*\)",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(
        r"\(\s*facts?\s*(?:,\s*)*\)",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(r"\(\s*(?:,\s*)*\)", "", cleaned)
    cleaned = re.sub(
        r"(?im)^\s*(?:source date|publication date|url|enlace|fecha de (?:la )?publicaci[oó]n)\s*:\s*"
        r"(?:not provided(?: in the provided data)?|not available|unknown|"
        r"no proporcionad[oa](?: en los datos)?|no disponible)\.?\s*$",
        "",
        cleaned,
    )

    # ReportLab intentionally does not interpret Markdown tables. Turn model-created
    # pipe rows into readable bullets so long evidence never overflows the page.
    normalized_lines: list[str] = []
    for raw_line in cleaned.splitlines():
        stripped = raw_line.strip()
        if re.fullmatch(
            r"(?i)(?:#{1,3}\s*)?(?:\d+[.)]\s*)?(?:"
            r"verified publication information|"
            r"informaci[oó]n verificada de la publicaci[oó]n|"
            r"source(?: date and url)?|fuente(?: y enlace)?|job source)\s*:?\s*",
            stripped,
        ):
            continue
        if re.match(
            r"(?i)^(?:source date|publication date|published|url|job listing|"
            r"fecha de (?:la )?publicaci[oó]n|enlace(?: de la vacante)?|fuente)\s*:",
            stripped,
        ):
            continue
        if "|" in stripped and not re.search(r"https?://", stripped):
            cells = [cell.strip() for cell in stripped.strip("|").split("|")]
            if cells and all(re.fullmatch(r":?-{3,}:?", cell) for cell in cells):
                continue
            if cells and any(
                marker in " ".join(cells).casefold()
                for marker in ("requirement", "evidence", "assessment", "requisito", "evidencia")
            ):
                continue
            visible_cells = [cell for cell in cells if cell]
            if visible_cells:
                label, *details = visible_cells
                normalized_lines.append(
                    f"- {label}: {'; '.join(details)}" if details else f"- {label}"
                )
            continue
        normalized_lines.append(raw_line)

    spanish = language.casefold().startswith("es")
    source_heading = (
        "## Información verificada de la publicación"
        if spanish
        else "## Verified publication information"
    )
    published_label = "Fecha de publicación" if spanish else "Published"
    source_label = "Procedencia" if spanish else "Source"
    link_label = "Enlace de la vacante" if spanish else "Job listing"
    published = job.posted_at.isoformat() if job.posted_at else (
        "No indicada" if spanish else "Not specified"
    )
    url = str(job.final_url or job.url or "")
    source_name = job.source_portal or job.source.replace("_", " ").title()
    normalized_lines.extend(
        [
            "",
            source_heading,
            f"{source_label}: {source_name}",
            f"{published_label}: {published}",
            f"{link_label}: {url}" if url else "",
        ]
    )
    return "\n".join(line for line in normalized_lines if line is not None).strip()


def _refresh_redacted_professional_preview(profile: Profile) -> None:
    """Bind cloud consent to the exact confirmed, contact-free facts sent later."""

    facts = [fact for fact in profile.facts if fact.verified and fact.text.strip()]
    text = redact_contact_text("\n".join(fact.text for fact in facts))
    profile.redacted_preview = RedactedProfessionalPreview(
        profile_revision=profile.revision + 1,
        language=None,
        redacted_text=text,
        included_record_ids=[fact.fact_id for fact in facts],
        redacted_categories=["contact"],
        content_hash=hashlib.sha256(text.encode("utf-8")).hexdigest(),
    )
    profile.cloud_processing_consent = None


def _sync_about_me_facts(
    dossier: AboutMeProfile,
    profiles: list[Profile],
    store: SQLiteStore,
) -> None:
    """Mirror explicit dossier entries into the evidence ledger of each profile."""

    for profile in profiles:
        existing_about = {
            fact.fact_id: fact
            for fact in profile.facts
            if fact.source_type == "about_me"
        }
        retained = [
            fact for fact in profile.facts if fact.source_type != "about_me"
        ]
        additions = []
        for entry in dossier.entries:
            if profile.profile_id not in entry.profile_ids:
                continue
            visible = f"{entry.title}: {entry.details}".strip()
            fact_id = f"about_{entry.entry_id}_{profile.profile_id}"
            previous = existing_about.get(fact_id)
            unchanged = bool(
                previous
                and previous.category == entry.category
                and previous.text == visible
                and previous.evidence == entry.details
                and previous.source_url == entry.url
                and previous.language == entry.language
                and previous.verified == entry.verified
            )
            if unchanged and previous is not None:
                additions.append(previous)
                continue
            additions.append(
                ProfileFact(
                    fact_id=fact_id,
                    category=entry.category,
                    text=visible,
                    evidence=entry.details,
                    source_type="about_me",
                    source_url=entry.url,
                    language=entry.language,
                    version=(previous.version + 1 if previous else 1),
                    verified=entry.verified,
                    verified_at=utc_now() if entry.verified else None,
                    created_at=previous.created_at if previous else utc_now(),
                )
            )
        if [item.model_dump() for item in profile.facts] == [
            item.model_dump() for item in [*retained, *additions]
        ]:
            continue
        profile.facts = [*retained, *additions]
        profile.version += 1
        _refresh_redacted_professional_preview(profile)
        store.save_profile(profile)


def _local_document_contact(store: SQLiteStore, profile: Profile) -> PrivateContactBlock:
    """Merge local dossier contacts into a rendered document without cloud transfer."""

    shared = store.get_about_me().contact
    own = profile.private_contact
    return PrivateContactBlock(
        full_name=own.full_name or shared.full_name,
        emails=list(dict.fromkeys([*own.emails, *shared.emails])),
        phones=list(dict.fromkeys([*own.phones, *shared.phones])),
        address_lines=list(
            dict.fromkeys([*own.address_lines, *shared.address_lines])
        ),
        city=own.city or shared.city,
        region=own.region or shared.region,
        country_code=own.country_code or shared.country_code,
        postal_code=own.postal_code or shared.postal_code,
        websites=list(dict.fromkeys([*own.websites, *shared.websites])),
    )


def get_store(request: Request) -> SQLiteStore:
    return request.app.state.store


StoreDep = Annotated[SQLiteStore, Depends(get_store)]


def _spawn(app: FastAPI, coroutine: Any) -> asyncio.Task[Any]:
    task = asyncio.create_task(coroutine)
    app.state.tasks.add(task)
    task.add_done_callback(app.state.tasks.discard)
    return task


def _configured_artifacts_root(settings: Settings) -> Path:
    configured_root = settings.artifacts_dir
    is_junction = getattr(configured_root, "is_junction", lambda: False)
    if configured_root.is_symlink() or is_junction():
        raise RuntimeError("Refusing to clear a linked artifacts_dir")
    root = configured_root.resolve(strict=False)
    if root == Path(root.anchor):
        raise RuntimeError("Refusing to clear a filesystem root as artifacts_dir")
    data_root = settings.data_dir.resolve(strict=False)
    if not root.is_relative_to(data_root) and root.name.casefold() != "artifacts":
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


def _remove_owned_artifact_files(settings: Settings, values: list[str | None]) -> int:
    """Delete only recorded document files contained by the configured artifact root."""

    root = _configured_artifacts_root(settings)
    removed = 0
    for value in dict.fromkeys(item for item in values if item):
        path = Path(value).resolve(strict=False)
        if path == root or not path.is_relative_to(root):
            logger.warning("Ignored artifact path outside configured root")
            continue
        if path.is_symlink() or path.is_file():
            path.unlink(missing_ok=True)
            removed += 1
    return removed


def create_app(
    *, settings: Settings | None = None, database_path: str | Path | None = None
) -> FastAPI:
    configured = settings or Settings()
    if database_path is not None:
        configured.database_path = Path(database_path)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        configured.ensure_directories()
        store = SQLiteStore(configured.resolved_database_path)
        store.migrate()
        store.recover_interrupted_documents()
        app.state.settings = configured
        app.state.store = store
        app.state.tasks = set()
        app.state.credential_store = CredentialStore(
            configured.credential_service,
            configured.credential_account,
            env_var="DEEPSEEK_API_KEY",
            secret_file_env_var="DEEPSEEK_API_KEY_FILE",
        )
        app.state.theirstack_credential_store = CredentialStore(
            configured.credential_service,
            configured.theirstack_credential_account,
            env_var="THEIRSTACK_API_KEY",
            secret_file_env_var="THEIRSTACK_API_KEY_FILE",
        )
        app.state.ai_client = StructuredAIClient(configured, app.state.credential_store)
        app.state.theirstack_client = TheirStackClient(
            configured, app.state.theirstack_credential_store
        )
        app.state.theirstack_page_locks = {}
        app.state.simple_search_service = None
        app.state.deepseek_last_verified_at = None
        app.state.theirstack_last_verified_at = None
        app.state.theirstack_api_credits = None
        yield
        tasks = list(app.state.tasks)
        for task in tasks:
            task.cancel()
        for task in tasks:
            with suppress(asyncio.CancelledError):
                await task

    app = FastAPI(
        title="Workspace API",
        version="2.0.0",
        description=(
            "Local-first job-search backend with deterministic discovery "
            "and optional DeepSeek document intelligence"
        ),
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=configured.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def session_guard(request: Request, call_next):
        public_paths = {
            "/",
            "/health",
            "/api/session",
            "/openapi.json",
            "/docs",
            "/redoc",
        }
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
            if not supplied or not secrets.compare_digest(
                supplied, configured.session_token
            ):
                return JSONResponse(
                    status_code=401, content={"detail": "Invalid session token"}
                )
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

    @app.get("/api/countries")
    async def countries() -> list[dict[str, str]]:
        return list(country_catalog())

    @app.get("/api/providers")
    async def providers(request: Request) -> list[dict[str, Any]]:
        return [
            {
                "provider": "theirstack",
                "primary": True,
                "configured": bool(
                    request.app.state.theirstack_client
                    and request.app.state.theirstack_client.configured()
                ),
                "billable_results": True,
                "batch_size": configured.theirstack_batch_size,
            },
            {
                "provider": "authorized_public_connectors",
                "primary": False,
                "configured": True,
                "billable_results": False,
            },
        ]

    @app.get("/api/providers/coverage")
    async def provider_coverage(
        request: Request,
        role: Annotated[str, Query(min_length=2, max_length=120)],
        country_code: Annotated[str, Query(min_length=2, max_length=2)],
        provider: Annotated[str, Query(pattern="^theirstack$")] = "theirstack",
    ) -> dict[str, Any]:
        try:
            normalized_country = normalize_country_code(country_code)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        client = request.app.state.theirstack_client
        if client is None:
            return [
                {
                    "provider": provider,
                    "country_code": normalized_country,
                    "available": False,
                    "estimated_total": None,
                    "status": "unavailable",
                    "note": f"{provider} is not configured",
                    "credits_per_result": 1,
                }
            ]
        coverage = await client.estimate_coverage(
            ProviderSearchQuery(
                role=role.strip(),
                aliases=(),
                country_code=normalized_country,
            )
        )
        return [
            {
                "provider": coverage.provider,
                "country_code": normalized_country,
                "available": coverage.available,
                "estimated_total": coverage.total_matches,
                "status": "available" if coverage.available else "unavailable",
                "note": coverage.warning,
                "credits_per_result": 1,
            }
        ]

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
        model_items = (
            model_payload.get("data", []) if isinstance(model_payload, dict) else []
        )
        available_models = {
            item.get("id") for item in model_items if isinstance(item, dict)
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
        invalidate = getattr(request.app.state.ai_client, "invalidate", None)
        if callable(invalidate):
            invalidate()
        request.app.state.deepseek_last_verified_at = utc_now()
        return deepseek_status_payload(request)

    @app.delete("/api/settings/deepseek", response_model=DeepSeekStatus)
    async def delete_deepseek_settings(request: Request) -> DeepSeekStatus:
        try:
            request.app.state.credential_store.delete()
        except CredentialStoreUnavailable as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        invalidate = getattr(request.app.state.ai_client, "invalidate", None)
        if callable(invalidate):
            invalidate()
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
            api_credits = await request.app.state.theirstack_client.validate_key(
                api_key
            )
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

    @app.get("/api/about-me", response_model=AboutMeProfile)
    async def get_about_me(store: StoreDep) -> AboutMeProfile:
        return store.get_about_me()

    @app.put("/api/about-me", response_model=AboutMeProfile)
    async def update_about_me(
        payload: AboutMeUpdate, store: StoreDep
    ) -> AboutMeProfile:
        profiles = store.list_profiles()
        profile_ids = {profile.profile_id for profile in profiles}
        unknown = sorted(
            {
                profile_id
                for entry in payload.entries
                for profile_id in entry.profile_ids
                if profile_id not in profile_ids
            }
        )
        if unknown:
            raise HTTPException(
                status_code=422,
                detail="Sobre mí references a professional profile that no longer exists",
            )
        previous = store.get_about_me()
        dossier = AboutMeProfile(
            contact=payload.contact,
            entries=payload.entries,
            revision=previous.revision + 1,
        )
        stored = store.save_about_me(dossier)
        _sync_about_me_facts(stored, profiles, store)
        return stored

    @app.post(
        "/api/profiles", response_model=Profile, status_code=status.HTTP_201_CREATED
    )
    async def create_profile(payload: ProfileCreate, store: StoreDep) -> Profile:
        requested_name = payload.display_name.casefold()
        if any(
            profile.display_name.casefold() == requested_name
            for profile in store.list_profiles()
        ):
            raise HTTPException(
                status_code=409,
                detail="A professional profile with this name already exists",
            )
        return store.save_profile(Profile(**payload.model_dump()))

    @app.post(
        "/api/profiles/import",
        response_model=dict[str, Any],
        status_code=status.HTTP_201_CREATED,
    )
    async def import_profile(
        store: StoreDep,
        file: Annotated[UploadFile, File()],
        name: Annotated[str | None, Query()] = None,
        language: Annotated[str | None, Query(min_length=2, max_length=63)] = None,
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
        inferred_language = language
        if inferred_language is None:
            words = set(re.findall(r"[a-záéíóúñ]+", extraction.text.casefold()))
            spanish_markers = {
                "años", "con", "educación", "experiencia", "habilidades",
                "para", "proyectos", "tecnologías", "trabajo",
            }
            english_markers = {
                "and", "education", "experience", "for", "projects",
                "skills", "technologies", "with", "work",
            }
            inferred_language = (
                "es"
                if len(words & spanish_markers) > len(words & english_markers)
                else "en"
            )
        try:
            normalized_language = normalize_bcp47(inferred_language).split("-", 1)[0]
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        if normalized_language not in {"es", "en"}:
            raise HTTPException(
                status_code=422,
                detail="Only Spanish (es) or English (en) résumés are accepted",
            )
        document_id = f"document_{hashlib.sha256(content).hexdigest()}"
        filename = Path(file.filename or "resume.txt").name
        redacted_text = redact_contact_text(extraction.text)
        contact_values = extract_contact_values(extraction.text)
        if extraction.pages:
            imported_facts = [
                fact
                for page_number, page_text in enumerate(extraction.pages, start=1)
                for fact in facts_from_text(
                    redact_contact_text(page_text),
                    source_document_id=document_id,
                    language=normalized_language,
                    source_page=page_number,
                )
            ]
        else:
            imported_facts = facts_from_text(
                redacted_text,
                source_document_id=document_id,
                language=normalized_language,
            )
        profile = store.get_profile(profile_id) if profile_id else None
        if profile_id and profile is None:
            raise HTTPException(status_code=404, detail="Profile not found")
        is_new_profile = profile is None
        if profile is None:
            profile = Profile(
                name=name or Path(filename).stem,
                resume_text=extraction.text,
                facts=imported_facts,
                confirmed=False,
            )
        elif language:
            profile.facts = [
                fact
                for fact in profile.facts
                if fact.source_type == "about_me"
                or fact.language != normalized_language
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
        profile.resumes[normalized_language] = ResumeDocument(
            document_id=document_id,
            language=normalized_language,
            filename=filename,
            text=extraction.text,
            extraction_method=extraction.method,
            warnings=extraction.warnings,
        )
        profile.private_contact.emails = list(
            dict.fromkeys(
                [
                    *profile.private_contact.emails,
                    *contact_values["emails"],
                ]
            )
        )
        profile.private_contact.phones = list(
            dict.fromkeys(
                [
                    *profile.private_contact.phones,
                    *contact_values["phones"],
                ]
            )
        )
        profile.resume_text = "\n\n".join(
            item.text for item in profile.resumes.values() if item.text
        )
        preview_revision = profile.revision if is_new_profile else profile.revision + 1
        preview_hash = hashlib.sha256(redacted_text.encode("utf-8")).hexdigest()
        profile.redacted_preview = RedactedProfessionalPreview(
            profile_revision=preview_revision,
            language=normalized_language,
            redacted_text=redacted_text,
            included_record_ids=[],
            redacted_categories=["contact"],
            content_hash=preview_hash,
        )
        profile.cloud_processing_consent = None
        profile = store.save_profile(profile)
        return {
            "profile": profile.model_dump(mode="json"),
            "extraction_method": extraction.method,
            "warnings": extraction.warnings,
        }

    @app.post(
        "/api/profiles/{profile_id}/reprocess",
        response_model=Profile,
    )
    async def reprocess_profile(profile_id: str, store: StoreDep) -> Profile:
        """Rebuild reviewable facts from stored résumé variants without replacing them."""

        profile = store.get_profile(profile_id)
        if profile is None:
            raise HTTPException(status_code=404, detail="Profile not found")
        if not profile.resumes:
            raise HTTPException(
                status_code=409,
                detail="Upload at least one résumé before optimizing extraction",
            )

        rebuilt_facts: list[ProfileFact] = []
        now = utc_now()
        for language, variant in profile.resumes.items():
            rebuilt_facts.extend(
                facts_from_text(
                    redact_contact_text(variant.text),
                    source_document_id=variant.document_id,
                    language=language,
                )
            )
            variant.confirmation_status = ConfirmationStatus.PENDING_REVIEW
            variant.confirmed_at = None

        if not rebuilt_facts:
            raise HTTPException(
                status_code=409,
                detail="The stored résumé contains no reviewable professional facts",
            )
        profile.facts = [
            fact for fact in profile.facts if fact.source_type == "about_me"
        ] + rebuilt_facts
        profile.confirmed = False
        profile.version += 1
        profile.updated_at = now
        _refresh_redacted_professional_preview(profile)
        return store.save_profile(profile)

    @app.get(
        "/api/profiles/{profile_id}/cloud-preview",
        response_model=RedactedProfessionalPreview,
    )
    async def get_cloud_preview(
        profile_id: str, store: StoreDep
    ) -> RedactedProfessionalPreview:
        profile = store.get_profile(profile_id)
        if profile is None:
            raise HTTPException(status_code=404, detail="Profile not found")
        if profile.redacted_preview is None:
            raise HTTPException(
                status_code=404, detail="No redacted preview is available"
            )
        return profile.redacted_preview

    @app.post(
        "/api/profiles/{profile_id}/cloud-consent",
        response_model=Profile,
    )
    async def decide_cloud_consent(
        profile_id: str,
        payload: CloudConsentDecision,
        store: StoreDep,
    ) -> Profile:
        profile = store.get_profile(profile_id)
        if profile is None:
            raise HTTPException(status_code=404, detail="Profile not found")
        preview = profile.redacted_preview
        if preview is None:
            raise HTTPException(
                status_code=409, detail="Import a résumé before deciding consent"
            )
        profile.cloud_processing_consent = CloudProcessingConsent(
            profile_revision=profile.revision + 1,
            preview_id=preview.preview_id,
            preview_hash=preview.content_hash,
            purposes=payload.purposes,
            status=ConsentStatus.GRANTED if payload.granted else ConsentStatus.DECLINED,
        )
        preview.profile_revision = profile.revision + 1
        profile.version += 1
        return store.save_profile(profile)

    @app.get("/api/profiles", response_model=list[Profile])
    async def list_profiles(store: StoreDep) -> list[Profile]:
        return store.list_profiles()

    @app.get("/api/profiles/{profile_id}", response_model=Profile)
    async def get_profile(profile_id: str, store: StoreDep) -> Profile:
        profile = store.get_profile(profile_id)
        if profile is None:
            raise HTTPException(status_code=404, detail="Profile not found")
        return profile

    @app.patch("/api/profiles/{profile_id}", response_model=Profile)
    async def update_profile(
        profile_id: str,
        payload: ProfileUpdate,
        store: StoreDep,
    ) -> Profile:
        try:
            profile = store.update_profile(profile_id, payload)
        except ProfileDisplayNameConflictError as exc:
            raise HTTPException(
                status_code=409,
                detail="A professional profile with this name already exists",
            ) from exc
        if profile is None:
            raise HTTPException(status_code=404, detail="Profile not found")
        return profile

    @app.post(
        "/api/profiles/{profile_id}/duplicate",
        response_model=Profile,
        status_code=status.HTTP_201_CREATED,
    )
    async def duplicate_profile(
        profile_id: str,
        store: StoreDep,
        payload: ProfileDuplicateCreate | None = None,
    ) -> Profile:
        try:
            duplicate = store.duplicate_profile(
                profile_id,
                display_name=payload.display_name if payload else None,
            )
        except ProfileDisplayNameConflictError as exc:
            raise HTTPException(
                status_code=409,
                detail="A professional profile with this name already exists",
            ) from exc
        if duplicate is None:
            raise HTTPException(status_code=404, detail="Profile not found")
        dossier = store.get_about_me()
        dossier_changed = False
        for entry in dossier.entries:
            if (
                profile_id in entry.profile_ids
                and duplicate.profile_id not in entry.profile_ids
            ):
                entry.profile_ids.append(duplicate.profile_id)
                entry.updated_at = utc_now()
                dossier_changed = True
        if dossier_changed:
            dossier.revision += 1
            store.save_about_me(dossier)
            _sync_about_me_facts(dossier, store.list_profiles(), store)
            duplicate = store.get_profile(duplicate.profile_id) or duplicate
        return duplicate

    @app.delete(
        "/api/profiles/{profile_id}",
        status_code=status.HTTP_204_NO_CONTENT,
    )
    async def delete_profile(
        profile_id: str, request: Request, store: StoreDep
    ) -> Response:
        guides = [
            guide
            for guide in store.list_interview_guides()
            if guide.profile_id == profile_id
        ]
        ats_versions = store.list_ats_resume_versions_for_profile(profile_id)
        artifact_paths = [
            *[guide.pdf_path for guide in guides],
            *[version.pdf_path for guide in guides for version in guide.versions],
            *[version.pdf_path for version in ats_versions],
            *[version.docx_path for version in ats_versions],
        ]
        try:
            deleted = store.delete_profile(profile_id)
        except ProfileHasActiveOperationsError as exc:
            raise HTTPException(
                status_code=409,
                detail={
                    "message": "The profile cannot be deleted while a related document is being prepared",
                    "operation_ids": exc.operation_ids,
                },
            ) from exc
        if not deleted:
            raise HTTPException(status_code=404, detail="Profile not found")
        dossier = store.get_about_me()
        dossier_changed = False
        for entry in dossier.entries:
            if profile_id in entry.profile_ids:
                entry.profile_ids = [
                    value for value in entry.profile_ids if value != profile_id
                ]
                entry.updated_at = utc_now()
                dossier_changed = True
        if dossier_changed:
            dossier.revision += 1
            store.save_about_me(dossier)
        _remove_owned_artifact_files(request.app.state.settings, artifact_paths)
        return Response(status_code=status.HTTP_204_NO_CONTENT)

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
                # Legacy profiles created by the original /profiles endpoint did
                # not have ResumeVariant rows. Preserve their reviewed state while
                # all new Global profiles still require a confirmed variant.
                variants_ready = profile.has_confirmed_resume or not profile.resumes
                profile.confirmed = (
                    variants_ready
                    and bool(profile.facts)
                    and all(item.verified for item in profile.facts)
                )
                _refresh_redacted_professional_preview(profile)
                return store.save_profile(profile)
        raise HTTPException(status_code=404, detail="Profile fact not found")

    @app.post("/api/profiles/{profile_id}/confirm", response_model=Profile)
    async def confirm_profile(profile_id: str, store: StoreDep) -> Profile:
        profile = store.get_profile(profile_id)
        if profile is None:
            raise HTTPException(status_code=404, detail="Profile not found")
        if not profile.facts:
            raise HTTPException(
                status_code=409, detail="The résumé contains no reviewable facts"
            )
        if not profile.resumes:
            raise HTTPException(
                status_code=409,
                detail="Upload at least one résumé before confirming",
            )
        now = utc_now()
        for fact in profile.facts:
            fact.verified = True
            fact.verified_at = now
        for variant in profile.resumes.values():
            variant.confirmation_status = "confirmed"
            variant.confirmed_at = now
        profile.confirmed = True
        profile.version += 1
        profile.updated_at = now
        _refresh_redacted_professional_preview(profile)
        return store.save_profile(profile)

    def simple_search_service(request: Request) -> JobSearchService:
        if request.app.state.simple_search_service is None:
            request.app.state.simple_search_service = JobSearchService(
                request.app.state.store,
                JobProviderGroup(
                    request.app.state.theirstack_client,
                    BreteProvider(),
                ),
            )
        return request.app.state.simple_search_service

    @app.post("/api/searches", response_model=SearchResult)
    async def simple_search(payload: JobSearchInput, request: Request) -> SearchResult:
        try:
            return await simple_search_service(request).search(payload)
        except SearchConflict as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.get("/api/searches/{search_id}", response_model=SearchResult)
    async def simple_search_result(search_id: str, request: Request) -> SearchResult:
        try:
            return simple_search_service(request).get(search_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Search not found") from exc

    @app.post("/api/searches/{search_id}/pages/{page}", response_model=SearchResult)
    async def simple_search_more(
        search_id: str, page: int, request: Request
    ) -> SearchResult:
        try:
            return await simple_search_service(request).more(search_id, page)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Search not found") from exc
        except SearchConflict as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    async def _create_job_analysis(
        job_id: str,
        profile_id: Annotated[str, Query()],
        output_language: str,
        request: Request,
        store: StoreDep,
    ) -> DeepFitAnalysisV2:
        job = store.get_job(job_id)
        profile = store.get_profile(profile_id)
        if job is None:
            raise HTTPException(status_code=404, detail="No se encontró la vacante.")
        if profile is None:
            raise HTTPException(status_code=404, detail="No se encontró el perfil.")
        if not profile.confirmed:
            raise HTTPException(
                status_code=409, detail="El perfil profesional aún no está confirmado."
            )
        if output_language not in {"es", "en"}:
            raise HTTPException(status_code=422, detail="El idioma del análisis no es compatible.")
        require_resume_language(profile, job)
        existing = store.latest_deep_analysis_v2(profile.profile_id, job.job_id)
        if (
            existing is not None
            and existing.profile_revision == profile.revision
            and existing.analysis_language == output_language
        ):
            return existing
        require_cloud_generation(profile, request, purpose="analyzing fit")
        try:
            analysis = await asyncio.to_thread(
                run_fit_analysis,
                job,
                profile,
                request.app.state.ai_client,
                require_model=True,
                output_language=output_language,
            )
        except RuntimeError as exc:
            raise HTTPException(
                status_code=503,
                detail=(
                    "DeepSeek no pudo completar el análisis de brechas. "
                    "Inténtalo nuevamente."
                ),
            ) from exc
        return store.save_deep_analysis_v2(analysis)

    def require_cloud_generation(
        profile: Profile,
        request: Request,
        *,
        purpose: str,
    ) -> None:
        if not profile.has_valid_cloud_consent:
            raise HTTPException(
                status_code=409,
                detail=(
                    "Revisa la vista profesional sin datos de contacto y autoriza "
                    "el procesamiento con DeepSeek antes de utilizar esta función."
                ),
            )
        del purpose
        if not request.app.state.credential_store.get():
            raise HTTPException(
                status_code=409,
                detail="Configura DeepSeek antes de utilizar esta función.",
            )

    def require_resume_language(profile: Profile, job: JobRecord) -> str:
        """Require a confirmed résumé matching the job's base language."""

        job_language = detect_job_language(job)
        job_base = normalize_bcp47(job_language).split("-", 1)[0]
        matching = [
            language
            for language, resume in profile.resumes.items()
            if resume.confirmed
            and normalize_bcp47(language).split("-", 1)[0] == job_base
        ]
        if not matching:
            raise HTTPException(
                status_code=409,
                detail=(
                    f"Esta vacante requiere un CV confirmado en {job_language}. "
                    "Súbelo y confírmalo en Mi CV."
                ),
            )
        return job_language

    @app.post(
        "/api/saved-jobs",
        response_model=SavedJob,
        status_code=status.HTTP_201_CREATED,
    )
    async def save_profile_free_job(
        payload: SavedJobCreate, store: StoreDep
    ) -> SavedJob:
        """Bookmark a new-search result without requiring a CV or profile."""
        job = store.get_job(payload.job_id)
        # Search records live in the modern searches table; the run fallback
        # keeps imported pre-migration searches readable.
        run = store.get_search(payload.search_id)
        if job is None or run is None:
            raise HTTPException(status_code=404, detail="Job or search not found")
        if run.request.get("flow") != "simple_search":
            raise HTTPException(
                status_code=409,
                detail="Only independent search results can be saved here",
            )
        if not any(
            item.get("job_id") == job.job_id for item in run.result.get("jobs", [])
        ):
            raise HTTPException(
                status_code=409, detail="Job does not belong to this search"
            )
        if job.url is None:
            raise HTTPException(
                status_code=409, detail="The job has no application URL"
            )
        existing = store.get_saved_job_for_job(job.job_id)
        if existing is not None:
            return existing
        portals = list(
            dict.fromkeys(
                item.source_portal for item in job.source_evidence if item.source_portal
            )
        )
        source_urls = list(
            dict.fromkeys(
                url
                for item in job.source_evidence
                for url in (item.final_url, item.source_url)
                if url
            )
        )
        saved = SavedJob(
            job_id=job.job_id,
            search_id=run.search_id,
            title=job.title,
            company=job.company,
            location=job.location,
            source_portals=portals
            or ([job.source_portal] if job.source_portal else []),
            source_urls=source_urls or [job.url],
            apply_url=job.url,
            apply_url_type=job.apply_url_type,
            description=job.description,
            published_at=job.posted_at,
        )
        return store.save_saved_job(saved)

    @app.get("/api/saved-jobs", response_model=list[SavedJob])
    async def list_profile_free_jobs(store: StoreDep) -> list[SavedJob]:
        return store.list_saved_jobs()

    @app.get("/api/saved-jobs/{saved_id}", response_model=SavedJob)
    async def get_profile_free_job(saved_id: str, store: StoreDep) -> SavedJob:
        saved = store.get_saved_job(saved_id)
        if saved is None:
            raise HTTPException(status_code=404, detail="No se encontró la vacante guardada.")
        return saved

    @app.delete("/api/saved-jobs/{saved_id}", status_code=status.HTTP_204_NO_CONTENT)
    async def delete_profile_free_job(
        saved_id: str, request: Request, store: StoreDep
    ) -> Response:
        guides = [
            guide
            for guide in store.list_interview_guides()
            if guide.saved_id == saved_id
        ]
        ats_versions = store.list_ats_resume_versions(saved_id)
        artifact_paths = [
            *[guide.pdf_path for guide in guides],
            *[version.pdf_path for guide in guides for version in guide.versions],
            *[version.pdf_path for version in ats_versions],
            *[version.docx_path for version in ats_versions],
        ]
        try:
            deleted = store.delete_saved_job(saved_id)
        except ActiveOperationsError as exc:
            raise HTTPException(
                status_code=409, detail="Wait for document preparation to finish"
            ) from exc
        if not deleted:
            raise HTTPException(status_code=404, detail="Saved job not found")
        _remove_owned_artifact_files(request.app.state.settings, artifact_paths)
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    @app.get("/api/applications", response_model=list[JobApplication])
    async def list_applications(store: StoreDep) -> list[JobApplication]:
        return store.list_job_applications()

    @app.post(
        "/api/applications",
        response_model=JobApplication,
        status_code=status.HTTP_201_CREATED,
    )
    async def create_application(
        payload: JobApplicationCreate, store: StoreDep
    ) -> JobApplication:
        saved = store.get_saved_job(payload.saved_id)
        profile = store.get_profile(payload.profile_id)
        if saved is None:
            raise HTTPException(status_code=404, detail="Saved job not found")
        if profile is None:
            raise HTTPException(status_code=404, detail="Profile not found")
        existing = store.get_job_application_for_saved_job(payload.saved_id)
        if existing is not None:
            return existing
        application = JobApplication(
            saved_id=saved.saved_id,
            profile_id=profile.profile_id,
            job_id=saved.job_id,
            title=saved.title,
            company=saved.company,
            location=saved.location,
            apply_url=saved.apply_url,
            status=payload.status,
            notes=payload.notes,
            events=[
                JobApplicationEvent(status=payload.status, note=payload.notes)
            ],
        )
        return store.save_job_application(application)

    @app.patch(
        "/api/applications/{application_id}", response_model=JobApplication
    )
    async def update_application(
        application_id: str,
        payload: JobApplicationUpdate,
        store: StoreDep,
    ) -> JobApplication:
        application = store.get_job_application(application_id)
        if application is None:
            raise HTTPException(status_code=404, detail="Application not found")
        if payload.status is not None and payload.status != application.status:
            application.status = payload.status
            application.events.append(
                JobApplicationEvent(
                    status=payload.status,
                    note=payload.notes or "",
                )
            )
        if payload.notes is not None:
            application.notes = payload.notes
        return store.save_job_application(application)

    @app.delete(
        "/api/applications/{application_id}",
        status_code=status.HTTP_204_NO_CONTENT,
    )
    async def delete_application(
        application_id: str, store: StoreDep
    ) -> Response:
        if not store.delete_job_application(application_id):
            raise HTTPException(status_code=404, detail="Application not found")
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    async def create_ats_resume(
        saved_id: str,
        profile_id: str,
        request: Request,
        store: StoreDep,
        regenerate: bool = False,
        idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
    ) -> ATSResumeVersion:
        saved = store.get_saved_job(saved_id)
        if saved is None:
            raise HTTPException(status_code=404, detail="Saved job not found")
        profile = store.get_profile(profile_id)
        job = store.get_job(saved.job_id)
        if profile is None or job is None:
            raise HTTPException(status_code=404, detail="No se encontró el perfil o la vacante.")
        existing_versions = [
            item
            for item in store.list_ats_resume_versions(saved_id)
            if item.profile_id == profile_id
        ]
        if existing_versions:
            latest = existing_versions[0]
            if (
                latest.profile_revision == profile.revision
                and latest.job_content_hash == job.content_hash
                and latest.status
                in {
                    GeneratedDocumentStatus.PREPARING,
                    GeneratedDocumentStatus.REVIEWING,
                }
            ):
                return latest
            if (
                not regenerate
                and latest.profile_revision == profile.revision
                and latest.job_content_hash == job.content_hash
                and latest.status == GeneratedDocumentStatus.AWAITING_APPROVAL
            ):
                return latest
        del idempotency_key
        require_cloud_generation(profile, request, purpose="creating an ATS résumé")
        require_resume_language(profile, job)
        version_number = (
            max((item.version for item in existing_versions), default=0) + 1
        )
        resume_id = (
            existing_versions[0].resume_id
            if existing_versions
            else ATSResume(saved_id=saved_id).resume_id
        )
        version = ATSResumeVersion(
            resume_id=resume_id,
            saved_id=saved_id,
            version=version_number,
            profile_id=profile.profile_id,
            profile_revision=profile.revision,
            job_id=job.job_id,
            job_content_hash=job.content_hash,
            status=GeneratedDocumentStatus.PREPARING,
        )
        store.save_ats_resume_version(version)
        try:
            operation = build_ats_resume_operation(request.app.state.ai_client)
            operation_result = await asyncio.to_thread(
                operation.invoke,
                {
                    "job": job.model_dump(mode="json"),
                    "profile": profile.model_dump(mode="json"),
                    "stage": "queued",
                },
            )
            version.document = ATSResumeDocument.model_validate(
                operation_result["document"]
            )
            version.review_issues = list(operation_result.get("review_issues", []))
            version.status = GeneratedDocumentStatus.AWAITING_APPROVAL
            version.error = None
        except Exception as exc:
            logger.exception(
                "ATS résumé generation failed", extra={"version_id": version.version_id}
            )
            version.status = GeneratedDocumentStatus.FAILED
            version.error = (
                "DeepSeek no pudo crear el CV ATS de forma segura. "
                "Puedes intentarlo nuevamente."
            )
            store.save_ats_resume_version(version)
            raise HTTPException(status_code=503, detail=version.error) from exc
        return store.save_ats_resume_version(version)

    @app.patch(
        "/api/ats-resumes/{resume_id}/approve",
        response_model=ATSResumeVersion,
    )
    async def approve_ats_resume(
        resume_id: str,
        payload: ATSResumeApproval,
        request: Request,
        store: StoreDep,
    ) -> ATSResumeVersion:
        version = store.get_ats_resume_version(
            resume_id
        ) or store.latest_ats_resume_version_by_resume_id(resume_id)
        if version is None:
            raise HTTPException(status_code=404, detail="ATS résumé not found")
        if version.status == GeneratedDocumentStatus.READY:
            return version
        if version.status != GeneratedDocumentStatus.AWAITING_APPROVAL:
            raise HTTPException(
                status_code=409, detail="ATS résumé is not awaiting approval"
            )
        if not payload.approved:
            version.status = GeneratedDocumentStatus.FAILED
            version.error = "Rejected by the user"
            return store.save_ats_resume_version(version)
        if version.document is None:
            raise HTTPException(status_code=409, detail="ATS résumé content is missing")
        profile = store.get_profile(version.profile_id)
        job = store.get_job(version.job_id)
        if profile is None or job is None:
            raise HTTPException(
                status_code=409, detail="ATS résumé source data is missing"
            )
        if (
            profile.revision != version.profile_revision
            or job.content_hash != version.job_content_hash
        ):
            raise HTTPException(
                status_code=409,
                detail="Profile or job changed; create a new ATS résumé version",
            )
        output_dir = request.app.state.settings.artifacts_dir / "ats-resumes"
        pdf_path = output_dir / f"{version.version_id}.pdf"
        docx_path = output_dir / f"{version.version_id}.docx"
        version.status = GeneratedDocumentStatus.RENDERING
        store.save_ats_resume_version(version)
        temp_pdf_path = pdf_path.with_suffix(".pdf.tmp")
        temp_docx_path = docx_path.with_suffix(".docx.tmp")
        try:
            contact = _local_document_contact(store, profile)
            await asyncio.gather(
                asyncio.to_thread(
                    render_ats_pdf,
                    version.document,
                    contact,
                    temp_pdf_path,
                ),
                asyncio.to_thread(
                    render_ats_docx,
                    version.document,
                    contact,
                    temp_docx_path,
                ),
            )
            os.replace(temp_pdf_path, pdf_path)
            os.replace(temp_docx_path, docx_path)
        except Exception as exc:
            temp_pdf_path.unlink(missing_ok=True)
            temp_docx_path.unlink(missing_ok=True)
            version.status = GeneratedDocumentStatus.FAILED
            version.error = (
                "No se pudieron validar los archivos del CV ATS. "
                "Puedes generar una nueva versión."
            )
            store.save_ats_resume_version(version)
            raise HTTPException(status_code=500, detail=version.error) from exc
        version.pdf_path = str(pdf_path)
        version.docx_path = str(docx_path)
        version.approved_at = utc_now()
        version.status = GeneratedDocumentStatus.READY
        version.error = None
        return store.save_ats_resume_version(version)

    def ats_download(version_id: str, suffix: str, store: SQLiteStore) -> Path:
        version = store.get_ats_resume_version(
            version_id
        ) or store.latest_ats_resume_version_by_resume_id(version_id)
        if version is None or version.status != GeneratedDocumentStatus.READY:
            raise HTTPException(status_code=404, detail="Approved ATS résumé not found")
        value = version.pdf_path if suffix == "pdf" else version.docx_path
        if not value or not Path(value).is_file():
            raise HTTPException(status_code=404, detail="ATS résumé file is missing")
        return Path(value)

    @app.get("/api/ats-resumes/{resume_id}.pdf")
    async def download_ats_pdf(resume_id: str, store: StoreDep) -> FileResponse:
        return FileResponse(
            ats_download(resume_id, "pdf", store),
            media_type="application/pdf",
            filename="workspace-ats-resume.pdf",
        )

    @app.get("/api/ats-resumes/{resume_id}.docx")
    async def download_ats_docx(resume_id: str, store: StoreDep) -> FileResponse:
        return FileResponse(
            ats_download(resume_id, "docx", store),
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            filename="workspace-ats-resume.docx",
        )

    @app.post(
        "/api/linkedin/imports",
        response_model=LinkedInProfileSnapshot,
        status_code=status.HTTP_201_CREATED,
    )
    async def import_linkedin_profile(
        request: Request,
        store: StoreDep,
    ) -> LinkedInProfileSnapshot:
        content_type = request.headers.get("content-type", "").casefold()
        source_filename: str | None = None
        if "application/json" in content_type:
            try:
                payload = LinkedInManualImport.model_validate(await request.json())
            except (ValueError, TypeError) as exc:
                raise HTTPException(
                    status_code=422, detail="Invalid LinkedIn import"
                ) from exc
            text = payload.text
            profile_id = payload.profile_id
            language = payload.language
            target_roles = payload.target_roles
        else:
            form = await request.form()
            profile_id = str(form.get("profile_id") or "")
            language = normalize_bcp47(str(form.get("language") or "und"))
            target_roles = [
                value.strip()
                for value in str(form.get("target_roles") or "").split(",")
                if value.strip()
            ]
            uploaded = form.get("file")
            # Starlette's multipart parser returns its own UploadFile class;
            # FastAPI's UploadFile is a subclass used for typed parameters, so
            # checking only the FastAPI class rejects valid browser uploads.
            if not isinstance(uploaded, (UploadFile, StarletteUploadFile)):
                raise HTTPException(
                    status_code=422,
                    detail="A LinkedIn PDF or text file is required",
                )
            content = await uploaded.read(10 * 1024 * 1024 + 1)
            if len(content) > 10 * 1024 * 1024:
                raise HTTPException(status_code=413, detail="Document exceeds 10 MB")
            source_filename = uploaded.filename or "linkedin.pdf"
            try:
                extraction = await asyncio.to_thread(
                    extract_document_text,
                    source_filename,
                    content,
                )
            except UnsupportedDocument as exc:
                raise HTTPException(status_code=415, detail=str(exc)) from exc
            text = extraction.text
        if language.split("-", 1)[0] not in {"es", "en"}:
            raise HTTPException(
                status_code=422,
                detail="LinkedIn output is available only in Spanish or English",
            )
        profile = store.get_profile(profile_id)
        if profile is None:
            raise HTTPException(status_code=404, detail="Profile not found")
        # Extract locally and redact contacts before persistence or any future
        # DeepSeek call.  The complete professional text is retained alongside
        # the parsed sections so unusual LinkedIn PDF layouts are not lost.
        safe_text = redact_contact_text(text)
        parsed = parse_linkedin_sections(safe_text)
        snapshot = LinkedInProfileSnapshot(
            profile_id=profile.profile_id,
            profile_revision=profile.revision,
            language=language,
            target_roles=target_roles,
            source_filename=source_filename,
            source_text=safe_text,
            sections=LinkedInSectionInput(**parsed),
        )
        return store.save_linkedin_snapshot(snapshot)

    @app.get(
        "/api/linkedin/imports",
        response_model=list[LinkedInProfileSnapshot],
    )
    async def list_linkedin_imports(
        store: StoreDep,
        profile_id: Annotated[str | None, Query()] = None,
    ) -> list[LinkedInProfileSnapshot]:
        return store.list_linkedin_snapshots(profile_id)

    @app.get(
        "/api/linkedin/imports/{snapshot_id}/optimizations",
        response_model=list[LinkedInOptimizationVersion],
    )
    async def list_linkedin_optimization_versions(
        snapshot_id: str,
        store: StoreDep,
    ) -> list[LinkedInOptimizationVersion]:
        if store.get_linkedin_snapshot(snapshot_id) is None:
            raise HTTPException(status_code=404, detail="LinkedIn import not found")
        return store.list_linkedin_optimizations(snapshot_id)

    @app.patch(
        "/api/linkedin/imports/{snapshot_id}/sections",
        response_model=LinkedInProfileSnapshot,
    )
    async def update_linkedin_sections(
        snapshot_id: str,
        payload: LinkedInSnapshotUpdate,
        store: StoreDep,
    ) -> LinkedInProfileSnapshot:
        snapshot = store.get_linkedin_snapshot(snapshot_id)
        if snapshot is None:
            raise HTTPException(status_code=404, detail="LinkedIn import not found")
        snapshot.sections = LinkedInSectionInput(
            **{
                key: redact_contact_text(value)
                for key, value in payload.sections.model_dump().items()
            }
        )
        snapshot.source_text = "\n\n".join(
            value
            for value in snapshot.sections.model_dump().values()
            if isinstance(value, str) and value.strip()
        )
        return store.save_linkedin_snapshot(snapshot)

    @app.post(
        "/api/linkedin/imports/{snapshot_id}/reparse",
        response_model=LinkedInProfileSnapshot,
    )
    async def reparse_linkedin_profile(
        snapshot_id: str,
        store: StoreDep,
    ) -> LinkedInProfileSnapshot:
        snapshot = store.get_linkedin_snapshot(snapshot_id)
        if snapshot is None:
            raise HTTPException(status_code=404, detail="LinkedIn import not found")
        snapshot.sections = LinkedInSectionInput(
            **parse_linkedin_sections(snapshot.source_text)
        )
        snapshot.updated_at = utc_now()
        return store.save_linkedin_snapshot(snapshot)

    @app.post(
        "/api/linkedin/imports/{snapshot_id}/optimize",
        response_model=LinkedInOptimizationVersion,
        status_code=status.HTTP_201_CREATED,
    )
    async def optimize_linkedin_profile(
        snapshot_id: str,
        request: Request,
        store: StoreDep,
        idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
    ) -> LinkedInOptimizationVersion:
        snapshot = store.get_linkedin_snapshot(snapshot_id)
        if snapshot is None:
            raise HTTPException(status_code=404, detail="LinkedIn import not found")
        profile = store.get_profile(snapshot.profile_id)
        if profile is None:
            raise HTTPException(status_code=404, detail="Profile not found")
        if not profile.confirmed:
            raise HTTPException(
                status_code=409,
                detail="Confirm the selected profile before generating LinkedIn copy",
            )
        try:
            body = await request.json()
        except (ValueError, TypeError):
            body = {}
        requested_roles = body.get("target_roles", []) if isinstance(body, dict) else []
        if isinstance(requested_roles, list):
            normalized_roles = [
                " ".join(str(value).split())[:120]
                for value in requested_roles
                if " ".join(str(value).split())
            ][:12]
            if normalized_roles != snapshot.target_roles:
                snapshot.target_roles = normalized_roles
                snapshot = store.save_linkedin_snapshot(snapshot)
        requested_language = body.get("language") if isinstance(body, dict) else None
        if requested_language:
            try:
                normalized_language = normalize_bcp47(str(requested_language))
            except ValueError as exc:
                raise HTTPException(status_code=422, detail=str(exc)) from exc
            if normalized_language != snapshot.language:
                snapshot.language = normalized_language
                snapshot = store.save_linkedin_snapshot(snapshot)
        if snapshot.language.split("-", 1)[0] not in {"es", "en"}:
            raise HTTPException(
                status_code=422,
                detail="LinkedIn output is available only in Spanish or English",
            )
        existing = store.list_linkedin_optimizations(snapshot_id)
        if (
            existing
            and existing[0].status == GeneratedDocumentStatus.READY
            and existing[0].profile_revision == profile.revision
            and existing[0].target_roles == snapshot.target_roles
            and existing[0].language == snapshot.language
            # A saved correction changes the snapshot timestamp.  Do not reuse
            # an older generation when the user explicitly presses Generate
            # again after editing the imported LinkedIn content.
            and existing[0].created_at >= snapshot.updated_at
        ):
            return existing[0]
        del idempotency_key
        require_cloud_generation(
            profile, request, purpose="generating LinkedIn profile copy"
        )
        version = LinkedInOptimizationVersion(
            snapshot_id=snapshot.snapshot_id,
            version=max((item.version for item in existing), default=0) + 1,
            profile_revision=profile.revision,
            language=snapshot.language,
            target_roles=snapshot.target_roles,
            status=GeneratedDocumentStatus.PREPARING,
        )
        store.save_linkedin_optimization(version)
        try:
            operation = build_linkedin_optimization_operation(
                request.app.state.ai_client
            )
            result = await asyncio.to_thread(
                operation.invoke,
                {
                    "snapshot": snapshot.model_dump(mode="json"),
                    "profile": profile.model_dump(mode="json"),
                    "stage": "queued",
                },
            )
            version.sections = [
                LinkedInOptimizationSection.model_validate(item)
                for item in result.get("sections", [])
            ]
            version.review_issues = list(result.get("review_issues", []))
            version.status = GeneratedDocumentStatus.READY
            version.error = None
        except Exception as exc:
            logger.exception(
                "LinkedIn optimization failed",
                extra={"optimization_id": version.optimization_id},
            )
            version.status = GeneratedDocumentStatus.FAILED
            version.error = (
                "DeepSeek no pudo completar la optimización de LinkedIn. "
                "Puedes intentarlo nuevamente."
            )
            store.save_linkedin_optimization(version)
            raise HTTPException(status_code=503, detail=version.error) from exc
        return store.save_linkedin_optimization(version)

    async def finish_interview_guide(
        *,
        guide_id: str,
        require_model: bool,
        app: FastAPI,
        store: SQLiteStore,
    ) -> None:
        guide = store.get_interview_guide(guide_id)
        if guide is None:
            return
        job = store.get_job(guide.job_id)
        profile = store.get_profile(guide.profile_id)
        if job is None or profile is None:
            return
        generated: dict[str, Artifact] = {}

        def draft_guide() -> None:
            guide.analysis = build_deep_analysis(job, profile)
            model_artifact: Artifact | None = None
            if require_model:
                safe_facts = cloud_safe_verified_facts(
                    profile,
                    limit=max(1, len(profile.facts)),
                    language=guide.language,
                    include_all=True,
                )
                result = app.state.ai_client.invoke(
                    AIOperation.CONTENT_WRITING,
                    {
                        "jobs": [
                            {
                                "job_id": job.job_id,
                                "title": job.title,
                                "company": job.company,
                                "location": job.location,
                                "description": job.description,
                                "requirements": extract_requirements(job, limit=200),
                                "published_at": (
                                    job.posted_at.isoformat() if job.posted_at else None
                                ),
                                "url": str(job.final_url or job.url or ""),
                            }
                        ],
                        "verified_profile_facts": safe_facts,
                        "task": (
                            "Select only confirmed evidence useful for an interview guide. "
                            "Technical reference answers are educational, never personal claims. "
                            f"Create the complete interview_guide in {guide.language}. Include "
                            "a precise role overview, responsibilities, requirement/evidence matrix, "
                            "real gaps, 8-12 vacancy-specific technical questions with substantial "
                            "reference answers, up to 3 practical exercises with evaluation criteria, "
                            "questions for the company, a prioritized study plan, source date, and URL. "
                            "Do not include STAR-story preparation or generic filler."
                        ),
                    },
                )
                if not isinstance(result.structured, ContentProposal):
                    raise RuntimeError("Interview writer returned an invalid proposal")
                offered = {item["fact_id"] for item in safe_facts}
                for selection in result.structured.selections:
                    if selection.job_id != job.job_id or not set(
                        selection.ordered_fact_ids
                    ).issubset(offered):
                        raise RuntimeError("Interview writer used unoffered evidence")
                guide_proposal = result.structured.interview_guide
                if guide_proposal is not None:
                    try:
                        proposed_language = normalize_bcp47(guide_proposal.language)
                    except ValueError as exc:
                        raise RuntimeError(
                            "Interview writer returned an invalid language"
                        ) from exc
                    if proposed_language.split("-", 1)[0] != guide.language.split("-", 1)[0]:
                        raise RuntimeError("Interview writer returned the wrong guide language")
                    normalized_content = _normalize_generated_guide_content(
                        guide_proposal.content,
                        job=job,
                        language=guide.language,
                    )
                    if _INTERNAL_EVIDENCE_ID_RE.search(normalized_content):
                        raise RuntimeError("Interview guide exposed an internal identifier")
                    claims: list[Claim] = []
                    for claim in guide_proposal.claims:
                        if not claim.fact_ids or not set(claim.fact_ids).issubset(offered):
                            raise RuntimeError(
                                "Interview guide used unsupported personal evidence"
                            )
                        claims.append(Claim(text=claim.text, fact_ids=claim.fact_ids))
                    model_artifact = Artifact(
                        run_id=guide.guide_id,
                        job_id=job.job_id,
                        profile_id=profile.profile_id,
                        kind="interview_guide",
                        title=guide_proposal.title,
                        content=normalized_content,
                        language=guide.language,
                        claims=claims,
                    )
            generated["artifact"] = model_artifact or build_interview_guide(
                guide=guide, job=job, profile=profile
            )
            guide.status = "reviewing"
            store.save_interview_guide(guide)

        def review_guide() -> None:
            artifact = generated.get("artifact")
            if artifact is None:
                raise RuntimeError("Interview guide draft is missing")
            if require_model:
                offered = {
                    item["fact_id"]
                    for item in cloud_safe_verified_facts(
                        profile,
                        limit=max(1, len(profile.facts)),
                        language=guide.language,
                        include_all=True,
                    )
                }
                if any(
                    not claim.fact_ids or not set(claim.fact_ids).issubset(offered)
                    for claim in artifact.claims
                ):
                    raise RuntimeError(
                        "Interview guide contains unsupported personal evidence"
                    )
                if _INTERNAL_EVIDENCE_ID_RE.search(artifact.content):
                    raise RuntimeError(
                        "Interview guide exposed an internal evidence identifier"
                    )

        def render_guide() -> str:
            artifact = generated.get("artifact")
            if artifact is None:
                raise RuntimeError("Interview guide draft is missing")
            output_path = (
                app.state.settings.artifacts_dir
                / "interview-guides"
                / f"{artifact.artifact_id}.pdf"
            )
            guide.status = "rendering"
            store.save_interview_guide(guide)
            render_artifact_pdf(artifact, output_path, styled=True)
            if (
                not output_path.is_file()
                or output_path.stat().st_size < 800
                or output_path.read_bytes()[:4] != b"%PDF"
            ):
                raise RuntimeError("PDF renderer did not produce a valid file")
            return artifact.artifact_id

        try:
            await asyncio.to_thread(draft_guide)
            await asyncio.to_thread(review_guide)
            document_id = await asyncio.to_thread(render_guide)
            artifact = generated.get("artifact")
            if artifact is None or document_id != artifact.artifact_id:
                raise RuntimeError("Interview guide operation did not complete")
            output_path = (
                app.state.settings.artifacts_dir
                / "interview-guides"
                / f"{document_id}.pdf"
            )
            guide.document_id = document_id
            guide.pdf_path = str(output_path)
            guide.status = "ready"
            guide.template_version = "2.0"
            guide.profile_revision = profile.revision
            guide.job_content_hash = job.content_hash
            guide.is_outdated = False
            guide.versions = [
                item for item in guide.versions if item.version != guide.version
            ]
            guide.versions.append(
                GuideVersionRecord(
                    version=guide.version,
                    document_id=document_id,
                    pdf_path=str(output_path),
                    template_version=guide.template_version,
                    profile_revision=profile.revision,
                )
            )
            guide.versions.sort(key=lambda item: item.version)
            guide.error = None
            store.save_interview_guide(guide)
        except Exception:
            logger.exception(
                "Interview guide generation failed",
                extra={"guide_id": guide.guide_id},
            )
            guide.status = "failed"
            guide.error = (
                "No se pudo crear el PDF. Puedes reintentar desde esta vacante."
            )
            store.save_interview_guide(guide)

    async def create_interview_guide(
        saved_id: str,
        profile_id: str,
        request: Request,
        store: SQLiteStore,
    ) -> InterviewGuide:
        saved = store.get_saved_job(saved_id)
        profile = store.get_profile(profile_id)
        job = store.get_job(saved.job_id) if saved else None
        if saved is None or profile is None or job is None:
            raise HTTPException(
                status_code=404,
                detail="No se encontró la vacante guardada o el perfil seleccionado.",
            )
        if not profile.ready_for_search:
            raise HTTPException(
                status_code=409,
                detail="Confirma al menos un CV antes de crear la guía.",
            )
        require_cloud_generation(
            profile, request, purpose="creating an interview guide"
        )
        require_resume_language(profile, job)
        if job.url is None or job.posted_at is None:
            raise HTTPException(
                status_code=409,
                detail="La vacante necesita un enlace y una fecha de publicación verificables.",
            )
        existing = store.get_interview_guide_for_saved_job(saved_id, profile_id)
        if existing and existing.status in {
            "preparing",
            "reviewing",
            "rendering",
            "ready",
        }:
            return refresh_guide_freshness(existing, store)
        guide = existing or InterviewGuide(
            saved_id=saved.saved_id,
            profile_id=profile.profile_id,
            job_id=job.job_id,
            search_id=saved.search_id,
            job_title=job.title,
            company=job.company,
            apply_url=job.url,
            published_at=job.posted_at,
            analysis=build_deep_analysis(job, profile),
            language=detect_job_language(job),
            profile_revision=profile.revision,
            job_content_hash=job.content_hash,
        )
        guide.status = "preparing"
        guide.document_id = None
        guide.pdf_path = None
        guide.error = None
        guide.profile_revision = profile.revision
        guide.job_content_hash = job.content_hash
        guide.is_outdated = False
        stored = store.save_interview_guide(guide)
        _spawn(
            request.app,
            finish_interview_guide(
                guide_id=stored.guide_id,
                require_model=True,
                app=request.app,
                store=store,
            ),
        )
        return stored

    def refresh_guide_freshness(
        guide: InterviewGuide, store: SQLiteStore
    ) -> InterviewGuide:
        profile = store.get_profile(guide.profile_id)
        job = store.get_job(guide.job_id)
        guide.is_outdated = bool(
            profile is None
            or job is None
            or guide.profile_revision != profile.revision
            or guide.job_content_hash != job.content_hash
        )
        return guide

    async def regenerate_interview_guide(
        guide: InterviewGuide,
        request: Request,
        store: SQLiteStore,
    ) -> InterviewGuide:
        if guide.status in {"preparing", "reviewing", "rendering"}:
            return refresh_guide_freshness(guide, store)
        profile = store.get_profile(guide.profile_id)
        job = store.get_job(guide.job_id)
        if profile is None or job is None:
            raise HTTPException(status_code=404, detail="Profile or job not found")
        require_cloud_generation(
            profile, request, purpose="regenerating an interview guide"
        )
        require_resume_language(profile, job)
        # Migrated guides may predate explicit version records. Preserve their
        # existing PDF before clearing the current document for regeneration.
        if guide.document_id and not any(
            item.version == guide.version for item in guide.versions
        ):
            guide.versions.append(
                GuideVersionRecord(
                    version=guide.version,
                    document_id=guide.document_id,
                    pdf_path=guide.pdf_path,
                    template_version=guide.template_version,
                    profile_revision=guide.profile_revision,
                    created_at=guide.updated_at,
                )
            )
        guide.version = (
            max(
                [guide.version, *(item.version for item in guide.versions)],
                default=guide.version,
            )
            + 1
        )
        guide.document_id = None
        guide.pdf_path = None
        guide.status = "preparing"
        guide.language = detect_job_language(job)
        guide.analysis = build_deep_analysis(job, profile)
        guide.profile_revision = profile.revision
        guide.job_content_hash = job.content_hash
        guide.is_outdated = False
        guide.error = None
        stored = store.save_interview_guide(guide)
        _spawn(
            request.app,
            finish_interview_guide(
                guide_id=stored.guide_id,
                require_model=True,
                app=request.app,
                store=store,
            ),
        )
        return stored

    def interview_guide_file(
        guide: InterviewGuide,
        version: int | None,
    ) -> Path:
        document_id = guide.document_id
        if version is not None:
            record = next(
                (item for item in guide.versions if item.version == version), None
            )
            document_id = record.document_id if record else None
        root = (configured.artifacts_dir / "interview-guides").resolve()
        path = (root / f"{document_id}.pdf").resolve() if document_id else None
        if path is None or path.parent != root or not path.is_file():
            raise HTTPException(
                status_code=404, detail="Interview guide file is missing"
            )
        return path

    @app.delete("/api/data")
    async def delete_local_data(
        payload: DataDeleteConfirmation,
        request: Request,
        store: StoreDep,
    ) -> dict[str, Any]:
        # Resolve the only filesystem target before deleting database rows.
        try:
            _configured_artifacts_root(request.app.state.settings)
        except RuntimeError as exc:
            raise HTTPException(
                status_code=409,
                detail="Configured deletion targets are unsafe; no data was deleted",
            ) from exc
        try:
            deleted = store.clear_all_data()
        except ActiveOperationsError as exc:
            raise HTTPException(
                status_code=409,
                detail={
                    "message": "Local data cannot be deleted while an operation is active",
                    "operation_id": str(exc),
                },
            ) from exc

        removed_artifact_entries = _purge_configured_artifacts(
            request.app.state.settings
        )

        return {
            "status": "deleted",
            "deleted": deleted,
            "removed_artifact_entries": removed_artifact_entries,
        }

    @app.get("/api/data/export")
    async def export(store: StoreDep) -> dict[str, Any]:
        return store.export_snapshot()

    @app.post(
        "/api/saved-jobs/{saved_id}/analyses",
        response_model=DeepFitAnalysisV2,
        status_code=status.HTTP_201_CREATED,
    )
    async def analyze_saved_job(
        saved_id: str,
        profile_id: Annotated[str, Query()],
        request: Request,
        store: StoreDep,
        language: Annotated[str, Query(pattern="^(es|en)$")] = "es",
    ) -> DeepFitAnalysisV2:
        saved = store.get_saved_job(saved_id)
        if saved is None:
            raise HTTPException(status_code=404, detail="Saved job not found")
        return await _create_job_analysis(
            saved.job_id, profile_id, language, request, store
        )

    @app.post(
        "/api/saved-jobs/{saved_id}/interview-guides",
        response_model=InterviewGuide,
        status_code=status.HTTP_202_ACCEPTED,
    )
    async def prepare_saved_job_guide(
        saved_id: str,
        profile_id: Annotated[str, Query()],
        request: Request,
        store: StoreDep,
    ) -> InterviewGuide:
        return await create_interview_guide(saved_id, profile_id, request, store)

    @app.get(
        "/api/saved-jobs/{saved_id}/interview-guides/{profile_id}",
        response_model=InterviewGuide,
    )
    async def get_saved_job_guide(
        saved_id: str,
        profile_id: str,
        store: StoreDep,
    ) -> InterviewGuide:
        saved = store.get_saved_job(saved_id)
        if saved is None:
            raise HTTPException(status_code=404, detail="Saved job not found")
        guide = store.get_interview_guide_for_saved_job(saved_id, profile_id)
        if guide is None:
            raise HTTPException(status_code=404, detail="Interview guide not found")
        return refresh_guide_freshness(guide, store)

    @app.post(
        "/api/saved-jobs/{saved_id}/interview-guides/{profile_id}/regenerate",
        response_model=InterviewGuide,
        status_code=status.HTTP_202_ACCEPTED,
    )
    async def regenerate_saved_job_guide(
        saved_id: str,
        profile_id: str,
        request: Request,
        store: StoreDep,
    ) -> InterviewGuide:
        guide = await get_saved_job_guide(saved_id, profile_id, store)
        return await regenerate_interview_guide(guide, request, store)

    @app.get("/api/saved-jobs/{saved_id}/interview-guides/{profile_id}/document.pdf")
    async def download_saved_job_guide(
        saved_id: str,
        profile_id: str,
        request: Request,
        store: StoreDep,
        disposition: Annotated[
            str, Query(pattern="^(inline|attachment)$")
        ] = "attachment",
        version: Annotated[int | None, Query(ge=1)] = None,
    ) -> FileResponse:
        guide = await get_saved_job_guide(saved_id, profile_id, store)
        return FileResponse(
            interview_guide_file(guide, version),
            media_type="application/pdf",
            filename=f"interview-guide-{guide.job_id}.pdf",
            content_disposition_type=disposition,
        )

    @app.post(
        "/api/saved-jobs/{saved_id}/ats-resumes",
        response_model=ATSResumeVersion,
        status_code=status.HTTP_202_ACCEPTED,
    )
    async def prepare_saved_job_resume(
        saved_id: str,
        profile_id: Annotated[str, Query()],
        request: Request,
        store: StoreDep,
        regenerate: Annotated[bool, Query()] = False,
    ) -> ATSResumeVersion:
        return await create_ats_resume(
            saved_id, profile_id, request, store, regenerate=regenerate
        )

    @app.get(
        "/api/saved-jobs/{saved_id}/ats-resumes", response_model=list[ATSResumeVersion]
    )
    async def saved_job_resumes(
        saved_id: str, profile_id: str, store: StoreDep
    ) -> list[ATSResumeVersion]:
        if store.get_saved_job(saved_id) is None:
            raise HTTPException(status_code=404, detail="Saved job not found")
        return [
            item
            for item in store.list_ats_resume_versions(saved_id)
            if item.profile_id == profile_id
        ]

    return app

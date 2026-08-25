from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator


def utc_now() -> datetime:
    return datetime.now(UTC)


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid", use_enum_values=True)


class SourceKind(StrEnum):
    MANUAL = "manual"
    GREENHOUSE = "greenhouse"
    LEVER = "lever"
    ASHBY = "ashby"
    HIMALAYAS = "himalayas"
    WWR = "we_work_remotely"
    JOBICY = "jobicy"
    REMOTIVE = "remotive"
    REMOTE_OK = "remote_ok"
    LINKEDIN = "linkedin"
    INDEED = "indeed"
    GLASSDOOR = "glassdoor"
    COMPUTRABAJO = "computrabajo"
    THEIRSTACK = "theirstack"
    REPLAY = "replay"


class AgentRole(StrEnum):
    COORDINATOR = "career_coordinator"
    SCOUT = "opportunity_scout"
    FIT_ANALYST = "fit_analyst"
    TAILOR = "application_tailor"
    REVIEWER = "quality_reviewer"


class AgentStatus(StrEnum):
    IDLE = "idle"
    QUEUED = "queued"
    WORKING = "working"
    WAITING = "waiting_for_approval"
    COMPLETED = "completed"
    ERROR = "error"


class RunMode(StrEnum):
    REPLAY = "replay"
    LIVE = "live"


class RunStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    AWAITING_USER = "awaiting_user"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ApprovalKind(StrEnum):
    PROFILE_CONFIRMATION = "profile_confirmation"
    SHORTLIST_SELECTION = "shortlist_selection"
    APPLICATION_APPROVAL = "application_approval"


class ApprovalStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class MatchStatus(StrEnum):
    MATCH = "match"
    GAP = "gap"
    UNKNOWN = "unknown"


class PipelineStatus(StrEnum):
    DISCOVERED = "discovered"
    ELIGIBLE = "eligible"
    ANALYZED = "analyzed"
    SHORTLISTED = "shortlisted"
    DRAFTING = "drafting"
    REVIEWING = "reviewing"
    READY_FOR_APPROVAL = "ready_for_approval"
    APPROVED = "approved"
    EXPORTED = "exported"
    APPLIED = "applied"
    INTERVIEWING = "interviewing"
    CLOSED = "closed"


class ProfileFact(Model):
    fact_id: str = Field(default_factory=lambda: new_id("fact"))
    category: str
    text: str
    evidence: str | None = None
    source_document_id: str | None = None
    source_span: str | None = None
    source_type: str = "document"
    source_url: HttpUrl | None = None
    source_page: int | None = Field(default=None, ge=1)
    language: Literal["es", "en"] | None = None
    version: int = Field(default=1, ge=1)
    verified: bool = False
    verified_at: datetime | None = None
    created_at: datetime = Field(default_factory=utc_now)


class ResumeDocument(Model):
    document_id: str
    language: Literal["es", "en"]
    filename: str
    text: str = ""
    extraction_method: str
    warnings: list[str] = Field(default_factory=list)
    imported_at: datetime = Field(default_factory=utc_now)


class ProfileFactUpdate(Model):
    text: str | None = Field(default=None, min_length=1, max_length=500)
    verified: bool | None = None


class RankingWeights(Model):
    requirements: float = Field(default=50, ge=0, le=100)
    experience: float = Field(default=20, ge=0, le=100)
    logistics: float = Field(default=15, ge=0, le=100)
    preferences: float = Field(default=15, ge=0, le=100)

    @model_validator(mode="after")
    def total_is_one_hundred(self) -> RankingWeights:
        total = self.requirements + self.experience + self.logistics + self.preferences
        if abs(total - 100) > 0.001:
            raise ValueError("ranking weights must add up to 100")
        return self


class UserPreferences(Model):
    desired_titles: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    excluded_keywords: list[str] = Field(default_factory=list)
    desired_locations: list[str] = Field(default_factory=list)
    remote_required: bool = False
    minimum_salary: float | None = Field(default=None, ge=0)
    currency: str | None = None
    work_authorization: str | None = None
    ranking_weights: RankingWeights = Field(default_factory=RankingWeights)


class Profile(Model):
    profile_id: str = Field(default_factory=lambda: new_id("profile"))
    name: str
    email: str | None = None
    summary: str = ""
    resume_text: str = ""
    resumes: dict[Literal["es", "en"], ResumeDocument] = Field(default_factory=dict)
    facts: list[ProfileFact] = Field(default_factory=list)
    preferences: UserPreferences = Field(default_factory=UserPreferences)
    version: int = Field(default=1, ge=1)
    confirmed: bool = False
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class ProfileCreate(Model):
    name: str
    email: str | None = None
    summary: str = ""
    resume_text: str = ""
    facts: list[ProfileFact] = Field(default_factory=list)
    preferences: UserPreferences = Field(default_factory=UserPreferences)
    confirmed: bool = False


class JobRecord(Model):
    job_id: str = Field(default_factory=lambda: new_id("job"))
    source: SourceKind
    sources: list[SourceKind] = Field(default_factory=list)
    external_id: str
    title: str
    company: str
    location: str = ""
    remote: bool | None = None
    employment_type: str | None = None
    salary_min: float | None = None
    salary_max: float | None = None
    salary_currency: str | None = None
    description: str
    requirements: list[str] = Field(default_factory=list)
    preferred_requirements: list[str] = Field(default_factory=list)
    url: HttpUrl | None = None
    provider: str | None = None
    source_portal: str | None = None
    source_url: HttpUrl | None = None
    final_url: HttpUrl | None = None
    apply_url_type: Literal["company", "portal"] = "company"
    posted_at: datetime | None = None
    date_confidence: Literal["exact", "unknown"] = "unknown"
    verification_level: Literal["official", "authorized_feed", "manual_portal"] = "official"
    official_url_verified: bool = False
    retrieved_at: datetime = Field(default_factory=utc_now)
    content_hash: str = ""
    raw: dict[str, Any] = Field(default_factory=dict)
    pipeline_status: PipelineStatus = PipelineStatus.DISCOVERED


class ManualJobCreate(Model):
    title: str
    company: str
    description: str
    location: str = ""
    remote: bool | None = None
    url: HttpUrl | None = None
    posted_at: datetime | None = None
    source: SourceKind = SourceKind.MANUAL
    salary_min: float | None = None
    salary_max: float | None = None
    salary_currency: str | None = None


class PipelineStatusUpdate(Model):
    status: PipelineStatus


class SearchRequest(Model):
    query: str = ""
    aliases: list[str] = Field(default_factory=list)
    location: str | None = None
    remote_only: bool = False
    sources: list[SourceKind] = Field(default_factory=list)
    source_identifiers: dict[str, str] = Field(default_factory=dict)
    limit: int = Field(default=2_000, ge=1, le=10_000)


class CareerSearchCreate(Model):
    profile_id: str
    role: str = Field(min_length=2, max_length=120)


class FitSummary(Model):
    score: float = Field(ge=0, le=100)
    level: Literal["high", "medium", "low"]
    strengths: list[str] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0, le=1)


class CareerJobResult(Model):
    job_id: str
    title: str
    company: str
    location: str
    remote: bool | None = None
    source: SourceKind
    sources: list[SourceKind] = Field(default_factory=list)
    published_at: datetime
    official_apply_url: HttpUrl
    apply_url: HttpUrl | None = None
    apply_url_type: Literal["company", "portal"] = "company"
    provider: str | None = None
    source_portal: str | None = None
    source_url: HttpUrl | None = None
    description_summary: str
    requirements: list[str] = Field(default_factory=list)
    fit_summary: FitSummary
    freshness_verified: Literal[True] = True
    official_url_verified: Literal[True] = True
    verification_level: Literal["official", "authorized_feed", "manual_portal"] = "official"


class DeepFitAnalysis(Model):
    job_id: str
    profile_id: str
    score: float = Field(ge=0, le=100)
    level: Literal["high", "medium", "low"]
    resume_language: Literal["es", "en"] = "en"
    matched_requirements: list[dict[str, str]] = Field(default_factory=list)
    missing_requirements: list[str] = Field(default_factory=list)
    cv_recommendations: list[str] = Field(default_factory=list)
    cautions: list[str] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=utc_now)


class InterestCreate(Model):
    profile_id: str
    run_id: str


class Interest(Model):
    interest_id: str = Field(default_factory=lambda: new_id("interest"))
    profile_id: str
    job_id: str
    run_id: str
    guide_run_id: str | None = None
    job_title: str
    company: str
    official_apply_url: HttpUrl
    published_at: datetime
    analysis: DeepFitAnalysis
    guide_artifact_id: str | None = None
    guide_language: Literal["es", "en"]
    guide_status: Literal["preparing", "ready", "failed"] = "preparing"
    guide_error: str | None = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)

    @model_validator(mode="after")
    def migrate_legacy_guide_status(self) -> Interest:
        if self.guide_artifact_id and self.guide_status == "preparing":
            self.guide_status = "ready"
        return self


class RankRequest(Model):
    profile_id: str
    job_ids: list[str] = Field(default_factory=list)


class CriterionResult(Model):
    name: str
    status: MatchStatus
    evidence: str | None = None
    weight: float = Field(default=1.0, ge=0)


class RankingBreakdown(Model):
    requirements: float = Field(ge=0, le=100)
    experience: float = Field(ge=0, le=100)
    logistics: float = Field(ge=0, le=100)
    preferences: float = Field(ge=0, le=100)
    confidence: float = Field(ge=0, le=1)

    @property
    def total(self) -> float:
        return round(min(100, self.requirements + self.experience + self.logistics + self.preferences), 2)


class RankedJob(Model):
    job: JobRecord
    score: float = Field(ge=0, le=100)
    eligible: bool | None
    breakdown: RankingBreakdown
    criteria: list[CriterionResult] = Field(default_factory=list)
    reasons: list[str] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)


class Claim(Model):
    text: str
    fact_ids: list[str] = Field(default_factory=list)


class Artifact(Model):
    artifact_id: str = Field(default_factory=lambda: new_id("artifact"))
    run_id: str
    job_id: str
    profile_id: str
    kind: str
    title: str
    content: str
    version: int = Field(default=1, ge=1)
    claims: list[Claim] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utc_now)


def stable_digest(value: Any) -> str:
    canonical = json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def build_integrity_snapshot(
    *,
    profile: Profile | None = None,
    jobs: list[JobRecord] | None = None,
    artifacts: list[Artifact] | None = None,
) -> dict[str, Any]:
    """Digest approval inputs while excluding operationally mutable metadata."""

    snapshot: dict[str, Any] = {"version": 1}
    if profile is not None:
        snapshot["profile"] = {
            "id": profile.profile_id,
            "digest": stable_digest(
                profile.model_dump(
                    mode="json", exclude={"facts", "created_at", "updated_at"}
                )
            ),
        }
        snapshot["facts"] = {
            "profile_id": profile.profile_id,
            "digest": stable_digest(
                [
                    fact.model_dump(mode="json", exclude={"created_at"})
                    for fact in sorted(profile.facts, key=lambda item: item.fact_id)
                ]
            ),
        }
    snapshot["jobs"] = {
        job.job_id: stable_digest(
            job.model_dump(
                mode="json", exclude={"pipeline_status", "retrieved_at", "raw"}
            )
        )
        for job in sorted(jobs or [], key=lambda item: item.job_id)
    }
    snapshot["artifacts"] = {
        artifact.artifact_id: stable_digest(
            artifact.model_dump(mode="json", exclude={"created_at"})
        )
        for artifact in sorted(artifacts or [], key=lambda item: item.artifact_id)
    }
    return snapshot


class ReviewIssue(Model):
    severity: str
    message: str
    claim: str | None = None


class ReviewReport(Model):
    approved: bool
    issues: list[ReviewIssue] = Field(default_factory=list)


class Approval(Model):
    approval_id: str = Field(default_factory=lambda: new_id("approval"))
    run_id: str
    kind: ApprovalKind
    status: ApprovalStatus = ApprovalStatus.PENDING
    allowed_decisions: list[str] = Field(default_factory=list)
    offered_entity_ids: list[str] = Field(default_factory=list)
    max_selected: int | None = Field(default=None, ge=1)
    integrity_snapshot: dict[str, Any] = Field(default_factory=dict)
    artifact_version: int | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    decision_payload: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utc_now)
    resolved_at: datetime | None = None


class ApprovalResolution(Model):
    decision: str
    payload: dict[str, Any] = Field(default_factory=dict)
    edits: dict[str, Any] = Field(default_factory=dict)
    artifact_version: int | None = None
    entity_ids: list[str] = Field(default_factory=list)

    @property
    def normalized_status(self) -> ApprovalStatus:
        if self.decision in {"approve", "approved", "select"}:
            return ApprovalStatus.APPROVED
        if self.decision in {"reject", "rejected", "skip"}:
            return ApprovalStatus.REJECTED
        raise ValueError("decision must approve/select or reject/skip")


class EventUI(Model):
    template_key: str
    template_args: dict[str, Any] = Field(default_factory=dict)
    severity: str = "info"
    progress: float | None = Field(default=None, ge=0, le=1)

    @model_validator(mode="before")
    @classmethod
    def discard_legacy_avatar_cues(cls, value: object) -> object:
        """Read pre-terrarium events without re-exposing removed avatar signals."""
        if isinstance(value, dict) and "animation_cue" in value:
            value = {key: item for key, item in value.items() if key != "animation_cue"}
        return value


class GraphEvent(Model):
    event_id: str = Field(default_factory=lambda: new_id("event"))
    schema_version: int = 1
    run_id: str
    sequence: int = Field(ge=1)
    timestamp: datetime = Field(default_factory=utc_now)
    type: str
    stage: str
    actor_kind: str = "workflow"
    actor_id: str = "workflow"
    target_id: str | None = None
    entity_ref: str | None = None
    causation_id: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    visibility: str
    ui: EventUI


class Run(Model):
    run_id: str = Field(default_factory=lambda: new_id("run"))
    thread_id: str | None = None
    mode: RunMode = RunMode.REPLAY
    status: RunStatus = RunStatus.QUEUED
    profile_id: str | None = None
    query: str = ""
    request: dict[str, Any] = Field(default_factory=dict)
    result: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class RunCreate(Model):
    mode: RunMode = RunMode.REPLAY
    profile_id: str | None = None
    search: SearchRequest | None = None
    job_ids: list[str] = Field(default_factory=list)
    query: str = ""
    location: str | None = None
    work_mode: str = "remote"
    sources: list[SourceKind] = Field(default_factory=list)
    source_identifiers: dict[str, str] = Field(default_factory=dict)
    limit: int = Field(default=20, ge=1, le=20)
    selected_job_ids: list[str] = Field(default_factory=list, max_length=3)
    use_model: bool = False
    generate_cover_letter: bool = True
    auto_approve: bool = False


class Health(Model):
    status: str = "ok"
    api_version: str = "0.2.0"
    replay_ready: bool = True
    deepseek_required_for_live: bool = True
    theirstack_ready: bool = True


class DeepSeekKeyInput(Model):
    api_key: str = Field(min_length=8, max_length=500)


class DeepSeekStatus(Model):
    configured: bool
    provider: Literal["deepseek"] = "deepseek"
    model: str
    last_verified_at: datetime | None = None


class TheirStackKeyInput(Model):
    api_key: str = Field(min_length=8, max_length=500)


class TheirStackStatus(Model):
    configured: bool
    provider: Literal["theirstack"] = "theirstack"
    batch_size: int = 25
    api_credits: int | None = None
    last_verified_at: datetime | None = None


class CareerSearchMoreCreate(Model):
    page: int = Field(ge=1)


class DataDeleteConfirmation(Model):
    confirmation: Literal["DELETE_ALL_LOCAL_DATA"]

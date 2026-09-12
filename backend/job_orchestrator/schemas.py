from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime
from enum import StrEnum
from typing import Annotated, Any, Literal
from uuid import uuid4

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    HttpUrl,
    field_validator,
    model_validator,
)


def utc_now() -> datetime:
    return datetime.now(UTC)


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid", use_enum_values=True)


_BCP47_PATTERN = re.compile(r"^(?=.{2,63}$)[A-Za-z]{2,8}(?:-[A-Za-z0-9]{1,8})*$")


def normalize_bcp47(value: str) -> str:
    """Validate and canonicalize a practical BCP-47 language tag.

    The application does not need to maintain a second language registry.  This
    deliberately accepts registered and private subtags while rejecting paths,
    whitespace and arbitrary free text.  Canonical casing keeps dictionary keys
    stable (`es-cr` -> `es-CR`, `zh-hant-tw` -> `zh-Hant-TW`).
    """

    cleaned = value.strip()
    if not _BCP47_PATTERN.fullmatch(cleaned):
        raise ValueError("language must be a valid BCP-47 tag")
    parts = cleaned.split("-")
    normalized = [parts[0].lower()]
    for index, part in enumerate(parts[1:], start=1):
        if len(part) == 4 and part.isalpha() and index == 1:
            normalized.append(part.title())
        elif (len(part) == 2 and part.isalpha()) or (len(part) == 3 and part.isdigit()):
            normalized.append(part.upper())
        else:
            normalized.append(part.lower())
    return "-".join(normalized)


BCP47Language = Annotated[str, AfterValidator(normalize_bcp47)]
ResumeLanguage = Literal["es", "en"]


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
    INFOJOBS = "infojobs"
    NAUKRI = "naukri"
    USAJOBS = "usajobs"
    BRETE = "brete"
    THEIRSTACK = "theirstack"
    REPLAY = "replay"


class SearchStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class MatchStatus(StrEnum):
    MATCH = "match"
    GAP = "gap"
    UNKNOWN = "unknown"


class SeniorityLevel(StrEnum):
    INTERNSHIP = "internship"
    ENTRY = "entry"
    JUNIOR = "junior"
    MID = "mid"
    SENIOR = "senior"
    LEAD = "lead"
    MANAGER = "manager"
    DIRECTOR = "director"
    EXECUTIVE = "executive"


class WorkMode(StrEnum):
    REMOTE = "remote"
    HYBRID = "hybrid"
    ONSITE = "onsite"


class RemoteEligibility(StrEnum):
    ELIGIBLE_FOR_COUNTRY = "eligible_for_country"
    INELIGIBLE = "ineligible"
    UNKNOWN = "unknown"
    WORLDWIDE = "worldwide"


class ApplyUrlType(StrEnum):
    OFFICIAL = "official"
    ATS = "ats"
    PORTAL = "portal"


class CompatibilityStatus(StrEnum):
    COMPATIBLE = "compatible"
    REVIEW_SEPARATELY = "review_separately"


class GeneratedDocumentStatus(StrEnum):
    PREPARING = "preparing"
    REVIEWING = "reviewing"
    AWAITING_APPROVAL = "awaiting_approval"
    APPROVED = "approved"
    RENDERING = "rendering"
    READY = "ready"
    FAILED = "failed"


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


class ConfirmationStatus(StrEnum):
    PENDING_REVIEW = "pending_review"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"


class ConsentStatus(StrEnum):
    PENDING = "pending"
    GRANTED = "granted"
    DECLINED = "declined"
    REVOKED = "revoked"


class ApplicationStatus(StrEnum):
    APPLIED = "applied"
    CONTACTED = "contacted"
    SCREENING = "screening"
    INTERVIEW = "interview"
    TECHNICAL_TEST = "technical_test"
    OFFER = "offer"
    HIRED = "hired"
    REJECTED = "rejected"
    NO_RESPONSE = "no_response"
    WITHDRAWN = "withdrawn"


class RecordProvenance(Model):
    """Local evidence pointing back to the exact imported source."""

    document_id: str | None = None
    page: int | None = Field(default=None, ge=1)
    fragment: str | None = Field(default=None, max_length=2_000)
    source_span: str | None = Field(default=None, max_length=500)
    char_start: int | None = Field(default=None, ge=0)
    char_end: int | None = Field(default=None, ge=0)
    source_type: str = "document"
    source_url: HttpUrl | None = None
    language: BCP47Language | None = None

    @model_validator(mode="after")
    def span_is_ordered(self) -> RecordProvenance:
        if (
            self.char_start is not None
            and self.char_end is not None
            and self.char_end < self.char_start
        ):
            raise ValueError("char_end must not precede char_start")
        return self


class ProfessionalRecord(Model):
    record_id: str = Field(default_factory=lambda: new_id("record"))
    provenance: RecordProvenance = Field(default_factory=RecordProvenance)
    language: BCP47Language
    profile_revision: int = Field(default=1, ge=1)
    confirmation_status: ConfirmationStatus = ConfirmationStatus.PENDING_REVIEW
    confirmed_at: datetime | None = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)

    @model_validator(mode="after")
    def confirmation_timestamp_is_consistent(self) -> ProfessionalRecord:
        if self.confirmation_status != ConfirmationStatus.CONFIRMED:
            self.confirmed_at = None
        elif self.confirmed_at is None:
            self.confirmed_at = utc_now()
        return self


class EmploymentRecord(ProfessionalRecord):
    employer: str | None = None
    title: str | None = None
    location: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    is_current: bool = False
    summary: str = ""
    responsibilities: list[str] = Field(default_factory=list)
    technologies: list[str] = Field(default_factory=list)


class ProjectRecord(ProfessionalRecord):
    name: str
    role: str | None = None
    summary: str = ""
    start_date: str | None = None
    end_date: str | None = None
    technologies: list[str] = Field(default_factory=list)
    highlights: list[str] = Field(default_factory=list)
    url: HttpUrl | None = None


class SkillRecord(ProfessionalRecord):
    name: str
    category: str | None = None
    proficiency: str | None = None
    years_experience: float | None = Field(default=None, ge=0)


class AchievementRecord(ProfessionalRecord):
    statement: str
    context: str | None = None
    metric: str | None = None


class EducationRecord(ProfessionalRecord):
    institution: str | None = None
    credential: str | None = None
    field_of_study: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    summary: str = ""


class CertificationRecord(ProfessionalRecord):
    name: str
    issuer: str | None = None
    issued_at: str | None = None
    expires_at: str | None = None
    credential_url: HttpUrl | None = None


class LanguageRecord(ProfessionalRecord):
    name: str
    proficiency: str | None = None
    credential: str | None = None


class ProfessionalRecordSet(Model):
    employment: list[EmploymentRecord] = Field(default_factory=list)
    projects: list[ProjectRecord] = Field(default_factory=list)
    skills: list[SkillRecord] = Field(default_factory=list)
    achievements: list[AchievementRecord] = Field(default_factory=list)
    education: list[EducationRecord] = Field(default_factory=list)
    certifications: list[CertificationRecord] = Field(default_factory=list)
    languages: list[LanguageRecord] = Field(default_factory=list)

    def all_records(self) -> list[ProfessionalRecord]:
        return [
            *self.employment,
            *self.projects,
            *self.skills,
            *self.achievements,
            *self.education,
            *self.certifications,
            *self.languages,
        ]


class PrivateContactBlock(Model):
    """Private local-only contact data, persisted outside profile JSON."""

    contact_id: str = Field(default_factory=lambda: new_id("contact"))
    full_name: str | None = None
    emails: list[str] = Field(default_factory=list)
    phones: list[str] = Field(default_factory=list)
    address_lines: list[str] = Field(default_factory=list)
    city: str | None = None
    region: str | None = None
    country_code: str | None = Field(default=None, min_length=2, max_length=2)
    postal_code: str | None = None
    websites: list[HttpUrl] = Field(default_factory=list)
    legacy_values: list[str] = Field(default_factory=list)
    updated_at: datetime = Field(default_factory=utc_now)

    @field_validator(
        "emails", "phones", "address_lines", "legacy_values", mode="before"
    )
    @classmethod
    def compact_string_lists(cls, value: object) -> object:
        if not isinstance(value, list):
            return value
        return list(
            dict.fromkeys(
                cleaned
                for item in value
                if isinstance(item, str) and (cleaned := " ".join(item.split()))
            )
        )

    @field_validator("country_code")
    @classmethod
    def normalize_country_code(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if not value.isalpha():
            raise ValueError("country_code must be ISO 3166-1 alpha-2")
        return value.upper()


class RedactedProfessionalPreview(Model):
    preview_id: str = Field(default_factory=lambda: new_id("preview"))
    profile_revision: int = Field(ge=1)
    language: BCP47Language | None = None
    redacted_text: str
    included_record_ids: list[str] = Field(default_factory=list)
    redacted_categories: list[str] = Field(default_factory=list)
    content_hash: str
    generated_at: datetime = Field(default_factory=utc_now)


class CloudProcessingConsent(Model):
    consent_id: str = Field(default_factory=lambda: new_id("consent"))
    provider: Literal["deepseek"] = "deepseek"
    profile_revision: int = Field(ge=1)
    preview_id: str
    preview_hash: str
    purposes: list[Literal["profile_extraction", "fit_analysis", "document_generation"]]
    status: ConsentStatus = ConsentStatus.PENDING
    decided_at: datetime | None = None
    revoked_at: datetime | None = None

    @model_validator(mode="after")
    def decision_timestamps_are_consistent(self) -> CloudProcessingConsent:
        if self.status in {ConsentStatus.GRANTED, ConsentStatus.DECLINED}:
            self.decided_at = self.decided_at or utc_now()
        if self.status == ConsentStatus.REVOKED:
            self.revoked_at = self.revoked_at or utc_now()
        return self


class CloudConsentDecision(Model):
    granted: bool
    purposes: list[
        Literal["profile_extraction", "fit_analysis", "document_generation"]
    ] = Field(default_factory=lambda: ["fit_analysis", "document_generation"])


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
    language: BCP47Language | None = None
    version: int = Field(default=1, ge=1)
    verified: bool = False
    verified_at: datetime | None = None
    created_at: datetime = Field(default_factory=utc_now)


class ResumeVariant(Model):
    variant_id: str = Field(default_factory=lambda: new_id("resume_variant"))
    document_id: str
    language: ResumeLanguage
    filename: str
    text: str = ""
    extraction_method: str
    warnings: list[str] = Field(default_factory=list)
    profile_revision: int = Field(default=1, ge=1)
    confirmation_status: ConfirmationStatus = ConfirmationStatus.PENDING_REVIEW
    confirmed_at: datetime | None = None
    imported_at: datetime = Field(default_factory=utc_now)

    @field_validator("language", mode="before")
    @classmethod
    def normalize_supported_resume_language(cls, value: object) -> object:
        language = normalize_bcp47(str(value)).split("-", 1)[0]
        if language not in {"es", "en"}:
            raise ValueError("resume language must be Spanish (es) or English (en)")
        return language

    @property
    def confirmed(self) -> bool:
        return self.confirmation_status == ConfirmationStatus.CONFIRMED


# Backwards-compatible import name used by the current API.
ResumeDocument = ResumeVariant


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
    target_seniorities: list[SeniorityLevel] = Field(default_factory=list)
    allowed_work_modes: list[WorkMode] = Field(default_factory=list)
    excluded_sectors: list[str] = Field(default_factory=list)
    remote_required: bool = False
    minimum_salary: float | None = Field(default=None, ge=0)
    currency: str | None = None
    work_authorization: str | None = None
    ranking_weights: RankingWeights = Field(default_factory=RankingWeights)

    @field_validator(
        "desired_titles",
        "keywords",
        "excluded_keywords",
        "desired_locations",
        "excluded_sectors",
        mode="before",
    )
    @classmethod
    def normalize_text_preferences(cls, value: object) -> object:
        if not isinstance(value, list):
            return value
        normalized: list[object] = []
        seen: set[str] = set()
        for item in value:
            if not isinstance(item, str):
                normalized.append(item)
                continue
            cleaned = " ".join(item.split())
            if not cleaned:
                continue
            key = cleaned.casefold()
            if key not in seen:
                seen.add(key)
                normalized.append(cleaned)
        return normalized

    @field_validator("target_seniorities", "allowed_work_modes", mode="after")
    @classmethod
    def unique_enum_preferences(cls, value: list[str]) -> list[str]:
        return list(dict.fromkeys(value))


class Profile(Model):
    profile_id: str = Field(default_factory=lambda: new_id("profile"))
    display_name: str = Field(default="Perfil actual", min_length=1, max_length=60)
    name: str
    # Accepted temporarily for legacy callers, excluded from serialized profile data.
    email: str | None = Field(default=None, exclude=True)
    private_contact: PrivateContactBlock = Field(
        default_factory=PrivateContactBlock,
        exclude=True,
    )
    summary: str = ""
    resume_text: str = ""
    resumes: dict[str, ResumeVariant] = Field(default_factory=dict)
    facts: list[ProfileFact] = Field(default_factory=list)
    professional_records: ProfessionalRecordSet = Field(
        default_factory=ProfessionalRecordSet
    )
    redacted_preview: RedactedProfessionalPreview | None = None
    cloud_processing_consent: CloudProcessingConsent | None = None
    preferences: UserPreferences = Field(default_factory=UserPreferences)
    version: int = Field(default=1, ge=1)
    revision: int = Field(default=1, ge=1)
    confirmed: bool = False
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)

    @model_validator(mode="before")
    @classmethod
    def discard_retired_resume_translation_state(cls, value: object) -> object:
        """Read legacy profiles without retaining the removed translation workflow."""

        if not isinstance(value, dict):
            return value
        migrated = dict(value)
        migrated.pop("translation_drafts", None)
        resumes = migrated.get("resumes")
        if isinstance(resumes, dict):
            cleaned_resumes: dict[str, object] = {}
            for language, raw_variant in resumes.items():
                try:
                    base_language = normalize_bcp47(str(language)).split("-", 1)[0]
                except ValueError:
                    # Malformed language keys remain validation errors instead of being
                    # silently accepted as legacy data.
                    cleaned_resumes[str(language)] = raw_variant
                    continue
                if base_language not in {"es", "en"}:
                    continue
                if isinstance(raw_variant, dict):
                    raw_variant = dict(raw_variant)
                    raw_variant.pop("translated_from_variant_id", None)
                    raw_variant.pop("translation_review_required", None)
                cleaned_resumes[str(language)] = raw_variant
            migrated["resumes"] = cleaned_resumes
        return migrated

    @field_validator("display_name")
    @classmethod
    def normalize_display_name(cls, value: str) -> str:
        cleaned = " ".join(value.split())
        if not cleaned:
            raise ValueError("display_name must not be blank")
        return cleaned

    @field_validator("resumes", mode="before")
    @classmethod
    def normalize_resume_language_keys(cls, value: object) -> object:
        if not isinstance(value, dict):
            return value
        normalized: dict[str, object] = {}
        for raw_language, raw_variant in value.items():
            language = normalize_bcp47(str(raw_language)).split("-", 1)[0]
            if language not in {"es", "en"}:
                raise ValueError("resume language must be Spanish (es) or English (en)")
            if language in normalized:
                raise ValueError(f"duplicate resume language variant: {language}")
            if isinstance(raw_variant, dict):
                raw_variant = {**raw_variant, "language": language}
            normalized[language] = raw_variant
        return normalized

    @model_validator(mode="after")
    def keep_private_legacy_email_local(self) -> Profile:
        if self.email and self.email not in self.private_contact.emails:
            self.private_contact.emails.append(self.email)
        for language, variant in self.resumes.items():
            if variant.language != language:
                raise ValueError("resume key and variant language must match")
        if self.cloud_processing_consent is not None:
            if self.redacted_preview is None:
                raise ValueError("cloud consent requires its redacted preview")
            if (
                self.cloud_processing_consent.preview_id
                != self.redacted_preview.preview_id
                or self.cloud_processing_consent.preview_hash
                != self.redacted_preview.content_hash
            ):
                raise ValueError("cloud consent must match the exact redacted preview")
        return self

    @property
    def has_confirmed_resume(self) -> bool:
        return any(variant.confirmed for variant in self.resumes.values())

    @property
    def ready_for_search(self) -> bool:
        return self.confirmed and self.has_confirmed_resume

    @property
    def has_valid_cloud_consent(self) -> bool:
        consent = self.cloud_processing_consent
        preview = self.redacted_preview
        return bool(
            consent
            and preview
            and consent.status == ConsentStatus.GRANTED
            and consent.profile_revision == self.revision
            and preview.profile_revision == self.revision
            and consent.preview_id == preview.preview_id
            and consent.preview_hash == preview.content_hash
        )


class ProfileCreate(Model):
    display_name: str = Field(default="Perfil actual", min_length=1, max_length=60)
    name: str
    email: str | None = None
    summary: str = ""
    resume_text: str = ""
    facts: list[ProfileFact] = Field(default_factory=list)
    preferences: UserPreferences = Field(default_factory=UserPreferences)
    confirmed: bool = False

    @field_validator("display_name")
    @classmethod
    def normalize_display_name(cls, value: str) -> str:
        cleaned = " ".join(value.split())
        if not cleaned:
            raise ValueError("display_name must not be blank")
        return cleaned


class ProfileUpdate(Model):
    display_name: str | None = Field(default=None, min_length=1, max_length=60)
    preferences: UserPreferences | None = None

    @field_validator("display_name")
    @classmethod
    def normalize_display_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = " ".join(value.split())
        if not cleaned:
            raise ValueError("display_name must not be blank")
        return cleaned

    @model_validator(mode="after")
    def at_least_one_change(self) -> ProfileUpdate:
        if self.display_name is None and self.preferences is None:
            raise ValueError("at least one profile field must be provided")
        return self


class ProfileDuplicateCreate(Model):
    display_name: str | None = Field(default=None, min_length=1, max_length=60)

    @field_validator("display_name")
    @classmethod
    def normalize_display_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = " ".join(value.split())
        if not cleaned:
            raise ValueError("display_name must not be blank")
        return cleaned


class JobSourceEvidence(Model):
    provider: str
    source_portal: str | None = None
    source_url: HttpUrl | None = None
    final_url: HttpUrl | None = None
    apply_url_type: ApplyUrlType = ApplyUrlType.PORTAL
    external_id: str | None = None
    observed_at: datetime = Field(default_factory=utc_now)


class JobRecord(Model):
    job_id: str = Field(default_factory=lambda: new_id("job"))
    source: SourceKind
    sources: list[SourceKind] = Field(default_factory=list)
    external_id: str
    title: str
    company: str
    location: str = ""
    country_code: str | None = Field(default=None, min_length=2, max_length=2)
    city: str | None = None
    region: str | None = None
    remote: bool | None = None
    remote_eligibility: RemoteEligibility = RemoteEligibility.UNKNOWN
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
    apply_url_type: ApplyUrlType = ApplyUrlType.OFFICIAL
    source_evidence: list[JobSourceEvidence] = Field(default_factory=list)
    posted_at: datetime | None = None
    date_confidence: Literal["exact", "unknown"] = "unknown"
    verification_level: Literal["official", "authorized_feed", "manual_portal"] = (
        "official"
    )
    official_url_verified: bool = False
    retrieved_at: datetime = Field(default_factory=utc_now)
    content_hash: str = ""
    raw: dict[str, Any] = Field(default_factory=dict)
    pipeline_status: PipelineStatus = PipelineStatus.DISCOVERED

    @field_validator("country_code")
    @classmethod
    def normalize_job_country(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip().upper()
        if not re.fullmatch(r"[A-Z]{2}", normalized):
            raise ValueError("country_code must be ISO 3166-1 alpha-2")
        return normalized

    @field_validator("apply_url_type", mode="before")
    @classmethod
    def migrate_company_url_type(cls, value: object) -> object:
        return "official" if value == "company" else value


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
    # Costa Rica remains the compatibility default for pre-Global clients. The
    # Global UI always sends the user's explicit ISO country selection.
    country_code: str = Field(default="CR", min_length=2, max_length=2)
    city_or_region: str | None = Field(default=None, max_length=120)
    modalities: list[WorkMode] = Field(default_factory=list)
    include_global_remote: bool = False
    paid_provider: Literal["theirstack"] = "theirstack"

    @field_validator("country_code")
    @classmethod
    def normalize_search_country(cls, value: str) -> str:
        normalized = value.strip().upper()
        if not re.fullmatch(r"[A-Z]{2}", normalized):
            raise ValueError("country_code must be ISO 3166-1 alpha-2")
        return normalized

    @field_validator("modalities", mode="after")
    @classmethod
    def unique_modalities(cls, value: list[str]) -> list[str]:
        return list(dict.fromkeys(value))


class CountrySearchScope(Model):
    country_code: str = Field(min_length=2, max_length=2)
    country_name: str
    city_or_region: str | None = None
    modalities: list[WorkMode] = Field(default_factory=list)
    include_global_remote: bool = False
    window_days: Literal[7] = 7
    started_at: datetime = Field(default_factory=utc_now)


class ProviderCoverage(Model):
    provider: str
    status: Literal["available", "unavailable", "partial", "unknown"] = "unknown"
    total_available: int | None = Field(default=None, ge=0)
    retrieved: int = Field(default=0, ge=0)
    accepted: int = Field(default=0, ge=0)
    message: str | None = None
    consumes_credits: bool = False


class JobSearchPage(Model):
    provider: str
    page: int = Field(ge=0)
    jobs: list[JobRecord] = Field(default_factory=list)
    total_available: int | None = Field(default=None, ge=0)
    next_page: int | None = Field(default=None, ge=0)
    can_load_more: bool = False
    coverage: ProviderCoverage


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
    country_code: str | None = None
    remote: bool | None = None
    source: SourceKind
    sources: list[SourceKind] = Field(default_factory=list)
    published_at: datetime
    official_apply_url: HttpUrl
    apply_url: HttpUrl | None = None
    apply_url_type: ApplyUrlType = ApplyUrlType.OFFICIAL
    remote_eligibility: RemoteEligibility = RemoteEligibility.UNKNOWN
    source_evidence: list[JobSourceEvidence] = Field(default_factory=list)
    provider: str | None = None
    source_portal: str | None = None
    source_url: HttpUrl | None = None
    description_summary: str
    requirements: list[str] = Field(default_factory=list)
    fit_summary: FitSummary
    freshness_verified: Literal[True] = True
    official_url_verified: Literal[True] = True
    verification_level: Literal["official", "authorized_feed", "manual_portal"] = (
        "official"
    )
    profile_id: str | None = None
    compatibility_status: CompatibilityStatus = CompatibilityStatus.COMPATIBLE
    filter_reasons: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

    @field_validator("apply_url_type", mode="before")
    @classmethod
    def migrate_result_company_url_type(cls, value: object) -> object:
        return "official" if value == "company" else value

    @field_validator("compatibility_status", mode="before")
    @classmethod
    def migrate_result_review_status(cls, value: object) -> object:
        return "review_separately" if value == "review" else value


class RequirementAnalysis(Model):
    requirement: str
    category: Literal[
        "technology", "experience", "education", "language", "logistics", "other"
    ] = "other"
    priority: Literal["required", "preferred", "unknown"] = "unknown"
    status: Literal["supported", "gap", "unknown"]
    fact_ids: list[str] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)
    explanation: str | None = None


class TechnologyFit(Model):
    technology: str
    status: Literal["supported", "gap", "unknown"]
    fact_ids: list[str] = Field(default_factory=list)


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
    requirement_analysis: list[RequirementAnalysis] = Field(default_factory=list)
    technology_summary: list[TechnologyFit] = Field(default_factory=list)
    supported_keywords: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.5, ge=0, le=1)
    generated_at: datetime = Field(default_factory=utc_now)


class DeepFitAnalysisV2(Model):
    analysis_id: str = Field(default_factory=lambda: new_id("analysis"))
    job_id: str
    profile_id: str
    profile_revision: int = Field(ge=1)
    resume_language: BCP47Language
    analysis_language: Literal["es", "en"] = "es"
    executive_summary: str
    score: float = Field(ge=0, le=100)
    level: Literal["high", "medium", "low"]
    requirement_analysis: list[RequirementAnalysis] = Field(default_factory=list)
    priority_gaps: list[str] = Field(default_factory=list)
    transferable_strengths: list[str] = Field(default_factory=list)
    cv_actions: list[str] = Field(default_factory=list)
    supported_keywords: list[str] = Field(default_factory=list)
    missing_technologies: list[str] = Field(default_factory=list)
    uncertainties: list[str] = Field(default_factory=list)
    integrity_notice: str = "Revisa las recomendaciones antes de modificar tu CV."
    confidence: float = Field(default=0.5, ge=0, le=1)
    generated_at: datetime = Field(default_factory=utc_now)


class GuideVersionRecord(Model):
    version: int = Field(ge=1)
    document_id: str
    pdf_path: str | None = None
    template_version: str
    profile_revision: int = Field(ge=1)
    created_at: datetime = Field(default_factory=utc_now)


class InterviewGuide(Model):
    guide_id: str = Field(default_factory=lambda: new_id("guide"))
    saved_id: str
    profile_id: str
    job_id: str
    search_id: str
    job_title: str
    company: str
    apply_url: HttpUrl
    published_at: datetime
    analysis: DeepFitAnalysis
    document_id: str | None = None
    pdf_path: str | None = None
    language: BCP47Language
    status: Literal["preparing", "reviewing", "rendering", "ready", "failed"] = (
        "preparing"
    )
    version: int = Field(default=1, ge=1)
    template_version: str = "2.0"
    profile_revision: int = Field(default=1, ge=1)
    job_content_hash: str = ""
    is_outdated: bool = False
    versions: list[GuideVersionRecord] = Field(default_factory=list)
    error: str | None = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class SavedJobCreate(Model):
    """Profile-free bookmark created from an independent job search."""

    job_id: str
    search_id: str


class SavedJob(Model):
    saved_id: str = Field(default_factory=lambda: new_id("saved"))
    job_id: str
    search_id: str
    title: str
    company: str
    location: str = ""
    source_portals: list[str] = Field(default_factory=list)
    source_urls: list[HttpUrl] = Field(default_factory=list)
    apply_url: HttpUrl
    apply_url_type: ApplyUrlType = ApplyUrlType.PORTAL
    description: str = ""
    published_at: datetime | None = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class AboutMeEntry(Model):
    """User-authored professional evidence shared with selected profiles."""

    entry_id: str = Field(default_factory=lambda: new_id("about"))
    category: Literal[
        "experience",
        "project",
        "skill",
        "education",
        "certification",
        "achievement",
    ]
    title: str = Field(min_length=1, max_length=200)
    details: str = Field(min_length=1, max_length=5_000)
    language: Literal["es", "en"]
    profile_ids: list[str] = Field(default_factory=list)
    url: HttpUrl | None = None
    verified: bool = True
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)

    @field_validator("profile_ids", mode="after")
    @classmethod
    def unique_profiles(cls, value: list[str]) -> list[str]:
        return list(dict.fromkeys(item for item in value if item))


class AboutMeProfile(Model):
    """Local professional dossier; contacts never enter cloud evidence."""

    dossier_id: str = "about_me"
    contact: PrivateContactBlock = Field(default_factory=PrivateContactBlock)
    entries: list[AboutMeEntry] = Field(default_factory=list)
    revision: int = Field(default=1, ge=1)
    updated_at: datetime = Field(default_factory=utc_now)


class AboutMeUpdate(Model):
    contact: PrivateContactBlock = Field(default_factory=PrivateContactBlock)
    entries: list[AboutMeEntry] = Field(default_factory=list)


class JobApplicationCreate(Model):
    saved_id: str
    profile_id: str
    status: ApplicationStatus = ApplicationStatus.APPLIED
    notes: str = Field(default="", max_length=5_000)


class JobApplicationUpdate(Model):
    status: ApplicationStatus | None = None
    notes: str | None = Field(default=None, max_length=5_000)

    @model_validator(mode="after")
    def requires_change(self) -> JobApplicationUpdate:
        if self.status is None and self.notes is None:
            raise ValueError("at least one application field must be provided")
        return self


class JobApplicationEvent(Model):
    event_id: str = Field(default_factory=lambda: new_id("application_event"))
    status: ApplicationStatus
    note: str = Field(default="", max_length=5_000)
    created_at: datetime = Field(default_factory=utc_now)


class JobApplication(Model):
    application_id: str = Field(default_factory=lambda: new_id("application"))
    saved_id: str
    profile_id: str
    job_id: str
    title: str
    company: str
    location: str = ""
    apply_url: HttpUrl
    status: ApplicationStatus = ApplicationStatus.APPLIED
    notes: str = Field(default="", max_length=5_000)
    events: list[JobApplicationEvent] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class ATSResumeLine(Model):
    record_ids: list[str] = Field(default_factory=list)
    original_text: str
    proposed_text: str
    context_heading: str | None = None


class ATSResumeDocument(Model):
    language: BCP47Language
    headline: str
    professional_summary: str
    skills: list[str] = Field(default_factory=list)
    experience: list[ATSResumeLine] = Field(default_factory=list)
    projects: list[ATSResumeLine] = Field(default_factory=list)
    education: list[ATSResumeLine] = Field(default_factory=list)
    certifications: list[ATSResumeLine] = Field(default_factory=list)
    languages: list[ATSResumeLine] = Field(default_factory=list)


class ATSResumeVersion(Model):
    version_id: str = Field(default_factory=lambda: new_id("ats_version"))
    resume_id: str
    saved_id: str
    version: int = Field(ge=1)
    profile_id: str
    profile_revision: int = Field(ge=1)
    job_id: str
    job_content_hash: str
    status: GeneratedDocumentStatus = GeneratedDocumentStatus.PREPARING
    document: ATSResumeDocument | None = None
    review_issues: list[str] = Field(default_factory=list)
    pdf_path: str | None = None
    docx_path: str | None = None
    error: str | None = None
    created_at: datetime = Field(default_factory=utc_now)
    approved_at: datetime | None = None


class ATSResume(Model):
    resume_id: str = Field(default_factory=lambda: new_id("ats_resume"))
    saved_id: str
    current_version: int = Field(default=1, ge=1)
    versions: list[ATSResumeVersion] = Field(default_factory=list)


class ATSResumeApproval(Model):
    approved: bool


class LinkedInSectionInput(Model):
    headline: str = ""
    about: str = ""
    experience: str = ""
    education: str = ""
    skills: str = ""
    certifications: str = ""


class LinkedInProfileSnapshot(Model):
    snapshot_id: str = Field(default_factory=lambda: new_id("linkedin_snapshot"))
    profile_id: str
    profile_revision: int = Field(ge=1)
    language: BCP47Language
    target_roles: list[str] = Field(default_factory=list)
    source_filename: str | None = None
    # Redacted text extracted from the LinkedIn export.  Keeping this text (and
    # never the original PDF bytes) lets the optimizer see the complete export,
    # including lines that the conservative section parser cannot classify.
    source_text: str = Field(default="", max_length=200_000)
    sections: LinkedInSectionInput = Field(default_factory=LinkedInSectionInput)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class LinkedInOptimizationSection(Model):
    section: Literal[
        "headline", "about", "experience", "education", "skills", "certifications"
    ]
    current_text: str
    proposed_text: str
    rationale: str
    keywords: list[str] = Field(default_factory=list)
    record_ids: list[str] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)


class LinkedInOptimizationVersion(Model):
    optimization_id: str = Field(
        default_factory=lambda: new_id("linkedin_optimization")
    )
    snapshot_id: str
    version: int = Field(ge=1)
    profile_revision: int = Field(ge=1)
    language: BCP47Language
    target_roles: list[str] = Field(default_factory=list)
    sections: list[LinkedInOptimizationSection] = Field(default_factory=list)
    status: GeneratedDocumentStatus = GeneratedDocumentStatus.PREPARING
    review_issues: list[str] = Field(default_factory=list)
    error: str | None = None
    created_at: datetime = Field(default_factory=utc_now)


class LinkedInManualImport(Model):
    profile_id: str
    language: BCP47Language
    target_roles: list[str] = Field(default_factory=list)
    text: str = Field(min_length=1, max_length=200_000)


class LinkedInSnapshotUpdate(Model):
    sections: LinkedInSectionInput


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
        return round(
            min(
                100,
                self.requirements + self.experience + self.logistics + self.preferences,
            ),
            2,
        )


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
    language: BCP47Language | None = None
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


class SearchRecord(Model):
    search_id: str = Field(default_factory=lambda: new_id("search"))
    status: SearchStatus = SearchStatus.QUEUED
    query: str = ""
    request: dict[str, Any] = Field(default_factory=dict)
    result: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)

    @model_validator(mode="before")
    @classmethod
    def read_previous_search_format(cls, value: Any) -> Any:
        if isinstance(value, dict) and "run_id" in value:
            value = dict(value)
            value["search_id"] = value.pop("run_id")
            for key in ("thread_id", "mode", "profile_id"):
                value.pop(key, None)
        return value


class Health(Model):
    status: str = "ok"
    api_version: str = "2.0.0"
    database_ready: bool = True
    job_search_ready: bool = True
    ai_optional: bool = True


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

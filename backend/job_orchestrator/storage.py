from __future__ import annotations

import json
import re
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from threading import RLock
from typing import Any

from pydantic import BaseModel

from .schemas import (
    AboutMeProfile,
    AchievementRecord,
    ATSResumeVersion,
    CertificationRecord,
    ConfirmationStatus,
    DeepFitAnalysisV2,
    EducationRecord,
    EmploymentRecord,
    InterviewGuide,
    JobApplication,
    JobRecord,
    LanguageRecord,
    LinkedInOptimizationVersion,
    LinkedInProfileSnapshot,
    PrivateContactBlock,
    ProfessionalRecordSet,
    Profile,
    ProfileUpdate,
    ProjectRecord,
    RecordProvenance,
    SavedJob,
    SearchRecord,
    SkillRecord,
    new_id,
    normalize_bcp47,
    utc_now,
)


class ActiveOperationsError(RuntimeError):
    pass


class ProfileDisplayNameConflictError(ValueError):
    pass


class ProfileHasActiveOperationsError(ActiveOperationsError):
    def __init__(self, profile_id: str, operation_ids: list[str]):
        self.profile_id = profile_id
        self.operation_ids = operation_ids
        super().__init__(", ".join(operation_ids))


SCHEMA = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS profiles (
    profile_id TEXT PRIMARY KEY,
    version INTEGER NOT NULL,
    display_name_normalized TEXT,
    data_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS profile_private_contacts (
    profile_id TEXT PRIMARY KEY REFERENCES profiles(profile_id) ON DELETE CASCADE,
    data_json TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS jobs (
    job_id TEXT PRIMARY KEY,
    source TEXT NOT NULL,
    external_id TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    data_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(source, external_id),
    UNIQUE(content_hash)
);
CREATE VIRTUAL TABLE IF NOT EXISTS jobs_fts USING fts5(
    job_id UNINDEXED,
    title,
    company,
    location,
    description
);
CREATE TABLE IF NOT EXISTS runs (
    run_id TEXT PRIMARY KEY,
    status TEXT NOT NULL,
    mode TEXT NOT NULL,
    data_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS searches (
    search_id TEXT PRIMARY KEY,
    status TEXT NOT NULL,
    mode TEXT NOT NULL,
    data_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_searches_updated ON searches(updated_at DESC);
CREATE TABLE IF NOT EXISTS events (
    event_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES runs(run_id) ON DELETE CASCADE,
    sequence INTEGER NOT NULL,
    type TEXT NOT NULL,
    data_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE(run_id, sequence)
);
CREATE INDEX IF NOT EXISTS idx_events_run_sequence ON events(run_id, sequence);
CREATE TABLE IF NOT EXISTS approvals (
    approval_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES runs(run_id) ON DELETE CASCADE,
    kind TEXT NOT NULL,
    status TEXT NOT NULL,
    data_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_approvals_run ON approvals(run_id, status);
CREATE TABLE IF NOT EXISTS artifacts (
    artifact_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES runs(run_id) ON DELETE CASCADE,
    job_id TEXT NOT NULL,
    profile_id TEXT NOT NULL,
    kind TEXT NOT NULL,
    version INTEGER NOT NULL,
    data_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE(run_id, job_id, profile_id, kind, version)
);
CREATE TABLE IF NOT EXISTS interests (
    interest_id TEXT PRIMARY KEY,
    profile_id TEXT NOT NULL REFERENCES profiles(profile_id) ON DELETE CASCADE,
    job_id TEXT NOT NULL REFERENCES jobs(job_id) ON DELETE CASCADE,
    run_id TEXT NOT NULL,
    data_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(profile_id, job_id)
);
CREATE INDEX IF NOT EXISTS idx_interests_profile_updated
ON interests(profile_id, updated_at DESC);
CREATE TABLE IF NOT EXISTS favorites (
    favorite_id TEXT PRIMARY KEY,
    profile_id TEXT NOT NULL REFERENCES profiles(profile_id) ON DELETE CASCADE,
    job_id TEXT NOT NULL REFERENCES jobs(job_id) ON DELETE CASCADE,
    run_id TEXT NOT NULL,
    data_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(profile_id, job_id)
);
CREATE INDEX IF NOT EXISTS idx_favorites_profile_updated
ON favorites(profile_id, updated_at DESC);
CREATE TABLE IF NOT EXISTS saved_jobs (
    saved_id TEXT PRIMARY KEY,
    job_id TEXT NOT NULL REFERENCES jobs(job_id) ON DELETE CASCADE,
    search_id TEXT NOT NULL,
    data_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(job_id)
);
CREATE INDEX IF NOT EXISTS idx_saved_jobs_updated
ON saved_jobs(updated_at DESC);
CREATE TABLE IF NOT EXISTS fit_analyses_v2 (
    analysis_id TEXT PRIMARY KEY,
    profile_id TEXT NOT NULL REFERENCES profiles(profile_id) ON DELETE CASCADE,
    job_id TEXT NOT NULL REFERENCES jobs(job_id) ON DELETE CASCADE,
    profile_revision INTEGER NOT NULL,
    data_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_fit_analyses_profile_job
ON fit_analyses_v2(profile_id, job_id, created_at DESC);
CREATE TABLE IF NOT EXISTS ats_resume_versions (
    version_id TEXT PRIMARY KEY,
    resume_id TEXT NOT NULL,
    favorite_id TEXT NOT NULL REFERENCES favorites(favorite_id) ON DELETE CASCADE,
    version INTEGER NOT NULL,
    status TEXT NOT NULL,
    data_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(favorite_id, version)
);
CREATE TABLE IF NOT EXISTS applications (
    application_id TEXT PRIMARY KEY,
    favorite_id TEXT NOT NULL REFERENCES favorites(favorite_id) ON DELETE CASCADE,
    profile_id TEXT NOT NULL REFERENCES profiles(profile_id) ON DELETE CASCADE,
    job_id TEXT NOT NULL REFERENCES jobs(job_id) ON DELETE CASCADE,
    status TEXT NOT NULL,
    data_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(favorite_id)
);
CREATE TABLE IF NOT EXISTS application_events (
    event_id TEXT PRIMARY KEY,
    application_id TEXT NOT NULL REFERENCES applications(application_id) ON DELETE CASCADE,
    created_at TEXT NOT NULL,
    data_json TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_application_events_timeline
ON application_events(application_id, created_at, event_id);
CREATE TABLE IF NOT EXISTS linkedin_snapshots (
    snapshot_id TEXT PRIMARY KEY,
    profile_id TEXT NOT NULL REFERENCES profiles(profile_id) ON DELETE CASCADE,
    data_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS linkedin_optimizations (
    optimization_id TEXT PRIMARY KEY,
    snapshot_id TEXT NOT NULL REFERENCES linkedin_snapshots(snapshot_id) ON DELETE CASCADE,
    version INTEGER NOT NULL,
    status TEXT NOT NULL,
    data_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE(snapshot_id, version)
);
"""


def _dump(model: BaseModel) -> str:
    return model.model_dump_json()


def _load[T: BaseModel](model_type: type[T], raw: str) -> T:
    return model_type.model_validate_json(raw)


def _normalize_display_name(value: str) -> str:
    return " ".join(value.split()).casefold()


def _load_private_contact(raw: str | None) -> PrivateContactBlock:
    if not raw:
        return PrivateContactBlock()
    return PrivateContactBlock.model_validate_json(raw)


def _load_profile_row(
    connection: sqlite3.Connection,
    row: sqlite3.Row,
) -> Profile:
    profile = _load(Profile, row["data_json"])
    contact_row = connection.execute(
        "SELECT data_json FROM profile_private_contacts WHERE profile_id=?",
        (profile.profile_id,),
    ).fetchone()
    if contact_row is not None:
        profile.private_contact = _load_private_contact(contact_row["data_json"])
        profile.email = (
            profile.private_contact.emails[0]
            if profile.private_contact.emails
            else None
        )
    return profile


def _save_private_contact(
    connection: sqlite3.Connection,
    profile_id: str,
    contact: PrivateContactBlock,
) -> None:
    contact.updated_at = utc_now()
    connection.execute(
        """INSERT INTO profile_private_contacts(profile_id, data_json, updated_at)
        VALUES(?, ?, ?)
        ON CONFLICT(profile_id) DO UPDATE SET
            data_json=excluded.data_json,
            updated_at=excluded.updated_at""",
        (profile_id, contact.model_dump_json(), contact.updated_at.isoformat()),
    )


def _legacy_provenance(fact: dict[str, Any]) -> RecordProvenance:
    source_url = fact.get("source_url")
    raw_language = fact.get("language")
    try:
        language = normalize_bcp47(str(raw_language)) if raw_language else None
    except ValueError:
        language = None
    return RecordProvenance(
        document_id=fact.get("source_document_id"),
        page=fact.get("source_page"),
        fragment=fact.get("evidence") or fact.get("source_span") or fact.get("text"),
        source_span=fact.get("source_span"),
        source_type=str(fact.get("source_type") or "document"),
        source_url=source_url,
        language=language,
    )


def _records_from_legacy_facts(
    facts: list[dict[str, Any]],
    *,
    profile_revision: int,
) -> ProfessionalRecordSet:
    """Create structured, source-linked records without deleting legacy facts."""

    records = ProfessionalRecordSet()
    for fact in facts:
        text = " ".join(str(fact.get("text") or "").split())
        if not text or str(fact.get("category") or "").casefold() == "contact":
            continue
        raw_language = fact.get("language") or "und"
        try:
            language = normalize_bcp47(str(raw_language))
        except ValueError:
            language = "und"
        common: dict[str, Any] = {
            "record_id": f"record_{fact.get('fact_id') or new_id('legacy')}",
            "provenance": _legacy_provenance(fact),
            "language": language,
            "profile_revision": profile_revision,
            "confirmation_status": (
                ConfirmationStatus.CONFIRMED
                if fact.get("verified")
                else ConfirmationStatus.PENDING_REVIEW
            ),
            "confirmed_at": fact.get("verified_at"),
            "created_at": fact.get("created_at") or utc_now(),
            "updated_at": fact.get("created_at") or utc_now(),
        }
        category = str(fact.get("category") or "").casefold().replace("-", "_")
        if category in {"experience", "employment", "work_experience"}:
            records.employment.append(EmploymentRecord(summary=text, **common))
        elif category in {"project", "projects"}:
            records.projects.append(ProjectRecord(name=text, **common))
        elif category in {"skill", "skills", "technology", "technologies"}:
            records.skills.append(SkillRecord(name=text, **common))
        elif category in {"education", "study", "studies"}:
            records.education.append(EducationRecord(summary=text, **common))
        elif category in {"certification", "certificate", "certifications"}:
            records.certifications.append(CertificationRecord(name=text, **common))
        elif category in {"language", "languages"}:
            records.languages.append(LanguageRecord(name=text, **common))
        elif category in {"achievement", "achievements", "accomplishment"}:
            records.achievements.append(AchievementRecord(statement=text, **common))
    return records


def _prepare_profile_for_storage(profile: Profile) -> Profile:
    """Keep contacts private and enrich fact-only callers without data loss."""

    contact_facts = [
        fact for fact in profile.facts if fact.category.casefold() == "contact"
    ]
    if contact_facts:
        profile.private_contact.legacy_values = list(
            dict.fromkeys(
                [
                    *profile.private_contact.legacy_values,
                    *(fact.text for fact in contact_facts if fact.text.strip()),
                ]
            )
        )
        profile.facts = [
            fact for fact in profile.facts if fact.category.casefold() != "contact"
        ]
    if profile.email and profile.email not in profile.private_contact.emails:
        profile.private_contact.emails.append(profile.email)
    derived = _records_from_legacy_facts(
        [fact.model_dump(mode="json") for fact in profile.facts],
        profile_revision=profile.revision,
    )
    # The current evidence ledger is authoritative. Rebuilding these derived
    # records removes stale lines when a résumé is replaced or a dossier entry
    # is edited, so no retired experience can reach document generation.
    profile.professional_records = derived

    facts_by_record_id = {f"record_{fact.fact_id}": fact for fact in profile.facts}
    for record in profile.professional_records.all_records():
        fact = facts_by_record_id.get(record.record_id)
        if fact is None:
            continue
        record.profile_revision = profile.revision
        record.confirmation_status = (
            ConfirmationStatus.CONFIRMED
            if fact.verified
            else ConfirmationStatus.PENDING_REVIEW
        )
        record.confirmed_at = fact.verified_at if fact.verified else None
        record.updated_at = utc_now()
    return profile


class SQLiteStore:
    """Small repository with one short-lived connection per operation."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = RLock()

    @contextmanager
    def connection(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path, timeout=30, check_same_thread=False)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA journal_mode = WAL")
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def migrate(self) -> None:
        with self._lock, self.connection() as connection:
            connection.executescript(SCHEMA)
            connection.execute(
                "INSERT OR IGNORE INTO schema_migrations(version, applied_at) VALUES(1, ?)",
                (utc_now().isoformat(),),
            )
            connection.execute("DELETE FROM jobs_fts")
            rows = connection.execute("SELECT data_json FROM jobs").fetchall()
            for row in rows:
                job = _load(JobRecord, row["data_json"])
                connection.execute(
                    "INSERT INTO jobs_fts(job_id, title, company, location, description) "
                    "VALUES(?, ?, ?, ?, ?)",
                    (job.job_id, job.title, job.company, job.location, job.description),
                )
            connection.execute(
                "INSERT OR IGNORE INTO schema_migrations(version, applied_at) VALUES(2, ?)",
                (utc_now().isoformat(),),
            )
            artifact_migration = connection.execute(
                "SELECT 1 FROM schema_migrations WHERE version=3"
            ).fetchone()
            if artifact_migration is None:
                connection.executescript(
                    """
                    BEGIN IMMEDIATE;
                    CREATE TABLE artifacts_v3 (
                        artifact_id TEXT PRIMARY KEY,
                        run_id TEXT NOT NULL REFERENCES runs(run_id) ON DELETE CASCADE,
                        job_id TEXT NOT NULL,
                        profile_id TEXT NOT NULL,
                        kind TEXT NOT NULL,
                        version INTEGER NOT NULL,
                        data_json TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        UNIQUE(run_id, job_id, profile_id, kind, version)
                    );
                    INSERT INTO artifacts_v3(
                        artifact_id, run_id, job_id, profile_id, kind, version,
                        data_json, created_at
                    )
                    SELECT artifact_id, run_id, job_id, profile_id, kind, version,
                           data_json, created_at
                    FROM artifacts;
                    DROP TABLE artifacts;
                    ALTER TABLE artifacts_v3 RENAME TO artifacts;
                    COMMIT;
                    """
                )
                connection.execute(
                    "INSERT INTO schema_migrations(version, applied_at) VALUES(3, ?)",
                    (utc_now().isoformat(),),
                )
            connection.execute(
                "INSERT OR IGNORE INTO schema_migrations(version, applied_at) VALUES(4, ?)",
                (utc_now().isoformat(),),
            )
            profile_migration = connection.execute(
                "SELECT 1 FROM schema_migrations WHERE version=5"
            ).fetchone()
            if profile_migration is None:
                columns = {
                    row["name"]
                    for row in connection.execute(
                        "PRAGMA table_info(profiles)"
                    ).fetchall()
                }
                if "display_name_normalized" not in columns:
                    connection.execute(
                        "ALTER TABLE profiles ADD COLUMN display_name_normalized TEXT"
                    )

                used_names: set[str] = set()
                rows = connection.execute(
                    "SELECT profile_id, data_json FROM profiles ORDER BY created_at, profile_id"
                ).fetchall()
                for row in rows:
                    payload = json.loads(row["data_json"])
                    requested_name = payload.get("display_name")
                    base_name = (
                        " ".join(requested_name.split())
                        if isinstance(requested_name, str) and requested_name.strip()
                        else "Perfil actual"
                    )
                    candidate = base_name[:60].rstrip()
                    sequence = 2
                    while _normalize_display_name(candidate) in used_names:
                        suffix = f" {sequence}"
                        candidate = f"{base_name[: 60 - len(suffix)].rstrip()}{suffix}"
                        sequence += 1
                    used_names.add(_normalize_display_name(candidate))
                    payload["display_name"] = candidate
                    raw_revision = payload.get("revision", payload.get("version", 1))
                    try:
                        payload["revision"] = max(1, int(raw_revision))
                    except (TypeError, ValueError):
                        payload["revision"] = 1
                    profile = Profile.model_validate(payload)
                    connection.execute(
                        """UPDATE profiles
                        SET version=?, display_name_normalized=?, data_json=?
                        WHERE profile_id=?""",
                        (
                            profile.version,
                            _normalize_display_name(profile.display_name),
                            _dump(profile),
                            profile.profile_id,
                        ),
                    )
                connection.execute(
                    """CREATE UNIQUE INDEX IF NOT EXISTS idx_profiles_display_name
                    ON profiles(display_name_normalized)
                    WHERE display_name_normalized IS NOT NULL"""
                )
                connection.execute(
                    "INSERT INTO schema_migrations(version, applied_at) VALUES(5, ?)",
                    (utc_now().isoformat(),),
                )
            else:
                connection.execute(
                    """CREATE UNIQUE INDEX IF NOT EXISTS idx_profiles_display_name
                    ON profiles(display_name_normalized)
                    WHERE display_name_normalized IS NOT NULL"""
                )

            structured_profile_migration = connection.execute(
                "SELECT 1 FROM schema_migrations WHERE version=6"
            ).fetchone()
            if structured_profile_migration is None:
                connection.execute("SAVEPOINT structured_profile_v6")
                try:
                    connection.execute(
                        """CREATE TABLE IF NOT EXISTS profile_private_contacts (
                            profile_id TEXT PRIMARY KEY
                                REFERENCES profiles(profile_id) ON DELETE CASCADE,
                            data_json TEXT NOT NULL,
                            updated_at TEXT NOT NULL
                        )"""
                    )
                    rows = connection.execute(
                        "SELECT profile_id, data_json FROM profiles ORDER BY created_at, profile_id"
                    ).fetchall()
                    for row in rows:
                        payload = json.loads(row["data_json"])
                        revision = max(
                            1,
                            int(
                                payload.get("revision", payload.get("version", 1)) or 1
                            ),
                        )
                        contact_payload = payload.pop("private_contact", None) or {}
                        legacy_email = payload.pop("email", None)
                        contact = PrivateContactBlock.model_validate(contact_payload)
                        if legacy_email and legacy_email not in contact.emails:
                            contact.emails.append(str(legacy_email))

                        raw_facts = payload.get("facts") or []
                        professional_facts: list[dict[str, Any]] = []
                        for fact in raw_facts:
                            if str(fact.get("category") or "").casefold() == "contact":
                                text = " ".join(str(fact.get("text") or "").split())
                                if text and text not in contact.legacy_values:
                                    contact.legacy_values.append(text)
                            else:
                                professional_facts.append(fact)
                        payload["facts"] = professional_facts

                        normalized_resumes: dict[str, dict[str, Any]] = {}
                        for raw_language, raw_resume in (
                            payload.get("resumes") or {}
                        ).items():
                            resume = dict(raw_resume)
                            language = normalize_bcp47(
                                str(resume.get("language") or raw_language)
                            )
                            if language in normalized_resumes:
                                raise ValueError(
                                    f"duplicate legacy resume language {language!r}"
                                )
                            resume.pop("confirmed", None)
                            resume["language"] = language
                            resume.setdefault("variant_id", new_id("resume_variant"))
                            resume.setdefault("profile_revision", revision)
                            resume.setdefault(
                                "confirmation_status",
                                (
                                    ConfirmationStatus.CONFIRMED.value
                                    if payload.get("confirmed")
                                    else ConfirmationStatus.PENDING_REVIEW.value
                                ),
                            )
                            if (
                                resume["confirmation_status"]
                                == ConfirmationStatus.CONFIRMED.value
                            ):
                                resume.setdefault(
                                    "confirmed_at",
                                    payload.get("updated_at") or utc_now().isoformat(),
                                )
                            normalized_resumes[language] = resume

                        legacy_resume_text = str(payload.get("resume_text") or "")
                        if not normalized_resumes and legacy_resume_text.strip():
                            language = normalize_bcp47(
                                str(
                                    next(
                                        (
                                            fact.get("language")
                                            for fact in professional_facts
                                            if fact.get("language")
                                        ),
                                        "und",
                                    )
                                )
                            )
                            normalized_resumes[language] = {
                                "variant_id": new_id("resume_variant"),
                                "document_id": new_id("document"),
                                "language": language,
                                "filename": "legacy-resume.txt",
                                "text": legacy_resume_text,
                                "extraction_method": "legacy_text",
                                "warnings": ["Migrated from legacy resume_text"],
                                "profile_revision": revision,
                                "confirmation_status": (
                                    ConfirmationStatus.CONFIRMED.value
                                    if payload.get("confirmed")
                                    else ConfirmationStatus.PENDING_REVIEW.value
                                ),
                                "confirmed_at": (
                                    payload.get("updated_at")
                                    if payload.get("confirmed")
                                    else None
                                ),
                                "imported_at": payload.get("created_at")
                                or utc_now().isoformat(),
                            }
                        payload["resumes"] = normalized_resumes
                        payload.setdefault(
                            "professional_records",
                            _records_from_legacy_facts(
                                professional_facts,
                                profile_revision=revision,
                            ).model_dump(mode="json"),
                        )
                        payload.setdefault("redacted_preview", None)
                        payload.setdefault("cloud_processing_consent", None)

                        profile = _prepare_profile_for_storage(
                            Profile.model_validate(payload)
                        )
                        connection.execute(
                            "UPDATE profiles SET data_json=? WHERE profile_id=?",
                            (_dump(profile), profile.profile_id),
                        )
                        _save_private_contact(
                            connection,
                            profile.profile_id,
                            contact,
                        )
                    connection.execute(
                        "INSERT INTO schema_migrations(version, applied_at) VALUES(6, ?)",
                        (utc_now().isoformat(),),
                    )
                    connection.execute("RELEASE SAVEPOINT structured_profile_v6")
                except Exception:
                    connection.execute("ROLLBACK TO SAVEPOINT structured_profile_v6")
                    connection.execute("RELEASE SAVEPOINT structured_profile_v6")
                    raise

            global_workflows_migration = connection.execute(
                "SELECT 1 FROM schema_migrations WHERE version=7"
            ).fetchone()
            if global_workflows_migration is None:
                connection.execute(
                    "INSERT INTO schema_migrations(version, applied_at) VALUES(7, ?)",
                    (utc_now().isoformat(),),
                )

            legacy_application_migration = connection.execute(
                "SELECT 1 FROM schema_migrations WHERE version=8"
            ).fetchone()
            if legacy_application_migration is None:
                connection.execute(
                    "INSERT INTO schema_migrations(version, applied_at) VALUES(8, ?)",
                    (utc_now().isoformat(),),
                )

            search_storage_migration = connection.execute(
                "SELECT 1 FROM schema_migrations WHERE version=9"
            ).fetchone()
            if search_storage_migration is None:
                connection.execute("SAVEPOINT search_storage_v9")
                try:
                    # Migrate only the modern profile-free search records. Other
                    # runs remain available for historical guide compatibility.
                    rows = connection.execute(
                        "SELECT run_id, status, mode, data_json, created_at, updated_at "
                        "FROM runs WHERE json_extract(data_json, '$.request.flow') = 'simple_search'"
                    ).fetchall()
                    for row in rows:
                        connection.execute(
                            """INSERT OR IGNORE INTO searches(
                                search_id, status, mode, data_json, created_at, updated_at
                            ) VALUES(?, ?, ?, ?, ?, ?)""",
                            (
                                row["run_id"],
                                row["status"],
                                row["mode"],
                                row["data_json"],
                                row["created_at"],
                                row["updated_at"],
                            ),
                        )
                    connection.execute(
                        "INSERT INTO schema_migrations(version, applied_at) VALUES(9, ?)",
                        (utc_now().isoformat(),),
                    )
                    connection.execute("RELEASE SAVEPOINT search_storage_v9")
                except Exception:
                    connection.execute("ROLLBACK TO SAVEPOINT search_storage_v9")
                    connection.execute("RELEASE SAVEPOINT search_storage_v9")
                    raise

            search_reference_migration = connection.execute(
                "SELECT 1 FROM schema_migrations WHERE version=10"
            ).fetchone()
            if search_reference_migration is None:
                # Favorites and interview-guide records predate the dedicated
                # searches table. Their run_id now represents the originating
                # operation identifier and may legitimately point to either a
                # modern search or a historical run. Rebuild the two tables to
                # remove the obsolete runs-only foreign key without losing data.
                connection.commit()
                connection.execute("PRAGMA foreign_keys = OFF")
                try:
                    connection.executescript(
                        """
                        BEGIN IMMEDIATE;
                        CREATE TABLE interests_v10 (
                            interest_id TEXT PRIMARY KEY,
                            profile_id TEXT NOT NULL REFERENCES profiles(profile_id) ON DELETE CASCADE,
                            job_id TEXT NOT NULL REFERENCES jobs(job_id) ON DELETE CASCADE,
                            run_id TEXT NOT NULL,
                            data_json TEXT NOT NULL,
                            created_at TEXT NOT NULL,
                            updated_at TEXT NOT NULL,
                            UNIQUE(profile_id, job_id)
                        );
                        INSERT INTO interests_v10
                        SELECT interest_id, profile_id, job_id, run_id, data_json,
                               created_at, updated_at
                        FROM interests;
                        DROP TABLE interests;
                        ALTER TABLE interests_v10 RENAME TO interests;
                        CREATE INDEX idx_interests_profile_updated
                        ON interests(profile_id, updated_at DESC);

                        CREATE TABLE favorites_v10 (
                            favorite_id TEXT PRIMARY KEY,
                            profile_id TEXT NOT NULL REFERENCES profiles(profile_id) ON DELETE CASCADE,
                            job_id TEXT NOT NULL REFERENCES jobs(job_id) ON DELETE CASCADE,
                            run_id TEXT NOT NULL,
                            data_json TEXT NOT NULL,
                            created_at TEXT NOT NULL,
                            updated_at TEXT NOT NULL,
                            UNIQUE(profile_id, job_id)
                        );
                        INSERT INTO favorites_v10
                        SELECT favorite_id, profile_id, job_id, run_id, data_json,
                               created_at, updated_at
                        FROM favorites;
                        DROP TABLE favorites;
                        ALTER TABLE favorites_v10 RENAME TO favorites;
                        CREATE INDEX idx_favorites_profile_updated
                        ON favorites(profile_id, updated_at DESC);
                        COMMIT;
                        """
                    )
                    connection.execute(
                        "INSERT INTO schema_migrations(version, applied_at) VALUES(10, ?)",
                        (utc_now().isoformat(),),
                    )
                finally:
                    connection.execute("PRAGMA foreign_keys = ON")

            modern_documents_migration = connection.execute(
                "SELECT 1 FROM schema_migrations WHERE version=11"
            ).fetchone()
            if modern_documents_migration is None:
                connection.commit()
                connection.execute("PRAGMA foreign_keys = OFF")
                try:
                    connection.executescript(
                        """
                        BEGIN IMMEDIATE;
                        CREATE TABLE interview_guides (
                            guide_id TEXT PRIMARY KEY,
                            saved_id TEXT NOT NULL REFERENCES saved_jobs(saved_id) ON DELETE CASCADE,
                            profile_id TEXT NOT NULL REFERENCES profiles(profile_id) ON DELETE CASCADE,
                            job_id TEXT NOT NULL REFERENCES jobs(job_id) ON DELETE CASCADE,
                            status TEXT NOT NULL,
                            data_json TEXT NOT NULL,
                            created_at TEXT NOT NULL,
                            updated_at TEXT NOT NULL,
                            UNIQUE(saved_id, profile_id)
                        );
                        CREATE INDEX idx_interview_guides_saved_profile
                        ON interview_guides(saved_id, profile_id, updated_at DESC);

                        CREATE TABLE ats_resume_versions_v11 (
                            version_id TEXT PRIMARY KEY,
                            resume_id TEXT NOT NULL,
                            saved_id TEXT NOT NULL REFERENCES saved_jobs(saved_id) ON DELETE CASCADE,
                            version INTEGER NOT NULL,
                            status TEXT NOT NULL,
                            data_json TEXT NOT NULL,
                            created_at TEXT NOT NULL,
                            updated_at TEXT NOT NULL,
                            UNIQUE(resume_id, version)
                        );
                        CREATE TABLE IF NOT EXISTS historical_records (
                            source_table TEXT NOT NULL,
                            record_id TEXT NOT NULL,
                            data_json TEXT NOT NULL,
                            PRIMARY KEY(source_table, record_id)
                        );
                        """
                    )

                    # Preserve original records, including retired application history,
                    # before changing any relationships or dropping old tables.
                    for table, key in (
                        ("interests", "interest_id"),
                        ("favorites", "favorite_id"),
                        ("applications", "application_id"),
                        ("application_events", "event_id"),
                        ("ats_resume_versions", "version_id"),
                    ):
                        connection.execute(
                            f"INSERT OR IGNORE INTO historical_records SELECT ?, {key}, data_json FROM {table}",
                            (table,),
                        )

                    legacy_jobs: dict[str, str] = {}
                    for table, id_column in (
                        ("interests", "interest_id"),
                        ("favorites", "favorite_id"),
                    ):
                        rows = connection.execute(
                            f"SELECT {id_column}, job_id, run_id, data_json, created_at, updated_at FROM {table}"
                        ).fetchall()
                        for row in rows:
                            job_id = str(row["job_id"])
                            if job_id in legacy_jobs:
                                continue
                            existing = connection.execute(
                                "SELECT saved_id FROM saved_jobs WHERE job_id=?",
                                (job_id,),
                            ).fetchone()
                            if existing:
                                legacy_jobs[job_id] = str(existing["saved_id"])
                                continue
                            job_row = connection.execute(
                                "SELECT data_json FROM jobs WHERE job_id=?", (job_id,)
                            ).fetchone()
                            if not job_row:
                                continue
                            job = _load(JobRecord, job_row["data_json"])
                            saved = SavedJob(
                                job_id=job.job_id,
                                search_id=str(row["run_id"]),
                                title=job.title,
                                company=job.company,
                                location=job.location,
                                source_portals=[job.source_portal]
                                if job.source_portal
                                else [],
                                source_urls=[job.url] if job.url else [],
                                apply_url=job.url,
                                apply_url_type=job.apply_url_type,
                                description=job.description,
                                published_at=job.posted_at,
                                created_at=row["created_at"],
                                updated_at=row["updated_at"],
                            )
                            connection.execute(
                                """INSERT OR IGNORE INTO saved_jobs(
                                    saved_id, job_id, search_id, data_json, created_at, updated_at
                                ) VALUES(?, ?, ?, ?, ?, ?)""",
                                (
                                    saved.saved_id,
                                    saved.job_id,
                                    saved.search_id,
                                    _dump(saved),
                                    saved.created_at.isoformat(),
                                    saved.updated_at.isoformat(),
                                ),
                            )
                            legacy_jobs[job_id] = saved.saved_id

                    for row in connection.execute(
                        "SELECT data_json FROM interests"
                    ).fetchall():
                        payload = json.loads(row["data_json"])
                        saved_id = legacy_jobs.get(str(payload.get("job_id", "")))
                        if not saved_id:
                            continue
                        versions = [
                            {
                                "version": item.get("version", 1),
                                "document_id": item.get("artifact_id", ""),
                                "template_version": item.get("template_version", "2.0"),
                                "profile_revision": item.get("profile_revision", 1),
                                "created_at": item.get(
                                    "created_at", utc_now().isoformat()
                                ),
                            }
                            for item in payload.get("guide_versions", [])
                            if item.get("artifact_id")
                        ]
                        guide = InterviewGuide(
                            guide_id=payload.get("interest_id", new_id("guide")),
                            saved_id=saved_id,
                            profile_id=payload["profile_id"],
                            job_id=payload["job_id"],
                            search_id=payload.get("run_id", "legacy"),
                            job_title=payload.get("job_title", "Vacante"),
                            company=payload.get("company", ""),
                            apply_url=payload["official_apply_url"],
                            published_at=payload["published_at"],
                            analysis=payload["analysis"],
                            document_id=payload.get("guide_artifact_id"),
                            language=payload.get("guide_language", "es"),
                            status=(
                                "ready"
                                if payload.get("guide_artifact_id")
                                else "failed"
                            ),
                            version=payload.get("guide_version", 1),
                            template_version=payload.get("template_version", "2.0"),
                            profile_revision=payload.get("profile_revision", 1),
                            job_content_hash=payload.get("job_content_hash", ""),
                            is_outdated=payload.get("is_outdated", False),
                            versions=versions,
                            error=payload.get("guide_error"),
                            created_at=payload.get("created_at", utc_now().isoformat()),
                            updated_at=payload.get("updated_at", utc_now().isoformat()),
                        )
                        connection.execute(
                            """INSERT OR IGNORE INTO interview_guides(
                                guide_id, saved_id, profile_id, job_id, status,
                                data_json, created_at, updated_at
                            ) VALUES(?, ?, ?, ?, ?, ?, ?, ?)""",
                            (
                                guide.guide_id,
                                guide.saved_id,
                                guide.profile_id,
                                guide.job_id,
                                guide.status,
                                _dump(guide),
                                guide.created_at.isoformat(),
                                guide.updated_at.isoformat(),
                            ),
                        )

                    for row in connection.execute(
                        "SELECT * FROM ats_resume_versions"
                    ).fetchall():
                        payload = json.loads(row["data_json"])
                        favorite = connection.execute(
                            "SELECT job_id FROM favorites WHERE favorite_id=?",
                            (row["favorite_id"],),
                        ).fetchone()
                        if not favorite:
                            continue
                        saved_id = legacy_jobs.get(str(favorite["job_id"]))
                        if not saved_id:
                            continue
                        payload["saved_id"] = saved_id
                        payload.pop("favorite_id", None)
                        connection.execute(
                            """INSERT OR IGNORE INTO ats_resume_versions_v11(
                                version_id, resume_id, saved_id, version, status,
                                data_json, created_at, updated_at
                            ) VALUES(?, ?, ?, ?, ?, ?, ?, ?)""",
                            (
                                row["version_id"],
                                row["resume_id"],
                                saved_id,
                                row["version"],
                                row["status"],
                                json.dumps(payload),
                                row["created_at"],
                                row["updated_at"],
                            ),
                        )
                    connection.execute("DROP TABLE ats_resume_versions")
                    connection.execute(
                        "ALTER TABLE ats_resume_versions_v11 RENAME TO ats_resume_versions"
                    )
                    for table in (
                        "application_events",
                        "applications",
                        "favorites",
                        "interests",
                    ):
                        connection.execute(f"DROP TABLE {table}")
                    connection.execute(
                        "INSERT INTO schema_migrations(version, applied_at) VALUES(11, ?)",
                        (utc_now().isoformat(),),
                    )
                    connection.commit()
                except Exception:
                    connection.rollback()
                    raise
                finally:
                    connection.execute("PRAGMA foreign_keys = ON")

            if (
                connection.execute(
                    "SELECT 1 FROM schema_migrations WHERE version=12"
                ).fetchone()
                is None
            ):
                # Some installations reached v11 before the archive table was
                # introduced. Create it independently so the v12 cleanup is
                # restart-safe instead of failing during application startup.
                connection.execute(
                    """CREATE TABLE IF NOT EXISTS historical_records(
                        source_table TEXT NOT NULL,
                        record_id TEXT NOT NULL,
                        data_json TEXT NOT NULL,
                        PRIMARY KEY(source_table, record_id)
                    )"""
                )
                for table, key in (
                    ("runs", "run_id"),
                    ("events", "event_id"),
                    ("approvals", "approval_id"),
                    ("artifacts", "artifact_id"),
                ):
                    connection.execute(
                        f"INSERT OR IGNORE INTO historical_records SELECT ?, {key}, data_json FROM {table}",
                        (table,),
                    )
                connection.execute(
                    "INSERT INTO schema_migrations VALUES(12, ?)",
                    (utc_now().isoformat(),),
                )
            for table in ("artifacts", "approvals", "events", "runs"):
                connection.execute(f"DROP TABLE IF EXISTS {table}")

            # The bootstrap schema contains retired tables for upgrades from old
            # releases. They must not reappear after a successful modern migration.
            for table in (
                "application_events",
                "applications",
                "favorites",
                "interests",
            ):
                connection.execute(f"DROP TABLE IF EXISTS {table}")

            if (
                connection.execute(
                    "SELECT 1 FROM schema_migrations WHERE version=13"
                ).fetchone()
                is None
            ):
                connection.executescript(
                    """
                    CREATE TABLE IF NOT EXISTS about_me (
                        dossier_id TEXT PRIMARY KEY,
                        revision INTEGER NOT NULL,
                        data_json TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    );
                    CREATE TABLE IF NOT EXISTS job_applications (
                        application_id TEXT PRIMARY KEY,
                        saved_id TEXT NOT NULL REFERENCES saved_jobs(saved_id) ON DELETE CASCADE,
                        profile_id TEXT NOT NULL REFERENCES profiles(profile_id) ON DELETE CASCADE,
                        job_id TEXT NOT NULL REFERENCES jobs(job_id) ON DELETE CASCADE,
                        status TEXT NOT NULL,
                        data_json TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL,
                        UNIQUE(saved_id)
                    );
                    CREATE INDEX IF NOT EXISTS idx_job_applications_updated
                    ON job_applications(updated_at DESC);
                    """
                )
                connection.execute(
                    "INSERT INTO schema_migrations(version, applied_at) VALUES(13, ?)",
                    (utc_now().isoformat(),),
                )

            if (
                connection.execute(
                    "SELECT 1 FROM schema_migrations WHERE version=14"
                ).fetchone()
                is None
            ):
                # Early modern databases retained the legacy uniqueness rule on
                # (saved_id, version). That makes version 1 for a second profile
                # collide with version 1 created for the first profile. A résumé
                # has its own stable resume_id, so version numbers must be scoped
                # to that résumé instead of to the saved vacancy.
                connection.commit()
                connection.execute("PRAGMA foreign_keys = OFF")
                try:
                    connection.executescript(
                        """
                        BEGIN IMMEDIATE;
                        CREATE TABLE ats_resume_versions_v14 (
                            version_id TEXT PRIMARY KEY,
                            resume_id TEXT NOT NULL,
                            saved_id TEXT NOT NULL REFERENCES saved_jobs(saved_id) ON DELETE CASCADE,
                            version INTEGER NOT NULL,
                            status TEXT NOT NULL,
                            data_json TEXT NOT NULL,
                            created_at TEXT NOT NULL,
                            updated_at TEXT NOT NULL,
                            UNIQUE(resume_id, version)
                        );
                        INSERT INTO ats_resume_versions_v14(
                            version_id, resume_id, saved_id, version, status,
                            data_json, created_at, updated_at
                        )
                        SELECT version_id, resume_id, saved_id, version, status,
                               data_json, created_at, updated_at
                        FROM ats_resume_versions;
                        DROP TABLE ats_resume_versions;
                        ALTER TABLE ats_resume_versions_v14 RENAME TO ats_resume_versions;
                        CREATE INDEX idx_ats_resume_versions_saved
                        ON ats_resume_versions(saved_id, created_at DESC);
                        COMMIT;
                        """
                    )
                    connection.execute(
                        "INSERT INTO schema_migrations(version, applied_at) VALUES(14, ?)",
                        (utc_now().isoformat(),),
                    )
                    connection.commit()
                except Exception:
                    connection.rollback()
                    raise
                finally:
                    connection.execute("PRAGMA foreign_keys = ON")

    @staticmethod
    def _display_name_owner(
        connection: sqlite3.Connection,
        display_name: str,
        *,
        excluding_profile_id: str | None = None,
    ) -> str | None:
        sql = "SELECT profile_id FROM profiles WHERE display_name_normalized=?"
        params: list[str] = [_normalize_display_name(display_name)]
        if excluding_profile_id is not None:
            sql += " AND profile_id<>?"
            params.append(excluding_profile_id)
        row = connection.execute(sql, params).fetchone()
        return str(row["profile_id"]) if row else None

    @classmethod
    def _next_available_display_name(
        cls,
        connection: sqlite3.Connection,
        base_name: str,
    ) -> str:
        base_name = " ".join(base_name.split())[:60].rstrip() or "Perfil actual"
        if cls._display_name_owner(connection, base_name) is None:
            return base_name
        sequence = 2
        while True:
            suffix = f" {sequence}"
            candidate = f"{base_name[: 60 - len(suffix)].rstrip()}{suffix}"
            if cls._display_name_owner(connection, candidate) is None:
                return candidate
            sequence += 1

    @classmethod
    def _assert_display_name_available(
        cls,
        connection: sqlite3.Connection,
        display_name: str,
        *,
        excluding_profile_id: str | None = None,
    ) -> None:
        if (
            cls._display_name_owner(
                connection,
                display_name,
                excluding_profile_id=excluding_profile_id,
            )
            is not None
        ):
            raise ProfileDisplayNameConflictError(display_name)

    def save_profile(self, profile: Profile) -> Profile:
        with self._lock, self.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT data_json FROM profiles WHERE profile_id=?",
                (profile.profile_id,),
            ).fetchone()
            if row is None:
                profile.display_name = self._next_available_display_name(
                    connection, profile.display_name
                )
            else:
                existing = _load_profile_row(connection, row)
                self._assert_display_name_available(
                    connection,
                    profile.display_name,
                    excluding_profile_id=profile.profile_id,
                )
                profile.revision = max(profile.revision, existing.revision + 1)

            profile = _prepare_profile_for_storage(profile)
            profile.updated_at = utc_now()
            connection.execute(
                """INSERT INTO profiles(
                    profile_id, version, display_name_normalized, data_json,
                    created_at, updated_at
                ) VALUES(?, ?, ?, ?, ?, ?)
                ON CONFLICT(profile_id) DO UPDATE SET
                    version=excluded.version,
                    display_name_normalized=excluded.display_name_normalized,
                    data_json=excluded.data_json,
                    updated_at=excluded.updated_at""",
                (
                    profile.profile_id,
                    profile.version,
                    _normalize_display_name(profile.display_name),
                    _dump(profile),
                    profile.created_at.isoformat(),
                    profile.updated_at.isoformat(),
                ),
            )
            _save_private_contact(
                connection,
                profile.profile_id,
                profile.private_contact,
            )
        return profile

    def get_profile(self, profile_id: str) -> Profile | None:
        with self.connection() as connection:
            row = connection.execute(
                "SELECT data_json FROM profiles WHERE profile_id=?", (profile_id,)
            ).fetchone()
            return _load_profile_row(connection, row) if row else None

    def list_profiles(self) -> list[Profile]:
        with self.connection() as connection:
            rows = connection.execute(
                "SELECT data_json FROM profiles ORDER BY updated_at DESC"
            ).fetchall()
            return [_load_profile_row(connection, row) for row in rows]

    def get_about_me(self) -> AboutMeProfile:
        with self.connection() as connection:
            row = connection.execute(
                "SELECT data_json FROM about_me WHERE dossier_id='about_me'"
            ).fetchone()
        return _load(AboutMeProfile, row["data_json"]) if row else AboutMeProfile()

    def save_about_me(self, dossier: AboutMeProfile) -> AboutMeProfile:
        dossier.updated_at = utc_now()
        with self.connection() as connection:
            connection.execute(
                """INSERT INTO about_me(dossier_id, revision, data_json, updated_at)
                VALUES(?, ?, ?, ?)
                ON CONFLICT(dossier_id) DO UPDATE SET
                    revision=excluded.revision,
                    data_json=excluded.data_json,
                    updated_at=excluded.updated_at""",
                (
                    dossier.dossier_id,
                    dossier.revision,
                    _dump(dossier),
                    dossier.updated_at.isoformat(),
                ),
            )
        return dossier

    def get_private_contact(self, profile_id: str) -> PrivateContactBlock | None:
        with self.connection() as connection:
            row = connection.execute(
                "SELECT data_json FROM profile_private_contacts WHERE profile_id=?",
                (profile_id,),
            ).fetchone()
        return _load_private_contact(row["data_json"]) if row else None

    def save_private_contact(
        self,
        profile_id: str,
        contact: PrivateContactBlock,
    ) -> PrivateContactBlock | None:
        with self._lock, self.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            if (
                connection.execute(
                    "SELECT 1 FROM profiles WHERE profile_id=?",
                    (profile_id,),
                ).fetchone()
                is None
            ):
                return None
            _save_private_contact(connection, profile_id, contact)
        return contact

    def update_profile(
        self,
        profile_id: str,
        update: ProfileUpdate,
    ) -> Profile | None:
        """Apply an explicit profile metadata update and advance its revision."""

        with self._lock, self.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT data_json FROM profiles WHERE profile_id=?",
                (profile_id,),
            ).fetchone()
            if row is None:
                return None
            profile = _load_profile_row(connection, row)
            if update.display_name is not None:
                self._assert_display_name_available(
                    connection,
                    update.display_name,
                    excluding_profile_id=profile_id,
                )
                profile.display_name = update.display_name
            if update.preferences is not None:
                profile.preferences = update.preferences
            profile.version += 1
            profile.revision += 1
            profile = _prepare_profile_for_storage(profile)
            profile.updated_at = utc_now()
            connection.execute(
                """UPDATE profiles
                SET version=?, display_name_normalized=?, data_json=?, updated_at=?
                WHERE profile_id=?""",
                (
                    profile.version,
                    _normalize_display_name(profile.display_name),
                    _dump(profile),
                    profile.updated_at.isoformat(),
                    profile.profile_id,
                ),
            )
            _save_private_contact(
                connection,
                profile.profile_id,
                profile.private_contact,
            )
            return profile

    def rename_profile(self, profile_id: str, display_name: str) -> Profile | None:
        return self.update_profile(
            profile_id,
            ProfileUpdate(display_name=display_name),
        )

    def duplicate_profile(
        self,
        profile_id: str,
        *,
        display_name: str | None = None,
    ) -> Profile | None:
        """Clone profile-owned CV data with fresh identifiers and no run history."""

        with self._lock, self.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT data_json FROM profiles WHERE profile_id=?",
                (profile_id,),
            ).fetchone()
            if row is None:
                return None
            source = _load_profile_row(connection, row)
            if display_name is None:
                duplicate_name = self._next_available_display_name(
                    connection, f"{source.display_name} copia"
                )
            else:
                duplicate_name = ProfileUpdate(display_name=display_name).display_name
                assert duplicate_name is not None
                self._assert_display_name_available(connection, duplicate_name)

            now = utc_now()
            document_ids: dict[str, str] = {}
            resumes = {}
            for language, resume in source.resumes.items():
                document_id = new_id("document")
                document_ids[resume.document_id] = document_id
                resumes[language] = resume.model_copy(
                    update={
                        "variant_id": new_id("resume_variant"),
                        "document_id": document_id,
                        "imported_at": now,
                    }
                )

            facts = []
            for fact in source.facts:
                source_document_id = fact.source_document_id
                if source_document_id is not None:
                    source_document_id = document_ids.setdefault(
                        source_document_id, new_id("document")
                    )
                facts.append(
                    fact.model_copy(
                        update={
                            "fact_id": new_id("fact"),
                            "source_document_id": source_document_id,
                            "created_at": now,
                        }
                    )
                )

            professional_records = _records_from_legacy_facts(
                [fact.model_dump(mode="json") for fact in facts],
                profile_revision=1,
            )

            duplicate = source.model_copy(
                deep=True,
                update={
                    "profile_id": new_id("profile"),
                    "display_name": duplicate_name,
                    "resumes": resumes,
                    "facts": facts,
                    "professional_records": professional_records,
                    "redacted_preview": None,
                    "cloud_processing_consent": None,
                    "version": 1,
                    "revision": 1,
                    "created_at": now,
                    "updated_at": now,
                    "private_contact": source.private_contact.model_copy(
                        deep=True,
                        update={"contact_id": new_id("contact"), "updated_at": now},
                    ),
                },
            )
            connection.execute(
                """INSERT INTO profiles(
                    profile_id, version, display_name_normalized, data_json,
                    created_at, updated_at
                ) VALUES(?, ?, ?, ?, ?, ?)""",
                (
                    duplicate.profile_id,
                    duplicate.version,
                    _normalize_display_name(duplicate.display_name),
                    _dump(duplicate),
                    duplicate.created_at.isoformat(),
                    duplicate.updated_at.isoformat(),
                ),
            )
            _save_private_contact(
                connection,
                duplicate.profile_id,
                duplicate.private_contact,
            )
            return duplicate

    def delete_profile(self, profile_id: str) -> bool:
        """Delete one profile and its owned history while preserving shared jobs."""

        with self._lock, self.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            profile = connection.execute(
                "SELECT 1 FROM profiles WHERE profile_id=?",
                (profile_id,),
            ).fetchone()
            if profile is None:
                return False

            active_documents = connection.execute(
                "SELECT guide_id FROM interview_guides WHERE profile_id=? AND status IN ('preparing', 'reviewing', 'rendering')",
                (profile_id,),
            ).fetchall()
            if active_documents:
                raise ProfileHasActiveOperationsError(
                    profile_id, [row[0] for row in active_documents]
                )
            active_ats = connection.execute(
                "SELECT version_id FROM ats_resume_versions WHERE json_extract(data_json, '$.profile_id')=? AND status IN ('preparing', 'rendering', 'reviewing')",
                (profile_id,),
            ).fetchall()
            if active_ats:
                raise ProfileHasActiveOperationsError(
                    profile_id, [row[0] for row in active_ats]
                )

            # ATS documents belong to the selected profile even though the
            # saved vacancy itself is profile-free. Remove completed/failed
            # versions explicitly before deleting the profile.
            connection.execute(
                "DELETE FROM ats_resume_versions "
                "WHERE json_extract(data_json, '$.profile_id')=?",
                (profile_id,),
            )
            cursor = connection.execute(
                "DELETE FROM profiles WHERE profile_id=?", (profile_id,)
            )
            return cursor.rowcount == 1

    def save_job(self, job: JobRecord) -> JobRecord:
        now = utc_now().isoformat()
        with self.connection() as connection:
            existing = connection.execute(
                "SELECT job_id FROM jobs WHERE content_hash=? OR (source=? AND external_id=?) LIMIT 1",
                (job.content_hash, job.source, job.external_id),
            ).fetchone()
            if existing:
                job.job_id = existing["job_id"]
                connection.execute(
                    "UPDATE jobs SET content_hash=?, data_json=?, updated_at=? WHERE job_id=?",
                    (job.content_hash, _dump(job), now, job.job_id),
                )
            else:
                connection.execute(
                    """INSERT INTO jobs(job_id, source, external_id, content_hash, data_json, created_at, updated_at)
                    VALUES(?, ?, ?, ?, ?, ?, ?)""",
                    (
                        job.job_id,
                        job.source,
                        job.external_id,
                        job.content_hash,
                        _dump(job),
                        job.retrieved_at.isoformat(),
                        now,
                    ),
                )
            connection.execute("DELETE FROM jobs_fts WHERE job_id=?", (job.job_id,))
            connection.execute(
                "INSERT INTO jobs_fts(job_id, title, company, location, description) "
                "VALUES(?, ?, ?, ?, ?)",
                (job.job_id, job.title, job.company, job.location, job.description),
            )
        return job

    def get_job(self, job_id: str) -> JobRecord | None:
        with self.connection() as connection:
            row = connection.execute(
                "SELECT data_json FROM jobs WHERE job_id=?", (job_id,)
            ).fetchone()
        return _load(JobRecord, row["data_json"]) if row else None

    def list_jobs(self, limit: int = 100) -> list[JobRecord]:
        with self.connection() as connection:
            rows = connection.execute(
                "SELECT data_json FROM jobs ORDER BY updated_at DESC LIMIT ?", (limit,)
            ).fetchall()
        return [_load(JobRecord, row["data_json"]) for row in rows]

    def save_interview_guide(self, guide: InterviewGuide) -> InterviewGuide:
        guide.updated_at = utc_now()
        with self._lock, self.connection() as connection:
            existing = connection.execute(
                "SELECT guide_id FROM interview_guides WHERE saved_id=? AND profile_id=?",
                (guide.saved_id, guide.profile_id),
            ).fetchone()
            if existing:
                guide.guide_id = str(existing["guide_id"])
            connection.execute(
                """INSERT INTO interview_guides(
                    guide_id, saved_id, profile_id, job_id, status,
                    data_json, created_at, updated_at
                ) VALUES(?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(guide_id) DO UPDATE SET
                    status=excluded.status, data_json=excluded.data_json,
                    updated_at=excluded.updated_at""",
                (
                    guide.guide_id,
                    guide.saved_id,
                    guide.profile_id,
                    guide.job_id,
                    guide.status,
                    _dump(guide),
                    guide.created_at.isoformat(),
                    guide.updated_at.isoformat(),
                ),
            )
        return guide

    def get_interview_guide(self, guide_id: str) -> InterviewGuide | None:
        with self.connection() as connection:
            row = connection.execute(
                "SELECT data_json FROM interview_guides WHERE guide_id=?", (guide_id,)
            ).fetchone()
        return _load(InterviewGuide, row["data_json"]) if row else None

    def get_interview_guide_for_saved_job(
        self, saved_id: str, profile_id: str
    ) -> InterviewGuide | None:
        with self.connection() as connection:
            row = connection.execute(
                """SELECT data_json FROM interview_guides
                WHERE saved_id=? AND profile_id=?""",
                (saved_id, profile_id),
            ).fetchone()
        return _load(InterviewGuide, row["data_json"]) if row else None

    def list_interview_guides(self) -> list[InterviewGuide]:
        with self.connection() as connection:
            rows = connection.execute(
                "SELECT data_json FROM interview_guides ORDER BY updated_at DESC"
            ).fetchall()
        return [_load(InterviewGuide, row["data_json"]) for row in rows]

    def save_saved_job(self, saved: SavedJob) -> SavedJob:
        """Idempotently bookmark a vacancy without requiring a profile."""
        saved.updated_at = utc_now()
        with self._lock, self.connection() as connection:
            existing = connection.execute(
                "SELECT data_json FROM saved_jobs WHERE job_id=?", (saved.job_id,)
            ).fetchone()
            if existing is not None:
                return _load(SavedJob, existing["data_json"])
            connection.execute(
                """INSERT INTO saved_jobs(
                    saved_id, job_id, search_id, data_json, created_at, updated_at
                ) VALUES(?, ?, ?, ?, ?, ?)""",
                (
                    saved.saved_id,
                    saved.job_id,
                    saved.search_id,
                    _dump(saved),
                    saved.created_at.isoformat(),
                    saved.updated_at.isoformat(),
                ),
            )
        return saved

    def get_saved_job(self, saved_id: str) -> SavedJob | None:
        with self.connection() as connection:
            row = connection.execute(
                "SELECT data_json FROM saved_jobs WHERE saved_id=?", (saved_id,)
            ).fetchone()
        return _load(SavedJob, row["data_json"]) if row else None

    def get_saved_job_for_job(self, job_id: str) -> SavedJob | None:
        with self.connection() as connection:
            row = connection.execute(
                "SELECT data_json FROM saved_jobs WHERE job_id=?", (job_id,)
            ).fetchone()
        return _load(SavedJob, row["data_json"]) if row else None

    def list_saved_jobs(self) -> list[SavedJob]:
        with self.connection() as connection:
            rows = connection.execute(
                "SELECT data_json FROM saved_jobs ORDER BY updated_at DESC"
            ).fetchall()
        return [_load(SavedJob, row["data_json"]) for row in rows]

    def delete_saved_job(self, saved_id: str) -> bool:
        with self._lock, self.connection() as connection:
            for table, identifier in (
                ("interview_guides", "guide_id"),
                ("ats_resume_versions", "version_id"),
            ):
                active = connection.execute(
                    f"SELECT {identifier} FROM {table} WHERE saved_id=? "
                    "AND status IN ('preparing', 'reviewing', 'rendering')",
                    (saved_id,),
                ).fetchone()
                if active:
                    raise ActiveOperationsError(str(active[0]))
            cursor = connection.execute(
                "DELETE FROM saved_jobs WHERE saved_id=?", (saved_id,)
            )
        return cursor.rowcount == 1

    def save_job_application(self, application: JobApplication) -> JobApplication:
        application.updated_at = utc_now()
        with self.connection() as connection:
            connection.execute(
                """INSERT INTO job_applications(
                    application_id, saved_id, profile_id, job_id, status,
                    data_json, created_at, updated_at
                ) VALUES(?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(application_id) DO UPDATE SET
                    profile_id=excluded.profile_id,
                    status=excluded.status,
                    data_json=excluded.data_json,
                    updated_at=excluded.updated_at""",
                (
                    application.application_id,
                    application.saved_id,
                    application.profile_id,
                    application.job_id,
                    application.status,
                    _dump(application),
                    application.created_at.isoformat(),
                    application.updated_at.isoformat(),
                ),
            )
        return application

    def get_job_application(self, application_id: str) -> JobApplication | None:
        with self.connection() as connection:
            row = connection.execute(
                "SELECT data_json FROM job_applications WHERE application_id=?",
                (application_id,),
            ).fetchone()
        return _load(JobApplication, row["data_json"]) if row else None

    def get_job_application_for_saved_job(
        self, saved_id: str
    ) -> JobApplication | None:
        with self.connection() as connection:
            row = connection.execute(
                "SELECT data_json FROM job_applications WHERE saved_id=?",
                (saved_id,),
            ).fetchone()
        return _load(JobApplication, row["data_json"]) if row else None

    def list_job_applications(self) -> list[JobApplication]:
        with self.connection() as connection:
            rows = connection.execute(
                "SELECT data_json FROM job_applications ORDER BY updated_at DESC"
            ).fetchall()
        return [_load(JobApplication, row["data_json"]) for row in rows]

    def delete_job_application(self, application_id: str) -> bool:
        with self.connection() as connection:
            cursor = connection.execute(
                "DELETE FROM job_applications WHERE application_id=?",
                (application_id,),
            )
        return cursor.rowcount == 1

    def save_deep_analysis_v2(self, analysis: DeepFitAnalysisV2) -> DeepFitAnalysisV2:
        with self.connection() as connection:
            connection.execute(
                """INSERT OR REPLACE INTO fit_analyses_v2(
                    analysis_id, profile_id, job_id, profile_revision,
                    data_json, created_at
                ) VALUES(?, ?, ?, ?, ?, ?)""",
                (
                    analysis.analysis_id,
                    analysis.profile_id,
                    analysis.job_id,
                    analysis.profile_revision,
                    _dump(analysis),
                    analysis.generated_at.isoformat(),
                ),
            )
        return analysis

    def latest_deep_analysis_v2(
        self, profile_id: str, job_id: str
    ) -> DeepFitAnalysisV2 | None:
        with self.connection() as connection:
            row = connection.execute(
                """SELECT data_json FROM fit_analyses_v2
                WHERE profile_id=? AND job_id=?
                ORDER BY created_at DESC LIMIT 1""",
                (profile_id, job_id),
            ).fetchone()
        return _load(DeepFitAnalysisV2, row["data_json"]) if row else None

    def list_deep_analyses_v2(self) -> list[DeepFitAnalysisV2]:
        with self.connection() as connection:
            rows = connection.execute(
                "SELECT data_json FROM fit_analyses_v2 ORDER BY created_at DESC"
            ).fetchall()
        return [_load(DeepFitAnalysisV2, row["data_json"]) for row in rows]

    def save_ats_resume_version(self, version: ATSResumeVersion) -> ATSResumeVersion:
        updated_at = utc_now()
        with self.connection() as connection:
            connection.execute(
                """INSERT INTO ats_resume_versions(
                    version_id, resume_id, saved_id, version, status,
                    data_json, created_at, updated_at
                ) VALUES(?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(version_id) DO UPDATE SET
                    status=excluded.status, data_json=excluded.data_json,
                    updated_at=excluded.updated_at""",
                (
                    version.version_id,
                    version.resume_id,
                    version.saved_id,
                    version.version,
                    version.status,
                    _dump(version),
                    version.created_at.isoformat(),
                    updated_at.isoformat(),
                ),
            )
        return version

    def get_ats_resume_version(self, version_id: str) -> ATSResumeVersion | None:
        with self.connection() as connection:
            row = connection.execute(
                "SELECT data_json FROM ats_resume_versions WHERE version_id=?",
                (version_id,),
            ).fetchone()
        return _load(ATSResumeVersion, row["data_json"]) if row else None

    def latest_ats_resume_version_by_resume_id(
        self, resume_id: str
    ) -> ATSResumeVersion | None:
        with self.connection() as connection:
            row = connection.execute(
                """SELECT data_json FROM ats_resume_versions
                WHERE resume_id=? ORDER BY version DESC LIMIT 1""",
                (resume_id,),
            ).fetchone()
        return _load(ATSResumeVersion, row["data_json"]) if row else None

    def list_ats_resume_versions(self, saved_id: str) -> list[ATSResumeVersion]:
        with self.connection() as connection:
            rows = connection.execute(
                """SELECT data_json FROM ats_resume_versions
                WHERE saved_id=? ORDER BY version DESC""",
                (saved_id,),
            ).fetchall()
        return [_load(ATSResumeVersion, row["data_json"]) for row in rows]

    def list_ats_resume_versions_for_profile(
        self, profile_id: str
    ) -> list[ATSResumeVersion]:
        with self.connection() as connection:
            rows = connection.execute(
                "SELECT data_json FROM ats_resume_versions "
                "WHERE json_extract(data_json, '$.profile_id')=? "
                "ORDER BY created_at DESC",
                (profile_id,),
            ).fetchall()
        return [_load(ATSResumeVersion, row["data_json"]) for row in rows]

    def list_all_ats_resume_versions(self) -> list[ATSResumeVersion]:
        with self.connection() as connection:
            rows = connection.execute(
                "SELECT data_json FROM ats_resume_versions ORDER BY created_at DESC"
            ).fetchall()
        return [_load(ATSResumeVersion, row["data_json"]) for row in rows]

    def save_linkedin_snapshot(
        self, snapshot: LinkedInProfileSnapshot
    ) -> LinkedInProfileSnapshot:
        snapshot.updated_at = utc_now()
        with self.connection() as connection:
            connection.execute(
                """INSERT INTO linkedin_snapshots(
                    snapshot_id, profile_id, data_json, created_at, updated_at
                ) VALUES(?, ?, ?, ?, ?)
                ON CONFLICT(snapshot_id) DO UPDATE SET
                    data_json=excluded.data_json, updated_at=excluded.updated_at""",
                (
                    snapshot.snapshot_id,
                    snapshot.profile_id,
                    _dump(snapshot),
                    snapshot.created_at.isoformat(),
                    snapshot.updated_at.isoformat(),
                ),
            )
        return snapshot

    def get_linkedin_snapshot(self, snapshot_id: str) -> LinkedInProfileSnapshot | None:
        with self.connection() as connection:
            row = connection.execute(
                "SELECT data_json FROM linkedin_snapshots WHERE snapshot_id=?",
                (snapshot_id,),
            ).fetchone()
        return _load(LinkedInProfileSnapshot, row["data_json"]) if row else None

    def list_linkedin_snapshots(
        self, profile_id: str | None = None
    ) -> list[LinkedInProfileSnapshot]:
        sql = "SELECT data_json FROM linkedin_snapshots"
        params: tuple[Any, ...] = ()
        if profile_id:
            sql += " WHERE profile_id=?"
            params = (profile_id,)
        sql += " ORDER BY updated_at DESC"
        with self.connection() as connection:
            rows = connection.execute(sql, params).fetchall()
        return [_load(LinkedInProfileSnapshot, row["data_json"]) for row in rows]

    def save_linkedin_optimization(
        self, optimization: LinkedInOptimizationVersion
    ) -> LinkedInOptimizationVersion:
        with self.connection() as connection:
            connection.execute(
                """INSERT INTO linkedin_optimizations(
                    optimization_id, snapshot_id, version, status, data_json, created_at
                ) VALUES(?, ?, ?, ?, ?, ?)
                ON CONFLICT(optimization_id) DO UPDATE SET
                    status=excluded.status, data_json=excluded.data_json""",
                (
                    optimization.optimization_id,
                    optimization.snapshot_id,
                    optimization.version,
                    optimization.status,
                    _dump(optimization),
                    optimization.created_at.isoformat(),
                ),
            )
        return optimization

    def list_linkedin_optimizations(
        self, snapshot_id: str
    ) -> list[LinkedInOptimizationVersion]:
        with self.connection() as connection:
            rows = connection.execute(
                """SELECT data_json FROM linkedin_optimizations
                WHERE snapshot_id=? ORDER BY version DESC""",
                (snapshot_id,),
            ).fetchall()
        return [_load(LinkedInOptimizationVersion, row["data_json"]) for row in rows]

    def search_jobs_text(self, query: str, limit: int = 100) -> list[JobRecord]:
        tokens = re.findall(r"[\w+#.]+", query.casefold())
        if not tokens:
            return self.list_jobs(limit)
        expression = " AND ".join(f'"{token}"' for token in tokens[:12])
        with self.connection() as connection:
            rows = connection.execute(
                """SELECT jobs.data_json
                FROM jobs_fts JOIN jobs ON jobs.job_id = jobs_fts.job_id
                WHERE jobs_fts MATCH ?
                ORDER BY bm25(jobs_fts), jobs.updated_at DESC
                LIMIT ?""",
                (expression, limit),
            ).fetchall()
        return [_load(JobRecord, row["data_json"]) for row in rows]

    def save_search(self, search: SearchRecord) -> SearchRecord:
        """Persist a modern profile-free search without mixing it with legacy runs."""

        search.updated_at = utc_now()
        with self.connection() as connection:
            connection.execute(
                """INSERT INTO searches(search_id, status, mode, data_json, created_at, updated_at)
                VALUES(?, ?, ?, ?, ?, ?)
                ON CONFLICT(search_id) DO UPDATE SET
                    status=excluded.status, data_json=excluded.data_json,
                    updated_at=excluded.updated_at""",
                (
                    search.search_id,
                    search.status,
                    "live",
                    _dump(search),
                    search.created_at.isoformat(),
                    search.updated_at.isoformat(),
                ),
            )
        return search

    def get_search(self, search_id: str) -> SearchRecord | None:
        with self.connection() as connection:
            row = connection.execute(
                "SELECT data_json FROM searches WHERE search_id=?", (search_id,)
            ).fetchone()
        return _load(SearchRecord, row["data_json"]) if row else None

    def list_searches(self, limit: int = 50) -> list[SearchRecord]:
        with self.connection() as connection:
            rows = connection.execute(
                "SELECT data_json FROM searches ORDER BY updated_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [_load(SearchRecord, row["data_json"]) for row in rows]

    def clear_all_data(self) -> dict[str, int]:
        """Delete user data atomically, refusing while any run can still mutate it."""

        table_order = (
            "linkedin_optimizations",
            "linkedin_snapshots",
            "job_applications",
            "ats_resume_versions",
            "interview_guides",
            "fit_analyses_v2",
            "saved_jobs",
            "historical_records",
            "searches",
            "jobs_fts",
            "jobs",
            "profile_private_contacts",
            "about_me",
            "profiles",
        )
        with self._lock, self.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            for table, key in (
                ("interview_guides", "guide_id"),
                ("ats_resume_versions", "version_id"),
            ):
                pending = connection.execute(
                    f"SELECT {key} FROM {table} WHERE status IN ('preparing', 'reviewing', 'rendering') LIMIT 1"
                ).fetchone()
                if pending:
                    raise ActiveOperationsError(str(pending[0]))
            active_search = connection.execute(
                """SELECT search_id FROM searches
                WHERE status IN ('queued', 'running') LIMIT 1"""
            ).fetchone()
            if active_search is not None:
                raise ActiveOperationsError(str(active_search["search_id"]))
            counts = {
                table: int(
                    connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                )
                for table in table_order
                if table != "jobs_fts"
            }
            for table in table_order:
                connection.execute(f"DELETE FROM {table}")
        return counts

    def recover_interrupted_documents(self) -> None:
        """Interrupted operations are retryable; never restart paid calls automatically."""
        with self._lock, self.connection() as connection:
            for table, key in (
                ("interview_guides", "guide_id"),
                ("ats_resume_versions", "version_id"),
            ):
                rows = connection.execute(
                    f"SELECT {key}, data_json FROM {table} WHERE status IN ('preparing', 'reviewing', 'rendering')"
                ).fetchall()
                for row in rows:
                    payload = json.loads(row["data_json"])
                    payload["status"] = "failed"
                    payload["error"] = (
                        "La preparación se interrumpió. Puedes volver a intentarlo."
                    )
                    connection.execute(
                        f"UPDATE {table} SET status='failed', data_json=? WHERE {key}=?",
                        (json.dumps(payload, ensure_ascii=False), row[0]),
                    )

    def export_snapshot(self) -> dict[str, Any]:
        jobs = self.list_jobs(limit=100_000)
        searches = self.list_searches(limit=100_000)
        profiles = self.list_profiles()
        snapshot: dict[str, Any] = {
            "profiles": [item.model_dump(mode="json") for item in profiles],
            "jobs": [item.model_dump(mode="json") for item in jobs],
            "searches": [item.model_dump(mode="json") for item in searches],
        }
        with self.connection() as connection:
            history = connection.execute(
                "SELECT source_table, record_id, data_json FROM historical_records"
            ).fetchall()
        if history:
            snapshot["historical_records"] = [
                {
                    "source_table": row["source_table"],
                    "record_id": row["record_id"],
                    "data": json.loads(row["data_json"]),
                }
                for row in history
            ]
        saved_jobs = [item.model_dump(mode="json") for item in self.list_saved_jobs()]
        analyses = [
            item.model_dump(mode="json") for item in self.list_deep_analyses_v2()
        ]
        interview_guides = [
            item.model_dump(mode="json") for item in self.list_interview_guides()
        ]
        ats_resumes = [
            item.model_dump(mode="json") for item in self.list_all_ats_resume_versions()
        ]
        linkedin_snapshots = [
            {
                **item.model_dump(mode="json"),
                "optimizations": [
                    version.model_dump(mode="json")
                    for version in self.list_linkedin_optimizations(item.snapshot_id)
                ],
            }
            for item in self.list_linkedin_snapshots()
        ]
        about_me = self.get_about_me()
        applications = [
            item.model_dump(mode="json") for item in self.list_job_applications()
        ]
        # Keep the original empty export contract stable while including every
        # Global entity as soon as it exists.
        if saved_jobs:
            snapshot["saved_jobs"] = saved_jobs
        if analyses:
            snapshot["fit_analyses"] = analyses
        if interview_guides:
            snapshot["interview_guides"] = interview_guides
        if ats_resumes:
            snapshot["ats_resumes"] = ats_resumes
        if linkedin_snapshots:
            snapshot["linkedin_snapshots"] = linkedin_snapshots
        if about_me.entries or any(
            (
                about_me.contact.full_name,
                about_me.contact.emails,
                about_me.contact.phones,
                about_me.contact.websites,
            )
        ):
            snapshot["about_me"] = about_me.model_dump(mode="json")
        if applications:
            snapshot["applications"] = applications
        if profiles:
            snapshot["private_contacts"] = [
                {
                    "profile_id": item.profile_id,
                    "contact": item.private_contact.model_dump(mode="json"),
                }
                for item in profiles
            ]
        return snapshot

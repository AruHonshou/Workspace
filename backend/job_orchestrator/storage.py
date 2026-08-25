from __future__ import annotations

import re
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from threading import RLock
from typing import Any

from pydantic import BaseModel

from .schemas import (
    Approval,
    Artifact,
    GraphEvent,
    Interest,
    JobRecord,
    Profile,
    Run,
    RunStatus,
    utc_now,
)


class ActiveRunsError(RuntimeError):
    pass


SCHEMA = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS profiles (
    profile_id TEXT PRIMARY KEY,
    version INTEGER NOT NULL,
    data_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
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
    run_id TEXT NOT NULL REFERENCES runs(run_id) ON DELETE CASCADE,
    data_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(profile_id, job_id)
);
CREATE INDEX IF NOT EXISTS idx_interests_profile_updated
ON interests(profile_id, updated_at DESC);
"""


def _dump(model: BaseModel) -> str:
    return model.model_dump_json()


def _load[T: BaseModel](model_type: type[T], raw: str) -> T:
    return model_type.model_validate_json(raw)


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

    def save_profile(self, profile: Profile) -> Profile:
        now = utc_now().isoformat()
        with self.connection() as connection:
            connection.execute(
                """INSERT INTO profiles(profile_id, version, data_json, created_at, updated_at)
                VALUES(?, ?, ?, ?, ?)
                ON CONFLICT(profile_id) DO UPDATE SET
                    version=excluded.version, data_json=excluded.data_json, updated_at=excluded.updated_at""",
                (profile.profile_id, profile.version, _dump(profile), profile.created_at.isoformat(), now),
            )
        return profile

    def get_profile(self, profile_id: str) -> Profile | None:
        with self.connection() as connection:
            row = connection.execute(
                "SELECT data_json FROM profiles WHERE profile_id=?", (profile_id,)
            ).fetchone()
        return _load(Profile, row["data_json"]) if row else None

    def list_profiles(self) -> list[Profile]:
        with self.connection() as connection:
            rows = connection.execute(
                "SELECT data_json FROM profiles ORDER BY updated_at DESC"
            ).fetchall()
        return [_load(Profile, row["data_json"]) for row in rows]

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
            row = connection.execute("SELECT data_json FROM jobs WHERE job_id=?", (job_id,)).fetchone()
        return _load(JobRecord, row["data_json"]) if row else None

    def list_jobs(self, limit: int = 100) -> list[JobRecord]:
        with self.connection() as connection:
            rows = connection.execute(
                "SELECT data_json FROM jobs ORDER BY updated_at DESC LIMIT ?", (limit,)
            ).fetchall()
        return [_load(JobRecord, row["data_json"]) for row in rows]

    def save_interest(self, interest: Interest) -> Interest:
        """Create or update one interest per profile and vacancy."""

        interest.updated_at = utc_now()
        with self._lock, self.connection() as connection:
            row = connection.execute(
                "SELECT interest_id, created_at FROM interests WHERE profile_id=? AND job_id=?",
                (interest.profile_id, interest.job_id),
            ).fetchone()
            if row:
                interest.interest_id = row["interest_id"]
                connection.execute(
                    "UPDATE interests SET run_id=?, data_json=?, updated_at=? WHERE interest_id=?",
                    (
                        interest.run_id,
                        _dump(interest),
                        interest.updated_at.isoformat(),
                        interest.interest_id,
                    ),
                )
            else:
                connection.execute(
                    """INSERT INTO interests(
                    interest_id, profile_id, job_id, run_id, data_json, created_at, updated_at
                    ) VALUES(?, ?, ?, ?, ?, ?, ?)""",
                    (
                        interest.interest_id,
                        interest.profile_id,
                        interest.job_id,
                        interest.run_id,
                        _dump(interest),
                        interest.created_at.isoformat(),
                        interest.updated_at.isoformat(),
                    ),
                )
        return interest

    def get_interest(self, interest_id: str) -> Interest | None:
        with self.connection() as connection:
            row = connection.execute(
                "SELECT data_json FROM interests WHERE interest_id=?", (interest_id,)
            ).fetchone()
        return _load(Interest, row["data_json"]) if row else None

    def get_interest_for_job(self, profile_id: str, job_id: str) -> Interest | None:
        with self.connection() as connection:
            row = connection.execute(
                "SELECT data_json FROM interests WHERE profile_id=? AND job_id=?",
                (profile_id, job_id),
            ).fetchone()
        return _load(Interest, row["data_json"]) if row else None

    def list_interests(self, profile_id: str | None = None) -> list[Interest]:
        sql = "SELECT data_json FROM interests"
        params: tuple[Any, ...] = ()
        if profile_id:
            sql += " WHERE profile_id=?"
            params = (profile_id,)
        sql += " ORDER BY updated_at DESC"
        with self.connection() as connection:
            rows = connection.execute(sql, params).fetchall()
        return [_load(Interest, row["data_json"]) for row in rows]

    def delete_interest(self, interest_id: str) -> bool:
        with self._lock, self.connection() as connection:
            cursor = connection.execute(
                "DELETE FROM interests WHERE interest_id=?", (interest_id,)
            )
        return cursor.rowcount == 1

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

    def save_run(self, run: Run) -> Run:
        run.updated_at = utc_now()
        with self.connection() as connection:
            connection.execute(
                """INSERT INTO runs(run_id, status, mode, data_json, created_at, updated_at)
                VALUES(?, ?, ?, ?, ?, ?)
                ON CONFLICT(run_id) DO UPDATE SET
                    status=excluded.status, data_json=excluded.data_json, updated_at=excluded.updated_at""",
                (
                    run.run_id,
                    run.status,
                    run.mode,
                    _dump(run),
                    run.created_at.isoformat(),
                    run.updated_at.isoformat(),
                ),
            )
        return run

    def save_run_if_not_terminal(self, run: Run) -> Run | None:
        """CAS-update a run without allowing stale workers to undo a terminal state."""

        run.updated_at = utc_now()
        with self._lock, self.connection() as connection:
            cursor = connection.execute(
                """UPDATE runs
                SET status=?, mode=?, data_json=?, updated_at=?
                WHERE run_id=?
                  AND status NOT IN ('completed', 'failed', 'cancelled')""",
                (
                    run.status,
                    run.mode,
                    _dump(run),
                    run.updated_at.isoformat(),
                    run.run_id,
                ),
            )
            if cursor.rowcount != 1:
                return None
        return run

    def get_run(self, run_id: str) -> Run | None:
        with self.connection() as connection:
            row = connection.execute("SELECT data_json FROM runs WHERE run_id=?", (run_id,)).fetchone()
        return _load(Run, row["data_json"]) if row else None

    def list_runs(self, limit: int = 50) -> list[Run]:
        with self.connection() as connection:
            rows = connection.execute(
                "SELECT data_json FROM runs ORDER BY updated_at DESC LIMIT ?", (limit,)
            ).fetchall()
        return [_load(Run, row["data_json"]) for row in rows]

    def cancel_run(self, run_id: str) -> Run | None:
        run, _ = self.cancel_run_once(run_id)
        return run

    def cancel_run_once(self, run_id: str) -> tuple[Run | None, bool]:
        """Atomically move a non-terminal run to cancelled exactly once."""

        with self._lock, self.connection() as connection:
            row = connection.execute(
                "SELECT data_json FROM runs WHERE run_id=?", (run_id,)
            ).fetchone()
            if row is None:
                return None, False
            run = _load(Run, row["data_json"])
            if run.status in {
                RunStatus.CANCELLED,
                RunStatus.COMPLETED,
                RunStatus.FAILED,
            }:
                return run, False
            run.status = RunStatus.CANCELLED
            run.updated_at = utc_now()
            connection.execute(
                "UPDATE runs SET status=?, data_json=?, updated_at=? WHERE run_id=?",
                (
                    run.status,
                    _dump(run),
                    run.updated_at.isoformat(),
                    run.run_id,
                ),
            )
            return run, True

    def append_event(self, event: GraphEvent) -> GraphEvent:
        with self._lock, self.connection() as connection:
            row = connection.execute(
                "SELECT COALESCE(MAX(sequence), 0) + 1 AS next FROM events WHERE run_id=?",
                (event.run_id,),
            ).fetchone()
            event.sequence = int(row["next"])
            connection.execute(
                """INSERT INTO events(event_id, run_id, sequence, type, data_json, created_at)
                VALUES(?, ?, ?, ?, ?, ?)""",
                (
                    event.event_id,
                    event.run_id,
                    event.sequence,
                    event.type,
                    _dump(event),
                    event.timestamp.isoformat(),
                ),
            )
        return event

    def next_event_sequence(self, run_id: str) -> int:
        with self.connection() as connection:
            row = connection.execute(
                "SELECT COALESCE(MAX(sequence), 0) + 1 AS next FROM events WHERE run_id=?",
                (run_id,),
            ).fetchone()
        return int(row["next"])

    def list_events(self, run_id: str, after: int = 0, limit: int = 500) -> list[GraphEvent]:
        with self.connection() as connection:
            rows = connection.execute(
                """SELECT data_json FROM events WHERE run_id=? AND sequence>?
                ORDER BY sequence ASC LIMIT ?""",
                (run_id, after, limit),
            ).fetchall()
        return [_load(GraphEvent, row["data_json"]) for row in rows]

    def save_approval(self, approval: Approval) -> Approval:
        now = utc_now().isoformat()
        with self.connection() as connection:
            connection.execute(
                """INSERT INTO approvals(approval_id, run_id, kind, status, data_json, created_at, updated_at)
                VALUES(?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(approval_id) DO UPDATE SET
                    status=excluded.status, data_json=excluded.data_json, updated_at=excluded.updated_at""",
                (
                    approval.approval_id,
                    approval.run_id,
                    approval.kind,
                    approval.status,
                    _dump(approval),
                    approval.created_at.isoformat(),
                    now,
                ),
            )
        return approval

    def resolve_approval(self, approval: Approval) -> Approval | None:
        """Atomically transition one approval from pending to its terminal decision."""

        now = utc_now().isoformat()
        with self._lock, self.connection() as connection:
            cursor = connection.execute(
                """UPDATE approvals
                SET status=?, data_json=?, updated_at=?
                WHERE approval_id=? AND status='pending'""",
                (
                    approval.status,
                    _dump(approval),
                    now,
                    approval.approval_id,
                ),
            )
            if cursor.rowcount != 1:
                return None
        return approval

    def get_approval(self, approval_id: str) -> Approval | None:
        with self.connection() as connection:
            row = connection.execute(
                "SELECT data_json FROM approvals WHERE approval_id=?", (approval_id,)
            ).fetchone()
        return _load(Approval, row["data_json"]) if row else None

    def list_approvals(self, run_id: str, pending_only: bool = False) -> list[Approval]:
        sql = "SELECT data_json FROM approvals WHERE run_id=?"
        params: list[Any] = [run_id]
        if pending_only:
            sql += " AND status='pending'"
        sql += " ORDER BY created_at"
        with self.connection() as connection:
            rows = connection.execute(sql, params).fetchall()
        return [_load(Approval, row["data_json"]) for row in rows]

    def save_artifact(self, artifact: Artifact) -> Artifact:
        with self._lock, self.connection() as connection:
            try:
                connection.execute(
                    """INSERT INTO artifacts(
                    artifact_id, run_id, job_id, profile_id, kind, version, data_json, created_at
                ) VALUES(?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        artifact.artifact_id,
                        artifact.run_id,
                        artifact.job_id,
                        artifact.profile_id,
                        artifact.kind,
                        artifact.version,
                        _dump(artifact),
                        artifact.created_at.isoformat(),
                    ),
                )
            except sqlite3.IntegrityError as exc:
                row = connection.execute(
                    """SELECT data_json FROM artifacts
                    WHERE artifact_id=? OR (
                        run_id=? AND job_id=? AND profile_id=? AND kind=? AND version=?
                    ) LIMIT 1""",
                    (
                        artifact.artifact_id,
                        artifact.run_id,
                        artifact.job_id,
                        artifact.profile_id,
                        artifact.kind,
                        artifact.version,
                    ),
                ).fetchone()
                existing = _load(Artifact, row["data_json"]) if row else None
                if existing == artifact:
                    return existing
                raise ValueError(
                    "Artifact versions are immutable within a run"
                ) from exc
        return artifact

    def save_artifact_if_run_active(self, artifact: Artifact) -> Artifact | None:
        """Insert an artifact only while its owning run is non-terminal.

        ``BEGIN IMMEDIATE`` serializes the status check and insert against cancellation,
        including callers using another store instance for the same SQLite database.
        """

        with self._lock, self.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                """SELECT status FROM runs
                WHERE run_id=?
                  AND status NOT IN ('completed', 'failed', 'cancelled')""",
                (artifact.run_id,),
            ).fetchone()
            if row is None:
                return None
            try:
                connection.execute(
                    """INSERT INTO artifacts(
                    artifact_id, run_id, job_id, profile_id, kind, version, data_json, created_at
                ) VALUES(?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        artifact.artifact_id,
                        artifact.run_id,
                        artifact.job_id,
                        artifact.profile_id,
                        artifact.kind,
                        artifact.version,
                        _dump(artifact),
                        artifact.created_at.isoformat(),
                    ),
                )
            except sqlite3.IntegrityError as exc:
                existing_row = connection.execute(
                    """SELECT data_json FROM artifacts
                    WHERE artifact_id=? OR (
                        run_id=? AND job_id=? AND profile_id=? AND kind=? AND version=?
                    ) LIMIT 1""",
                    (
                        artifact.artifact_id,
                        artifact.run_id,
                        artifact.job_id,
                        artifact.profile_id,
                        artifact.kind,
                        artifact.version,
                    ),
                ).fetchone()
                existing = (
                    _load(Artifact, existing_row["data_json"])
                    if existing_row
                    else None
                )
                if existing == artifact:
                    return existing
                raise ValueError(
                    "Artifact versions are immutable within a run"
                ) from exc
        return artifact

    def get_artifact(self, artifact_id: str) -> Artifact | None:
        with self.connection() as connection:
            row = connection.execute(
                "SELECT data_json FROM artifacts WHERE artifact_id=?", (artifact_id,)
            ).fetchone()
        return _load(Artifact, row["data_json"]) if row else None

    def list_artifacts(self, run_id: str) -> list[Artifact]:
        with self.connection() as connection:
            rows = connection.execute(
                "SELECT data_json FROM artifacts WHERE run_id=? ORDER BY created_at", (run_id,)
            ).fetchall()
        return [_load(Artifact, row["data_json"]) for row in rows]

    def clear_all_data(self) -> dict[str, int]:
        """Delete user data atomically, refusing while any run can still mutate it."""

        table_order = (
            "interests",
            "artifacts",
            "approvals",
            "events",
            "runs",
            "jobs_fts",
            "jobs",
            "profiles",
        )
        with self._lock, self.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            active = connection.execute(
                """SELECT run_id FROM runs
                WHERE status IN ('queued', 'running', 'awaiting_user') LIMIT 1"""
            ).fetchone()
            if active is not None:
                raise ActiveRunsError(str(active["run_id"]))
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

    def export_snapshot(self) -> dict[str, Any]:
        jobs = self.list_jobs(limit=100_000)
        runs = self.list_runs(limit=100_000)
        return {
            "profiles": [item.model_dump(mode="json") for item in self.list_profiles()],
            "jobs": [item.model_dump(mode="json") for item in jobs],
            "runs": [item.model_dump(mode="json") for item in runs],
            "events": [
                event.model_dump(mode="json")
                for run in runs
                for event in self.list_events(run.run_id, limit=100_000)
            ],
            "approvals": [
                approval.model_dump(mode="json")
                for run in runs
                for approval in self.list_approvals(run.run_id)
            ],
            "artifacts": [
                artifact.model_dump(mode="json")
                for run in runs
                for artifact in self.list_artifacts(run.run_id)
            ],
        }

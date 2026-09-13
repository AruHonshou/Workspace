import json

import pytest

from job_orchestrator.schemas import JobRecord, Profile, SourceKind, utc_now
from job_orchestrator.storage import SCHEMA, ActiveOperationsError, SQLiteStore


def legacy_store(tmp_path):
    store = SQLiteStore(tmp_path / "upgrade.sqlite3")
    store.migrate()
    profiles = [
        store.save_profile(Profile(display_name=name, name="Ada"))
        for name in ("QA", "Developer")
    ]
    job = store.save_job(
        JobRecord(
            source=SourceKind.MANUAL,
            external_id="migration-job",
            title="QA",
            company="Example",
            description="Test APIs",
            url="https://example.com/job",
            posted_at=utc_now(),
        )
    )
    stamp = utc_now().isoformat()
    with store.connection() as db:
        db.execute("DROP TABLE ats_resume_versions")
        db.execute("DROP TABLE interview_guides")
        db.execute("DELETE FROM schema_migrations WHERE version=11")
        db.executescript(SCHEMA)
        for index, profile in enumerate(profiles):
            favorite_id = f"favorite_{index}"
            payload = {
                "favorite_id": favorite_id,
                "profile_id": profile.profile_id,
                "job_id": job.job_id,
            }
            db.execute(
                "INSERT INTO favorites VALUES(?, ?, ?, ?, ?, ?, ?)",
                (
                    favorite_id,
                    profile.profile_id,
                    job.job_id,
                    "search_old",
                    json.dumps(payload),
                    stamp,
                    stamp,
                ),
            )
            version = {
                "version_id": f"version_{index}",
                "resume_id": f"resume_{index}",
                "favorite_id": favorite_id,
                "version": 1,
                "profile_id": profile.profile_id,
                "profile_revision": 1,
                "job_id": job.job_id,
                "job_content_hash": job.content_hash,
                "status": "ready",
                "pdf_path": f"existing-{index}.pdf",
            }
            db.execute(
                "INSERT INTO ats_resume_versions VALUES(?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    version["version_id"],
                    version["resume_id"],
                    favorite_id,
                    1,
                    "ready",
                    json.dumps(version),
                    stamp,
                    stamp,
                ),
            )
        guide = {
            "interest_id": "interest_old",
            "profile_id": profiles[0].profile_id,
            "job_id": job.job_id,
            "run_id": "search_old",
            "job_title": job.title,
            "company": job.company,
            "official_apply_url": str(job.url),
            "published_at": stamp,
            "analysis": {
                "job_id": job.job_id,
                "profile_id": profiles[0].profile_id,
                "score": 70,
                "level": "medium",
            },
            "guide_language": "en",
            "guide_artifact_id": "artifact_existing",
            "guide_versions": [{"version": 1, "artifact_id": "artifact_existing"}],
        }
        db.execute(
            "INSERT INTO interests VALUES(?, ?, ?, ?, ?, ?, ?)",
            (
                "interest_old",
                profiles[0].profile_id,
                job.job_id,
                "search_old",
                json.dumps(guide),
                stamp,
                stamp,
            ),
        )
        db.execute(
            "INSERT INTO applications VALUES(?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "application_old",
                "favorite_0",
                profiles[0].profile_id,
                job.job_id,
                "interview",
                json.dumps({"note": "Preserve my interview notes"}),
                stamp,
                stamp,
            ),
        )
    return store


def test_upgrade_preserves_both_profiles_documents_and_archives_retired_history(
    tmp_path,
):
    store = legacy_store(tmp_path)
    store.migrate()
    store.migrate()  # Real apps restart; retired tables must not reappear.
    saved = store.list_saved_jobs()
    assert len(saved) == 1
    versions = store.list_ats_resume_versions(saved[0].saved_id)
    assert len(versions) == 2
    assert {item.pdf_path for item in versions} == {"existing-0.pdf", "existing-1.pdf"}
    guide = store.list_interview_guides()[0]
    assert guide.document_id == "artifact_existing"
    assert guide.versions[0].document_id == "artifact_existing"
    assert guide.saved_id == saved[0].saved_id
    assert "Preserve my interview notes" in json.dumps(store.export_snapshot())
    with store.connection() as db:
        assert db.execute("PRAGMA foreign_key_check").fetchall() == []
        names = {
            row[0]
            for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
    assert not names.intersection(
        {"interests", "favorites", "applications", "application_events"}
    )


def test_failed_upgrade_rolls_back_without_partial_tables_or_lost_records(
    tmp_path, monkeypatch
):
    store = legacy_store(tmp_path)
    import job_orchestrator.storage as module

    real = module.InterviewGuide

    def fail(**kwargs):
        raise RuntimeError("Synthetic migration interruption")

    monkeypatch.setattr(module, "InterviewGuide", fail)
    with pytest.raises(RuntimeError, match="interruption"):
        store.migrate()
    with store.connection() as db:
        assert db.execute("SELECT COUNT(*) FROM interests").fetchone()[0] == 1
        assert db.execute("SELECT COUNT(*) FROM ats_resume_versions").fetchone()[0] == 2
        assert (
            db.execute("SELECT 1 FROM schema_migrations WHERE version=11").fetchone()
            is None
        )
        assert (
            db.execute(
                "SELECT 1 FROM sqlite_master WHERE name='interview_guides'"
            ).fetchone()
            is None
        )
    monkeypatch.setattr(module, "InterviewGuide", real)
    store.migrate()
    assert len(store.list_interview_guides()) == 1


def test_interrupted_guide_is_retryable_without_new_paid_calls(tmp_path):
    store = legacy_store(tmp_path)
    store.migrate()
    guide = store.list_interview_guides()[0]
    guide.status = "rendering"
    store.save_interview_guide(guide)
    store.recover_interrupted_documents()
    recovered = store.get_interview_guide(guide.guide_id)
    assert recovered.status == "failed"
    assert recovered.versions == guide.versions


def test_v12_upgrade_repairs_an_older_v11_database_without_archive_table(tmp_path):
    store = SQLiteStore(tmp_path / "v11-without-archive.sqlite3")
    store.migrate()
    with store.connection() as db:
        db.execute("DROP TABLE historical_records")
        db.execute("DELETE FROM schema_migrations WHERE version=12")

    store.migrate()

    with store.connection() as db:
        assert db.execute("SELECT 1 FROM schema_migrations WHERE version=12").fetchone()
        assert db.execute(
            "SELECT 1 FROM sqlite_master WHERE name='historical_records'"
        ).fetchone()
        assert db.execute("PRAGMA foreign_key_check").fetchall() == []


@pytest.mark.parametrize("status", ["preparing", "reviewing", "rendering"])
def test_active_resume_protects_saved_job_from_deletion(tmp_path, status):
    store = legacy_store(tmp_path)
    store.migrate()
    saved = store.list_saved_jobs()[0]
    resume = store.list_ats_resume_versions(saved.saved_id)[0]
    resume.status = status
    store.save_ats_resume_version(resume)
    with pytest.raises(ActiveOperationsError):
        store.delete_saved_job(saved.saved_id)
    assert store.get_saved_job(saved.saved_id) is not None
    assert store.get_ats_resume_version(resume.version_id) is not None

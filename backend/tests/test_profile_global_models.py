from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest
from pydantic import ValidationError

from job_orchestrator.schemas import (
    CloudProcessingConsent,
    ConfirmationStatus,
    ConsentStatus,
    PrivateContactBlock,
    Profile,
    ProfileFact,
    RedactedProfessionalPreview,
    ResumeVariant,
    normalize_bcp47,
    utc_now,
)
from job_orchestrator.storage import SQLiteStore


def _confirmed_variant(language: str = "es") -> ResumeVariant:
    return ResumeVariant(
        document_id="document_cv",
        language=language,
        filename="cv.pdf",
        text="QA engineer with Playwright experience.",
        extraction_method="pdf_text",
        confirmation_status=ConfirmationStatus.CONFIRMED,
    )


def test_resume_variants_are_limited_to_spanish_and_english() -> None:
    profile = Profile(
        name="Ada",
        confirmed=True,
        resumes={
            "es-cr": _confirmed_variant("es-CR"),
            "en-us": ResumeVariant(
                document_id="document_en",
                language="en-US",
                filename="resume.pdf",
                extraction_method="pdf_text",
            ),
        },
    )

    assert set(profile.resumes) == {"es", "en"}
    assert profile.has_confirmed_resume is True
    assert profile.ready_for_search is True
    assert normalize_bcp47("zh-hant-tw") == "zh-Hant-TW"

    with pytest.raises((ValidationError, ValueError)):
        ResumeVariant(
            document_id="unsupported",
            language="pt-BR",
            filename="curriculo.pdf",
            extraction_method="pdf_text",
        )

    with pytest.raises((ValidationError, ValueError)):
        ResumeVariant(
            document_id="bad",
            language="../../secret",
            filename="bad.pdf",
            extraction_method="pdf_text",
        )


def test_legacy_translation_state_is_discarded_without_losing_es_en_resumes() -> None:
    profile = Profile.model_validate(
        {
            "name": "Ada",
            "translation_drafts": [{"draft_id": "legacy"}],
            "resumes": {
                "es-CR": {
                    "document_id": "document_es",
                    "language": "es-CR",
                    "filename": "cv.pdf",
                    "extraction_method": "pdf_text",
                    "translated_from_variant_id": "legacy_source",
                    "translation_review_required": True,
                },
                "en-US": {
                    "document_id": "document_en",
                    "language": "en-US",
                    "filename": "resume.pdf",
                    "extraction_method": "pdf_text",
                },
                "pt-BR": {
                    "document_id": "document_pt",
                    "language": "pt-BR",
                    "filename": "curriculo.pdf",
                    "extraction_method": "pdf_text",
                },
            },
        }
    )

    assert set(profile.resumes) == {"es", "en"}
    serialized = profile.model_dump(mode="json")
    assert "translation_drafts" not in serialized
    assert "translated_from_variant_id" not in str(serialized)


def test_contacts_are_stored_separately_and_never_enter_profile_json(
    tmp_path: Path,
) -> None:
    store = SQLiteStore(tmp_path / "profiles.sqlite3")
    store.migrate()
    saved = store.save_profile(
        Profile(
            name="Ada",
            email="ada@example.test",
            private_contact=PrivateContactBlock(
                phones=["+506 8888-7777"],
                address_lines=["Private street 1"],
            ),
            facts=[
                ProfileFact(category="contact", text="ada@example.test"),
                ProfileFact(
                    category="skill",
                    text="Automated API testing with Python",
                    language="en-US",
                    verified=True,
                ),
            ],
        )
    )

    with sqlite3.connect(store.path) as connection:
        raw_profile = connection.execute(
            "SELECT data_json FROM profiles WHERE profile_id=?",
            (saved.profile_id,),
        ).fetchone()[0]
        raw_contact = connection.execute(
            "SELECT data_json FROM profile_private_contacts WHERE profile_id=?",
            (saved.profile_id,),
        ).fetchone()[0]

    assert "ada@example.test" not in raw_profile
    assert "+506 8888-7777" not in raw_profile
    assert "Private street 1" not in raw_profile
    assert "ada@example.test" in raw_contact
    assert [fact.category for fact in saved.facts] == ["skill"]
    assert len(saved.professional_records.skills) == 1
    assert saved.professional_records.skills[0].provenance.fragment == (
        "Automated API testing with Python"
    )

    reloaded = store.get_profile(saved.profile_id)
    assert reloaded is not None
    assert reloaded.private_contact.emails == ["ada@example.test"]
    assert reloaded.private_contact.phones == ["+506 8888-7777"]
    snapshot = store.export_snapshot()
    assert "private_contact" not in snapshot["profiles"][0]
    assert snapshot["private_contacts"][0]["contact"]["emails"] == ["ada@example.test"]


def test_consent_is_bound_to_the_exact_redacted_preview_and_revision() -> None:
    preview = RedactedProfessionalPreview(
        profile_revision=7,
        language="es-CO",
        redacted_text="Experiencia profesional en QA.",
        included_record_ids=["record_skill"],
        redacted_categories=["email", "phone"],
        content_hash="sha256:preview",
    )
    consent = CloudProcessingConsent(
        profile_revision=7,
        preview_id=preview.preview_id,
        preview_hash=preview.content_hash,
        purposes=["fit_analysis"],
        status=ConsentStatus.GRANTED,
    )
    profile = Profile(
        name="Ada",
        redacted_preview=preview,
        cloud_processing_consent=consent,
    )

    assert profile.cloud_processing_consent is not None
    assert profile.cloud_processing_consent.status == "granted"
    assert profile.cloud_processing_consent.decided_at is not None
    assert profile.cloud_processing_consent.preview_hash == preview.content_hash


def test_profile_storage_does_not_truncate_large_fact_sets(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path / "complete.sqlite3")
    store.migrate()
    profile = store.save_profile(
        Profile(
            name="Complete profile",
            facts=[
                ProfileFact(
                    category="skill",
                    text=f"Verified professional skill {index}",
                    language="en",
                    verified=True,
                )
                for index in range(125)
            ],
        )
    )

    reloaded = store.get_profile(profile.profile_id)
    assert reloaded is not None
    assert len(reloaded.facts) == 125
    assert len(reloaded.professional_records.skills) == 125


def test_structured_profile_migration_rolls_back_as_one_transaction(
    tmp_path: Path,
) -> None:
    database = tmp_path / "broken-legacy.sqlite3"
    timestamp = utc_now().isoformat()
    legacy_payload = {
        "profile_id": "profile_broken",
        "display_name": "Broken",
        "name": "Ada",
        "email": "must-remain-on-rollback@example.test",
        "resumes": {
            "es": {
                "document_id": "document_1",
                "language": "es",
                "filename": "one.pdf",
                "extraction_method": "pdf_text",
            },
            "ES": {
                "document_id": "document_2",
                "language": "ES",
                "filename": "two.pdf",
                "extraction_method": "pdf_text",
            },
        },
        "facts": [],
        "version": 1,
        "revision": 1,
        "confirmed": False,
        "created_at": timestamp,
        "updated_at": timestamp,
    }
    with sqlite3.connect(database) as connection:
        connection.executescript(
            """
            CREATE TABLE schema_migrations (
                version INTEGER PRIMARY KEY,
                applied_at TEXT NOT NULL
            );
            CREATE TABLE profiles (
                profile_id TEXT PRIMARY KEY,
                version INTEGER NOT NULL,
                display_name_normalized TEXT,
                data_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            """
        )
        connection.executemany(
            "INSERT INTO schema_migrations(version, applied_at) VALUES(?, ?)",
            [(version, timestamp) for version in range(1, 6)],
        )
        connection.execute(
            """INSERT INTO profiles(
                profile_id, version, display_name_normalized, data_json,
                created_at, updated_at
            ) VALUES(?, ?, ?, ?, ?, ?)""",
            (
                "profile_broken",
                1,
                "broken",
                json.dumps(legacy_payload),
                timestamp,
                timestamp,
            ),
        )

    with pytest.raises(ValueError, match="duplicate legacy resume language"):
        SQLiteStore(database).migrate()

    with sqlite3.connect(database) as connection:
        raw_after = connection.execute(
            "SELECT data_json FROM profiles WHERE profile_id='profile_broken'"
        ).fetchone()[0]
        migration = connection.execute(
            "SELECT 1 FROM schema_migrations WHERE version=6"
        ).fetchone()
        contacts = connection.execute(
            "SELECT COUNT(*) FROM profile_private_contacts"
        ).fetchone()[0]

    assert json.loads(raw_after) == legacy_payload
    assert migration is None
    assert contacts == 0

from job_orchestrator.ranking import normalize_job
from job_orchestrator.schemas import SavedJob, SourceKind, utc_now


def _confirmed_profile(client) -> str:
    imported = client.post(
        "/api/profiles/import",
        params={"language": "es"},
        files={
            "file": (
                "cv.txt",
                b"Desarrolle pruebas automatizadas y valide APIs REST con Postman.",
                "text/plain",
            )
        },
    )
    imported.raise_for_status()
    profile_id = imported.json()["profile"]["profile_id"]
    client.post(f"/api/profiles/{profile_id}/confirm").raise_for_status()
    client.post(
        f"/api/profiles/{profile_id}/cloud-consent",
        json={"granted": True, "purposes": ["document_generation"]},
    ).raise_for_status()
    return profile_id


def test_about_me_is_local_persistent_evidence_and_revokes_old_consent(client) -> None:
    profile_id = _confirmed_profile(client)

    response = client.put(
        "/api/about-me",
        json={
            "contact": {
                "full_name": "Ada Example",
                "emails": ["ada@example.test"],
                "phones": [],
                "address_lines": [],
                "city": "San Jose",
                "region": "San Jose",
                "country_code": None,
                "postal_code": None,
                "websites": ["https://portfolio.example.test"],
                "legacy_values": [],
            },
            "entries": [
                {
                    "category": "project",
                    "title": "Suite de regresion",
                    "details": "Automatice flujos criticos con Playwright.",
                    "language": "es",
                    "profile_ids": [profile_id],
                }
            ],
        },
    )
    response.raise_for_status()
    dossier = response.json()
    assert dossier["contact"]["full_name"] == "Ada Example"
    assert dossier["entries"][0]["profile_ids"] == [profile_id]

    profile = client.get(f"/api/profiles/{profile_id}").json()
    about_facts = [
        fact for fact in profile["facts"] if fact["source_type"] == "about_me"
    ]
    assert len(about_facts) == 1
    assert "Playwright" in about_facts[0]["text"]
    assert profile["cloud_processing_consent"] is None
    assert "ada@example.test" not in profile["redacted_preview"]["redacted_text"]

    duplicated = client.post(f"/api/profiles/{profile_id}/duplicate")
    duplicated.raise_for_status()
    duplicate_id = duplicated.json()["profile_id"]
    duplicated_dossier = client.get("/api/about-me").json()
    assert duplicate_id in duplicated_dossier["entries"][0]["profile_ids"]
    duplicate_facts = [
        fact
        for fact in duplicated.json()["facts"]
        if fact["source_type"] == "about_me"
    ]
    assert len(duplicate_facts) == 1

    assert client.delete(f"/api/profiles/{duplicate_id}").status_code == 204
    cleaned_dossier = client.get("/api/about-me").json()
    assert duplicate_id not in cleaned_dossier["entries"][0]["profile_ids"]

    stored = client.get("/api/about-me")
    stored.raise_for_status()
    assert stored.json()["entries"][0]["title"] == dossier["entries"][0]["title"]
    assert stored.json()["entries"][0]["profile_ids"] == [profile_id]


def test_application_tracker_is_idempotent_and_records_stage_history(client) -> None:
    profile_id = _confirmed_profile(client)
    job = normalize_job(
        source=SourceKind.MANUAL,
        external_id="tracked-job",
        title="QA Engineer",
        company="Example",
        description="Playwright and API testing.",
        location="Costa Rica",
        remote=True,
        url="https://jobs.example.test/tracked-job",
        posted_at=utc_now(),
    )
    client.app.state.store.save_job(job)
    saved = client.app.state.store.save_saved_job(
        SavedJob(
            job_id=job.job_id,
            search_id="search_test",
            title=job.title,
            company=job.company,
            location=job.location,
            source_portals=["LinkedIn"],
            source_urls=[job.url],
            apply_url=job.url,
            description=job.description,
            published_at=job.posted_at,
        )
    )

    first = client.post(
        "/api/applications",
        json={"saved_id": saved.saved_id, "profile_id": profile_id},
    )
    first.raise_for_status()
    second = client.post(
        "/api/applications",
        json={"saved_id": saved.saved_id, "profile_id": profile_id},
    )
    second.raise_for_status()
    assert second.json()["application_id"] == first.json()["application_id"]

    application_id = first.json()["application_id"]
    updated = client.patch(
        f"/api/applications/{application_id}",
        json={"status": "interview", "notes": "Entrevista tecnica el viernes"},
    )
    updated.raise_for_status()
    assert updated.json()["status"] == "interview"
    assert [event["status"] for event in updated.json()["events"]] == [
        "applied",
        "interview",
    ]

    listed = client.get("/api/applications")
    listed.raise_for_status()
    assert [item["application_id"] for item in listed.json()] == [application_id]

    removed = client.delete(f"/api/applications/{application_id}")
    assert removed.status_code == 204
    assert client.get("/api/applications").json() == []

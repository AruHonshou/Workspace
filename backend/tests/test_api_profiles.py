from __future__ import annotations

from job_orchestrator.storage import ProfileHasActiveOperationsError


def _create_profile(client, display_name: str = "QA") -> dict:
    response = client.post(
        "/api/profiles",
        json={"display_name": display_name, "name": "Ada Local"},
    )
    assert response.status_code == 201, response.text
    return response.json()


def _import_resume(client, profile_id: str, language: str) -> dict:
    response = client.post(
        "/api/profiles/import",
        params={"language": language, "profile_id": profile_id},
        files={
            "file": (
                f"cv-{language}.txt",
                (
                    "Experiencia en pruebas automatizadas con Python."
                    if language == "es"
                    else "Automated testing experience with Python."
                ).encode(),
                "text/plain",
            )
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["profile"]


def test_profile_names_are_unique_for_create_update_and_duplicate(client) -> None:
    qa = _create_profile(client, "QA Automation")
    data = _create_profile(client, "Datos")

    duplicate_create = client.post(
        "/api/profiles",
        json={"display_name": "  qa   automation ", "name": "Other"},
    )
    assert duplicate_create.status_code == 409

    duplicate_rename = client.patch(
        f"/api/profiles/{data['profile_id']}",
        json={"display_name": "QA AUTOMATION"},
    )
    assert duplicate_rename.status_code == 409

    explicit_duplicate = client.post(
        f"/api/profiles/{qa['profile_id']}/duplicate",
        json={"display_name": "datos"},
    )
    assert explicit_duplicate.status_code == 409


def test_profile_metadata_and_cv_edits_advance_one_revision_each(client) -> None:
    profile = _create_profile(client)
    assert profile["revision"] == 1

    renamed = client.patch(
        f"/api/profiles/{profile['profile_id']}",
        json={"display_name": "QA Senior"},
    )
    assert renamed.status_code == 200, renamed.text
    assert renamed.json()["revision"] == 2

    spanish = _import_resume(client, profile["profile_id"], "es")
    assert spanish["revision"] == 3
    english = _import_resume(client, profile["profile_id"], "en")
    assert english["revision"] == 4

    fact_id = english["facts"][0]["fact_id"]
    reviewed = client.patch(
        f"/api/profile-facts/{fact_id}",
        json={"verified": True},
    )
    assert reviewed.status_code == 200, reviewed.text
    assert reviewed.json()["revision"] == 5

    confirmed = client.post(f"/api/profiles/{profile['profile_id']}/confirm")
    assert confirmed.status_code == 200, confirmed.text
    assert confirmed.json()["revision"] == 6
    assert confirmed.json()["confirmed"] is True


def test_duplicate_has_fresh_identity_and_no_history(client) -> None:
    profile = _create_profile(client)
    _import_resume(client, profile["profile_id"], "es")
    _import_resume(client, profile["profile_id"], "en")
    confirmed = client.post(f"/api/profiles/{profile['profile_id']}/confirm").json()

    response = client.post(f"/api/profiles/{profile['profile_id']}/duplicate")
    assert response.status_code == 201, response.text
    duplicate = response.json()
    assert duplicate["profile_id"] != confirmed["profile_id"]
    assert duplicate["display_name"] == "QA copia"
    assert duplicate["revision"] == 1
    assert duplicate["confirmed"] is True
    assert set(duplicate["resumes"]) == {"es", "en"}
    assert {item["fact_id"] for item in duplicate["facts"]}.isdisjoint(
        {item["fact_id"] for item in confirmed["facts"]}
    )


def test_confirmation_requires_a_resume_but_job_search_does_not(client) -> None:
    profile = _create_profile(client)
    no_resume_confirmation = client.post(
        f"/api/profiles/{profile['profile_id']}/confirm"
    )
    assert no_resume_confirmation.status_code == 409

    _import_resume(client, profile["profile_id"], "es")
    one_resume_confirmation = client.post(
        f"/api/profiles/{profile['profile_id']}/confirm"
    )
    assert one_resume_confirmation.status_code == 200
    search_schema = client.get("/openapi.json").json()["components"]["schemas"][
        "JobSearchInput"
    ]
    assert "profile_id" not in search_schema["properties"]


def test_reprocess_profile_groups_facts_and_preserves_original_resume(client) -> None:
    profile = _create_profile(client)
    source = (
        "PROFESSIONAL EXPERIENCE\n"
        "• Built Playwright regression tests for checkout flows and\n"
        "integrated them with GitHub Actions, reducing runtime by 40%.\n"
        "LinkedIn: linkedin.com/in/example | [redacted-email]\n"
        "TECHNICAL SKILLS\n"
        "Automation: Playwright, Selenium, Postman\n"
    )
    imported_response = client.post(
        "/api/profiles/import",
        params={"language": "en", "profile_id": profile["profile_id"]},
        files={"file": ("cv-en.txt", source.encode(), "text/plain")},
    )
    assert imported_response.status_code == 201, imported_response.text
    client.post(f"/api/profiles/{profile['profile_id']}/confirm").raise_for_status()

    response = client.post(f"/api/profiles/{profile['profile_id']}/reprocess")
    assert response.status_code == 200, response.text
    rebuilt = response.json()

    assert rebuilt["confirmed"] is False
    assert rebuilt["resumes"]["en"]["confirmation_status"] == "pending_review"
    assert rebuilt["resumes"]["en"]["text"] == source.rstrip()
    assert [fact["text"] for fact in rebuilt["facts"]] == [
        (
            "Built Playwright regression tests for checkout flows and integrated "
            "them with GitHub Actions, reducing runtime by 40%."
        ),
        "Automation: Playwright, Selenium, Postman",
    ]
    assert all("redacted" not in fact["text"].casefold() for fact in rebuilt["facts"])
    assert all(not fact["verified"] for fact in rebuilt["facts"])


def test_delete_profile_returns_conflict_for_active_documents(
    client, monkeypatch
) -> None:
    profile = _create_profile(client)

    def active(_profile_id):
        raise ProfileHasActiveOperationsError(_profile_id, ["guide_active"])

    monkeypatch.setattr(client.app.state.store, "delete_profile", active)

    blocked = client.delete(f"/api/profiles/{profile['profile_id']}")
    assert blocked.status_code == 409
    assert blocked.json()["detail"]["operation_ids"] == ["guide_active"]

    monkeypatch.undo()
    deleted = client.delete(f"/api/profiles/{profile['profile_id']}")
    assert deleted.status_code == 204
    assert client.get(f"/api/profiles/{profile['profile_id']}").status_code == 404


def test_profile_mutations_return_not_found(client) -> None:
    assert (
        client.patch(
            "/api/profiles/profile_missing", json={"display_name": "Missing"}
        ).status_code
        == 404
    )
    assert client.post("/api/profiles/profile_missing/duplicate").status_code == 404
    assert client.delete("/api/profiles/profile_missing").status_code == 404

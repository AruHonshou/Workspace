from pathlib import Path

import pytest
from job_orchestrator.ranking import normalize_manual_job
from job_orchestrator.schemas import (
    ManualJobCreate,
    Profile,
    SearchRecord,
    SearchStatus,
)
from job_orchestrator.storage import ActiveOperationsError, SQLiteStore


def test_migration_and_search_round_trip(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path / "store.sqlite3")
    store.migrate()
    profile = store.save_profile(Profile(name="Ada"))
    search = store.save_search(
        SearchRecord(query="QA", request={"flow": "simple_search"})
    )
    store.migrate()
    assert store.get_profile(profile.profile_id) == profile
    assert store.get_search(search.search_id) == search
    assert store.list_searches() == [search]


def test_job_deduplicates_by_content(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path / "store.sqlite3")
    store.migrate()
    payload = ManualJobCreate(
        title="Engineer", company="A", description="Same description"
    )
    first = store.save_job(normalize_manual_job(payload))
    second = store.save_job(normalize_manual_job(payload))
    assert first.job_id == second.job_id
    assert len(store.list_jobs()) == 1
    assert [item.job_id for item in store.search_jobs_text("Engineer Same")] == [
        first.job_id
    ]


def test_active_search_prevents_data_deletion(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path / "store.sqlite3")
    store.migrate()
    search = store.save_search(SearchRecord(status=SearchStatus.RUNNING))
    with pytest.raises(ActiveOperationsError):
        store.clear_all_data()
    assert store.get_search(search.search_id) is not None
    search.status = SearchStatus.COMPLETED
    store.save_search(search)
    store.clear_all_data()
    assert store.list_searches() == []

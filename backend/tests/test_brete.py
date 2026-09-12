from datetime import datetime, timezone

import pytest
from job_orchestrator.connectors.providers import ProviderSearchQuery
from job_orchestrator.providers.jobs.brete import BreteProvider


def test_brete_parses_public_cards_without_accounts_or_detail_scraping() -> None:
    html = """
    <div class="job-listing">
      <h4 class="job-listing-company">Empresa Ejemplo</h4>
      <h3 class="job-listing-title">Ingeniero de Calidad</h3>
      <h4 class="job-listing-description">Profesionales en calidad</h4>
      <li><i class="icon-material-outline-add-location"></i>San José</li>
      <small>Publicado el 6 de septiembre del 2026</small>
    </div>
    <div class="clearfix"></div><div class="pagination-container"></div>
    """
    jobs = BreteProvider()._parse(html, "https://ane.cr/Puesto?Empleos=Calidad")
    assert len(jobs) == 1
    assert jobs[0].title == "Ingeniero de Calidad"
    assert jobs[0].company == "Empresa Ejemplo"
    assert jobs[0].country_code == "CR"
    assert jobs[0].source_portal == "Brete"
    assert str(jobs[0].url).startswith("https://ane.cr/Puesto")
    assert jobs[0].posted_at == datetime(2026, 9, 6, tzinfo=timezone.utc)


@pytest.mark.asyncio
async def test_brete_is_an_explicit_costa_rica_only_provider() -> None:
    result = await BreteProvider().search(
        ProviderSearchQuery(
            role="QA",
            aliases=(),
            country_code="CO",
            max_age_days=7,
            page=0,
            page_size=20,
        )
    )
    assert result.jobs == []
    assert result.total_available == 0
    assert result.can_load_more is False

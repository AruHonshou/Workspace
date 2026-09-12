from __future__ import annotations

import pytest
from job_orchestrator.countries import (
    country_catalog,
    country_name,
    normalize_country_code,
)


def test_country_codes_are_normalized_and_validated() -> None:
    assert normalize_country_code(" co ") == "CO"
    assert country_name("CR") == "Costa Rica"
    with pytest.raises(ValueError, match="ISO 3166-1"):
        normalize_country_code("XX")


def test_catalog_contains_global_iso_countries_in_stable_order() -> None:
    catalog = country_catalog()
    codes = {item["code"] for item in catalog}
    assert {"CR", "CO", "US", "IN", "ES", "JP"}.issubset(codes)
    assert catalog == tuple(
        sorted(catalog, key=lambda item: (item["name"].casefold(), item["code"]))
    )

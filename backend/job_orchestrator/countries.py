from __future__ import annotations

from functools import lru_cache

import pycountry


@lru_cache(maxsize=1)
def country_catalog() -> tuple[dict[str, str], ...]:
    """Return a stable ISO-3166 alpha-2 catalog without locale assumptions."""

    rows = [
        {"code": str(country.alpha_2), "name": str(country.name)}
        for country in pycountry.countries
        if getattr(country, "alpha_2", None) and getattr(country, "name", None)
    ]
    rows.sort(key=lambda item: (item["name"].casefold(), item["code"]))
    return tuple(rows)


def normalize_country_code(value: str) -> str:
    normalized = value.strip().upper()
    if len(normalized) != 2 or pycountry.countries.get(alpha_2=normalized) is None:
        raise ValueError("country_code must be a valid ISO 3166-1 alpha-2 code")
    return normalized


def country_name(value: str) -> str:
    code = normalize_country_code(value)
    country = pycountry.countries.get(alpha_2=code)
    assert country is not None
    return str(country.name)


__all__ = ["country_catalog", "country_name", "normalize_country_code"]

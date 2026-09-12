from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

from ..schemas import JobRecord


@dataclass(frozen=True, slots=True)
class ProviderSearchQuery:
    """Provider-neutral, immutable search scope.

    Providers may support only a subset of the optional filters, but they must
    never silently change the country, freshness window, page or page size.
    """

    role: str
    aliases: tuple[str, ...]
    country_code: str
    page: int = 0
    page_size: int = 25
    max_age_days: int = 7
    portals: tuple[str, ...] = ()
    city_or_region: str | None = None
    modalities: tuple[str, ...] = ()
    include_global_remote: bool = False
    cursor: str | None = None


@dataclass(frozen=True, slots=True)
class ProviderCoverage:
    provider: str
    country_code: str
    total_matches: int | None
    available: bool
    free_count_used: bool = False
    warning: str | None = None


@dataclass(slots=True)
class ProviderSearchPage:
    provider: str
    jobs: list[JobRecord]
    page: int
    page_size: int
    total_available: int | None
    can_load_more: bool
    next_cursor: str | None = None
    coverage: ProviderCoverage | None = None
    warnings: list[str] = field(default_factory=list)


@runtime_checkable
class JobSearchProvider(Protocol):
    """Common boundary for authorized job-data providers.

    `estimate_coverage` must not intentionally retrieve unblurred job records or
    spend result credits. A provider that cannot offer a free count should
    return an unavailable coverage value instead of falling back to a billable
    request.
    """

    provider_id: str
    billable_results: bool

    def configured(self) -> bool: ...

    async def estimate_coverage(
        self, query: ProviderSearchQuery
    ) -> ProviderCoverage: ...

    async def search(self, query: ProviderSearchQuery) -> ProviderSearchPage: ...


__all__ = [
    "JobSearchProvider",
    "ProviderCoverage",
    "ProviderSearchPage",
    "ProviderSearchQuery",
]

from __future__ import annotations

import asyncio

from ...connectors.providers import (
    JobSearchProvider,
    ProviderCoverage,
    ProviderSearchPage,
    ProviderSearchQuery,
)


class JobProviderGroup:
    """Run independent providers concurrently and preserve partial success."""

    provider_id = "combined"
    billable_results = True

    def __init__(self, *providers: JobSearchProvider | None):
        self.providers = tuple(provider for provider in providers if provider is not None)

    def configured(self) -> bool:
        return any(provider.configured() for provider in self.providers)

    async def estimate_coverage(self, query: ProviderSearchQuery) -> ProviderCoverage:
        values = await asyncio.gather(
            *(provider.estimate_coverage(query) for provider in self.providers),
            return_exceptions=True,
        )
        available = [
            value
            for value in values
            if isinstance(value, ProviderCoverage) and value.available
        ]
        totals = [
            value.total_matches
            for value in available
            if value.total_matches is not None
        ]
        return ProviderCoverage(
            provider=self.provider_id,
            country_code=query.country_code,
            total_matches=sum(totals) if totals else None,
            available=bool(available),
        )

    async def search(self, query: ProviderSearchQuery) -> ProviderSearchPage:
        active = [provider for provider in self.providers if provider.configured()]
        values = await asyncio.gather(
            *(provider.search(query) for provider in active), return_exceptions=True
        )
        jobs = []
        warnings = [
            "TheirStack no está configurado; la cobertura se limita a fuentes públicas disponibles."
            for provider in self.providers
            if provider.provider_id == "theirstack" and not provider.configured()
        ]
        totals = []
        can_load_more = False
        for provider, value in zip(active, values, strict=True):
            if isinstance(value, Exception):
                warnings.append(
                    f"{provider.provider_id} no respondió; la cobertura fue parcial."
                )
                continue
            jobs.extend(value.jobs)
            warnings.extend(value.warnings)
            if value.total_available is not None:
                totals.append(value.total_available)
            can_load_more = can_load_more or value.can_load_more
        if not active:
            raise RuntimeError("No hay proveedores de búsqueda configurados")
        return ProviderSearchPage(
            provider=self.provider_id,
            jobs=jobs,
            page=query.page,
            page_size=query.page_size,
            total_available=sum(totals) if totals else None,
            can_load_more=can_load_more,
            warnings=list(dict.fromkeys(warnings)),
        )

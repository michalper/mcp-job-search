"""Orchestrates search_jobs across all registered sources."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from . import cache
from .sources import adzuna, arbeitnow, jsearch
from .sources.base import NormalizedJob, SourceError

_REGISTRY = {
    arbeitnow.name: arbeitnow,
    adzuna.name: adzuna,
    jsearch.name: jsearch,
}


@dataclass(frozen=True)
class SearchResult:
    jobs: list[NormalizedJob]
    source_errors: list[SourceError]


def search_jobs(
    keywords: str,
    location: str | None = None,
    remote_only: bool = False,
    sources: list[str] | None = None,
    use_cache: bool = True,
) -> dict[str, Any]:
    if use_cache:
        cached = cache.get_cached(keywords, location, remote_only, sources)
        if cached is not None:
            return {**cached, "from_cache": True}

    wanted = sources if sources is not None else list(_REGISTRY)
    jobs: list[NormalizedJob] = []
    errors: list[SourceError] = []

    for source_name in wanted:
        module = _REGISTRY.get(source_name)
        if module is None:
            errors.append(SourceError(source=source_name, reason="unknown source"))
            continue
        if not module.available():
            errors.append(SourceError(source=source_name, reason="not configured — skipped"))
            continue
        found, error = module.search(keywords, location, remote_only)
        jobs.extend(found)
        if error is not None:
            errors.append(error)

    result = {
        "jobs": [asdict(j) for j in jobs],
        "source_errors": [asdict(e) for e in errors],
    }
    if use_cache:
        cache.store(keywords, location, remote_only, sources, result)
    return {**result, "from_cache": False}

"""Orchestrates search_jobs across all registered sources."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from . import cache
from .sources import adzuna, arbeitnow, jsearch
from .sources.base import NormalizedJob, SourceError

_REGISTRY = {
    arbeitnow.name: arbeitnow,
    adzuna.name: adzuna,
    jsearch.name: jsearch,
}


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
    had_transient_failure = False

    for source_name in wanted:
        module = _REGISTRY.get(source_name)
        if module is None:
            errors.append(SourceError(source=source_name, reason="unknown source"))
            continue
        if not module.available():
            # Permanent for this environment (no key set) — not a reason to
            # skip caching, or a fully-configured query would never cache.
            errors.append(SourceError(source=source_name, reason="not configured — skipped"))
            continue
        found, error = module.search(keywords, location, remote_only)
        jobs.extend(found)
        if error is not None:
            errors.append(error)
            # a real request/parse failure — don't cache this as "the" result
            had_transient_failure = True

    result = {
        "jobs": [asdict(j) for j in jobs],
        "source_errors": [asdict(e) for e in errors],
    }
    if use_cache and not had_transient_failure:
        cache.store(keywords, location, remote_only, sources, result)
    return {**result, "from_cache": False}

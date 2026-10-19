"""A small on-disk cache for search_jobs results.

Exists to protect JSearch's 200-requests/month free quota from being burned
by repeated identical queries in a single session — not a general-purpose
cache. One JSON file per cache key under `SEARCH_CACHE_DIR`; corrupted or
unreadable entries are treated as a miss, never raised.
"""

from __future__ import annotations

import hashlib
import json
import time
from typing import Any

from . import config as app_config


def _config_fingerprint() -> dict[str, Any]:
    """Config state that changes what a query returns, even for identical
    keywords/location/remote_only/sources — must be part of the cache key, or
    e.g. setting JSEARCH_COUNTRY mid-session replays a stale wrong-country
    result instead of querying fresh."""
    return {
        "adzuna_country": app_config.adzuna_country(),
        "adzuna_configured": app_config.adzuna_credentials() is not None,
        "jsearch_country": app_config.jsearch_country(),
        "jsearch_configured": app_config.jsearch_key() is not None,
    }


def _cache_key(
    keywords: str, location: str | None, remote_only: bool, sources: list[str] | None
) -> str:
    raw = json.dumps(
        {
            "keywords": keywords.strip().lower(),
            "location": (location or "").strip().lower(),
            "remote_only": remote_only,
            # `is not None` (not truthiness) so sources=[] and sources=None
            # hash differently — they mean "no sources" vs "all sources".
            "sources": sorted(sources) if sources is not None else None,
            "config": _config_fingerprint(),
        },
        sort_keys=True,
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def get_cached(
    keywords: str, location: str | None, remote_only: bool, sources: list[str] | None
) -> dict[str, Any] | None:
    key = _cache_key(keywords, location, remote_only, sources)
    path = app_config.search_cache_dir() / f"{key}.json"
    try:
        entry = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None

    age = time.time() - entry.get("cached_at", 0)
    if age > app_config.search_cache_ttl_seconds():
        return None
    result = entry.get("result")
    return result if isinstance(result, dict) else None


def store(
    keywords: str,
    location: str | None,
    remote_only: bool,
    sources: list[str] | None,
    result: dict[str, Any],
) -> None:
    cache_dir = app_config.search_cache_dir()
    key = _cache_key(keywords, location, remote_only, sources)
    try:
        cache_dir.mkdir(parents=True, exist_ok=True)
        path = cache_dir / f"{key}.json"
        path.write_text(json.dumps({"cached_at": time.time(), "result": result}), encoding="utf-8")
    except OSError:
        pass  # caching is a courtesy, never a hard requirement

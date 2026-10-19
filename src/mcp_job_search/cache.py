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


def _cache_key(
    keywords: str, location: str | None, remote_only: bool, sources: list[str] | None
) -> str:
    raw = json.dumps(
        {
            "keywords": keywords.strip().lower(),
            "location": (location or "").strip().lower(),
            "remote_only": remote_only,
            "sources": sorted(sources) if sources else None,
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

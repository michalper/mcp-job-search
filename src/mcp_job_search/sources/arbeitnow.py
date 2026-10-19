"""Arbeitnow job-board API — free, no API key.

Verified live (2026-10-19): `GET /api/job-board-api` returns up to 300 jobs per
page, newest first, NO server-side filtering — `?search=` and `?location=`
are accepted but silently ignored (confirmed: identical result counts and
content with and without `search=`). All keyword/location/remote filtering
below therefore happens client-side, against page 1 only (newest 300) — this
is a fast, free, best-effort source, not an exhaustive search. Also observed:
the feed currently skews DACH/France; it returned zero Poland-tagged listings
in a live sample, so for Polish-market users this source mainly contributes
EU-remote listings, not local ones.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any

from .base import NormalizedJob, SourceError

name = "arbeitnow"

_API_URL = "https://www.arbeitnow.com/api/job-board-api"
_TIMEOUT = 10
_USER_AGENT = "mcp-job-search/0.1 (+https://github.com/michalper/mcp-job-search)"


def available() -> bool:
    return True  # no credentials required


def _fetch_page() -> list[dict[str, Any]]:
    req = urllib.request.Request(_API_URL, headers={"User-Agent": _USER_AGENT})
    with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:  # nosec B310 - fixed https URL
        payload = json.loads(resp.read().decode("utf-8"))
    data = payload.get("data", [])
    return data if isinstance(data, list) else []


def _matches(job: dict[str, Any], keywords: str, location: str | None, remote_only: bool) -> bool:
    if remote_only and not job.get("remote"):
        return False
    if location and location.lower() not in str(job.get("location", "")).lower():
        return False
    haystack = " ".join(
        [
            str(job.get("title", "")),
            str(job.get("description", "")),
            " ".join(job.get("tags", []) or []),
        ]
    ).lower()
    return all(term.lower() in haystack for term in keywords.split() if term)


def _to_normalized(job: dict[str, Any]) -> NormalizedJob:
    return NormalizedJob(
        title=str(job.get("title", "")),
        company=job.get("company_name"),
        location=job.get("location"),
        salary=None,  # Arbeitnow does not expose salary data
        url=str(job.get("url", "")),
        source=name,
        posted_date=str(job.get("created_at")) if job.get("created_at") is not None else None,
        remote=job.get("remote"),
    )


def search(
    keywords: str, location: str | None, remote_only: bool
) -> tuple[list[NormalizedJob], SourceError | None]:
    try:
        raw_jobs = _fetch_page()
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        return [], SourceError(source=name, reason=f"request failed: {exc}")

    matched = [j for j in raw_jobs if _matches(j, keywords, location, remote_only)]
    return [_to_normalized(j) for j in matched], None

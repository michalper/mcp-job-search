"""Adzuna job-search aggregator API — free API key via registration.

Verified live (2026-10-19, without real credentials): `GET /v1/api/jobs/pl/search/1`
returns `AUTH_FAIL` rather than a 404/"unknown country" error, confirming Poland
(`pl`) is a recognized Adzuna country code. Actual job coverage for the Polish
IT market has NOT been verified empirically — that requires a real `ADZUNA_APP_ID`/
`ADZUNA_APP_KEY` pair (free registration at https://developer.adzuna.com/) and a
live query; do that before relying on this source for the Polish market.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from .. import config
from .base import NormalizedJob, SourceError

name = "adzuna"

_TIMEOUT = 10
_USER_AGENT = "mcp-job-search/0.1 (+https://github.com/michalper/mcp-job-search)"


def available() -> bool:
    return config.adzuna_credentials() is not None


def _build_url(keywords: str, location: str | None, remote_only: bool) -> str | None:
    creds = config.adzuna_credentials()
    if creds is None:
        return None
    app_id, app_key = creds
    country = config.adzuna_country()
    params: dict[str, str] = {
        "app_id": app_id,
        "app_key": app_key,
        "what": keywords,
        "content-type": "application/json",
    }
    if location:
        params["where"] = location
    if remote_only:
        # Adzuna has no dedicated remote filter; "remote" as a free-text term
        # is the best available approximation.
        params["what"] = f"{keywords} remote"
    query = urllib.parse.urlencode(params)
    return f"https://api.adzuna.com/v1/api/jobs/{country}/search/1?{query}"


def _salary_text(job: dict[str, Any]) -> str | None:
    lo, hi = job.get("salary_min"), job.get("salary_max")
    if lo is None and hi is None:
        return None
    if lo is not None and hi is not None and lo != hi:
        return f"{lo:.0f}-{hi:.0f}"
    value = lo if lo is not None else hi
    return f"{value:.0f}"


def _to_normalized(job: dict[str, Any]) -> NormalizedJob:
    company = job.get("company", {}) or {}
    location = job.get("location", {}) or {}
    return NormalizedJob(
        title=str(job.get("title", "")),
        company=company.get("display_name"),
        location=location.get("display_name"),
        salary=_salary_text(job),
        url=str(job.get("redirect_url", "")),
        source=name,
        posted_date=job.get("created"),
        remote=None,  # Adzuna doesn't expose a structured remote flag
    )


def search(
    keywords: str, location: str | None, remote_only: bool
) -> tuple[list[NormalizedJob], SourceError | None]:
    url = _build_url(keywords, location, remote_only)
    if url is None:
        return [], SourceError(source=name, reason="ADZUNA_APP_ID/ADZUNA_APP_KEY not set — skipped")

    req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:  # nosec B310 - fixed https URL
            payload = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        return [], SourceError(source=name, reason=f"request failed: {exc}")

    if not isinstance(payload, dict):
        shape = type(payload).__name__
        return [], SourceError(source=name, reason=f"unexpected response shape: {shape}")

    if "exception" in payload:
        detail = payload.get("display", payload["exception"])
        return [], SourceError(source=name, reason=f"Adzuna error: {detail}")

    results = payload.get("results", [])
    return [_to_normalized(j) for j in results if isinstance(j, dict)], None

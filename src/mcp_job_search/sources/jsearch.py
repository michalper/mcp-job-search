"""JSearch (RapidAPI) — aggregates Google for Jobs (Indeed, LinkedIn,
Glassdoor, ZipRecruiter and others indexed there). Free tier: 200
requests/month. Needs `RAPIDAPI_JSEARCH_KEY`.

Verified live (2026-10-19), three things an earlier version of this file got
wrong by trusting the parameter docs instead of a real request/response:
1. The endpoint is `/search-v2`, not `/search` (404 otherwise) — confirmed
   from RapidAPI's own "Code snippet" panel, not the docs prose.
2. The response nests results under `data.jobs`, not a flat `data` list.
3. `country` defaults to "us" server-side; putting "in Poland" in the
   free-text `query` does NOT change which country is searched — `country`
   must be set explicitly (see `config.jsearch_country()` / `JSEARCH_COUNTRY`).
   Without it, a real `query="PHP developer", location="Poland"` call
   returned zero results; with `country=pl` it returned 10 real Warsaw
   listings (Boldare, SoftTeco, Ness Solution among them).
"""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from .. import config
from .base import NormalizedJob, SourceError

name = "jsearch"

_HOST = "jsearch.p.rapidapi.com"
_TIMEOUT = 10
_USER_AGENT = "mcp-job-search/0.1 (+https://github.com/michalper/mcp-job-search)"


def available() -> bool:
    return config.jsearch_key() is not None


def _build_query(keywords: str, location: str | None) -> str:
    return f"{keywords} in {location}" if location else keywords


def _salary_text(job: dict[str, Any]) -> str | None:
    lo, hi = job.get("job_min_salary"), job.get("job_max_salary")
    currency = job.get("job_salary_currency") or ""
    if not lo and not hi:
        return None
    if lo and hi and lo != hi:
        return f"{lo:.0f}-{hi:.0f} {currency}".strip()
    return f"{(lo or hi):.0f} {currency}".strip()


def _to_normalized(job: dict[str, Any]) -> NormalizedJob:
    return NormalizedJob(
        title=str(job.get("job_title", "")),
        company=job.get("employer_name"),
        location=job.get("job_city") or job.get("job_country"),
        salary=_salary_text(job),
        url=str(job.get("job_apply_link") or job.get("job_google_link") or ""),
        source=name,
        posted_date=job.get("job_posted_at_datetime_utc"),
        remote=job.get("job_is_remote"),
    )


def search(
    keywords: str, location: str | None, remote_only: bool
) -> tuple[list[NormalizedJob], SourceError | None]:
    key = config.jsearch_key()
    if key is None:
        return [], SourceError(source=name, reason="RAPIDAPI_JSEARCH_KEY not set — skipped")

    params = {
        "query": _build_query(keywords, location),
        "num_pages": "1",
        "date_posted": "all",
        "country": config.jsearch_country(),
    }
    if remote_only:
        params["work_from_home"] = "true"
    url = f"https://{_HOST}/search-v2?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(
        url,
        headers={
            "X-RapidAPI-Key": key,
            "X-RapidAPI-Host": _HOST,
            "User-Agent": _USER_AGENT,
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:  # nosec B310 - fixed https URL
            payload = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        return [], SourceError(source=name, reason=f"request failed: {exc}")

    if payload.get("status") == "ERROR":
        detail = payload.get("error", payload)
        return [], SourceError(source=name, reason=f"JSearch error: {detail}")

    data = payload.get("data")
    # v2 nests the list under data.jobs (verified live 2026-10-19); keep the
    # old flat-list shape as a fallback in case a future response reverts.
    results = data.get("jobs", []) if isinstance(data, dict) else (data or [])
    return [_to_normalized(j) for j in results if isinstance(j, dict)], None

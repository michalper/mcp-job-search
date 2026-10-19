"""JSearch (RapidAPI) — aggregates Google for Jobs, Indeed, LinkedIn, Glassdoor,
ZipRecruiter. Free tier: 200 requests/month. Needs `RAPIDAPI_JSEARCH_KEY`.

NOT YET VERIFIED empirically whether it surfaces Polish IT-board listings
(pracuj.pl / justjoin.it / nofluffjobs) — those boards may publish Google for
Jobs structured data, which would make this the one legitimate path to their
postings, but this needs a real key and a live query to confirm. Do that check
before promising this source covers the Polish IT market — see build-order
step 3 in the project plan.
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

    params = {"query": _build_query(keywords, location), "page": "1", "num_pages": "1"}
    if remote_only:
        params["remote_jobs_only"] = "true"
    url = f"https://{_HOST}/search?{urllib.parse.urlencode(params)}"
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

    results = payload.get("data", [])
    return [_to_normalized(j) for j in results if isinstance(j, dict)], None

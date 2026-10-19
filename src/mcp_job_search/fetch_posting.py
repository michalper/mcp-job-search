"""fetch_job_posting — reads ONE job-posting URL the user already found manually.

This is deliberately not a search/index tool: it fetches exactly the page a
human handed it, the same way a browser would, and extracts readable text
generically (via `trafilatura`) rather than with per-site parsers. It exists
for boards with no public search API (NoFluffJobs, JustJoin.it, Pracuj.pl, a
company's own careers page, ...) — the human finds the posting, this tool
turns it into structured text for drafting a CV/cover letter against.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from typing import Any
from urllib.parse import urlparse

import trafilatura

_TIMEOUT = 10
_USER_AGENT = (
    "Mozilla/5.0 (compatible; mcp-job-search/0.1; "
    "+https://github.com/michalper/mcp-job-search)"
)
_ALLOWED_SCHEMES = {"http", "https"}


@dataclass(frozen=True)
class JobPosting:
    url: str
    found: bool
    title: str | None
    body_text: str | None
    reason: str | None


def _validate_url(url: str) -> str | None:
    parsed = urlparse(url)
    if parsed.scheme not in _ALLOWED_SCHEMES or not parsed.netloc:
        return f"unsupported or malformed URL: {url!r}"
    return None


def fetch_job_posting(url: str) -> dict[str, Any]:
    error = _validate_url(url)
    if error is not None:
        return asdict(JobPosting(url=url, found=False, title=None, body_text=None, reason=error))

    req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:  # nosec B310 - scheme checked above
            html = resp.read().decode("utf-8", errors="replace")
    except (urllib.error.URLError, TimeoutError) as exc:
        return asdict(
            JobPosting(
                url=url, found=False, title=None, body_text=None,
                reason=f"fetch failed: {exc}",
            )
        )

    extracted = trafilatura.extract(html, with_metadata=True, output_format="json")
    if not extracted:
        return asdict(
            JobPosting(
                url=url,
                found=False,
                title=None,
                body_text=None,
                reason="page fetched but no extractable article text found",
            )
        )

    parsed = json.loads(extracted)
    return asdict(
        JobPosting(
            url=url,
            found=True,
            title=parsed.get("title"),
            body_text=parsed.get("text"),
            reason=None,
        )
    )

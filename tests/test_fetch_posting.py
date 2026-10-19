from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from mcp_job_search.fetch_posting import fetch_job_posting

FIXTURES = Path(__file__).parent / "fixtures"


def _fake_response(html: str) -> MagicMock:
    cm = MagicMock()
    cm.__enter__.return_value.read.return_value = html.encode("utf-8")
    cm.__exit__.return_value = False
    return cm


def test_rejects_malformed_url() -> None:
    result = fetch_job_posting("not-a-url")
    assert result["found"] is False
    assert "unsupported" in (result["reason"] or "").lower()


def test_rejects_non_http_scheme() -> None:
    result = fetch_job_posting("ftp://example.com/job")
    assert result["found"] is False


def test_extracts_text_from_fixture_html() -> None:
    html = (FIXTURES / "sample_posting.html").read_text()
    with patch("urllib.request.urlopen", return_value=_fake_response(html)):
        result = fetch_job_posting("https://example.com/jobs/123")
    assert result["found"] is True
    assert result["body_text"]
    assert "Senior PHP Developer" in result["body_text"]
    # nav/footer boilerplate should not dominate the extracted text
    assert "Cookie banner" not in (result["body_text"] or "")


def test_fetch_failure_returns_found_false() -> None:
    import urllib.error

    with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("boom")):
        result = fetch_job_posting("https://example.com/jobs/123")
    assert result["found"] is False
    assert "fetch failed" in (result["reason"] or "")

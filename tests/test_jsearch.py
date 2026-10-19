from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from mcp_job_search.sources import jsearch

FIXTURES = Path(__file__).parent / "fixtures"


def _fake_response(payload: dict) -> MagicMock:
    cm = MagicMock()
    cm.__enter__.return_value.read.return_value = json.dumps(payload).encode("utf-8")
    cm.__exit__.return_value = False
    return cm


def test_unavailable_without_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("RAPIDAPI_JSEARCH_KEY", raising=False)
    assert jsearch.available() is False
    jobs, error = jsearch.search("PHP", location=None, remote_only=False)
    assert jobs == []
    assert error is not None
    assert "not set" in error.reason


def test_search_with_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RAPIDAPI_JSEARCH_KEY", "abc123")
    payload = json.loads((FIXTURES / "jsearch_response.json").read_text())
    with patch("urllib.request.urlopen", return_value=_fake_response(payload)) as mocked:
        jobs, error = jsearch.search("PHP", location="Warsaw", remote_only=True)
    assert error is None
    assert len(jobs) == 1
    assert jobs[0].company == "Acme Shop"
    assert jobs[0].remote is True
    assert jobs[0].salary == "15000-20000 PLN"
    requested_url = mocked.call_args.args[0].full_url
    assert "/search-v2?" in requested_url
    assert "country=us" in requested_url  # default; JSEARCH_COUNTRY overrides it
    assert "work_from_home=true" in requested_url


def test_search_respects_jsearch_country_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RAPIDAPI_JSEARCH_KEY", "abc123")
    monkeypatch.setenv("JSEARCH_COUNTRY", "pl")
    payload = json.loads((FIXTURES / "jsearch_response.json").read_text())
    with patch("urllib.request.urlopen", return_value=_fake_response(payload)) as mocked:
        jsearch.search("PHP", location=None, remote_only=False)
    requested_url = mocked.call_args.args[0].full_url
    assert "country=pl" in requested_url


def test_search_falls_back_to_flat_data_list(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RAPIDAPI_JSEARCH_KEY", "abc123")
    flat_payload = {"status": "OK", "data": [{"job_title": "PHP Dev", "employer_name": "X"}]}
    with patch("urllib.request.urlopen", return_value=_fake_response(flat_payload)):
        jobs, error = jsearch.search("PHP", location=None, remote_only=False)
    assert error is None
    assert len(jobs) == 1
    assert jobs[0].title == "PHP Dev"


def test_search_returns_error_on_api_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RAPIDAPI_JSEARCH_KEY", "abc123")
    payload = {"status": "ERROR", "error": "quota exceeded"}
    with patch("urllib.request.urlopen", return_value=_fake_response(payload)):
        jobs, error = jsearch.search("PHP", location=None, remote_only=False)
    assert jobs == []
    assert error is not None
    assert "quota exceeded" in error.reason


def test_search_returns_error_on_non_dict_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RAPIDAPI_JSEARCH_KEY", "abc123")
    cm = MagicMock()
    cm.__enter__.return_value.read.return_value = b'"unexpected string response"'
    cm.__exit__.return_value = False
    with patch("urllib.request.urlopen", return_value=cm):
        jobs, error = jsearch.search("PHP", location=None, remote_only=False)
    assert jobs == []
    assert error is not None
    assert "unexpected response shape" in error.reason


def test_zero_salary_min_is_not_treated_as_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RAPIDAPI_JSEARCH_KEY", "abc123")
    payload = {
        "status": "OK",
        "data": {
            "jobs": [
                {
                    "job_title": "Junior PHP Developer",
                    "employer_name": "Acme",
                    "job_min_salary": 0,
                    "job_max_salary": 12000,
                    "job_salary_currency": "USD",
                }
            ]
        },
    }
    with patch("urllib.request.urlopen", return_value=_fake_response(payload)):
        jobs, error = jsearch.search("PHP", location=None, remote_only=False)
    assert error is None
    assert jobs[0].salary == "0-12000 USD"

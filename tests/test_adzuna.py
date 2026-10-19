from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from mcp_job_search.sources import adzuna

FIXTURES = Path(__file__).parent / "fixtures"


def _fake_response(payload: dict) -> MagicMock:
    cm = MagicMock()
    cm.__enter__.return_value.read.return_value = json.dumps(payload).encode("utf-8")
    cm.__exit__.return_value = False
    return cm


def test_unavailable_without_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ADZUNA_APP_ID", raising=False)
    monkeypatch.delenv("ADZUNA_APP_KEY", raising=False)
    assert adzuna.available() is False
    jobs, error = adzuna.search("PHP", location=None, remote_only=False)
    assert jobs == []
    assert error is not None
    assert "not set" in error.reason


def test_search_with_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ADZUNA_APP_ID", "id123")
    monkeypatch.setenv("ADZUNA_APP_KEY", "key123")
    payload = json.loads((FIXTURES / "adzuna_response.json").read_text())
    with patch("urllib.request.urlopen", return_value=_fake_response(payload)):
        jobs, error = adzuna.search("PHP", location="Warszawa", remote_only=False)
    assert error is None
    assert len(jobs) == 1
    assert jobs[0].company == "Acme Shop"
    assert jobs[0].salary == "15000-20000"


def test_search_returns_error_on_api_exception(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ADZUNA_APP_ID", "id123")
    monkeypatch.setenv("ADZUNA_APP_KEY", "key123")
    payload = {"display": "Authorisation failed", "exception": "AUTH_FAIL"}
    with patch("urllib.request.urlopen", return_value=_fake_response(payload)):
        jobs, error = adzuna.search("PHP", location=None, remote_only=False)
    assert jobs == []
    assert error is not None
    assert "AUTH_FAIL" in error.reason or "Authorisation failed" in error.reason


def test_search_returns_error_on_non_dict_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ADZUNA_APP_ID", "id123")
    monkeypatch.setenv("ADZUNA_APP_KEY", "key123")
    cm = MagicMock()
    cm.__enter__.return_value.read.return_value = b"[1, 2, 3]"
    cm.__exit__.return_value = False
    with patch("urllib.request.urlopen", return_value=cm):
        jobs, error = adzuna.search("PHP", location=None, remote_only=False)
    assert jobs == []
    assert error is not None
    assert "unexpected response shape" in error.reason


def test_zero_salary_min_is_not_treated_as_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ADZUNA_APP_ID", "id123")
    monkeypatch.setenv("ADZUNA_APP_KEY", "key123")
    payload = {
        "results": [
            {
                "title": "Junior PHP Developer",
                "company": {"display_name": "Acme"},
                "location": {"display_name": "Warszawa"},
                "salary_min": 0,
                "salary_max": 5000,
                "redirect_url": "https://x",
                "created": "2026-10-18T10:00:00Z",
            }
        ]
    }
    with patch("urllib.request.urlopen", return_value=_fake_response(payload)):
        jobs, error = adzuna.search("PHP", location=None, remote_only=False)
    assert error is None
    assert jobs[0].salary == "0-5000"

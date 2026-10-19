from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from mcp_job_search.sources import arbeitnow

FIXTURES = Path(__file__).parent / "fixtures"


def _fake_response(payload: dict) -> MagicMock:
    cm = MagicMock()
    cm.__enter__.return_value.read.return_value = json.dumps(payload).encode("utf-8")
    cm.__exit__.return_value = False
    return cm


def _load_fixture() -> dict:
    return json.loads((FIXTURES / "arbeitnow_response.json").read_text())


def test_available_always_true() -> None:
    assert arbeitnow.available() is True


def test_search_filters_by_keyword() -> None:
    with patch("urllib.request.urlopen", return_value=_fake_response(_load_fixture())):
        jobs, error = arbeitnow.search("PHP", location=None, remote_only=False)
    assert error is None
    titles = {j.title for j in jobs}
    assert "Senior PHP Developer" in titles
    assert "PHP Engineer" in titles
    assert "Sales Manager" not in titles


def test_search_filters_by_remote_only() -> None:
    with patch("urllib.request.urlopen", return_value=_fake_response(_load_fixture())):
        jobs, error = arbeitnow.search("", location=None, remote_only=True)
    assert error is None
    assert all(j.remote for j in jobs)
    assert len(jobs) == 2


def test_search_filters_by_location() -> None:
    with patch("urllib.request.urlopen", return_value=_fake_response(_load_fixture())):
        jobs, error = arbeitnow.search("", location="Berlin", remote_only=False)
    assert error is None
    assert len(jobs) == 1
    assert jobs[0].location == "Berlin"


def test_search_returns_error_on_network_failure() -> None:
    import urllib.error

    with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("boom")):
        jobs, error = arbeitnow.search("PHP", location=None, remote_only=False)
    assert jobs == []
    assert error is not None
    assert error.source == "arbeitnow"

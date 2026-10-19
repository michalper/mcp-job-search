from __future__ import annotations

from pathlib import Path

import pytest

from mcp_job_search import cache


@pytest.fixture(autouse=True)
def _isolated_cache_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SEARCH_CACHE_DIR", str(tmp_path / "search_cache"))


def test_miss_when_nothing_cached() -> None:
    assert cache.get_cached("PHP", None, False, None) is None


def test_store_then_get_cached_round_trips() -> None:
    cache.store("PHP", "Warsaw", True, ["arbeitnow"], {"jobs": [1, 2]})
    result = cache.get_cached("PHP", "Warsaw", True, ["arbeitnow"])
    assert result == {"jobs": [1, 2]}


def test_different_query_params_are_different_cache_entries() -> None:
    cache.store("PHP", None, False, None, {"jobs": ["a"]})
    assert cache.get_cached("Java", None, False, None) is None


def test_expired_entry_is_a_miss(monkeypatch: pytest.MonkeyPatch) -> None:
    import json

    monkeypatch.setenv("SEARCH_CACHE_TTL_SECONDS", "1")
    cache.store("PHP", None, False, None, {"jobs": []})
    entry_path = next(iter(_app_cache_dir().glob("*.json")))
    # rewrite the cached_at timestamp to be well in the past
    data = json.loads(entry_path.read_text())
    data["cached_at"] = 0
    entry_path.write_text(json.dumps(data))
    assert cache.get_cached("PHP", None, False, None) is None


def test_corrupted_cache_file_is_a_miss() -> None:
    cache.store("PHP", None, False, None, {"jobs": []})
    entry_path = next(iter(_app_cache_dir().glob("*.json")))
    entry_path.write_text("not json")
    assert cache.get_cached("PHP", None, False, None) is None


def _app_cache_dir() -> Path:
    from mcp_job_search import config

    return config.search_cache_dir()

from __future__ import annotations

import pytest

from mcp_job_search import search
from mcp_job_search.sources.base import NormalizedJob, SourceError


class _FakeSource:
    def __init__(
        self,
        name: str,
        is_available: bool,
        jobs: list[NormalizedJob],
        error: SourceError | None,
    ):
        self.name = name
        self._available = is_available
        self._jobs = jobs
        self._error = error
        self.called = False

    def available(self) -> bool:
        return self._available

    def search(self, keywords, location, remote_only):
        self.called = True
        return self._jobs, self._error


def test_merges_jobs_and_errors_from_available_sources(monkeypatch: pytest.MonkeyPatch) -> None:
    job = NormalizedJob(
        title="PHP Dev", company="X", location="Remote", salary=None,
        url="https://x", source="fake_ok", posted_date=None, remote=True,
    )
    ok_source = _FakeSource("fake_ok", True, [job], None)
    broken_error = SourceError(source="fake_broken", reason="boom")
    broken_source = _FakeSource("fake_broken", True, [], broken_error)
    skipped_source = _FakeSource("fake_skipped", False, [], None)

    monkeypatch.setattr(
        search,
        "_REGISTRY",
        {s.name: s for s in (ok_source, broken_source, skipped_source)},
    )

    result = search.search_jobs(keywords="PHP")
    assert len(result["jobs"]) == 1
    assert result["jobs"][0]["title"] == "PHP Dev"
    reasons = {e["source"]: e["reason"] for e in result["source_errors"]}
    assert reasons["fake_broken"] == "boom"
    assert "skipped" in reasons["fake_skipped"]
    assert skipped_source.called is False


def test_sources_filter_restricts_to_named_sources(monkeypatch: pytest.MonkeyPatch) -> None:
    job = NormalizedJob(
        title="PHP Dev", company="X", location="Remote", salary=None,
        url="https://x", source="fake_a", posted_date=None, remote=True,
    )
    a = _FakeSource("fake_a", True, [job], None)
    b = _FakeSource("fake_b", True, [job], None)
    monkeypatch.setattr(search, "_REGISTRY", {s.name: s for s in (a, b)})

    result = search.search_jobs(keywords="PHP", sources=["fake_a"])
    assert len(result["jobs"]) == 1
    assert a.called is True
    assert b.called is False


def test_unknown_source_name_reported_as_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(search, "_REGISTRY", {})
    result = search.search_jobs(keywords="PHP", sources=["does_not_exist"])
    assert result["jobs"] == []
    assert result["source_errors"][0]["reason"] == "unknown source"

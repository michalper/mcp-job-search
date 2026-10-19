from __future__ import annotations

from mcp_job_search.server import (
    fetch_job_posting,
    lint_cv,
    log_application,
    render_pdf,
    search_jobs,
)


def test_render_pdf_tool_reports_missing_file(tmp_path) -> None:
    result = render_pdf(str(tmp_path / "missing.html"))
    assert result["success"] is False


def test_lint_cv_tool_reports_missing_file(tmp_path) -> None:
    result = lint_cv(str(tmp_path / "missing.html"))
    assert result["clean"] is False


def test_fetch_job_posting_tool_rejects_bad_url() -> None:
    result = fetch_job_posting("not-a-url")
    assert result["found"] is False


def test_search_jobs_tool_skips_unconfigured_sources(monkeypatch) -> None:
    monkeypatch.delenv("ADZUNA_APP_ID", raising=False)
    monkeypatch.delenv("ADZUNA_APP_KEY", raising=False)
    monkeypatch.delenv("RAPIDAPI_JSEARCH_KEY", raising=False)
    result = search_jobs(keywords="PHP", sources=["adzuna", "jsearch"])
    assert result["jobs"] == []
    assert len(result["source_errors"]) == 2


def test_log_application_tool_never_raises_without_config(monkeypatch) -> None:
    monkeypatch.delenv("REGISTRY_CONFIG_PATH", raising=False)
    # falls back to the bundled example config, whose registry_path (~/applications.md)
    # won't exist on a fresh checkout — must fail gracefully, never raise
    result = log_application(portal="test", date="2026-10-19", company="X", role="Y")
    assert result["success"] is False
    assert result["error"] is not None

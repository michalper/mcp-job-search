from __future__ import annotations

from pathlib import Path

from mcp_job_search.lint import lint_cv

PKG = Path(__file__).parent.parent / "src" / "mcp_job_search"
FIXTURES = Path(__file__).parent / "fixtures"
RULES = PKG / "examples" / "lint_rules.example.yaml"


def test_clean_cv_has_no_errors() -> None:
    result = lint_cv(str(FIXTURES / "sample_cv_clean.html"), rules_path=str(RULES))
    assert result["clean"] is True
    errors = [f for f in result["findings"] if f["severity"] == "error"]
    assert errors == []


def test_violations_cv_flags_content_and_skill_and_weight_bans() -> None:
    result = lint_cv(str(FIXTURES / "sample_cv_with_violations.html"), rules_path=str(RULES))
    assert result["clean"] is False
    messages = " ".join(f["message"] for f in result["findings"])
    assert "corporate jargon" in messages
    assert "cloud/K8s" in messages
    assert ".gitignore" in messages
    assert "commit count" in messages
    assert "full[\\s-]?stack" not in messages  # sanity: message text, not the raw pattern
    assert "title claim" in messages


def test_link_in_body_flagged_as_note() -> None:
    result = lint_cv(str(FIXTURES / "sample_cv_with_violations.html"), rules_path=str(RULES))
    notes = [f["message"] for f in result["findings"] if f["severity"] == "note"]
    assert any("example.com/portfolio" in m for m in notes)


def test_missing_html_file_reports_error() -> None:
    result = lint_cv(str(FIXTURES / "does_not_exist.html"), rules_path=str(RULES))
    assert result["clean"] is False
    assert "not found" in result["findings"][0]["message"]


def test_missing_rules_file_reports_graceful_error(tmp_path: Path) -> None:
    result = lint_cv(
        str(FIXTURES / "sample_cv_clean.html"), rules_path=str(tmp_path / "does_not_exist.yaml")
    )
    assert result["clean"] is False
    assert "lint rules file not found" in result["findings"][0]["message"]


def test_invalid_yaml_rules_file_reports_graceful_error(tmp_path: Path) -> None:
    bad_rules = tmp_path / "bad.yaml"
    bad_rules.write_text("content_bans: [this is not: valid: yaml: at all")
    result = lint_cv(str(FIXTURES / "sample_cv_clean.html"), rules_path=str(bad_rules))
    assert result["clean"] is False
    assert "not valid YAML" in result["findings"][0]["message"]


def test_bundled_example_registry_maps_status_column() -> None:
    # regression: the Status column's field name is status_note, not "status" —
    # the bundled example must map it or every log_application against the
    # README's documented default config silently drops the status text
    import yaml

    example = PKG / "examples" / "registry.example.yaml"
    cfg = yaml.safe_load(example.read_text())
    assert cfg.get("column_map", {}).get("Status") == "status_note"


def test_page_limit_checked_only_with_pdf_path(tmp_path: Path) -> None:
    pdf_path = tmp_path / "michalper_cv_acme_cover_letter_en.pdf"
    # 2 pages, but cover_letter filename implies a limit of 1
    pdf_path.write_bytes(
        b"%PDF-1.4\n1 0 obj << /Type /Page >> endobj\n2 0 obj << /Type /Page >> endobj\n"
    )
    html_path = tmp_path / "michalper_cv_acme_cover_letter_en.html"
    html_path.write_text("<html><body class=\"main\">hi</body></html>")

    result = lint_cv(str(html_path), pdf_path=str(pdf_path), rules_path=str(RULES))
    assert result["clean"] is False
    assert any("limit is 1" in f["message"] for f in result["findings"])

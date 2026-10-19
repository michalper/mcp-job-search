from __future__ import annotations

import shutil
from pathlib import Path

import yaml

from mcp_job_search.applications import log_application

FIXTURES = Path(__file__).parent / "fixtures"


def _setup_registry(tmp_path: Path) -> tuple[Path, Path]:
    registry = tmp_path / "registry.md"
    shutil.copy(FIXTURES / "sample_registry.md", registry)
    cfg_path = tmp_path / "registry_config.yaml"
    cfg_path.write_text(
        yaml.dump(
            {
                "registry_path": str(registry),
                "columns": ["Date", "Company", "Role", "Rate", "Mode", "Level", "Status"],
                "date_column": "Date",
                "missing_value": "—",
                "column_map": {"Status": "status_note"},
            }
        )
    )
    return cfg_path, registry


def test_inserts_row_in_date_order(tmp_path: Path) -> None:
    cfg_path, registry = _setup_registry(tmp_path)
    result = log_application(
        portal="justjoin.it", date_="2026-10-15", company="New Co", role="Backend Dev",
        registry_config_path=str(cfg_path),
    )
    assert result["success"] is True
    text = registry.read_text()
    row_lines = [ln for ln in text.splitlines() if ln.strip().startswith("|") and "New Co" in ln]
    assert len(row_lines) == 1
    # should land between the 2026-10-18 and 2026-10-10 rows
    idx_new = text.index("New Co")
    idx_18 = text.index("Example Corp")
    idx_10 = text.index("Older Co")
    assert idx_18 < idx_new < idx_10


def test_creates_new_section_when_portal_missing(tmp_path: Path) -> None:
    cfg_path, registry = _setup_registry(tmp_path)
    result = log_application(
        portal="nofluffjobs", date_="2026-10-19", company="Fresh Co", role="PHP Dev",
        registry_config_path=str(cfg_path),
    )
    assert result["success"] is True
    assert result["created_new_section"] is True
    assert "## nofluffjobs" in registry.read_text()


def test_dry_run_does_not_write(tmp_path: Path) -> None:
    cfg_path, registry = _setup_registry(tmp_path)
    before = registry.read_text()
    result = log_application(
        portal="justjoin.it", date_="2026-10-15", company="Ghost Co", role="X",
        registry_config_path=str(cfg_path), dry_run=True,
    )
    assert result["success"] is True
    assert "Ghost Co" in result["row_inserted"]
    assert registry.read_text() == before


def test_rejects_malformed_date(tmp_path: Path) -> None:
    cfg_path, _ = _setup_registry(tmp_path)
    result = log_application(
        portal="justjoin.it", date_="not-a-date", company="X", role="Y",
        registry_config_path=str(cfg_path),
    )
    assert result["success"] is False
    assert "YYYY-MM-DD" in result["error"]


def test_column_map_supports_non_english_headers(tmp_path: Path) -> None:
    registry = tmp_path / "registry.md"
    registry.write_text(
        "## justjoin.it\n\n| Data | Firma | Stanowisko | Status |\n|---|---|---|---|\n"
    )
    cfg_path = tmp_path / "registry_config.yaml"
    cfg_path.write_text(
        yaml.dump(
            {
                "registry_path": str(registry),
                "columns": ["Data", "Firma", "Stanowisko", "Status"],
                "date_column": "Data",
                "column_map": {
                    "Data": "date", "Firma": "company",
                    "Stanowisko": "role", "Status": "status_note",
                },
            }
        )
    )
    result = log_application(
        portal="justjoin.it", date_="2026-10-19", company="Acme PL", role="Dev",
        status_note="aktywne", registry_config_path=str(cfg_path),
    )
    assert result["success"] is True
    assert result["row_inserted"] == "| 2026-10-19 | Acme PL | Dev | aktywne |"


def test_explicit_empty_string_is_preserved_not_replaced_with_placeholder(tmp_path: Path) -> None:
    cfg_path, _registry = _setup_registry(tmp_path)
    result = log_application(
        portal="justjoin.it", date_="2026-10-19", company="X", role="Y",
        status_note="", registry_config_path=str(cfg_path),
    )
    assert result["success"] is True
    # an explicit "" means "write a blank cell", distinct from an omitted
    # (None) field, which falls back to the missing_value placeholder
    assert result["row_inserted"].endswith("|  |")


def test_missing_values_use_placeholder(tmp_path: Path) -> None:
    cfg_path, _registry = _setup_registry(tmp_path)
    result = log_application(
        portal="justjoin.it", date_="2026-10-19", company="NoRate Co", role="Dev",
        registry_config_path=str(cfg_path),
    )
    assert result["success"] is True
    assert "—" in result["row_inserted"]

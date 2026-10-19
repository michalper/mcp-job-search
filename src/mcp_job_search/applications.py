"""log_application — appends one row to a Markdown job-application registry.

The registry format and target file are configurable (see
`src/mcp_job_search/examples/registry.example.yaml`) rather than hardcoded, so this works against
any "one '## <portal>' section per job board, one Markdown table per section"
file. It never invents prose for free-text fields — it places exactly what
the caller passes, preserving a human-edited file's own style.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path
from typing import Any

import yaml

from . import config as app_config


@dataclass(frozen=True)
class LogResult:
    success: bool
    portal_section: str
    created_new_section: bool
    row_inserted: str
    error: str | None


def _load_registry_config(config_path: Path) -> dict[str, Any]:
    with config_path.open(encoding="utf-8") as fh:
        loaded = yaml.safe_load(fh) or {}
    return loaded if isinstance(loaded, dict) else {}


def _validate_date(value: str) -> str | None:
    try:
        date.fromisoformat(value)
    except ValueError:
        return f"date must be YYYY-MM-DD, got {value!r}"
    return None


def _build_row(columns: list[str], values: dict[str, str | None], missing_value: str) -> str:
    # `is None` on purpose: an explicit "" means the caller wants a blank
    # cell, not a missing one — only an unset (None) value falls back.
    cells = [
        str(values.get(col)) if values.get(col) is not None else missing_value for col in columns
    ]
    return "| " + " | ".join(cells) + " |"


def _fail(portal: str, error: str) -> dict[str, Any]:
    return asdict(
        LogResult(
            success=False, portal_section=portal, created_new_section=False,
            row_inserted="", error=error,
        )
    )


def log_application(
    portal: str,
    date_: str,
    company: str,
    role: str,
    rate: str | None = None,
    mode: str | None = None,
    level: str | None = None,
    status_note: str | None = None,
    dry_run: bool = False,
    registry_config_path: str | None = None,
) -> dict[str, Any]:
    date_error = _validate_date(date_)
    if date_error is not None:
        return _fail(portal, date_error)

    if registry_config_path:
        cfg_path = Path(registry_config_path).expanduser().resolve()
    else:
        cfg_path = app_config.registry_config_path()
    if not cfg_path.is_file():
        return _fail(portal, f"registry config not found: {cfg_path}")

    cfg = _load_registry_config(cfg_path)
    default_columns = ["Date", "Company", "Role", "Rate", "Mode", "Level", "Status"]
    columns: list[str] = cfg.get("columns") or default_columns
    date_column = cfg.get("date_column", "Date")
    missing_value = cfg.get("missing_value", "—")
    registry_path = Path(str(cfg.get("registry_path", "~/applications.md"))).expanduser()

    if not registry_path.is_file():
        return _fail(portal, f"registry file not found: {registry_path}")

    field_values = {
        "date": date_, "company": company, "role": role,
        "rate": rate, "mode": mode, "level": level, "status_note": status_note,
    }
    # `column_map` lets a registry use any language/names for its headers
    # (e.g. Polish "Firma"/"Stanowisko") by mapping each header to one of the
    # field names above. Without it, headers are matched case-insensitively
    # against the field names themselves (so "Company"/"company" both work).
    column_map: dict[str, str] = cfg.get("column_map") or {}
    values_by_lower = {k.lower(): v for k, v in field_values.items()}
    row_values: dict[str, str | None] = {}
    for col in columns:
        field = column_map.get(col, col).lower()
        row_values[col] = values_by_lower.get(field)
    if date_column in row_values:
        row_values[date_column] = date_
    new_row = _build_row(columns, row_values, missing_value)

    text = registry_path.read_text(encoding="utf-8")
    lines = text.splitlines()

    heading_pattern = re.compile(rf"^##\s+{re.escape(portal)}\s*$", re.I)
    heading_idx = next(
        (i for i, line in enumerate(lines) if heading_pattern.match(line.strip())), None
    )

    created_new_section = heading_idx is None
    if heading_idx is None:
        header_row = "| " + " | ".join(columns) + " |"
        sep_row = "|" + "|".join(["---"] * len(columns)) + "|"
        new_lines = [*lines, "", f"## {portal}", "", header_row, sep_row, new_row]
    else:
        # find the table under this heading: header row, separator row, then data rows
        i = heading_idx + 1
        while i < len(lines) and not lines[i].strip().startswith("|"):
            i += 1
        if i + 1 >= len(lines):
            return _fail(portal, f"found '## {portal}' but no table under it")
        table_start = i + 2  # skip header row + separator row
        insert_at = table_start
        for j in range(table_start, len(lines)):
            row = lines[j]
            if not row.strip().startswith("|"):
                break
            cells = [c.strip() for c in row.strip().strip("|").split("|")]
            try:
                date_idx = columns.index(date_column)
            except ValueError:
                date_idx = 0
            existing_date = cells[date_idx] if date_idx < len(cells) else ""
            existing_date = existing_date.strip("*")  # file sometimes bolds a highlighted row
            if existing_date and existing_date <= date_:
                insert_at = j
                break
            insert_at = j + 1
        new_lines = [*lines[:insert_at], new_row, *lines[insert_at:]]

    if not dry_run:
        registry_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")

    return asdict(
        LogResult(
            success=True, portal_section=portal, created_new_section=created_new_section,
            row_inserted=new_row, error=None,
        )
    )

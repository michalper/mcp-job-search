"""Read/write access to a Markdown job-application registry.

The registry format and target file are configurable (see
`src/mcp_job_search/examples/registry.example.yaml`) rather than hardcoded, so this works against
any "one '## <portal>' section per job board, one Markdown table per section"
file. Three operations: `log_application` appends a new row, `list_applications`
reads/filters existing rows (e.g. to check for a duplicate before applying),
and `update_application_status` edits one row's status cell in place. None of
them invent prose for free-text fields — they place exactly what the caller
passes, preserving a human-edited file's own style.
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


@dataclass(frozen=True)
class _RegistryContext:
    cfg: dict[str, Any]
    registry_path: Path


def _resolve_registry(
    registry_config_path: str | None,
) -> tuple[_RegistryContext | None, str | None]:
    if registry_config_path:
        cfg_path = Path(registry_config_path).expanduser().resolve()
    else:
        cfg_path = app_config.registry_config_path()
    if not cfg_path.is_file():
        return None, f"registry config not found: {cfg_path}"

    cfg = _load_registry_config(cfg_path)
    registry_path = Path(str(cfg.get("registry_path", "~/applications.md"))).expanduser()
    if not registry_path.is_file():
        return None, f"registry file not found: {registry_path}"
    return _RegistryContext(cfg=cfg, registry_path=registry_path), None


@dataclass(frozen=True)
class _Table:
    heading: str
    heading_line: int
    header_cells: list[str]
    header_line: int
    rows: list[tuple[int, list[str]]]  # (0-indexed line number, cells)


def _iter_tables(lines: list[str]) -> list[_Table]:
    """One `_Table` per `## <heading>` section that has a Markdown table
    directly under it (header row, separator row, then `|`-prefixed rows)."""
    tables: list[_Table] = []
    i = 0
    while i < len(lines):
        stripped = lines[i].strip()
        if stripped.startswith("## "):
            heading = stripped[3:].strip()
            heading_line = i
            j = i + 1
            while j < len(lines) and not lines[j].strip().startswith("|"):
                if lines[j].strip().startswith("## "):
                    j = -1  # no table before the next heading
                    break
                j += 1
            if j != -1 and j < len(lines):
                header_cells = [c.strip() for c in lines[j].strip().strip("|").split("|")]
                k = j + 2  # skip header row + separator row
                rows: list[tuple[int, list[str]]] = []
                while k < len(lines) and lines[k].strip().startswith("|"):
                    cells = [c.strip() for c in lines[k].strip().strip("|").split("|")]
                    rows.append((k, cells))
                    k += 1
                tables.append(
                    _Table(
                        heading=heading, heading_line=heading_line,
                        header_cells=header_cells, header_line=j, rows=rows,
                    )
                )
        i += 1
    return tables


def _field_name(column: str, column_map: dict[str, str]) -> str:
    return column_map.get(column, column).lower()


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


@dataclass(frozen=True)
class ApplicationEntry:
    portal: str
    line_number: int  # 1-indexed line in the registry file, for debugging/targeting
    fields: dict[str, str]


@dataclass(frozen=True)
class ListResult:
    applications: list[dict[str, Any]]
    count: int
    error: str | None


def list_applications(
    portal: str | None = None,
    company: str | None = None,
    registry_config_path: str | None = None,
) -> dict[str, Any]:
    ctx, error = _resolve_registry(registry_config_path)
    if ctx is None:
        return asdict(ListResult(applications=[], count=0, error=error))

    column_map: dict[str, str] = ctx.cfg.get("column_map") or {}
    lines = ctx.registry_path.read_text(encoding="utf-8").splitlines()

    entries: list[ApplicationEntry] = []
    for table in _iter_tables(lines):
        if portal is not None and table.heading.lower() != portal.lower():
            continue
        for line_idx, cells in table.rows:
            fields = {
                _field_name(col, column_map): cell
                for col, cell in zip(table.header_cells, cells, strict=False)
            }
            if company is not None and company.lower() not in fields.get("company", "").lower():
                continue
            entries.append(
                ApplicationEntry(portal=table.heading, line_number=line_idx + 1, fields=fields)
            )

    return asdict(
        ListResult(applications=[asdict(e) for e in entries], count=len(entries), error=None)
    )


@dataclass(frozen=True)
class UpdateResult:
    success: bool
    matched_count: int
    updated_line: int | None
    old_row: str | None
    new_row: str | None
    error: str | None


def update_application_status(
    portal: str,
    company: str,
    new_status: str,
    role: str | None = None,
    dry_run: bool = False,
    registry_config_path: str | None = None,
) -> dict[str, Any]:
    def fail(msg: str | None, matched: int = 0) -> dict[str, Any]:
        return asdict(
            UpdateResult(
                success=False, matched_count=matched, updated_line=None,
                old_row=None, new_row=None, error=msg,
            )
        )

    ctx, error = _resolve_registry(registry_config_path)
    if ctx is None:
        return fail(error)

    column_map: dict[str, str] = ctx.cfg.get("column_map") or {}
    missing_value = ctx.cfg.get("missing_value", "—")
    lines = ctx.registry_path.read_text(encoding="utf-8").splitlines()
    tables = [t for t in _iter_tables(lines) if t.heading.lower() == portal.lower()]
    if not tables:
        return fail(f"no '## {portal}' section with a table found")

    matches: list[tuple[_Table, int, list[str]]] = []
    for table in tables:
        status_col = next(
            (c for c in table.header_cells if _field_name(c, column_map) == "status_note"), None
        )
        company_col = next(
            (c for c in table.header_cells if _field_name(c, column_map) == "company"), None
        )
        if status_col is None or company_col is None:
            continue
        role_col = next(
            (c for c in table.header_cells if _field_name(c, column_map) == "role"), None
        )
        company_idx = table.header_cells.index(company_col)
        role_idx = table.header_cells.index(role_col) if role_col else None
        for line_idx, cells in table.rows:
            if company_idx >= len(cells) or company.lower() not in cells[company_idx].lower():
                continue
            if role is not None and (
                role_idx is None
                or role_idx >= len(cells)
                or role.lower() not in cells[role_idx].lower()
            ):
                continue
            matches.append((table, line_idx, cells))

    if not matches:
        scope = f"portal={portal!r} company={company!r}" + (f" role={role!r}" if role else "")
        return fail(f"no matching row found ({scope})")
    if len(matches) > 1:
        lines_found = [m[1] + 1 for m in matches]
        return fail(
            f"{len(matches)} rows match — pass role to disambiguate (lines {lines_found})",
            matched=len(matches),
        )

    table, line_idx, cells = matches[0]
    status_col = next(c for c in table.header_cells if _field_name(c, column_map) == "status_note")
    status_idx = table.header_cells.index(status_col)
    new_cells = list(cells) + [missing_value] * (len(table.header_cells) - len(cells))
    new_cells[status_idx] = new_status
    old_row = lines[line_idx]
    new_row = "| " + " | ".join(new_cells) + " |"

    if not dry_run:
        new_lines = list(lines)
        new_lines[line_idx] = new_row
        ctx.registry_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")

    return asdict(
        UpdateResult(
            success=True, matched_count=1, updated_line=line_idx + 1,
            old_row=old_row, new_row=new_row, error=None,
        )
    )

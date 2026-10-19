"""lint_cv — configurable mechanical linter for CV/cover-letter HTML.

This is a generic RULES ENGINE, not a hardcoded rule set: every regex/limit
comes from a YAML file (see `src/mcp_job_search/examples/lint_rules.example.yaml` for the shape).
Point `LINT_RULES_PATH` at your own file to lint against your own facts —
this keeps personal/confidential banned-phrase lists out of this public repo.

Mirrors (by design, not by import — two separate repos, independent
histories) the mechanical checks in a private companion project's
`cv-pdf-straznik.py` PostToolUse hook: banned-phrase regexes, a skills-section-
only ban list, "lightweight achievement" overclaim patterns, a title check, an
optional GDPR-clause check, a body-link-style check, and page-count limits by
filename pattern. When the source of truth for those rules changes, update
both copies — see that project's own cross-reference comment.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import yaml

from . import config as app_config
from .pdf import count_pdf_pages


@dataclass(frozen=True)
class LintResult:
    html_path: str
    pdf_path: str | None
    rules_path: str
    findings: list[dict[str, str]] = field(default_factory=list)
    clean: bool = True


def _load_rules(rules_path: Path) -> dict[str, Any]:
    with rules_path.open(encoding="utf-8") as fh:
        loaded = yaml.safe_load(fh) or {}
    return loaded if isinstance(loaded, dict) else {}


def _page_limit(rules: dict[str, Any], filename: str) -> int:
    limits = rules.get("page_limits", {}) or {}
    name = filename.lower()
    for prefix in limits.get("filename_startswith_unlimited", []) or []:
        if name.startswith(str(prefix).lower()):
            return 0
    for substr, limit in (limits.get("filename_contains", {}) or {}).items():
        if str(substr).lower() in name:
            return int(limit)
    return int(limits.get("default", 2))


def _is_unlimited_path(rules: dict[str, Any], html_path: Path) -> bool:
    limits = rules.get("page_limits", {}) or {}
    path_str = str(html_path).lower()
    return any(
        str(substr).lower() in path_str
        for substr in limits.get("path_contains_unlimited", []) or []
    )


def lint_cv(
    html_path: str, pdf_path: str | None = None, rules_path: str | None = None
) -> dict[str, Any]:
    html_p = Path(html_path).expanduser().resolve()
    if rules_path:
        rules_p = Path(rules_path).expanduser().resolve()
    else:
        rules_p = app_config.lint_rules_path()

    if not html_p.is_file():
        return asdict(
            LintResult(
                html_path=str(html_p), pdf_path=pdf_path, rules_path=str(rules_p),
                findings=[{"severity": "error", "message": f"HTML file not found: {html_p}"}],
                clean=False,
            )
        )

    if not rules_p.is_file():
        message = f"lint rules file not found: {rules_p}"
        return asdict(
            LintResult(
                html_path=str(html_p), pdf_path=pdf_path, rules_path=str(rules_p),
                findings=[{"severity": "error", "message": message}],
                clean=False,
            )
        )
    try:
        rules = _load_rules(rules_p)
    except yaml.YAMLError as exc:
        message = f"lint rules file is not valid YAML: {exc}"
        return asdict(
            LintResult(
                html_path=str(html_p), pdf_path=pdf_path, rules_path=str(rules_p),
                findings=[{"severity": "error", "message": message}],
                clean=False,
            )
        )
    html = html_p.read_text(encoding="utf-8", errors="replace")
    findings: list[dict[str, str]] = []

    def add(severity: str, message: str) -> None:
        findings.append({"severity": severity, "message": message})

    if not _is_unlimited_path(rules, html_p):
        for ban in rules.get("content_bans", []) or []:
            if re.search(ban["pattern"], html, re.I):
                add("error", ban["message"])

        skill_cfg = rules.get("skill_section", {}) or {}
        if skill_cfg.get("selector"):
            skill_text = " | ".join(re.findall(skill_cfg["selector"], html))
            for ban in skill_cfg.get("bans", []) or []:
                if re.search(ban["pattern"], skill_text, re.I):
                    add("error", ban["message"])

        for ban in rules.get("weight_bans", []) or []:
            if re.search(ban["pattern"], html, re.I):
                add("error", ban["message"])

        title_cfg = rules.get("title", {}) or {}
        if title_cfg.get("selector"):
            match = re.search(title_cfg["selector"], html)
            if match:
                for ban in title_cfg.get("bans", []) or []:
                    if re.search(ban["pattern"], match.group(1), re.I):
                        add("error", ban["message"])

        gdpr_cfg = rules.get("gdpr", {}) or {}
        if gdpr_cfg.get("enabled"):
            name = html_p.name.lower()
            suffix = str(gdpr_cfg.get("filename_suffix", "")).lower()
            excludes = [str(x).lower() for x in gdpr_cfg.get("exclude_contains", []) or []]
            applies = suffix and name.endswith(suffix) and not any(ex in name for ex in excludes)
            if applies and gdpr_cfg.get("required_text", "") not in html:
                add("note", gdpr_cfg.get("message", "required clause missing"))

        link_cfg = rules.get("link_check", {}) or {}
        if link_cfg.get("enabled") and link_cfg.get("main_selector"):
            main_part = html.split(link_cfg["main_selector"], 1)[-1]
            for href in re.findall(r'<a href="(https?://[^"]+)"', main_part):
                add("note", f"link rendered as <a href> in body ({href}) — use plain text")

    if pdf_path:
        pdf_p = Path(pdf_path).expanduser().resolve()
        if pdf_p.is_file():
            page_count = count_pdf_pages(pdf_p)
            if html_p.stat().st_mtime > pdf_p.stat().st_mtime:
                add("error", f"{pdf_p.name} is older than {html_p.name} — re-render")
            limit = _page_limit(rules, html_p.name)
            if limit > 0 and page_count > limit:
                add(
                    "error",
                    f"{page_count} pages, limit is {limit} — cut facts, don't shrink the font",
                )
        else:
            add("error", f"PDF not found: {pdf_p}")

    errors_present = any(f["severity"] == "error" for f in findings)
    return asdict(
        LintResult(
            html_path=str(html_p),
            pdf_path=str(Path(pdf_path).expanduser().resolve()) if pdf_path else None,
            rules_path=str(rules_p),
            findings=findings,
            clean=not errors_present,
        )
    )

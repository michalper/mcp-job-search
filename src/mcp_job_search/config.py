"""Configuration — environment variables only, never a config-loading dependency.

All of this is optional except nothing: every tool degrades gracefully when a
variable is unset (sources are skipped, lint/registry tools fall back to a
bundled generic example config) rather than failing the whole server.
"""

from __future__ import annotations

import os
from pathlib import Path


def adzuna_credentials() -> tuple[str, str] | None:
    app_id = os.environ.get("ADZUNA_APP_ID")
    app_key = os.environ.get("ADZUNA_APP_KEY")
    if not app_id or not app_key:
        return None
    return app_id, app_key


def adzuna_country() -> str:
    return os.environ.get("ADZUNA_COUNTRY", "pl")


def jsearch_key() -> str | None:
    return os.environ.get("RAPIDAPI_JSEARCH_KEY") or None


_PACKAGE_ROOT = Path(__file__).resolve().parent.parent.parent


def lint_rules_path() -> Path:
    configured = os.environ.get("LINT_RULES_PATH")
    if configured:
        return Path(configured).expanduser()
    return _PACKAGE_ROOT / "config" / "lint_rules.example.yaml"


def registry_config_path() -> Path:
    configured = os.environ.get("REGISTRY_CONFIG_PATH")
    if configured:
        return Path(configured).expanduser()
    return _PACKAGE_ROOT / "config" / "registry.example.yaml"

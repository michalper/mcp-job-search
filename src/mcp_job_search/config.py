"""Configuration — environment variables only, never a config-loading dependency.

All of this is optional except nothing: every tool degrades gracefully when a
variable is unset (sources are skipped, lint/registry tools fall back to a
bundled generic example config) rather than failing the whole server.
"""

from __future__ import annotations

import os
import shutil
import sys
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


def jsearch_country() -> str:
    """ISO 3166-1 alpha-2 country code. JSearch's own API default is "us" —
    mirrored here rather than guessed from the free-text `location` search
    param, since the API has no country-name-to-code resolution of its own."""
    return os.environ.get("JSEARCH_COUNTRY", "us")


_MACOS_CHROME_CANDIDATES = [
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
]
_LINUX_CHROME_BINARIES = [
    "google-chrome-stable", "google-chrome", "chromium-browser", "chromium",
]
_WINDOWS_CHROME_CANDIDATES = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
]


def chrome_path() -> str:
    """Resolution order: `CHROME_PATH` env var, then a platform-appropriate
    guess. Returns the first candidate even if it doesn't exist (rather than
    raising) so render_pdf's existing "Chrome invocation failed" error — not
    an unrelated config exception — is what the caller sees."""
    configured = os.environ.get("CHROME_PATH")
    if configured:
        return configured

    if sys.platform == "darwin":
        for candidate in _MACOS_CHROME_CANDIDATES:
            if Path(candidate).is_file():
                return candidate
        return _MACOS_CHROME_CANDIDATES[0]

    if sys.platform.startswith("win"):
        for candidate in _WINDOWS_CHROME_CANDIDATES:
            if Path(candidate).is_file():
                return candidate
        return _WINDOWS_CHROME_CANDIDATES[0]

    for binary in _LINUX_CHROME_BINARIES:
        found = shutil.which(binary)
        if found:
            return found
    return _LINUX_CHROME_BINARIES[0]


_EXAMPLES_DIR = Path(__file__).resolve().parent / "examples"


def lint_rules_path() -> Path:
    configured = os.environ.get("LINT_RULES_PATH")
    if configured:
        return Path(configured).expanduser()
    return _EXAMPLES_DIR / "lint_rules.example.yaml"


def registry_config_path() -> Path:
    configured = os.environ.get("REGISTRY_CONFIG_PATH")
    if configured:
        return Path(configured).expanduser()
    return _EXAMPLES_DIR / "registry.example.yaml"


def search_cache_dir() -> Path:
    configured = os.environ.get("SEARCH_CACHE_DIR")
    if configured:
        return Path(configured).expanduser()
    return Path.home() / ".cache" / "mcp-job-search" / "search"


def search_cache_ttl_seconds() -> int:
    configured = os.environ.get("SEARCH_CACHE_TTL_SECONDS")
    if not configured:
        return 21600  # 6 hours
    try:
        return int(configured)
    except ValueError:
        return 21600

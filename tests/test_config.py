from __future__ import annotations

import pytest

from mcp_job_search import config


def test_chrome_path_respects_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CHROME_PATH", "/custom/chrome")
    assert config.chrome_path() == "/custom/chrome"


def test_chrome_path_falls_back_to_macos_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CHROME_PATH", raising=False)
    monkeypatch.setattr(config.sys, "platform", "darwin")
    monkeypatch.setattr(config.Path, "is_file", lambda self: False)
    assert config.chrome_path() == config._MACOS_CHROME_CANDIDATES[0]


def test_chrome_path_finds_linux_binary_on_path(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CHROME_PATH", raising=False)
    monkeypatch.setattr(config.sys, "platform", "linux")
    def fake_which(name: str) -> str | None:
        return "/usr/bin/chromium" if name == "chromium" else None

    monkeypatch.setattr(config.shutil, "which", fake_which)
    assert config.chrome_path() == "/usr/bin/chromium"


def test_chrome_path_linux_fallback_when_nothing_found(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CHROME_PATH", raising=False)
    monkeypatch.setattr(config.sys, "platform", "linux")
    monkeypatch.setattr(config.shutil, "which", lambda name: None)
    assert config.chrome_path() == config._LINUX_CHROME_BINARIES[0]


def test_adzuna_credentials_require_both_values(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ADZUNA_APP_ID", "id")
    monkeypatch.delenv("ADZUNA_APP_KEY", raising=False)
    assert config.adzuna_credentials() is None
    monkeypatch.setenv("ADZUNA_APP_KEY", "key")
    assert config.adzuna_credentials() == ("id", "key")


def test_example_configs_resolve_inside_the_installable_package(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("LINT_RULES_PATH", raising=False)
    monkeypatch.delenv("REGISTRY_CONFIG_PATH", raising=False)
    lint_path = config.lint_rules_path()
    registry_path = config.registry_config_path()
    # must live under src/mcp_job_search/ (ships in the wheel), not a
    # sibling config/ directory (never packaged — would 404 after `pip install`)
    assert lint_path.parent.name == "examples"
    assert lint_path.parent.parent.name == "mcp_job_search"
    assert lint_path.is_file()
    assert registry_path.is_file()

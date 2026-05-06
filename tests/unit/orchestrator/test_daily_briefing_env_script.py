"""Tests for ``scripts/check_daily_briefing_env.py``."""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path
from types import ModuleType

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
_SCRIPT = _REPO_ROOT / "scripts" / "check_daily_briefing_env.py"

_VALID_ENV = {
    "CLAUDE_CODE_OAUTH_TOKEN": "claude-token",
    "TELEGRAM_BOT_TOKEN": "telegram-token",
    "TELEGRAM_BRIEFING_CHANNEL_ID": "@investo_briefing",
    "TELEGRAM_OPERATOR_CHAT_ID": "123456789",
    "SITE_URL_BASE": "https://murphygo.github.io/investo",
}


def _load_script_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("check_daily_briefing_env", _SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_script_exists() -> None:
    assert _SCRIPT.exists()


def test_validate_env_accepts_valid_env() -> None:
    script = _load_script_module()
    assert script.validate_env(_VALID_ENV) == []


def test_validate_env_reports_missing_required_vars() -> None:
    script = _load_script_module()
    env = _VALID_ENV | {"TELEGRAM_BOT_TOKEN": "  ", "SITE_URL_BASE": ""}

    errors = script.validate_env(env)

    assert errors == [
        "Missing required GitHub Secret: TELEGRAM_BOT_TOKEN",
        "Missing required GitHub Secret: SITE_URL_BASE",
    ]


def test_validate_env_rejects_equal_chat_ids_after_strip() -> None:
    script = _load_script_module()
    env = _VALID_ENV | {
        "TELEGRAM_BRIEFING_CHANNEL_ID": " @same ",
        "TELEGRAM_OPERATOR_CHAT_ID": "@same",
    }

    errors = script.validate_env(env)

    assert errors == ["TELEGRAM_BRIEFING_CHANNEL_ID and TELEGRAM_OPERATOR_CHAT_ID must be disjoint"]


def test_validate_env_rejects_malformed_site_url() -> None:
    script = _load_script_module()
    env = _VALID_ENV | {"SITE_URL_BASE": "murphygo.github.io/investo"}

    errors = script.validate_env(env)

    assert errors == ["SITE_URL_BASE must be an HTTP(S) URL"]


def test_subprocess_invocation_redacts_secret_values() -> None:
    env = _VALID_ENV | {
        "TELEGRAM_BRIEFING_CHANNEL_ID": "same-secret-chat",
        "TELEGRAM_OPERATOR_CHAT_ID": " same-secret-chat ",
        "SITE_URL_BASE": "not-a-url",
    }

    result = subprocess.run(
        [sys.executable, str(_SCRIPT)],
        capture_output=True,
        text=True,
        env=env,
        cwd=_REPO_ROOT,
    )

    assert result.returncode == 1
    assert "::error::TELEGRAM_BRIEFING_CHANNEL_ID" in result.stdout
    assert "::error::SITE_URL_BASE" in result.stdout
    assert "same-secret-chat" not in result.stdout
    assert "not-a-url" not in result.stdout


def test_daily_briefing_workflow_calls_script() -> None:
    workflow = (_REPO_ROOT / ".github" / "workflows" / "daily-briefing.yml").read_text(
        encoding="utf-8"
    )

    assert "python scripts/check_daily_briefing_env.py" in workflow

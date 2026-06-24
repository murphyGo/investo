"""Tests for the dedicated repo quality GitHub Actions workflow."""

from __future__ import annotations

from pathlib import Path

_WORKFLOW = Path(__file__).resolve().parents[3] / ".github" / "workflows" / "quality.yml"


def test_quality_workflow_exists() -> None:
    assert _WORKFLOW.exists()


def test_quality_workflow_has_required_triggers_and_permissions() -> None:
    text = _WORKFLOW.read_text(encoding="utf-8")

    assert "pull_request:" in text
    assert "push:" in text
    assert "branches: [main]" in text
    assert "workflow_dispatch:" in text
    assert "permissions:" in text
    assert "contents: read" in text
    assert "secrets." not in text


def test_quality_workflow_runs_required_commands() -> None:
    text = _WORKFLOW.read_text(encoding="utf-8")
    required = [
        "uv run ruff check src tests scripts",
        "uv run ruff format --check src tests scripts",
        "uv run mypy src",
        "uv run pytest",
        "uv run python scripts/check_no_anthropic_sdk.py",
        "uv run python scripts/check_no_paid_apis.py",
    ]

    for command in required:
        assert command in text

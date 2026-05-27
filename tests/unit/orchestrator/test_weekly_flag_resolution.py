"""Tests for DEBT-059 weekly workflow flag resolution."""

from __future__ import annotations

import importlib.util
from datetime import datetime
from pathlib import Path
from types import ModuleType

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
_SCRIPT = _REPO_ROOT / "scripts" / "resolve_weekly_flags.py"
_WORKFLOW = _REPO_ROOT / ".github" / "workflows" / "daily-briefing.yml"


def _load_script_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("resolve_weekly_flags", _SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_schedule_run_during_kst_saturday_09_enables_weekly_flags() -> None:
    script = _load_script_module()
    now = datetime(2026, 5, 16, 9, 5, tzinfo=script.KST)

    assert script.resolve_flags("schedule", now) == {
        "INVESTO_PUBLISH_WEEKLY": "1",
        "INVESTO_WEEKLY_OPS_DIGEST": "1",
    }


def test_schedule_payload_enables_weekly_flags_even_when_github_starts_late() -> None:
    script = _load_script_module()
    delayed_start = datetime(2026, 5, 23, 12, 34, tzinfo=script.KST)

    assert script.resolve_flags(
        "schedule",
        delayed_start,
        event_schedule="0 0 * * 6",
    ) == {
        "INVESTO_PUBLISH_WEEKLY": "1",
        "INVESTO_WEEKLY_OPS_DIGEST": "1",
    }


def test_non_weekly_schedule_payload_disables_weekly_flags_on_saturday() -> None:
    script = _load_script_module()
    delayed_daily_start = datetime(2026, 5, 16, 12, 34, tzinfo=script.KST)

    assert script.resolve_flags(
        "schedule",
        delayed_daily_start,
        event_schedule="0 22 * * 0,1,2,3,4",
    ) == {
        "INVESTO_PUBLISH_WEEKLY": "0",
        "INVESTO_WEEKLY_OPS_DIGEST": "0",
    }


def test_schedule_run_outside_kst_saturday_09_disables_weekly_flags() -> None:
    script = _load_script_module()

    assert script.resolve_flags(
        "schedule",
        datetime(2026, 5, 16, 8, 59, tzinfo=script.KST),
    ) == {
        "INVESTO_PUBLISH_WEEKLY": "0",
        "INVESTO_WEEKLY_OPS_DIGEST": "0",
    }
    assert script.resolve_flags(
        "schedule",
        datetime(2026, 5, 15, 9, 0, tzinfo=script.KST),
    ) == {
        "INVESTO_PUBLISH_WEEKLY": "0",
        "INVESTO_WEEKLY_OPS_DIGEST": "0",
    }


def test_manual_dispatch_defaults_weekly_flags_off_even_on_saturday() -> None:
    script = _load_script_module()

    assert script.resolve_flags(
        "workflow_dispatch",
        datetime(2026, 5, 16, 9, 0, tzinfo=script.KST),
    ) == {
        "INVESTO_PUBLISH_WEEKLY": "0",
        "INVESTO_WEEKLY_OPS_DIGEST": "0",
    }


def test_write_github_env_appends_both_flags(tmp_path: Path) -> None:
    script = _load_script_module()
    github_env = tmp_path / "github_env"

    script.write_github_env(
        {"INVESTO_PUBLISH_WEEKLY": "1", "INVESTO_WEEKLY_OPS_DIGEST": "1"},
        github_env,
    )

    assert github_env.read_text(encoding="utf-8") == (
        "INVESTO_PUBLISH_WEEKLY=1\nINVESTO_WEEKLY_OPS_DIGEST=1\n"
    )


def test_read_event_schedule_from_github_payload(tmp_path: Path) -> None:
    script = _load_script_module()
    event_path = tmp_path / "event.json"
    event_path.write_text('{"schedule": "0 0 * * 6"}', encoding="utf-8")

    assert script.read_event_schedule(str(event_path)) == "0 0 * * 6"


def test_daily_briefing_workflow_uses_weekly_flag_script() -> None:
    workflow = _WORKFLOW.read_text(encoding="utf-8")

    assert "python scripts/resolve_weekly_flags.py" in workflow
    assert "github.event.schedule == '0 0 * * 6'" not in workflow

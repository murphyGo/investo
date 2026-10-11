"""The cutover audit reads reviewed evidence and cannot enable capabilities."""

import json
import subprocess
import sys
from pathlib import Path

from investo.models.event_config import EVENT_V3_ACTIVE_READY, EventExecutionConfig

ROOT = Path(__file__).resolve().parents[3]


def test_default_and_preview_cannot_activate_public_schema_three():
    import pytest

    assert EventExecutionConfig().document_schema == 2
    assert EventExecutionConfig().mode == "off"
    assert EVENT_V3_ACTIVE_READY is False
    with pytest.raises(ValueError):
        EventExecutionConfig(mode="active", document_schema=3).validate_publication()
    with pytest.raises(ValueError):
        EventExecutionConfig(mode="preview", document_schema=3).validate_publication()


def test_honest_blocked_audit_succeeds_but_require_ready_fails():
    args = [
        sys.executable,
        str(ROOT / "scripts/check_event_cutover.py"),
        "--evidence",
        str(ROOT / "ops/event_v3_acceptance.json"),
        "--reviewed-code-sha",
        json.loads((ROOT / "ops/event_v3_acceptance.json").read_text())["reviewed_code_sha"],
        "--policy",
        str(ROOT / "ops/event_v3_preview_policy.json"),
    ]
    result = subprocess.run(args, capture_output=True, text=True, check=False)
    assert result.returncode == 0
    data = json.loads(result.stdout)
    assert data["status"] == "blocked" and data["release_ready"] is False
    assert all(not ready for ready in data["human_ready"].values())
    assert data["accepted_scheduled_runs"] == 0 and not data["cleanup_ready"]
    pending = subprocess.run(
        [*args, "--require-ready"], capture_output=True, text=True, check=False
    )
    assert pending.returncode == 1

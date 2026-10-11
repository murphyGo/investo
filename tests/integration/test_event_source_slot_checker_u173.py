"""Missing runtime/source evidence is visible, not an offline checker failure."""

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_checker_reports_all_eight_blocked_slots_without_source_readiness():
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/check_event_source_slots.py"),
            "--manifest",
            str(ROOT / "ops/event_source_slot_qualification.json"),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    rows = [json.loads(line) for line in result.stdout.splitlines()]
    assert rows[-1] == dict(rows=8, verified=0, blocked=8, activation_ready=False)
    assert len(rows) == 9 and all(r["status"] == "blocked" for r in rows[:-1])
    assert all("access.not_verified" in r["codes"] for r in rows[:-1])

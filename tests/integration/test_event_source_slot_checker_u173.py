"""Missing runtime/source evidence is visible, not an offline checker failure."""

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_checker_distinguishes_scoped_parser_verification_from_runtime_readiness():
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
    assert rows[-1] == dict(rows=8, verified=2, blocked=6, activation_ready=False)
    assert len(rows) == 9 and sum(r["status"] == "verified" for r in rows[:-1]) == 2
    assert all("runtime.not_verified" in r["codes"] for r in rows[:-1])

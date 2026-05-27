#!/usr/bin/env python3
"""Resolve weekly-publish flags for the daily briefing GitHub workflow.

The Saturday cron is an operational intent, not a cron-string contract:
publish the public weekly digest and operator weekly ops digest only
when the scheduled event came from the KST Saturday 09:00 cron arm.
Manual dispatches stay opt-out by default even if they happen during that
hour. GitHub Actions scheduled runs can start late, so wall-clock time is
only a fallback when the event payload is unavailable.
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

KST = ZoneInfo("Asia/Seoul")
WEEKLY_FLAG_NAMES: tuple[str, str] = (
    "INVESTO_PUBLISH_WEEKLY",
    "INVESTO_WEEKLY_OPS_DIGEST",
)
SATURDAY_WEEKLY_CRON = "0 0 * * 6"


def resolve_flags(
    event_name: str,
    now_kst: datetime,
    *,
    event_schedule: str | None = None,
) -> dict[str, str]:
    """Return workflow env flags for ``event_name`` at ``now_kst``."""
    enabled = False
    if event_name == "schedule":
        if event_schedule is not None:
            enabled = event_schedule.strip() == SATURDAY_WEEKLY_CRON
        else:
            local_now = now_kst.astimezone(KST)
            enabled = local_now.weekday() == 5 and local_now.hour == 9
    value = "1" if enabled else "0"
    return {name: value for name in WEEKLY_FLAG_NAMES}


def read_event_schedule(github_event_path: str | None) -> str | None:
    """Read the cron expression from GitHub's event payload when present."""
    if not github_event_path:
        return None
    try:
        payload = json.loads(Path(github_event_path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    schedule = payload.get("schedule")
    return schedule if isinstance(schedule, str) else None


def write_github_env(flags: dict[str, str], github_env: Path) -> None:
    """Append ``flags`` to GitHub Actions' env file."""
    with github_env.open("a", encoding="utf-8") as handle:
        for name in WEEKLY_FLAG_NAMES:
            handle.write(f"{name}={flags[name]}\n")


def main() -> int:
    flags = resolve_flags(
        os.environ.get("GITHUB_EVENT_NAME", ""),
        datetime.now(tz=KST),
        event_schedule=read_event_schedule(os.environ.get("GITHUB_EVENT_PATH")),
    )
    github_env = os.environ.get("GITHUB_ENV")
    if github_env:
        write_github_env(flags, Path(github_env))
    else:
        for name in WEEKLY_FLAG_NAMES:
            print(f"{name}={flags[name]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

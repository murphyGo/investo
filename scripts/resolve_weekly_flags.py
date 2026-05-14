#!/usr/bin/env python3
"""Resolve weekly-publish flags for the daily briefing GitHub workflow.

The Saturday cron is an operational intent, not a cron-string contract:
publish the public weekly digest and operator weekly ops digest only
when a scheduled run starts during KST Saturday 09:00. Manual dispatches
stay opt-out by default even if they happen during that hour.
"""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

KST = ZoneInfo("Asia/Seoul")
WEEKLY_FLAG_NAMES: tuple[str, str] = (
    "INVESTO_PUBLISH_WEEKLY",
    "INVESTO_WEEKLY_OPS_DIGEST",
)


def resolve_flags(event_name: str, now_kst: datetime) -> dict[str, str]:
    """Return workflow env flags for ``event_name`` at ``now_kst``."""
    local_now = now_kst.astimezone(KST)
    enabled = event_name == "schedule" and local_now.weekday() == 5 and local_now.hour == 9
    value = "1" if enabled else "0"
    return {name: value for name in WEEKLY_FLAG_NAMES}


def write_github_env(flags: dict[str, str], github_env: Path) -> None:
    """Append ``flags`` to GitHub Actions' env file."""
    with github_env.open("a", encoding="utf-8") as handle:
        for name in WEEKLY_FLAG_NAMES:
            handle.write(f"{name}={flags[name]}\n")


def main() -> int:
    flags = resolve_flags(
        os.environ.get("GITHUB_EVENT_NAME", ""),
        datetime.now(tz=KST),
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

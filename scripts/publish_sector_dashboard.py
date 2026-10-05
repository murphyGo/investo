#!/usr/bin/env python3
"""Build the public sector pair or verify it before deployment; never perform git writes."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

import httpx

from investo._internal.sector_public_summary import screen_public_summary
from investo.models.sector_public import PublicSourceIssueCode
from investo.sector_dashboard.public_build import build_public_sector, hold_failed_public_build
from investo.sector_dashboard.public_probe import resolve_probe_target_date
from investo.sector_dashboard.public_render import verify_public_sector_projection
from investo.sector_dashboard.public_store import read_public_sector_projection
from investo.sector_dashboard.yahoo_data import YAHOO_USER_AGENT

_ROOT = Path(__file__).resolve().parents[1]


async def _build() -> tuple[str, int]:
    try:
        target_date = resolve_probe_target_date(datetime.now(UTC))
    except ValueError:
        outcome = hold_failed_public_build(_ROOT, (PublicSourceIssueCode.CALENDAR,))
        return outcome.model_dump_json(), 2
    async with httpx.AsyncClient(
        headers={"User-Agent": YAHOO_USER_AGENT},
        timeout=httpx.Timeout(15.0, connect=5.0, read=10.0),
        limits=httpx.Limits(max_connections=3, max_keepalive_connections=3),
        follow_redirects=False,
        trust_env=False,
    ) as client:
        report = await build_public_sector(client, repository_root=_ROOT, target_date=target_date)
    return report.model_dump_json(), report.exit_code


def _verify() -> tuple[str, int]:
    projection = read_public_sector_projection(_ROOT)
    if projection is None:
        return '{"status":"blocked","failure_codes":["build.store"]}', 2
    snapshot = verify_public_sector_projection(projection.snapshot_bytes, projection.markdown_bytes)
    return json.dumps(
        {
            "status": "verified",
            "snapshot_id": snapshot.snapshot_id,
            "as_of_date": str(snapshot.as_of_date),
        }
    ), 0


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if args not in (["--write"], ["--verify-only"]):
        print('{"status":"blocked","failure_codes":["build.arguments"]}')
        return 2
    logging.disable(logging.CRITICAL)
    try:
        text, status = asyncio.run(_build()) if args == ["--write"] else _verify()
        safe = screen_public_summary(text)
        if safe is None:
            safe, status = '{"status":"blocked","failure_codes":["build.output"]}', 2
        # Do not expose a promotable control output until the summary has passed screening.
        summary = os.environ.get("GITHUB_STEP_SUMMARY")
        if summary:
            with Path(summary).open("a", encoding="utf-8") as handle:
                handle.write("## Public sector dashboard\n\n```json\n" + safe + "\n```\n")
        output = os.environ.get("GITHUB_OUTPUT")
        if output and args == ["--write"]:
            build_status = json.loads(safe).get("status")
            if build_status not in {"promoted", "unchanged", "held_last_good", "blocked"}:
                raise ValueError("invalid control status")
            with Path(output).open("a", encoding="utf-8") as handle:
                handle.write(f"build_status={build_status}\n")
        print(safe)
        return status
    except Exception:
        print('{"status":"blocked","failure_codes":["build.internal"]}')
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

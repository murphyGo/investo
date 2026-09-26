#!/usr/bin/env python3
"""u145 Step 5: qualify the production path without public writes or publication."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import sys
from datetime import UTC, datetime
from pathlib import Path

import httpx

from investo._internal.redaction import SECRET_ENV_VARS, redact_text, scan_for_leak
from investo.sector_dashboard.hf_data import HF_USER_AGENT
from investo.sector_dashboard.public_probe import probe_public_sector, resolve_probe_target_date


async def _probe() -> tuple[str, int]:
    try:
        target_date = resolve_probe_target_date(datetime.now(UTC))
    except ValueError:
        return '{"status":"blocked","reason_codes":["source.calendar"]}', 2
    async with httpx.AsyncClient(
        headers={"User-Agent": HF_USER_AGENT},
        timeout=httpx.Timeout(15.0, connect=5.0, read=10.0),
        limits=httpx.Limits(max_connections=3, max_keepalive_connections=3),
        follow_redirects=False,
        trust_env=False,
    ) as client:
        result = await probe_public_sector(client, environ=os.environ, target_date=target_date)
    payload = result.model_dump(mode="json")
    # Runtime metadata is closed before it reaches log/Step Summary surfaces.
    commit = os.environ.get("GITHUB_SHA", "")
    run_id = os.environ.get("GITHUB_RUN_ID", "")
    payload["commit"] = commit if re.fullmatch(r"[0-9a-f]{40}", commit) else None
    payload["run_id"] = run_id if re.fullmatch(r"[0-9]{1,20}", run_id) else None
    return json.dumps(payload, sort_keys=True, separators=(",", ":")), (
        0 if result.status == "qualified" else 2
    )


def _screen_summary(text: str) -> str | None:
    secrets = tuple(
        value for name in SECRET_ENV_VARS if (value := os.environ.get(name, "").strip())
    )
    if len(text) > 4096 or any(value in text for value in secrets):
        return None
    try:
        payload = json.loads(text)
    except (ValueError, RecursionError):
        return None
    if not isinstance(payload, dict):
        return None
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    if len(canonical) > 4096 or any(value in canonical for value in secrets):
        return None
    screened = dict(payload)
    # These identities are already validated by the renderer or _probe.
    # Exact configured secrets were checked before and after JSON decoding.
    # Exempt only exact field/shape pairs from generic credential heuristics.
    for field, pattern in (
        ("snapshot_id", r"sha256:[0-9a-f]{64}"),
        ("commit", r"[0-9a-f]{40}"),
        ("run_id", r"[0-9]{1,20}"),
    ):
        identity = screened.get(field)
        if isinstance(identity, str) and re.fullmatch(pattern, identity):
            screened[field] = "[VERIFIED_ID]"
    scan_text = json.dumps(screened, sort_keys=True, separators=(",", ":"))
    if redact_text(scan_text) != scan_text or scan_for_leak(scan_text) is not None:
        return None
    return canonical


def main(argv: list[str] | None = None) -> int:
    # There is deliberately no write mode, date override, URL, ticker or key argument.
    if (sys.argv[1:] if argv is None else argv) != ["--probe-only"]:
        print('{"status":"blocked","reason_codes":["probe.arguments"]}')
        return 2
    logging.disable(logging.CRITICAL)
    try:
        text, status = asyncio.run(_probe())
        safe = _screen_summary(text)
        if safe is None:
            text, status = '{"status":"blocked","reason_codes":["probe.output"]}', 2
        else:
            text = safe
        summary = os.environ.get("GITHUB_STEP_SUMMARY")
        if summary:
            with Path(summary).open("a", encoding="utf-8") as handle:
                handle.write("## u145 production-adapter probe\n\n```json\n" + text + "\n```\n")
        print(text)
        return status
    except Exception:
        print('{"status":"blocked","reason_codes":["probe.internal"]}')
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

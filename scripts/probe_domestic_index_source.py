"""Manually probe one fixed source; emit counts, never price rows or credentials."""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
from dataclasses import asdict
from datetime import date

import httpx

from investo.sources._window import FetchWindow
from investo.sources.fsc_krx_index_price import FscKrxIndexPriceAdapter, IndexDiagnosticError


async def probe(target_date: date, client: httpx.AsyncClient) -> tuple[dict[str, object], int]:
    adapter = FscKrxIndexPriceAdapter()
    try:
        report = await adapter.fetch_with_diagnostics(
            client, FetchWindow.from_kst_date(target_date)
        )
    except IndexDiagnosticError as exc:
        return {
            "source": adapter.name,
            "target_date": target_date.isoformat(),
            "status": "failed",
            "usable_items": 0,
            "diagnostics": [asdict(row) for row in exc.diagnostics],
        }, 2
    return {
        "source": adapter.name,
        "target_date": target_date.isoformat(),
        "status": "ok" if report.items else "zero",
        "usable_items": len(report.items),
        "diagnostics": [asdict(row) for row in report.diagnostics],
    }, 0


async def _run(target_date: date) -> int:
    async with httpx.AsyncClient(follow_redirects=False) as client:
        result, code = await probe(target_date, client)
    print(json.dumps(result, ensure_ascii=True, sort_keys=True))
    return code


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target-date", required=True, type=date.fromisoformat)
    args = parser.parse_args()
    # httpx INFO includes query URLs. This source-only CLI never logs requests.
    logging.basicConfig(level=logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.CRITICAL)
    logging.getLogger("httpcore").setLevel(logging.CRITICAL)
    return asyncio.run(_run(args.target_date))


if __name__ == "__main__":
    raise SystemExit(main())

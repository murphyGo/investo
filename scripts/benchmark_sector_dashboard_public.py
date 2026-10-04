#!/usr/bin/env python3
"""TS-8: twelve full-window, 1 MiB JSON responses; no provider contact."""

from __future__ import annotations

import asyncio
import json
import resource
import sys
import time
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo


def _rss_bytes() -> int:
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return int(rss if sys.platform == "darwin" else rss * 1024)


async def _benchmark() -> dict[str, object]:
    baseline = _rss_bytes()
    cpu_started = time.process_time()
    wall_started = time.monotonic()
    import httpx

    from investo.models.market_calendar import is_trading_day
    from investo.sector_dashboard.public_probe import probe_public_sector

    target = date(2026, 10, 2)
    days = [target - timedelta(days=i) for i in range(200, -1, -1)]
    days = [d for d in days if is_trading_day("us-equity", d)]
    prices = [100.0 + i * 0.1 for i in range(len(days))]
    stamps = [
        int(datetime.combine(d, datetime.min.time(), ZoneInfo("America/New_York")).timestamp())
        for d in days
    ]
    limit = 1024 * 1024

    def handler(request: httpx.Request) -> httpx.Response:
        ticker = request.url.path.rsplit("/", 1)[1]
        payload = {
            "chart": {
                "error": None,
                "result": [
                    {
                        "meta": {
                            "symbol": ticker,
                            "currency": "USD",
                            "instrumentType": "ETF",
                            "exchangeTimezoneName": "America/New_York",
                            "dataGranularity": "1d",
                        },
                        "timestamp": stamps,
                        "indicators": {
                            "quote": [
                                {
                                    "open": prices,
                                    "high": [p + 1 for p in prices],
                                    "low": [p - 1 for p in prices],
                                    "close": prices,
                                    "volume": [1000] * len(days),
                                }
                            ]
                        },
                    }
                ],
            }
        }
        body = json.dumps(payload).encode().ljust(limit, b" ")
        return httpx.Response(200, content=body, headers={"Content-Type": "application/json"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler), trust_env=False) as client:
        result = await probe_public_sector(client, target_date=target)
    cpu_ms = round((time.process_time() - cpu_started) * 1000)
    wall_ms = round((time.monotonic() - wall_started) * 1000)
    rss_delta = max(0, _rss_bytes() - baseline)
    passed = (
        result.status == "qualified"
        and result.request_count == 12
        and cpu_ms <= 30_000
        and wall_ms <= 120_000
        and rss_delta <= 256 * 1024 * 1024
    )
    return {
        "mode": "synthetic_resource_benchmark",
        "status": "passed" if passed else "failed",
        "series_count": 12,
        "rows_per_series": len(days),
        "response_bytes": limit,
        "request_count": result.request_count,
        "probe_status": result.status,
        "cpu_ms": cpu_ms,
        "wall_ms": wall_ms,
        "peak_rss_above_baseline_bytes": rss_delta,
    }


def main() -> int:
    try:
        evidence = asyncio.run(_benchmark())
    except Exception:
        evidence = {"status": "failed", "reason_code": "benchmark.internal"}
    print(json.dumps(evidence, sort_keys=True, separators=(",", ":")))
    return 0 if evidence["status"] == "passed" else 2


if __name__ == "__main__":
    raise SystemExit(main())

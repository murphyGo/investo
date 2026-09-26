#!/usr/bin/env python3
"""TS-8 synthetic 11 x 10,000-row benchmark; never contacts the provider."""

from __future__ import annotations

import asyncio
import io
import json
import resource
import sys
import time
from datetime import date, datetime, timedelta


def _rss_bytes() -> int:
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return int(rss if sys.platform == "darwin" else rss * 1024)


async def _benchmark() -> dict[str, object]:
    # Include cold imports and fixture generation: stricter than the production
    # decode/normalize/compute/render budget above interpreter baseline.
    baseline = _rss_bytes()
    cpu_started = time.process_time()
    wall_started = time.monotonic()
    import httpx
    import pyarrow as pa
    import pyarrow.parquet as pq

    from investo.models.market_calendar import is_trading_day
    from investo.sector_dashboard.hf_data import HF_API_BASE
    from investo.sector_dashboard.public_probe import probe_public_sector

    if pa.__version__ != "25.0.1":
        return {"status": "failed", "reason_code": "benchmark.dependency"}
    target = date(2026, 9, 25)
    days = []
    cursor = target
    while len(days) < 10_000:
        if is_trading_day("us-equity", cursor):
            days.append(datetime.combine(cursor, datetime.min.time()))
        cursor -= timedelta(days=1)
    days.reverse()
    prices = [100.0 + index * 0.01 for index in range(len(days))]
    table = pa.table(
        {
            "datetime": pa.array(days, type=pa.timestamp("ns")),
            "Open": pa.array(prices, type=pa.float64()),
            "High": pa.array([p + 1 for p in prices], type=pa.float64()),
            "Low": pa.array([p - 1 for p in prices], type=pa.float64()),
            "Close": pa.array(prices, type=pa.float64()),
            "Volume": pa.array([1000] * len(days), type=pa.int64()),
            "source": pa.array(["iex"] * len(days), type=pa.large_string()),
        }
    )
    output = io.BytesIO()
    pq.write_table(table, output)
    body = output.getvalue()
    del days, prices, table, output

    def handler(request: httpx.Request) -> httpx.Response:
        ticker = request.url.path.rsplit("/", 1)[1]
        if "/download-token/" in request.url.path:
            return httpx.Response(
                200, json={"url": f"{HF_API_BASE}/download/{ticker}?token=synthetic"}
            )
        return httpx.Response(
            200, content=body, headers={"Content-Type": "application/octet-stream"}
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler), trust_env=False) as client:
        result = await probe_public_sector(
            client, environ={"HF_DATA_API_KEY": "synthetic-resource-benchmark"}, target_date=target
        )
    cpu_ms = round((time.process_time() - cpu_started) * 1000)
    wall_ms = round((time.monotonic() - wall_started) * 1000)
    rss_delta = max(0, _rss_bytes() - baseline)
    passed = (
        result.status == "qualified"
        and result.request_count == 22
        and len(body) <= 2 * 1024 * 1024
        and cpu_ms <= 30_000
        and wall_ms <= 120_000
        and rss_delta <= 256 * 1024 * 1024
    )
    return {
        "mode": "synthetic_resource_benchmark",
        "status": "passed" if passed else "failed",
        "pyarrow_version": pa.__version__,
        "series_count": 11,
        "rows_per_series": 10_000,
        "response_bytes": len(body),
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

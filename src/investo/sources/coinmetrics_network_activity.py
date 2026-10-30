"""No-key daily BTC/ETH network activity, isolated from exchange-flow collection."""

from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
from typing import ClassVar

import httpx

from investo.models import Category, NormalizedItem
from investo.models.exchange_flows import utc_time
from investo.models.network_activity import ACTIVITY_METRICS, NetworkActivity, activity_count
from investo.sources._parse import parse_json_response
from investo.sources._registry import register
from investo.sources._retry import RetryConfig, retry_get
from investo.sources._window import FetchWindow
from investo.sources.protocol import SourceFetchError


@register
class CoinMetricsNetworkActivityAdapter:
    name: ClassVar[str] = "coinmetrics-network-activity"
    category: ClassVar[Category] = "macro"

    async def fetch(self, client: httpx.AsyncClient, window: FetchWindow) -> list[NormalizedItem]:
        request_at = datetime.now(UTC)
        as_of = min(
            request_at, window.end_utc, window.evidence_received_at or request_at
        ).astimezone(UTC)
        latest = as_of.date() - timedelta(days=1)
        first = latest - timedelta(days=7)
        response = await retry_get(
            client,
            "https://community-api.coinmetrics.io/v4/timeseries/asset-metrics",
            source_name=self.name,
            params={
                "assets": "btc,eth",
                "metrics": "AdrActCnt,TxCnt",
                "frequency": "1d",
                "start_time": first.isoformat(),
                "end_time": latest.isoformat(),
                "page_size": "16",
            },
            config=RetryConfig(max_response_bytes=64 * 1024),
        )
        collected_at = datetime.now(UTC)
        payload = parse_json_response(response, source_name=self.name, append_exc=False)
        if (
            not isinstance(payload, dict)
            or not isinstance(payload.get("data"), list)
            or len(payload["data"]) > 16
            or payload.get("next_page_url")
        ):
            raise SourceFetchError(self.name, "unexpected network activity schema", transient=False)
        counts: dict[tuple[str, str, date], str] = {}
        conflicts: set[tuple[str, str, date]] = set()
        for row in payload["data"]:
            try:
                if not isinstance(row, dict) or row.get("asset") not in ("btc", "eth"):
                    raise ValueError("invalid network row")
                instant = utc_time(row.get("time"))
                if instant.time() != time.min or not first <= instant.date() <= latest:
                    raise ValueError("invalid observation day")
            except (ValueError, TypeError, OverflowError):
                continue
            for metric in ACTIVITY_METRICS:
                try:
                    value = activity_count(row.get(metric))
                except ValueError:
                    continue
                key = (row["asset"], metric, instant.date())
                if key in counts and counts[key] != value:
                    conflicts.add(key)
                counts[key] = value
        for key in conflicts:
            del counts[key]
        items = []
        for asset in ("btc", "eth"):
            for metric, label in ACTIVITY_METRICS.items():
                days = [day for a, m, day in counts if (a, m) == (asset, metric)]
                if not days:
                    continue
                day = max(days)
                previous = [
                    counts.get((asset, metric, day - timedelta(days=offset)))
                    for offset in range(7, 0, -1)
                ]
                baseline = tuple(value for value in previous if value is not None)
                try:
                    activity = NetworkActivity(
                        asset,
                        metric,
                        day,
                        counts[(asset, metric, day)],
                        baseline if len(baseline) == 7 else (),
                        collected_at,
                        as_of,
                    )
                except (ValueError, OverflowError):
                    continue
                items.append(
                    NormalizedItem(
                        source_name=self.name,
                        category=self.category,
                        title=f"{asset.upper()} 일별 {label} ({day}, UTC)",
                        summary=(
                            f"{activity.value} · Coin Metrics 관측 UTC 일별 {label}. "
                            "조회 시점의 값이며 검토 상태 미제공, 이후 수정 가능. "
                            "실제 사용자 수·매매량·가격 방향을 의미하지 않음. CC BY-NC 4.0."
                        ),
                        url="https://github.com/coinmetrics/data",
                        # No provider publication/revision instant is supplied.
                        published_at=collected_at,
                        raw_metadata=activity.metadata(),
                    )
                )
        if payload["data"] and not items:
            raise SourceFetchError(self.name, "no valid recent network counts", transient=False)
        return items

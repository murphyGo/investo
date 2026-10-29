"""Coin Metrics Community daily BTC/ETH flows, for noncommercial briefings.

No key or paid fallback. CC BY-NC 4.0 attribution is preserved by the
deterministic indicator renderer. Synthetic fixtures contain no upstream data.
"""

from __future__ import annotations

from datetime import UTC, datetime, time, timedelta
from typing import ClassVar

import httpx

from investo.models import Category, NormalizedItem
from investo.models.exchange_flows import ExchangeFlow, utc_time
from investo.sources._parse import parse_json_response
from investo.sources._registry import register
from investo.sources._retry import retry_get
from investo.sources._window import FetchWindow
from investo.sources.protocol import SourceFetchError

_ENDPOINT = "https://community-api.coinmetrics.io/v4/timeseries/asset-metrics"
_INFLOW = "FlowInExNtv"
_OUTFLOW = "FlowOutExNtv"


def _text(value: object) -> str:
    if not isinstance(value, str):
        raise ValueError("expected flow string")
    return value


@register
class CoinMetricsExchangeFlowsAdapter:
    name: ClassVar[str] = "coinmetrics-exchange-flows"
    category: ClassVar[Category] = "macro"

    async def fetch(self, client: httpx.AsyncClient, window: FetchWindow) -> list[NormalizedItem]:
        request_at = datetime.now(UTC)
        as_of = min(request_at, window.end_utc, window.evidence_received_at or request_at)
        latest_day = as_of.date() - timedelta(days=1)
        first_day = latest_day - timedelta(days=2)
        response = await retry_get(
            client,
            _ENDPOINT,
            source_name=self.name,
            params={
                "assets": "btc,eth",
                "metrics": f"{_INFLOW},{_OUTFLOW}",
                "frequency": "1d",
                "start_time": first_day.isoformat(),
                "end_time": latest_day.isoformat(),
                "page_size": "6",
                "status": "all",
            },
        )
        collected_at = datetime.now(UTC)
        payload = parse_json_response(response, source_name=self.name, append_exc=False)
        if (
            not isinstance(payload, dict)
            or not isinstance(payload.get("data"), list)
            or len(payload["data"]) > 6
            or payload.get("next_page_url")
        ):
            raise SourceFetchError(self.name, "unexpected daily flow schema", transient=False)
        rows = payload["data"]
        flows: dict[tuple[str, str], ExchangeFlow] = {}
        conflicts: set[tuple[str, str]] = set()
        for row in rows:
            try:
                if not isinstance(row, dict):
                    raise ValueError("invalid row")
                observed = utc_time(row.get("time"))
                if observed.time() != time.min or not first_day <= observed.date() <= latest_day:
                    raise ValueError("invalid observation date")
                flow = ExchangeFlow(
                    asset=_text(row.get("asset")),
                    day=observed.date(),
                    inflow=_text(row.get(_INFLOW)),
                    outflow=_text(row.get(_OUTFLOW)),
                    inflow_status=_text(row.get(f"{_INFLOW}-status")),
                    outflow_status=_text(row.get(f"{_OUTFLOW}-status")),
                    inflow_updated_at=utc_time(row.get(f"{_INFLOW}-status-time")),
                    outflow_updated_at=utc_time(row.get(f"{_OUTFLOW}-status-time")),
                    collected_at=collected_at,
                    as_of=as_of,
                )
            except (ValueError, TypeError, OverflowError):
                continue
            key = (flow.asset, flow.day.isoformat())
            if key in flows and flows[key] != flow:
                conflicts.add(key)
            flows[key] = flow
        latest: dict[str, ExchangeFlow] = {}
        for key, flow in sorted(flows.items()):
            if key not in conflicts:
                latest[flow.asset] = flow
        if rows and not latest:
            raise SourceFetchError(self.name, "no valid daily flow pairs", transient=False)
        return [
            NormalizedItem(
                source_name=self.name,
                category=self.category,
                title=f"{flow.asset.upper()} 거래소 일별 순유입 ({flow.day}, UTC)",
                summary=(
                    f"{flow.netflow} {flow.asset.upper()} · {flow.status_label}. "
                    "Coin Metrics 추적 주소, 거래소 간 이체 제외. Investo 유입 - 유출 계산. "
                    "CC BY-NC 4.0 비상업 데이터; 실시간/체결량이 아님."
                ),
                url="https://github.com/coinmetrics/data",
                published_at=flow.available_at,
                raw_metadata=flow.metadata(),
            )
            for flow in latest.values()
        ]

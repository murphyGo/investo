"""Nasdaq earnings calendar adapter — first ``earnings`` source.

Consumes Nasdaq's public calendar JSON endpoint for the target date and
emits one :class:`NormalizedItem` per scheduled earnings event.

Design choices:

* **No API key** — the endpoint is reachable with browser-style request
  headers and requires no account or GitHub Secret.
* **Date-scoped endpoint** — the adapter queries exactly one date:
  ``window.target_date.isoformat()``.
* **Event-date timestamp** — Nasdaq supplies report buckets such as
  pre-market / after-hours, not an exact timestamp. ``published_at`` is
  anchored to UTC midnight on the event date, which falls inside the
  corresponding KST :class:`FetchWindow`; the report bucket is preserved
  in ``raw_metadata["report_time"]``.
* **Flat metadata** — all Nasdaq fields are stored as strings and empty
  optional values are omitted.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, time
from typing import Any, ClassVar
from urllib.parse import quote

import httpx
from pydantic import ValidationError

from investo.models import Category, NormalizedItem
from investo.sources._config import SUMMARY_MAX_LEN
from investo.sources._registry import register
from investo.sources._retry import retry_get
from investo.sources._sanitize import strip_html
from investo.sources._window import FetchWindow
from investo.sources.protocol import SourceFetchError

_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/124 Safari/537.36"
)


@register
class NasdaqEarningsCalendarAdapter:
    """Adapter for Nasdaq's public earnings calendar JSON endpoint."""

    name: ClassVar[str] = "nasdaq-earnings-calendar"
    category: ClassVar[Category] = "earnings"

    _ENDPOINT: ClassVar[str] = "https://api.nasdaq.com/api/calendar/earnings"

    async def fetch(
        self,
        client: httpx.AsyncClient,
        window: FetchWindow,
    ) -> list[NormalizedItem]:
        response = await retry_get(
            client,
            self._ENDPOINT,
            source_name=self.name,
            params={"date": window.target_date.isoformat()},
            headers={
                "User-Agent": _USER_AGENT,
                "Accept": "application/json, text/plain, */*",
                "Origin": "https://www.nasdaq.com",
                "Referer": "https://www.nasdaq.com/market-activity/earnings",
            },
        )
        try:
            payload = response.json()
        except json.JSONDecodeError as exc:
            raise SourceFetchError(
                source_name=self.name,
                message=f"malformed JSON: {exc}",
                transient=False,
                cause=exc,
            ) from exc

        rows = self._extract_rows(payload)
        published_at = datetime.combine(window.target_date, time.min, tzinfo=UTC)

        items: list[NormalizedItem] = []
        for row in rows:
            normalized = self._normalize_row(row, published_at)
            if normalized is not None:
                items.append(normalized)
        return items

    def _extract_rows(self, payload: Any) -> list[Any]:
        if not isinstance(payload, dict):
            raise SourceFetchError(
                source_name=self.name,
                message=f"expected object response, got {type(payload).__name__}",
                transient=False,
            )
        status = payload.get("status")
        if isinstance(status, dict) and status.get("rCode") not in (None, 200):
            raise SourceFetchError(
                source_name=self.name,
                message=f"unexpected status rCode: {status.get('rCode')}",
                transient=False,
            )
        data = payload.get("data")
        if not isinstance(data, dict):
            raise SourceFetchError(
                source_name=self.name,
                message="missing data object",
                transient=False,
            )
        rows = data.get("rows")
        if rows is None:
            return []
        if not isinstance(rows, list):
            raise SourceFetchError(
                source_name=self.name,
                message=f"expected data.rows list, got {type(rows).__name__}",
                transient=False,
            )
        return rows

    def _normalize_row(self, row: Any, published_at: datetime) -> NormalizedItem | None:
        if not isinstance(row, dict):
            return None

        symbol = self._clean(row.get("symbol"))
        name = self._clean(row.get("name"))
        if not symbol or not name:
            return None

        report_time = self._normalize_report_time(self._clean(row.get("time")))
        eps_forecast = self._clean(row.get("epsForecast"))
        fiscal_quarter = self._clean(row.get("fiscalQuarterEnding"))
        no_of_ests = self._clean(row.get("noOfEsts"))
        market_cap = self._clean(row.get("marketCap"))
        last_year_eps = self._clean(row.get("lastYearEPS"))
        last_year_report_date = self._clean(row.get("lastYearRptDt"))

        title_parts = [f"{symbol} earnings"]
        if report_time:
            title_parts.append(report_time)
        if eps_forecast:
            title_parts.append(f"EPS forecast {eps_forecast}")
        title = " — ".join(title_parts)

        summary_parts = [name]
        if fiscal_quarter:
            summary_parts.append(f"Fiscal quarter: {fiscal_quarter}")
        if market_cap:
            summary_parts.append(f"Market cap: {market_cap}")
        if no_of_ests:
            summary_parts.append(f"Estimates: {no_of_ests}")
        if last_year_eps:
            summary_parts.append(f"Last year EPS: {last_year_eps}")
        summary = "; ".join(summary_parts)
        if len(summary) > SUMMARY_MAX_LEN:
            summary = summary[:SUMMARY_MAX_LEN]

        raw_metadata = self._metadata(
            {
                "symbol": symbol,
                "company_name": name,
                "report_time": report_time,
                "fiscal_quarter_ending": fiscal_quarter,
                "eps_forecast": eps_forecast,
                "no_of_ests": no_of_ests,
                "market_cap": market_cap,
                "last_year_eps": last_year_eps,
                "last_year_report_date": last_year_report_date,
            }
        )

        try:
            encoded_symbol = quote(symbol.lower(), safe="")
            return NormalizedItem(
                source_name=self.name,
                category=self.category,
                title=title,
                summary=summary,
                url=f"https://www.nasdaq.com/market-activity/stocks/{encoded_symbol}/earnings",
                published_at=published_at,
                raw_metadata=raw_metadata,
            )
        except ValidationError:
            return None

    @staticmethod
    def _clean(value: Any) -> str | None:
        if not isinstance(value, str):
            return None
        cleaned = strip_html(value).strip()
        if not cleaned or cleaned.upper() == "N/A":
            return None
        return cleaned

    @staticmethod
    def _normalize_report_time(value: str | None) -> str | None:
        if value is None:
            return None
        mapping = {
            "time-pre-market": "pre-market",
            "time-after-hours": "after-hours",
            "time-not-supplied": "not-supplied",
        }
        return mapping.get(value, value)

    @staticmethod
    def _metadata(values: dict[str, str | None]) -> dict[str, str]:
        return {key: value for key, value in values.items() if value}

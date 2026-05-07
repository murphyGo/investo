"""Nasdaq earnings calendar adapter — first ``earnings`` source.

Consumes Nasdaq's public calendar JSON endpoint for the target date and
emits one :class:`NormalizedItem` per scheduled earnings event.

Design choices:

* **No API key** — the endpoint is reachable with browser-style request
  headers and requires no account or GitHub Secret.
* **Date-scoped endpoint** — the adapter queries the target date by
  default. u35 event-lookahead opt-in: when
  ``INVESTO_EARNINGS_LOOKAHEAD_DAYS`` is set to a positive integer
  (clamped to ``[1, 14]``), the adapter additionally queries each of
  the next ``N`` calendar days and tags those rows with a
  forward-looking ``scheduled_at`` timestamp distinct from the
  original publish date. The default (env var unset / blank) keeps
  the original target-date-only behavior so existing fixtures and
  contract tests stay byte-stable.
* **Event-date timestamp** — Nasdaq supplies report buckets such as
  pre-market / after-hours, not an exact timestamp. ``published_at`` is
  anchored to UTC midnight on the event date, which falls inside the
  corresponding KST :class:`FetchWindow`; the report bucket is preserved
  in ``raw_metadata["report_time"]``. For lookahead rows, ``published_at``
  stays anchored to the *target date* (so window filtering still keeps
  the row in the right publish slice) and ``scheduled_at`` carries the
  forward calendar date. ``raw_metadata["scheduled_date"]`` makes the
  event date greppable in the audit log.
* **Flat metadata** — all Nasdaq fields are stored as strings and empty
  optional values are omitted.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import UTC, date, datetime, time, timedelta
from typing import Any, ClassVar, Final
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

_logger = logging.getLogger(__name__)

# u35 event-lookahead opt-in env var. Unset / blank / non-numeric / out
# of range values fall back to ``0`` (target-date-only, the historical
# behavior). Range clamp keeps a typo from blowing up the request count.
_ENV_LOOKAHEAD_DAYS: Final[str] = "INVESTO_EARNINGS_LOOKAHEAD_DAYS"
_LOOKAHEAD_MAX_DAYS: Final[int] = 14

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
        target_published_at = datetime.combine(window.target_date, time.min, tzinfo=UTC)
        lookahead_days = _resolve_lookahead_days()

        items: list[NormalizedItem] = []
        # Day 0 — the historic target-date query. ``scheduled_at`` is
        # ``None`` so the row is treated as a backward-looking earnings
        # release of the publish window.
        items.extend(
            await self._fetch_for_date(
                client,
                event_date=window.target_date,
                published_at=target_published_at,
                scheduled_at=None,
            )
        )
        # Day 1 .. N — opt-in lookahead pass. Each day's rows are tagged
        # with ``scheduled_at`` so downstream callers (briefing pipeline
        # lookahead bucket, notifier imminent-tag) can distinguish
        # forward-scheduled events from same-day releases.
        for offset in range(1, lookahead_days + 1):
            event_date = window.target_date + timedelta(days=offset)
            scheduled_at = datetime.combine(event_date, time.min, tzinfo=UTC)
            items.extend(
                await self._fetch_for_date(
                    client,
                    event_date=event_date,
                    published_at=target_published_at,
                    scheduled_at=scheduled_at,
                )
            )
        return items

    async def _fetch_for_date(
        self,
        client: httpx.AsyncClient,
        *,
        event_date: date,
        published_at: datetime,
        scheduled_at: datetime | None,
    ) -> list[NormalizedItem]:
        """Query one calendar date and normalize the rows.

        Lookahead errors do **not** crash the whole adapter — Nasdaq's
        endpoint returns an empty ``data.rows`` for many forward dates
        (calendar not yet populated for some symbols). A single-day
        :class:`SourceFetchError` is logged at WARNING and contributes
        ``[]``; the target-date pass still propagates errors to keep
        the historical fast-fail contract.
        """
        try:
            response = await retry_get(
                client,
                self._ENDPOINT,
                source_name=self.name,
                params={"date": event_date.isoformat()},
                headers={
                    "User-Agent": _USER_AGENT,
                    "Accept": "application/json, text/plain, */*",
                    "Origin": "https://www.nasdaq.com",
                    "Referer": "https://www.nasdaq.com/market-activity/earnings",
                },
            )
        except SourceFetchError:
            if scheduled_at is None:
                # Day-0 failure is a real error — propagate.
                raise
            _logger.warning(
                "nasdaq-earnings lookahead day %s fetch failed; skipping",
                event_date.isoformat(),
            )
            return []
        try:
            payload = response.json()
        except json.JSONDecodeError as exc:
            if scheduled_at is None:
                raise SourceFetchError(
                    source_name=self.name,
                    message=f"malformed JSON: {exc}",
                    transient=False,
                    cause=exc,
                ) from exc
            _logger.warning(
                "nasdaq-earnings lookahead day %s malformed JSON; skipping: %s",
                event_date.isoformat(),
                exc,
            )
            return []

        try:
            rows = self._extract_rows(payload)
        except SourceFetchError:
            if scheduled_at is None:
                raise
            _logger.warning(
                "nasdaq-earnings lookahead day %s payload shape rejected; skipping",
                event_date.isoformat(),
            )
            return []

        items: list[NormalizedItem] = []
        for row in rows:
            normalized = self._normalize_row(
                row,
                published_at=published_at,
                scheduled_at=scheduled_at,
                event_date=event_date,
            )
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

    def _normalize_row(
        self,
        row: Any,
        *,
        published_at: datetime,
        scheduled_at: datetime | None,
        event_date: date,
    ) -> NormalizedItem | None:
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

        # u35: lookahead rows surface their forward calendar date in the
        # title so the LLM (and a human grep'ping the audit log) can
        # distinguish "today's release" from "scheduled in N days".
        title_parts = [f"{symbol} earnings"]
        if scheduled_at is not None:
            title_parts.append(event_date.isoformat())
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

        raw_metadata_inputs: dict[str, str | None] = {
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
        if scheduled_at is not None:
            raw_metadata_inputs["scheduled_date"] = event_date.isoformat()
        raw_metadata = self._metadata(raw_metadata_inputs)

        try:
            encoded_symbol = quote(symbol.lower(), safe="")
            return NormalizedItem(
                source_name=self.name,
                category=self.category,
                title=title,
                summary=summary,
                url=f"https://www.nasdaq.com/market-activity/stocks/{encoded_symbol}/earnings",
                published_at=published_at,
                scheduled_at=scheduled_at,
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


def _resolve_lookahead_days() -> int:
    """Read ``INVESTO_EARNINGS_LOOKAHEAD_DAYS`` and clamp to ``[0, _LOOKAHEAD_MAX_DAYS]``.

    Returns ``0`` when unset / blank / non-numeric / negative — that
    keeps the historic single-date behavior. Values above the cap are
    clamped to ``_LOOKAHEAD_MAX_DAYS`` and a warning is logged so an
    operator typo (e.g. ``=140``) surfaces in the GHA log instead of
    silently exploding the request count.
    """
    raw = os.environ.get(_ENV_LOOKAHEAD_DAYS, "").strip()
    if not raw:
        return 0
    try:
        value = int(raw)
    except ValueError:
        _logger.warning(
            "%s=%r invalid (non-numeric); using default=0",
            _ENV_LOOKAHEAD_DAYS,
            raw,
        )
        return 0
    if value < 0:
        _logger.warning(
            "%s=%r invalid (negative); using default=0",
            _ENV_LOOKAHEAD_DAYS,
            raw,
        )
        return 0
    if value > _LOOKAHEAD_MAX_DAYS:
        _logger.warning(
            "%s=%r above max=%d; clamping",
            _ENV_LOOKAHEAD_DAYS,
            raw,
            _LOOKAHEAD_MAX_DAYS,
        )
        return _LOOKAHEAD_MAX_DAYS
    return value

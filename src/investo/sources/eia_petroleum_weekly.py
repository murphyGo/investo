"""EIA weekly petroleum facts adapter."""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from typing import Any, ClassVar
from zoneinfo import ZoneInfo

import httpx
from pydantic import ValidationError

from investo.models import Category, NormalizedItem
from investo.sources._config import format_float
from investo.sources._fanout import gather_with_error_isolation
from investo.sources._parse import parse_json_response
from investo.sources._registry import register
from investo.sources._retry import RetryConfig, retry_get
from investo.sources._window import FetchWindow
from investo.sources.protocol import SourceFetchError

_ENV_KEY = "EIA_API_KEY"
_DEMO_KEY = "DEMO_KEY"
_ENDPOINT = "https://api.eia.gov/v2/petroleum/sum/sndw/data/"
_EIA_PAGE_URL = "https://www.eia.gov/petroleum/supply/weekly/"
_NY = ZoneInfo("America/New_York")
_WEEKLY_RELEASE_TIME = time(10, 30)
_RETRY_CONFIG = RetryConfig(timeout_s=12.0, retries=1, backoffs=(1.0,), total_budget_s=25.0)


@dataclass(frozen=True, slots=True)
class _SeriesConfig:
    series_id: str
    label: str


_SERIES_CONFIGS: tuple[_SeriesConfig, ...] = (
    _SeriesConfig("WCESTUS1", "Commercial crude stocks excluding SPR"),
    _SeriesConfig("WGTSTUS1", "Total gasoline stocks"),
    _SeriesConfig("WDISTUS1", "Distillate fuel oil stocks"),
    _SeriesConfig("WCRFPUS2", "U.S. crude oil field production"),
    _SeriesConfig("WCEIMUS2", "Commercial crude oil imports excluding SPR"),
    _SeriesConfig("WPULEUS3", "Refinery utilization"),
)


@register
class EiaPetroleumWeeklyAdapter:
    """Adapter for EIA Weekly Petroleum Status public API rows."""

    name: ClassVar[str] = "eia-petroleum-weekly"
    category: ClassVar[Category] = "macro"

    async def fetch(
        self,
        client: httpx.AsyncClient,
        window: FetchWindow,
    ) -> list[NormalizedItem]:
        api_key = os.environ.get(_ENV_KEY, "").strip() or _DEMO_KEY
        return await gather_with_error_isolation(
            (self._fetch_one(client, config, api_key, window) for config in _SERIES_CONFIGS),
            source_name=self.name,
        )

    async def _fetch_one(
        self,
        client: httpx.AsyncClient,
        config: _SeriesConfig,
        api_key: str,
        window: FetchWindow,
    ) -> NormalizedItem | None:
        response = await retry_get(
            client,
            _ENDPOINT,
            source_name=self.name,
            params={
                "api_key": api_key,
                "frequency": "weekly",
                "data[0]": "value",
                "facets[series][]": config.series_id,
                "sort[0][column]": "period",
                "sort[0][direction]": "desc",
                "end": window.target_date.isoformat(),
                "offset": "0",
                "length": "1",
            },
            config=_RETRY_CONFIG,
        )
        payload = parse_json_response(
            response,
            source_name=self.name,
            message=f"malformed EIA JSON for {config.series_id}",
        )
        row = _extract_first_row(payload, source_name=self.name, series_id=config.series_id)
        try:
            return _row_to_item(
                row, config=config, source_name=self.name, target_date=window.target_date
            )
        except (KeyError, TypeError, ValueError, ValidationError):
            return None


def _extract_first_row(payload: Any, *, source_name: str, series_id: str) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise SourceFetchError(
            source_name=source_name,
            message=f"non-object EIA response for {series_id}",
            transient=False,
        )
    if isinstance(payload.get("error"), dict):
        error = payload["error"]
        code = str(error.get("code") or "EIA_ERROR")
        raise SourceFetchError(
            source_name=source_name,
            message=f"EIA API error for {series_id}: {code}",
            transient=False,
        )
    response = payload.get("response")
    if not isinstance(response, dict):
        raise SourceFetchError(
            source_name=source_name,
            message=f"missing EIA response for {series_id}",
            transient=False,
        )
    data = response.get("data")
    if not isinstance(data, list) or not data:
        raise SourceFetchError(
            source_name=source_name,
            message=f"empty EIA rows for {series_id}",
            transient=False,
        )
    row = data[0]
    if not isinstance(row, dict):
        raise SourceFetchError(
            source_name=source_name,
            message=f"malformed EIA row for {series_id}",
            transient=False,
        )
    return row


def _row_to_item(
    row: dict[str, Any],
    *,
    config: _SeriesConfig,
    source_name: str,
    target_date: date,
) -> NormalizedItem:
    period = date.fromisoformat(str(row["period"]))
    if period > target_date:
        raise ValueError("EIA row is after target date")
    release_date = _estimated_wpsr_release_date(period)
    if release_date > target_date:
        raise ValueError("EIA row has not been released by target date")
    value = float(row["value"])
    units = str(row.get("units") or "").strip()
    description = str(row.get("series-description") or config.label).strip()
    published_at = datetime.combine(release_date, _WEEKLY_RELEASE_TIME, tzinfo=_NY).astimezone(UTC)
    title = f"EIA {config.label} {period.isoformat()}: {value:g} {units}"
    summary = f"{description}: {value:g} {units}; weekly EIA WPSR fact, not current-session data"
    return NormalizedItem(
        source_name=source_name,
        category="macro",
        title=title,
        summary=summary,
        url=_EIA_PAGE_URL,
        published_at=published_at,
        raw_metadata={
            "series_id": config.series_id,
            "series_description": description,
            "release_date": release_date.isoformat(),
            "as_of_date": period.isoformat(),
            "value": format_float(value),
            "units": units,
            "source_lag_days": str((target_date - period).days),
            "release_lag_days": str((target_date - release_date).days),
            "data_frequency": "weekly",
            "delayed_data_label": "weekly EIA petroleum status data, not intraday",
            "api_key_mode": "EIA_API_KEY" if os.environ.get(_ENV_KEY, "").strip() else "DEMO_KEY",
        },
    )


def _estimated_wpsr_release_date(period: date) -> date:
    """Estimate the WPSR public release date for a Friday week-ending date.

    EIA's v2 petroleum rows carry the data period but not the report
    publication date. WPSR normally publishes the following Wednesday at
    10:30 ET; U.S. federal holidays early in the week move that release
    back by one business day. The conservative holiday adjustment avoids
    backfill leakage before a delayed release.
    """

    release = period + timedelta(days=5)
    week_monday = period + timedelta(days=3)
    if any(_is_us_federal_holiday(week_monday + timedelta(days=offset)) for offset in range(3)):
        release += timedelta(days=1)
    while release.weekday() >= 5:
        release += timedelta(days=1)
    return release


def _is_us_federal_holiday(day: date) -> bool:
    observed = {
        _observed_fixed_holiday(day.year, 1, 1),
        _nth_weekday(day.year, 1, 0, 3),
        _nth_weekday(day.year, 2, 0, 3),
        _last_weekday(day.year, 5, 0),
        _observed_fixed_holiday(day.year, 6, 19),
        _observed_fixed_holiday(day.year, 7, 4),
        _nth_weekday(day.year, 9, 0, 1),
        _nth_weekday(day.year, 10, 0, 2),
        _observed_fixed_holiday(day.year, 11, 11),
        _nth_weekday(day.year, 11, 3, 4),
        _observed_fixed_holiday(day.year, 12, 25),
    }
    return day in observed


def _observed_fixed_holiday(year: int, month: int, day: int) -> date:
    actual = date(year, month, day)
    if actual.weekday() == 5:
        return actual - timedelta(days=1)
    if actual.weekday() == 6:
        return actual + timedelta(days=1)
    return actual


def _nth_weekday(year: int, month: int, weekday: int, nth: int) -> date:
    current = date(year, month, 1)
    offset = (weekday - current.weekday()) % 7
    return current + timedelta(days=offset + 7 * (nth - 1))


def _last_weekday(year: int, month: int, weekday: int) -> date:
    if month == 12:
        current = date(year + 1, 1, 1) - timedelta(days=1)
    else:
        current = date(year, month + 1, 1) - timedelta(days=1)
    offset = (current.weekday() - weekday) % 7
    return current - timedelta(days=offset)


__all__ = [
    "EiaPetroleumWeeklyAdapter",
]

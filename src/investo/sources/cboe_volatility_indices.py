"""Cboe volatility-index CSV adapter."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import UTC, date, datetime, time
from io import StringIO
from typing import ClassVar
from zoneinfo import ZoneInfo

import httpx
from pydantic import ValidationError

from investo.models import Category, NormalizedItem
from investo.sources._config import format_float
from investo.sources._fanout import gather_with_error_isolation
from investo.sources._registry import register
from investo.sources._retry import RetryConfig, retry_get
from investo.sources._window import FetchWindow
from investo.sources.protocol import SourceFetchError

_CHICAGO = ZoneInfo("America/Chicago")
_CLOSE_TIME = time(15, 15)
_BASE_URL = "https://cdn.cboe.com/api/global/us_indices/daily_prices"
_RETRY_CONFIG = RetryConfig(timeout_s=10.0, retries=1, backoffs=(1.0,), total_budget_s=20.0)


@dataclass(frozen=True, slots=True)
class _IndexConfig:
    code: str
    label: str


_INDEX_CONFIGS: tuple[_IndexConfig, ...] = (
    _IndexConfig("VVIX", "VVIX volatility-of-volatility index"),
    _IndexConfig("SKEW", "SKEW tail-risk index"),
)


@register
class CboeVolatilityIndicesAdapter:
    """Adapter for official Cboe VVIX/SKEW daily CSVs."""

    name: ClassVar[str] = "cboe-volatility-indices"
    category: ClassVar[Category] = "macro"

    async def fetch(
        self,
        client: httpx.AsyncClient,
        window: FetchWindow,
    ) -> list[NormalizedItem]:
        return await gather_with_error_isolation(
            (self._fetch_one(client, config, window) for config in _INDEX_CONFIGS),
            source_name=self.name,
        )

    async def _fetch_one(
        self,
        client: httpx.AsyncClient,
        config: _IndexConfig,
        window: FetchWindow,
    ) -> NormalizedItem | None:
        url = f"{_BASE_URL}/{config.code}_History.csv"
        response = await retry_get(client, url, source_name=self.name, config=_RETRY_CONFIG)
        try:
            row = _latest_row_on_or_before(
                response.text, code=config.code, target_date=window.target_date
            )
        except ValueError as exc:
            raise SourceFetchError(
                source_name=self.name,
                message=f"malformed Cboe CSV for {config.code}: {exc}",
                transient=False,
                cause=exc,
            ) from exc
        if row is None:
            return None
        try:
            return _row_to_item(
                row, config=config, source_name=self.name, target_date=window.target_date
            )
        except (KeyError, TypeError, ValueError, ValidationError):
            return None


def _latest_row_on_or_before(
    text: str,
    *,
    code: str,
    target_date: date,
) -> dict[str, str] | None:
    rows: list[tuple[date, dict[str, str]]] = []
    reader = csv.DictReader(StringIO(text))
    if "DATE" not in (reader.fieldnames or []) or code not in (reader.fieldnames or []):
        raise ValueError(f"missing DATE/{code} headers")
    for row in reader:
        row_date_text = (row.get("DATE") or "").strip()
        value = (row.get(code) or "").strip()
        if not row_date_text or not value:
            continue
        row_date = datetime.strptime(row_date_text, "%m/%d/%Y").date()
        if row_date <= target_date:
            rows.append((row_date, row))
    if not rows:
        return None
    return max(rows, key=lambda pair: pair[0])[1]


def _row_to_item(
    row: dict[str, str],
    *,
    config: _IndexConfig,
    source_name: str,
    target_date: date,
) -> NormalizedItem:
    row_date = datetime.strptime(row["DATE"], "%m/%d/%Y").date()
    value = float(row[config.code])
    published_at = datetime.combine(row_date, _CLOSE_TIME, tzinfo=_CHICAGO).astimezone(UTC)
    title = f"Cboe {config.code} {row_date.isoformat()}: {value:.2f}"
    summary = f"{config.label}: {value:.2f}; official daily close, not an intraday snapshot"
    return NormalizedItem(
        source_name=source_name,
        category="macro",
        title=title,
        summary=summary,
        url=f"{_BASE_URL}/{config.code}_History.csv",
        published_at=published_at,
        raw_metadata={
            "index_code": config.code,
            "as_of_date": row_date.isoformat(),
            "value": format_float(value),
            "units": "index points",
            "source_lag_days": str((target_date - row_date).days),
            "data_frequency": "daily",
            "delayed_data_label": "official Cboe daily close, not intraday",
        },
    )

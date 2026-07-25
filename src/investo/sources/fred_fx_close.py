"""FRED H.10 DEXKOUS adapter for the KRW-per-USD daily close."""

from __future__ import annotations

import math
import os
from datetime import UTC, date, datetime, time
from typing import Any, ClassVar
from zoneinfo import ZoneInfo

import httpx
from pydantic import ValidationError

from investo.models import Category, NormalizedItem
from investo.sources._config import SUMMARY_MAX_LEN, format_float
from investo.sources._core_fact_map import core_fact_for_ticker, core_fact_metadata_key
from investo.sources._parse import parse_json_response
from investo.sources._registry import register
from investo.sources._retry import retry_get
from investo.sources._window import FetchWindow
from investo.sources.protocol import SourceFetchError

_NY = ZoneInfo("America/New_York")
_ENV_KEY = "FRED_API_KEY"
_SERIES_ID = "DEXKOUS"
_TICKER = "KRW=X"
_MAX_AGE_DAYS = 7
_PLACEHOLDER = "."


@register
class FredFxCloseAdapter:
    """Fetch the latest fresh DEXKOUS observation through the FRED API."""

    name: ClassVar[str] = "fred-fx-close"
    category: ClassVar[Category] = "price"
    _ENDPOINT: ClassVar[str] = "https://api.stlouisfed.org/fred/series/observations"

    async def fetch(
        self,
        client: httpx.AsyncClient,
        window: FetchWindow,
    ) -> list[NormalizedItem]:
        api_key = os.environ.get(_ENV_KEY, "").strip()
        if not api_key:
            raise SourceFetchError(
                source_name=self.name,
                message=f"{_ENV_KEY} not set; {self.name} adapter will not run",
                transient=False,
            )

        response = await retry_get(
            client,
            self._ENDPOINT,
            source_name=self.name,
            params={
                "series_id": _SERIES_ID,
                "api_key": api_key,
                "file_type": "json",
                "sort_order": "desc",
                "limit": "16",
            },
        )
        payload = parse_json_response(
            response,
            source_name=self.name,
            message=f"malformed JSON for {_SERIES_ID}",
            append_exc=False,
        )
        if not isinstance(payload, dict):
            raise SourceFetchError(
                source_name=self.name,
                message=f"non-object FRED response for {_SERIES_ID}",
                transient=False,
            )
        observations = payload.get("observations")
        if not isinstance(observations, list):
            raise SourceFetchError(
                source_name=self.name,
                message=f"missing observations for {_SERIES_ID}",
                transient=False,
            )

        valid = _valid_observations(observations, target_date=window.target_date)
        if not valid:
            return []
        source_date, close = valid[0]
        if (window.target_date - source_date).days > _MAX_AGE_DAYS:
            return []
        previous_close = valid[1][1] if len(valid) > 1 else None
        item = _build_item(
            source_name=self.name,
            source_date=source_date,
            close=close,
            previous_close=previous_close,
        )
        return [item] if item is not None else []


def _valid_observations(
    observations: list[Any],
    *,
    target_date: date,
) -> list[tuple[date, float]]:
    valid: list[tuple[date, float]] = []
    for observation in observations:
        if not isinstance(observation, dict):
            continue
        raw_value = observation.get("value")
        if raw_value is None or raw_value == _PLACEHOLDER:
            continue
        try:
            source_date = date.fromisoformat(str(observation["date"]))
            close = float(raw_value)
        except (KeyError, TypeError, ValueError):
            continue
        if not math.isfinite(close):
            continue
        if source_date <= target_date:
            valid.append((source_date, close))
    valid.sort(key=lambda row: row[0], reverse=True)
    return valid


def _build_item(
    *,
    source_name: str,
    source_date: date,
    close: float,
    previous_close: float | None,
) -> NormalizedItem | None:
    raw_metadata = {
        "ticker": _TICKER,
        "series_id": _SERIES_ID,
        "close": format_float(close),
        "source_date": source_date.isoformat(),
        "provenance": "fred-h10",
    }
    if previous_close is not None:
        raw_metadata["previous_close"] = format_float(previous_close)
    fact = core_fact_for_ticker(_TICKER)
    if fact is not None:
        raw_metadata[core_fact_metadata_key(fact)] = format_float(close)

    summary = f"{_SERIES_ID}: {close:,.2f} KRW per USD"
    if previous_close is not None:
        summary += f"; prior={previous_close:,.2f}"
    try:
        return NormalizedItem(
            source_name=source_name,
            category="price",
            title=f"원/달러 환율 {close:,.2f}원",
            summary=summary[:SUMMARY_MAX_LEN],
            url=f"https://fred.stlouisfed.org/series/{_SERIES_ID}",
            published_at=datetime.combine(source_date, time(12, 0), tzinfo=_NY).astimezone(UTC),
            raw_metadata=raw_metadata,
        )
    except ValidationError:
        return None


__all__ = ["FredFxCloseAdapter"]

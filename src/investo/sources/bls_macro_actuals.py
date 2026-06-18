"""BLS official macro actuals adapter."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date
from typing import Any, ClassVar, Final

import httpx
from pydantic import ValidationError

from investo.models import Category, NormalizedItem
from investo.sources._config import SUMMARY_MAX_LEN
from investo.sources._parse import parse_json_response
from investo.sources._registry import register
from investo.sources._retry import retry_get
from investo.sources._window import FetchWindow
from investo.sources.protocol import SourceFetchError

_ENDPOINT_BASE: Final[str] = "https://api.bls.gov/publicAPI/v2/timeseries/data"
_SOURCE_URL_BASE: Final[str] = "https://www.bls.gov/data/"
_LOOKBACK_DAYS: Final[int] = 95


@dataclass(frozen=True)
class _BlsSeries:
    code: str
    series_id: str
    label: str
    unit: str


_SERIES: Final[tuple[_BlsSeries, ...]] = (
    _BlsSeries("CPI", "CUSR0000SA0", "Consumer Price Index", "index"),
    _BlsSeries("CORE_CPI", "CUSR0000SA0L1E", "Core Consumer Price Index", "index"),
    _BlsSeries("NFP", "CES0000000001", "Total nonfarm payroll employment", "thousands"),
    _BlsSeries("UNRATE", "LNS14000000", "Unemployment Rate", "percent"),
    _BlsSeries("AHE", "CES0500000003", "Average hourly earnings", "dollars"),
    _BlsSeries("LFPR", "LNS11300000", "Labor Force Participation Rate", "percent"),
    _BlsSeries("PPI", "WPSFD4", "Producer Price Index Final Demand", "index"),
    _BlsSeries("JOLTS", "JTS000000000000000JOL", "Job Openings", "level"),
)
_SERIES_BY_CODE: Final[dict[str, _BlsSeries]] = {series.code: series for series in _SERIES}


@register
class BlsMacroActualsAdapter:
    """Adapter for bounded BLS Public Data API macro actuals."""

    name: ClassVar[str] = "bls-macro-actuals"
    category: ClassVar[Category] = "macro"

    async def fetch(
        self,
        client: httpx.AsyncClient,
        window: FetchWindow,
    ) -> list[NormalizedItem]:
        items: list[NormalizedItem] = []
        for series in _SERIES:
            try:
                item = await self._fetch_one(client, series, window)
            except SourceFetchError:
                continue
            if item is not None:
                items.append(item)
        return items

    async def _fetch_one(
        self,
        client: httpx.AsyncClient,
        series: _BlsSeries,
        window: FetchWindow,
    ) -> NormalizedItem | None:
        response = await retry_get(
            client,
            f"{_ENDPOINT_BASE}/{series.series_id}",
            source_name=self.name,
            params={
                "startyear": str(window.target_date.year - 1),
                "endyear": str(window.target_date.year),
            },
        )
        payload = parse_json_response(
            response,
            source_name=self.name,
            message=f"malformed BLS JSON for {series.series_id}",
            append_exc=False,
        )
        data = _extract_series_data(payload, series.series_id, source_name=self.name)
        latest = _first_monthly_observation(data)
        if latest is None:
            return None
        prior = _first_monthly_observation(data, start_idx=latest[0] + 1)
        latest_obs = latest[1]
        try:
            release_period = _period_label(latest_obs)
        except (TypeError, ValueError):
            return None
        observed_at = window.start_utc.astimezone(UTC)
        if (window.target_date - _period_date(release_period)).days > _LOOKBACK_DAYS:
            return None

        actual_value = str(latest_obs.get("value", "")).strip()
        if not actual_value:
            return None
        prior_value = ""
        if prior is not None:
            prior_value = str(prior[1].get("value", "")).strip()

        summary = f"{series.label}: actual={actual_value} {series.unit}; period={release_period}"
        if prior_value:
            summary += f"; prior={prior_value}"
        if len(summary) > SUMMARY_MAX_LEN:
            summary = summary[:SUMMARY_MAX_LEN]

        raw_metadata: dict[str, str] = {
            "series_id": series.series_id,
            "macro_event_key": f"us:{series.code}:period={release_period}",
            "macro_event_label": series.label,
            "macro_event_status": "actual",
            "macro_priority": "P1",
            "release_period": release_period,
            "macro_release_period": release_period,
            "actual_value": actual_value,
            "macro_actual": actual_value,
            "value": actual_value,
            "unit": series.unit,
            "source_url": _SOURCE_URL_BASE,
            "observed_at": observed_at.isoformat(),
            "official_source": "true",
        }
        if prior_value:
            raw_metadata["prior_value"] = prior_value
            raw_metadata["macro_prior"] = prior_value
            raw_metadata["previous_value"] = prior_value

        try:
            return NormalizedItem(
                source_name=self.name,
                category=self.category,
                title=f"{series.label} actual: {actual_value} ({release_period})",
                summary=summary,
                url=_SOURCE_URL_BASE,
                published_at=observed_at,
                raw_metadata=raw_metadata,
            )
        except ValidationError:
            return None


def _extract_series_data(payload: Any, series_id: str, *, source_name: str) -> list[Any]:
    if not isinstance(payload, dict):
        raise SourceFetchError(
            source_name=source_name,
            message="non-object BLS response",
            transient=False,
        )
    if payload.get("status") not in {None, "REQUEST_SUCCEEDED"}:
        raise SourceFetchError(
            source_name=source_name,
            message="BLS request failed",
            transient=False,
        )
    results = payload.get("Results")
    series_list = results.get("series") if isinstance(results, dict) else None
    if not isinstance(series_list, list):
        raise SourceFetchError(
            source_name=source_name,
            message="missing BLS series list",
            transient=False,
        )
    for entry in series_list:
        if isinstance(entry, dict) and entry.get("seriesID") == series_id:
            data = entry.get("data")
            return data if isinstance(data, list) else []
    return []


def _first_monthly_observation(
    data: list[Any],
    *,
    start_idx: int = 0,
) -> tuple[int, dict[str, Any]] | None:
    for idx in range(start_idx, len(data)):
        row = data[idx]
        if not isinstance(row, dict):
            continue
        period = str(row.get("period", ""))
        value = str(row.get("value", "")).strip()
        if period.startswith("M") and period != "M13" and value:
            return idx, row
    return None


def _period_label(row: dict[str, Any]) -> str:
    year = int(str(row.get("year")))
    month = int(str(row.get("period"))[1:])
    return f"{year:04d}-{month:02d}"


def _period_date(period: str) -> date:
    return date.fromisoformat(f"{period}-01")


__all__ = ["BlsMacroActualsAdapter"]

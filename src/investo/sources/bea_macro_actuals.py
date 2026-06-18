"""BEA official macro actuals adapter."""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import UTC
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

_ENV_KEY: Final[str] = "BEA_API_KEY"
_ENDPOINT: Final[str] = "https://apps.bea.gov/api/data"
_SOURCE_URL: Final[str] = "https://www.bea.gov/data"


@dataclass(frozen=True)
class _BeaSeries:
    code: str
    table_name: str
    line_number: str
    frequency: str
    label: str
    unit: str


_SERIES: Final[tuple[_BeaSeries, ...]] = (
    _BeaSeries("GDP", "T10101", "1", "Q", "Gross Domestic Product", "percent change"),
    _BeaSeries("PCE", "T20804", "2", "M", "Personal Consumption Expenditures", "percent change"),
    _BeaSeries("CORE_PCE", "T20804", "42", "M", "Core PCE Price Index", "percent change"),
)


@register
class BeaMacroActualsAdapter:
    """Adapter for bounded BEA NIPA actuals."""

    name: ClassVar[str] = "bea-macro-actuals"
    category: ClassVar[Category] = "macro"

    async def fetch(
        self,
        client: httpx.AsyncClient,
        window: FetchWindow,
    ) -> list[NormalizedItem]:
        api_key = os.environ.get(_ENV_KEY, "")
        if not api_key:
            raise SourceFetchError(
                source_name=self.name,
                message=f"{_ENV_KEY} not set; {self.name} adapter will not run",
                transient=False,
            )
        items: list[NormalizedItem] = []
        for series in _SERIES:
            try:
                item = await self._fetch_one(client, series, api_key, window)
            except SourceFetchError:
                continue
            if item is not None:
                items.append(item)
        return items

    async def _fetch_one(
        self,
        client: httpx.AsyncClient,
        series: _BeaSeries,
        api_key: str,
        window: FetchWindow,
    ) -> NormalizedItem | None:
        response = await retry_get(
            client,
            _ENDPOINT,
            source_name=self.name,
            params={
                "UserID": api_key,
                "method": "GetData",
                "datasetname": "NIPA",
                "TableName": series.table_name,
                "LineNumber": series.line_number,
                "Frequency": series.frequency,
                "Year": str(window.target_date.year),
                "ResultFormat": "JSON",
            },
        )
        payload = parse_json_response(
            response,
            source_name=self.name,
            message=f"malformed BEA JSON for {series.code}",
            append_exc=False,
        )
        rows = _extract_data_rows(payload, source_name=self.name)
        latest = _first_matching_row(rows, series)
        if latest is None:
            return None
        prior = _first_matching_row(rows, series, start_idx=latest[0] + 1)
        latest_row = latest[1]
        actual_value = _clean_value(latest_row.get("DataValue"))
        if not actual_value:
            return None
        prior_value = _clean_value(prior[1].get("DataValue")) if prior is not None else ""
        release_period = str(latest_row.get("TimePeriod") or "").strip()
        if not release_period:
            return None
        canonical_period = _canonical_period(release_period)
        observed_at = window.start_utc.astimezone(UTC)

        summary = f"{series.label}: actual={actual_value} {series.unit}; period={release_period}"
        if prior_value:
            summary += f"; prior={prior_value}"
        if len(summary) > SUMMARY_MAX_LEN:
            summary = summary[:SUMMARY_MAX_LEN]

        raw_metadata: dict[str, str] = {
            "table_name": series.table_name,
            "line_number": series.line_number,
            "macro_event_key": f"us:{series.code}:period={canonical_period}",
            "macro_event_label": series.label,
            "macro_event_status": "actual",
            "macro_priority": "P1",
            "release_period": release_period,
            "macro_release_period": release_period,
            "actual_value": actual_value,
            "macro_actual": actual_value,
            "value": actual_value,
            "unit": series.unit,
            "source_url": _SOURCE_URL,
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
                url=_SOURCE_URL,
                published_at=observed_at,
                raw_metadata=raw_metadata,
            )
        except ValidationError:
            return None


def _extract_data_rows(payload: Any, *, source_name: str) -> list[Any]:
    if not isinstance(payload, dict):
        raise SourceFetchError(
            source_name=source_name,
            message="non-object BEA response",
            transient=False,
        )
    beaapi = payload.get("BEAAPI")
    results = beaapi.get("Results") if isinstance(beaapi, dict) else None
    if not isinstance(results, dict):
        raise SourceFetchError(
            source_name=source_name,
            message="missing BEA results",
            transient=False,
        )
    if "Error" in results:
        raise SourceFetchError(
            source_name=source_name,
            message="BEA request failed",
            transient=False,
        )
    data = results.get("Data")
    return data if isinstance(data, list) else []


def _first_matching_row(
    rows: list[Any],
    series: _BeaSeries,
    *,
    start_idx: int = 0,
) -> tuple[int, dict[str, Any]] | None:
    for idx in range(start_idx, len(rows)):
        row = rows[idx]
        if not isinstance(row, dict):
            continue
        if str(row.get("LineNumber") or "").strip() != series.line_number:
            continue
        if not _clean_value(row.get("DataValue")):
            continue
        return idx, row
    return None


def _clean_value(value: Any) -> str:
    return str(value or "").strip().replace(",", "")


def _canonical_period(value: str) -> str:
    if len(value) == 7 and value[4] == "M":
        return f"{value[:4]}-{value[5:]}"
    return value


__all__ = ["BeaMacroActualsAdapter"]

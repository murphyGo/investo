"""BEA official macro actuals adapter."""

from __future__ import annotations

import asyncio
import logging
import os
import re
from dataclasses import dataclass, replace
from datetime import UTC
from decimal import Decimal, InvalidOperation
from typing import Any, ClassVar, Final

import httpx
from pydantic import ValidationError

from investo.models import Category, NormalizedItem
from investo.sources._config import SUMMARY_MAX_LEN
from investo.sources._parse import parse_json_response
from investo.sources._registry import register
from investo.sources._retry import DEFAULT_CONFIG, retry_get
from investo.sources._window import FetchWindow
from investo.sources.protocol import SourceFetchError

_ENV_KEY: Final[str] = "BEA_API_KEY"
_ENDPOINT: Final[str] = "https://apps.bea.gov/api/data"
_SOURCE_URL: Final[str] = "https://www.bea.gov/data"
_ADAPTER_BUDGET_S: Final[float] = 60.0
_logger = logging.getLogger(__name__)


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
        succeeded = 0
        failures: list[SourceFetchError] = []
        timed_out = False
        deadline = asyncio.get_running_loop().time() + _ADAPTER_BUDGET_S
        timeout = asyncio.timeout(_ADAPTER_BUDGET_S)
        try:
            async with timeout:
                for series in _SERIES:
                    remaining = deadline - asyncio.get_running_loop().time()
                    if remaining <= 0:
                        timed_out = True
                        break
                    try:
                        item = await self._fetch_one(
                            client, series, api_key, window, remaining_budget_s=remaining
                        )
                    except SourceFetchError as error:
                        failures.append(error)
                        continue
                    succeeded += 1
                    if item is not None:
                        items.append(item)
        except TimeoutError:
            if not timeout.expired():
                raise
            timed_out = True
        _logger.info(
            "[bea-macro-actuals] completed_series=%d failed_series=%d "
            "terminal_errors=%d deadline_exhausted=%s emitted_items=%d",
            succeeded,
            len(failures),
            sum(not error.transient for error in failures),
            timed_out,
            len(items),
        )
        if succeeded == 0 and (failures or timed_out):
            raise SourceFetchError(
                source_name=self.name,
                message="BEA collection failed without a completed successful response",
                transient=timed_out or any(error.transient for error in failures),
            )
        return items

    async def _fetch_one(
        self,
        client: httpx.AsyncClient,
        series: _BeaSeries,
        api_key: str,
        window: FetchWindow,
        *,
        remaining_budget_s: float = _ADAPTER_BUDGET_S,
    ) -> NormalizedItem | None:
        response = await retry_get(
            client,
            _ENDPOINT,
            source_name=self.name,
            config=replace(
                DEFAULT_CONFIG, total_budget_s=min(_ADAPTER_BUDGET_S, remaining_budget_s)
            ),
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
        matching = [
            row
            for row in rows
            if isinstance(row, dict)
            and str(row.get("LineNumber", "")).strip() == series.line_number
        ]
        _logger.info(
            "[bea-macro-actuals] series=%s rows=%d matching_rows=%d "
            "invalid_values=%d invalid_periods=%d",
            series.code,
            len(rows),
            len(matching),
            sum(not _clean_value(row.get("DataValue")) for row in matching),
            sum(not _valid_period(row.get("TimePeriod"), series.frequency) for row in matching),
        )
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
    if not isinstance(data, list):
        raise SourceFetchError(
            source_name=source_name, message="invalid BEA data schema", transient=False
        )
    return data


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
        if not _clean_value(row.get("DataValue")) or not _valid_period(
            row.get("TimePeriod"), series.frequency
        ):
            continue
        return idx, row
    return None


def _clean_value(value: Any) -> str:
    if value is None or isinstance(value, bool):
        return ""
    text = str(value).strip().replace(",", "")
    try:
        numeric = Decimal(text)
    except InvalidOperation:
        return ""
    return text if numeric.is_finite() else ""


def _valid_period(value: Any, frequency: str) -> bool:
    if not isinstance(value, str):
        return False
    pattern = r"[0-9]{4}Q[1-4]" if frequency == "Q" else r"[0-9]{4}M(?:0[1-9]|1[0-2])"
    return re.fullmatch(pattern, value.strip()) is not None


def _canonical_period(value: str) -> str:
    if len(value) == 7 and value[4] == "M":
        return f"{value[:4]}-{value[5:]}"
    return value


__all__ = ["BeaMacroActualsAdapter"]

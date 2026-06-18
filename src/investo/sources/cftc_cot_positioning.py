"""CFTC COT/TFF regulated futures positioning adapter."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from typing import Any, ClassVar, Literal
from zoneinfo import ZoneInfo

import httpx
from pydantic import ValidationError

from investo.models import Category, NormalizedItem
from investo.sources._config import format_float, format_int
from investo.sources._parse import parse_json_response
from investo.sources._registry import register
from investo.sources._retry import RetryConfig, retry_get
from investo.sources._window import FetchWindow
from investo.sources.protocol import SourceFetchError

_NY = ZoneInfo("America/New_York")
_RELEASE_TIME = time(15, 30)
_RETRY_CONFIG = RetryConfig(timeout_s=12.0, retries=1, backoffs=(1.0,), total_budget_s=25.0)
_CFTC_PAGE_URL = "https://www.cftc.gov/MarketReports/CommitmentsofTraders/index.htm"
_TFF_ENDPOINT = "https://publicreporting.cftc.gov/resource/gpe5-46if.json"
_DISAGG_ENDPOINT = "https://publicreporting.cftc.gov/resource/72hh-3qpy.json"
_MAX_ROWS = "50"

_ReportKind = Literal["tff", "disaggregated"]


@dataclass(frozen=True, slots=True)
class _ContractConfig:
    report_kind: _ReportKind
    code: str
    label: str
    group: str
    primary_category: str


_CONTRACTS: tuple[_ContractConfig, ...] = (
    _ContractConfig("tff", "13874A", "E-mini S&P 500", "equity_index", "leveraged_money"),
    _ContractConfig("tff", "209742", "Nasdaq-100 mini", "equity_index", "leveraged_money"),
    _ContractConfig("tff", "1170E1", "VIX futures", "volatility", "leveraged_money"),
    _ContractConfig("tff", "043602", "10Y Treasury note", "rates", "leveraged_money"),
    _ContractConfig("tff", "098662", "U.S. Dollar Index", "fx", "leveraged_money"),
    _ContractConfig("tff", "133741", "Bitcoin CME", "crypto", "leveraged_money"),
    _ContractConfig("tff", "146021", "Ether CME", "crypto", "leveraged_money"),
    _ContractConfig("disaggregated", "067651", "WTI crude oil", "energy", "managed_money"),
    _ContractConfig("disaggregated", "088691", "Gold", "metals", "managed_money"),
)


@register
class CftcCotPositioningAdapter:
    """Adapter for official CFTC COT/TFF weekly positioning rows."""

    name: ClassVar[str] = "cftc-cot-positioning"
    category: ClassVar[Category] = "macro"

    async def fetch(
        self,
        client: httpx.AsyncClient,
        window: FetchWindow,
    ) -> list[NormalizedItem]:
        items: list[NormalizedItem] = []
        for report_kind, endpoint in (
            ("tff", _TFF_ENDPOINT),
            ("disaggregated", _DISAGG_ENDPOINT),
        ):
            configs = tuple(config for config in _CONTRACTS if config.report_kind == report_kind)
            if not configs:
                continue
            rows = await self._fetch_report_rows(
                client,
                endpoint=endpoint,
                configs=configs,
                window=window,
            )
            items.extend(
                _rows_to_items(rows, configs=configs, source_name=self.name, window=window)
            )
        return items

    async def _fetch_report_rows(
        self,
        client: httpx.AsyncClient,
        *,
        endpoint: str,
        configs: tuple[_ContractConfig, ...],
        window: FetchWindow,
    ) -> list[dict[str, Any]]:
        codes = ", ".join(f"'{config.code}'" for config in configs)
        response = await retry_get(
            client,
            endpoint,
            source_name=self.name,
            params={
                "$where": (
                    f"cftc_contract_market_code in({codes}) "
                    f"and report_date_as_yyyy_mm_dd <= '{window.target_date.isoformat()}T00:00:00'"
                ),
                "$order": "report_date_as_yyyy_mm_dd DESC",
                "$limit": _MAX_ROWS,
            },
            config=_RETRY_CONFIG,
        )
        payload = parse_json_response(
            response,
            source_name=self.name,
            message="malformed CFTC JSON",
        )
        if not isinstance(payload, list):
            raise SourceFetchError(
                source_name=self.name,
                message="non-list CFTC response",
                transient=False,
            )
        return [row for row in payload if isinstance(row, dict)]


def _rows_to_items(
    rows: list[dict[str, Any]],
    *,
    configs: tuple[_ContractConfig, ...],
    source_name: str,
    window: FetchWindow,
) -> list[NormalizedItem]:
    by_code: dict[str, dict[str, Any]] = {}
    for row in rows:
        code = str(row.get("cftc_contract_market_code") or "").strip()
        if code in by_code:
            continue
        by_code[code] = row
    items: list[NormalizedItem] = []
    for config in configs:
        candidate = by_code.get(config.code)
        if candidate is None:
            continue
        try:
            items.append(
                _row_to_item(candidate, config=config, source_name=source_name, window=window)
            )
        except (KeyError, TypeError, ValueError, ValidationError):
            continue
    return items


def _row_to_item(
    row: dict[str, Any],
    *,
    config: _ContractConfig,
    source_name: str,
    window: FetchWindow,
) -> NormalizedItem:
    as_of_date = _parse_cftc_date(str(row["report_date_as_yyyy_mm_dd"]))
    release_date = _estimated_release_date(as_of_date)
    published_at = datetime.combine(release_date, _RELEASE_TIME, tzinfo=_NY).astimezone(UTC)
    if published_at >= window.end_utc:
        raise ValueError("CFTC row has not been released by window end")
    open_interest = _parse_int(row.get("open_interest_all"))
    long_value, short_value, spread_value = _category_positions(row, config)
    net = long_value - short_value
    net_pct_oi = (net / open_interest) * 100 if open_interest else 0.0
    title = f"CFTC {config.label} {config.primary_category} net {net:+d} contracts"
    summary = (
        f"{config.label}: {config.primary_category} long {long_value:,}, short {short_value:,}, "
        f"net {net:+,} ({net_pct_oi:+.1f}% of OI); weekly CFTC report, not intraday flow"
    )
    return NormalizedItem(
        source_name=source_name,
        category="macro",
        title=title,
        summary=summary,
        url=_CFTC_PAGE_URL,
        published_at=published_at,
        raw_metadata={
            "report_kind": config.report_kind,
            "contract_code": config.code,
            "contract_label": config.label,
            "contract_group": config.group,
            "market_and_exchange": str(row.get("market_and_exchange_names") or "").strip(),
            "trader_category": config.primary_category,
            "as_of_date": as_of_date.isoformat(),
            "report_date": as_of_date.isoformat(),
            "release_date": release_date.isoformat(),
            "long_contracts": format_int(long_value),
            "short_contracts": format_int(short_value),
            "spread_contracts": format_int(spread_value),
            "net_contracts": format_int(net),
            "net_pct_open_interest": format_float(net_pct_oi, precision=2),
            "open_interest": format_int(open_interest),
            "units": str(row.get("contract_units") or "contracts").strip(),
            "source_lag_days": str((window.target_date - as_of_date).days),
            "release_lag_days": str((window.target_date - release_date).days),
            "data_frequency": "weekly",
            "delayed_data_label": "weekly CFTC report, Tuesday positions released Friday",
        },
    )


def _category_positions(row: dict[str, Any], config: _ContractConfig) -> tuple[int, int, int]:
    if config.report_kind == "tff":
        return (
            _parse_int(row.get("lev_money_positions_long")),
            _parse_int(row.get("lev_money_positions_short")),
            _parse_int(row.get("lev_money_positions_spread", 0)),
        )
    return (
        _parse_int(row.get("m_money_positions_long_all")),
        _parse_int(row.get("m_money_positions_short_all")),
        _parse_int(row.get("m_money_positions_spread", 0)),
    )


def _parse_cftc_date(text: str) -> date:
    return datetime.fromisoformat(text.replace("Z", "+00:00")).date()


def _parse_int(value: Any) -> int:
    text = str(value or "").strip()
    if not text:
        raise ValueError("missing integer")
    return int(float(text))


def _estimated_release_date(as_of_date: date) -> date:
    release = as_of_date + timedelta(days=3)
    while release.weekday() >= 5 or _is_us_federal_holiday(release):
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

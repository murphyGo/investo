"""Official FSC index V2 daily prices with bounded, payload-free diagnostics.

The source identity, basis timestamp and public containment contracts are
unchanged. Diagnostic reports contain only closed reasons, dates and counts.
"""

from __future__ import annotations

import asyncio
import math
import os
import re
from collections import Counter
from dataclasses import dataclass, replace
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal, DecimalException
from typing import Any, ClassVar, Literal
from zoneinfo import ZoneInfo

import httpx
from defusedxml import ElementTree
from defusedxml.common import DefusedXmlException
from pydantic import ValidationError

from investo.models import Category, NormalizedItem
from investo.sources._config import SUMMARY_MAX_LEN, format_float, format_int, parse_symbol_list
from investo.sources._parse import required_str
from investo.sources._registry import register
from investo.sources._retry import RetryConfig, retry_get
from investo.sources._window import FetchWindow
from investo.sources.protocol import SourceFetchError

_KST = ZoneInfo("Asia/Seoul")
_ENV_INDEX_NAMES = "INVESTO_KRX_INDEX_NAMES"
_ENV_SERVICE_KEY = "INVESTO_KRX_SERVICE_KEY"
_ENV_FALLBACK_SERVICE_KEY = "INVESTO_DATA_GO_KR_SERVICE_KEY"
_LOOKBACK_DAYS = 7
_CLOSE_TIME_KST = time(16, 0, tzinfo=_KST)
_DATA_PAGE_URL = "https://www.data.go.kr/data/15094807/openapi.do"
_RETRY_CONFIG = RetryConfig(timeout_s=20.0, retries=1, backoffs=(1.0,), total_budget_s=45.0)
_TOTAL_BUDGET_S = 60.0
_PAGE_SIZE = 100
_MAX_PAGES = 2
_RESULT_CODES = frozenset({"00", "01", "04", "05", "10", "12", "20", "22", "23", "29", "30", "31"})
Reason = Literal[
    "usable",
    "provider_no_rows",
    "name_mismatch",
    "all_filtered",
    "page_incomplete",
    "schema_error",
    "api_error",
    "transport_error",
    "deadline",
    "missing_key",
]


@dataclass(frozen=True, slots=True)
class IndexDiagnostic:
    requested_date: str
    page: int
    reason: Reason
    http_status: int | None = None
    result_code: str | None = None
    total_count: int | None = None
    returned_rows: int = 0
    wanted_match_count: int = 0
    valid_row_count: int = 0
    selected_date: str | None = None
    exclusions: tuple[tuple[str, int], ...] = ()


@dataclass(frozen=True, slots=True)
class IndexFetchReport:
    items: tuple[NormalizedItem, ...]
    diagnostics: tuple[IndexDiagnostic, ...]


class IndexDiagnosticError(SourceFetchError):
    """Fixed error text and sanitized receipt; never carries provider text."""

    def __init__(
        self, reason: Reason, diagnostics: tuple[IndexDiagnostic, ...], *, transient: bool = False
    ) -> None:
        super().__init__(
            source_name="fsc-krx-index-price",
            message=f"index source: {reason}; check INVESTO_KRX_SERVICE_KEY configuration",
            transient=transient,
        )
        self.diagnostics = diagnostics


@dataclass(frozen=True, slots=True)
class _IndexPage:
    rows: tuple[dict[str, Any], ...]
    total_count: int
    result_code: str
    complete: bool


@register
class FscKrxIndexPriceAdapter:
    """Official V2 endpoint documented in the current data.go.kr guide."""

    name: ClassVar[str] = "fsc-krx-index-price"
    category: ClassVar[Category] = "price"
    _DEFAULT_INDEX_NAMES: ClassVar[tuple[str, ...]] = ("코스피", "코스닥", "코스피 200")
    _ENDPOINT: ClassVar[str] = (
        "https://apis.data.go.kr/1160100/GetMarketIndexInfoService_V2/getStockMarketIndex_V2"
    )

    async def fetch(self, client: httpx.AsyncClient, window: FetchWindow) -> list[NormalizedItem]:
        return list((await self.fetch_with_diagnostics(client, window)).items)

    async def fetch_with_diagnostics(
        self, client: httpx.AsyncClient, window: FetchWindow
    ) -> IndexFetchReport:
        service_key = _read_service_key()
        receipts: list[IndexDiagnostic] = []
        if not service_key:
            raise IndexDiagnosticError(
                "missing_key", (IndexDiagnostic(window.target_date.isoformat(), 0, "missing_key"),)
            )
        index_names = parse_symbol_list(_ENV_INDEX_NAMES, self._DEFAULT_INDEX_NAMES)
        wanted = {name.strip() for name in index_names if name.strip()}
        loop = asyncio.get_running_loop()
        expires = loop.time() + _TOTAL_BUDGET_S
        timeout = asyncio.timeout(_TOTAL_BUDGET_S)
        selected: dict[str, NormalizedItem] = {}
        requested = window.target_date
        page_no = 0
        try:
            async with timeout:
                for requested in _candidate_dates(window.target_date):
                    selected = {}
                    expected_total: int | None = None
                    for page_no in range(1, _MAX_PAGES + 1):
                        remaining = max(0.001, expires - loop.time())
                        config = replace(
                            _RETRY_CONFIG,
                            timeout_s=min(_RETRY_CONFIG.timeout_s, remaining),
                            total_budget_s=min(_RETRY_CONFIG.total_budget_s, remaining),
                        )
                        try:
                            response = await retry_get(
                                client,
                                self._ENDPOINT,
                                source_name=self.name,
                                params={
                                    "serviceKey": service_key,
                                    "resultType": "json",
                                    "basDt": requested.strftime("%Y%m%d"),
                                    "pageNo": str(page_no),
                                    "numOfRows": str(_PAGE_SIZE),
                                },
                                config=config,
                            )
                        except SourceFetchError as exc:
                            # Shared retry errors can contain URLs; suppress their text/cause.
                            match = re.search(
                                r"failed: status ([1-5][0-9]{2}) "
                                r"(?:\(terminal\)|after [0-9]+ attempts)",
                                str(exc),
                            )
                            status = int(match[1]) if match else None
                            receipts.append(
                                IndexDiagnostic(
                                    requested.isoformat(),
                                    page_no,
                                    "transport_error",
                                    http_status=status,
                                )
                            )
                            if selected:
                                return _report(selected, index_names, receipts)
                            raise IndexDiagnosticError(
                                "transport_error", tuple(receipts), transient=exc.transient
                            ) from None
                        try:
                            payload = response.json()
                        except (ValueError, RecursionError):
                            code = _xml_error_code(response.content)
                            reason: Reason = "api_error" if code is not None else "schema_error"
                            receipts.append(
                                IndexDiagnostic(
                                    requested.isoformat(),
                                    page_no,
                                    reason,
                                    response.status_code,
                                    code,
                                )
                            )
                            if selected:
                                return _report(selected, index_names, receipts)
                            raise IndexDiagnosticError(reason, tuple(receipts)) from None
                        try:
                            page = _extract_page(
                                payload,
                                source_name=self.name,
                                expected_page=page_no,
                                expected_total=expected_total,
                            )
                        except IndexDiagnosticError as exc:
                            reason = exc.diagnostics[-1].reason
                            receipts.append(
                                replace(
                                    exc.diagnostics[-1],
                                    requested_date=requested.isoformat(),
                                    page=page_no,
                                    http_status=response.status_code,
                                )
                            )
                            if selected:
                                return _report(selected, index_names, receipts)
                            raise IndexDiagnosticError(reason, tuple(receipts)) from None
                        if expected_total is None:
                            expected_total = page.total_count
                        matched = 0
                        valid = 0
                        excluded: Counter[str] = Counter()
                        for row in page.rows:
                            index_name = str(row.get("idxNm") or "").strip()
                            if index_name not in wanted:
                                excluded["name_mismatch"] += 1
                                continue
                            matched += 1
                            try:
                                basis = _parse_bas_dt(required_str(row, "basDt"))
                                if (
                                    basis != requested
                                    or not 0 <= (window.target_date - basis).days <= _LOOKBACK_DAYS
                                ):
                                    excluded["basis_date"] += 1
                                    continue
                                item = _row_to_item(
                                    row, source_name=self.name, target_date=window.target_date
                                )
                            except (TypeError, ValueError, ValidationError, OverflowError):
                                excluded["invalid_row"] += 1
                                continue
                            valid += 1
                            if index_name in selected:
                                excluded["duplicate"] += 1
                            else:
                                selected[index_name] = item
                        reason = (
                            "usable"
                            if selected
                            else (
                                "provider_no_rows"
                                if page.total_count == 0
                                else "all_filtered"
                                if matched
                                else "name_mismatch"
                            )
                        )
                        more = page.total_count > page_no * _PAGE_SIZE
                        if not page.complete or (more and page_no == _MAX_PAGES):
                            reason = "page_incomplete"
                        receipts.append(
                            IndexDiagnostic(
                                requested.isoformat(),
                                page_no,
                                reason,
                                response.status_code,
                                page.result_code,
                                page.total_count,
                                len(page.rows),
                                matched,
                                valid,
                                requested.isoformat() if selected else None,
                                tuple(sorted(excluded.items())),
                            )
                        )
                        if reason == "page_incomplete" and not selected:
                            raise IndexDiagnosticError("page_incomplete", tuple(receipts))
                        if not page.complete:
                            return _report(selected, index_names, receipts)
                        if wanted.issubset(selected) or not more:
                            break
                    if selected:
                        return _report(selected, index_names, receipts)
        except TimeoutError:
            if not timeout.expired():
                raise
            receipts.append(IndexDiagnostic(requested.isoformat(), page_no, "deadline"))
            if selected:
                return _report(selected, index_names, receipts)
            raise IndexDiagnosticError("deadline", tuple(receipts), transient=True) from None
        return IndexFetchReport((), tuple(receipts))

    def _rows_to_items(
        self,
        rows: list[dict[str, Any]],
        *,
        wanted: set[str],
        index_order: tuple[str, ...],
        target_date: date,
    ) -> list[NormalizedItem]:
        parsed: dict[str, NormalizedItem] = {}
        for row in rows:
            index_name = str(row.get("idxNm") or "").strip()
            if not index_name or (wanted and index_name not in wanted):
                continue
            try:
                parsed.setdefault(
                    index_name, _row_to_item(row, source_name=self.name, target_date=target_date)
                )
            except (TypeError, ValueError, ValidationError, OverflowError):
                continue
        return list(_report(parsed, index_order, []).items)


def _report(
    selected: dict[str, NormalizedItem], order: tuple[str, ...], receipts: list[IndexDiagnostic]
) -> IndexFetchReport:
    positions = {name: idx for idx, name in enumerate(order)}
    items = tuple(
        selected[name]
        for name in sorted(selected, key=lambda name: (positions.get(name, len(order)), name))
    )
    return IndexFetchReport(items, tuple(receipts))


def _closed_code(value: Any) -> str:
    code = str(value).strip()
    return code if code in _RESULT_CODES else "unknown"


def _xml_error_code(content: bytes) -> str | None:
    try:
        root = ElementTree.fromstring(content)
    except (ElementTree.ParseError, DefusedXmlException, ValueError):
        return None
    for element in root.iter():
        if element.tag.split("}")[-1] in {"returnReasonCode", "resultCode"}:
            return _closed_code(element.text)
    return None


def _extract_page(
    payload: Any, *, source_name: str, expected_page: int = 1, expected_total: int | None = None
) -> _IndexPage:
    del source_name  # fixed-source diagnostics cannot accept an arbitrary log identity
    response = payload.get("response") if isinstance(payload, dict) else None
    header = response.get("header") if isinstance(response, dict) else None
    if not isinstance(response, dict) or not isinstance(header, dict):
        raise IndexDiagnosticError("schema_error", (IndexDiagnostic("", 0, "schema_error"),))
    code = _closed_code(header.get("resultCode"))
    if code != "00":
        raise IndexDiagnosticError(
            "api_error", (IndexDiagnostic("", 0, "api_error", result_code=code),)
        )
    body = response.get("body")
    if not isinstance(body, dict):
        raise IndexDiagnosticError(
            "schema_error", (IndexDiagnostic("", 0, "schema_error", result_code=code),)
        )
    try:
        if (
            _integer(body.get("pageNo")) != expected_page
            or _integer(body.get("numOfRows")) != _PAGE_SIZE
        ):
            raise ValueError("unexpected pagination")
        total = _integer(body.get("totalCount"))
        if not 0 <= total <= 10_000_000:
            raise ValueError("invalid count")
        items = body.get("items")
        raw: Any = items.get("item", []) if isinstance(items, dict) else items
        if raw is None or raw == "":
            raw = []
        if isinstance(raw, dict):
            raw = [raw]
        if (
            not isinstance(raw, list)
            or len(raw) > _PAGE_SIZE
            or any(not isinstance(row, dict) for row in raw)
        ):
            raise ValueError("invalid rows")
        if (total == 0 and raw) or (total > 0 and not raw):
            raise ValueError("inconsistent rows")
    except (TypeError, ValueError, OverflowError):
        raise IndexDiagnosticError(
            "schema_error", (IndexDiagnostic("", 0, "schema_error", result_code=code),)
        ) from None
    expected_rows = min(_PAGE_SIZE, max(0, total - (expected_page - 1) * _PAGE_SIZE))
    complete = len(raw) == expected_rows and (expected_total is None or total == expected_total)
    return _IndexPage(tuple(raw), total, code, complete)


def _extract_rows(payload: Any, *, source_name: str) -> list[dict[str, Any]]:
    return list(_extract_page(payload, source_name=source_name).rows)


def _number(value: Any) -> float:
    if value is None or isinstance(value, bool):
        raise ValueError("missing number")
    result = float(str(value).strip().replace(",", ""))
    if not math.isfinite(result):
        raise ValueError("nonfinite number")
    return result


def _integer(value: Any) -> int:
    if value is None or isinstance(value, bool):
        raise ValueError("missing integer")
    try:
        result = Decimal(str(value).strip().replace(",", ""))
        if (
            not result.is_finite()
            or result.copy_abs() > Decimal("1e30")
            or result != result.to_integral_value()
        ):
            raise ValueError("invalid integer")
        return int(result)
    except DecimalException:
        raise ValueError("invalid integer") from None


def _read_service_key() -> str:
    return (
        os.environ.get(_ENV_SERVICE_KEY, "").strip()
        or os.environ.get(_ENV_FALLBACK_SERVICE_KEY, "").strip()
    )


def _candidate_dates(target_date: date) -> tuple[date, ...]:
    return tuple(target_date - timedelta(days=offset) for offset in range(_LOOKBACK_DAYS + 1))


def _row_to_item(row: dict[str, Any], *, source_name: str, target_date: date) -> NormalizedItem:
    index_name = required_str(row, "idxNm")
    bas_dt = _parse_bas_dt(required_str(row, "basDt"))
    if not 0 <= (target_date - bas_dt).days <= _LOOKBACK_DAYS:
        raise ValueError("basis date outside lookback")
    close = _number(row.get("clpr"))
    change = _number(row.get("vs"))
    pct_change = _number(row.get("fltRt"))
    open_ = _number(row.get("mkp"))
    high = _number(row.get("hipr"))
    low = _number(row.get("lopr"))
    volume = _integer(row.get("trqu"))
    trading_value = _integer(row.get("trPrc"))
    market_cap = _integer(row.get("lstgMrktTotAmt"))
    if min(close, open_, high, low) <= 0 or min(volume, trading_value, market_cap) < 0:
        raise ValueError("invalid price or quantity")
    if low > min(open_, close) or high < max(open_, close) or low > high:
        raise ValueError("invalid OHLC range")
    published_at = datetime.combine(bas_dt, _CLOSE_TIME_KST).astimezone(UTC)
    pct_prefix = "+" if pct_change > 0 else ""
    change_prefix = "+" if change > 0 else ""
    summary = (
        f"O:{open_:,.2f} H:{high:,.2f} L:{low:,.2f} C:{close:,.2f}; "
        f"거래량:{volume:,}; 거래대금:{trading_value:,}; 시총:{market_cap:,}"
    )
    if len(summary) > SUMMARY_MAX_LEN:
        summary = summary[: SUMMARY_MAX_LEN - 1].rstrip() + "…"
    title = (
        f"{index_name} {close:,.2f} ({pct_prefix}{pct_change:.2f}%, {change_prefix}{change:,.2f})"
    )
    return NormalizedItem(
        source_name=source_name,
        category="price",
        title=title,
        summary=summary,
        url=_DATA_PAGE_URL,
        published_at=published_at,
        raw_metadata={
            "index_name": index_name,
            "index_code": str(row.get("idxCsf") or ""),
            "bas_dt": bas_dt.isoformat(),
            "open": format_float(open_),
            "high": format_float(high),
            "low": format_float(low),
            "close": format_float(close),
            "change": format_float(change),
            "pct_change": format_float(pct_change),
            "volume": format_int(volume),
            "trading_value": format_int(trading_value),
            "market_cap": format_int(market_cap),
            "source_date_lag_days": format_int((target_date - bas_dt).days),
        },
    )


def _parse_bas_dt(value: str) -> date:
    return datetime.strptime(value, "%Y%m%d").date()

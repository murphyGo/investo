"""FSC/data.go.kr KRX stock daily price adapter."""

from __future__ import annotations

import asyncio
import json
import os
from datetime import UTC, date, datetime, time, timedelta
from typing import Any, ClassVar
from zoneinfo import ZoneInfo

import httpx
from pydantic import ValidationError

from investo.models import Category, NormalizedItem
from investo.sources._config import SUMMARY_MAX_LEN, format_float, format_int, parse_symbol_list
from investo.sources._registry import register
from investo.sources._retry import RetryConfig, retry_get
from investo.sources._window import FetchWindow
from investo.sources.protocol import SourceFetchError

_KST = ZoneInfo("Asia/Seoul")
_ENV_TICKERS = "INVESTO_KRX_STOCK_TICKERS"
_ENV_SERVICE_KEY = "INVESTO_KRX_SERVICE_KEY"
_ENV_FALLBACK_SERVICE_KEY = "INVESTO_DATA_GO_KR_SERVICE_KEY"
_LOOKBACK_DAYS = 7
_CLOSE_TIME_KST = time(16, 0, tzinfo=_KST)
_DATA_PAGE_URL = "https://www.data.go.kr/data/15094808/openapi.do"
_RETRY_CONFIG = RetryConfig(timeout_s=20.0, retries=1, backoffs=(1.0,), total_budget_s=45.0)


@register
class FscKrxStockPriceAdapter:
    """Adapter for ``금융위원회_주식시세정보`` public-data rows."""

    name: ClassVar[str] = "fsc-krx-stock-price"
    category: ClassVar[Category] = "price"

    _DEFAULT_TICKERS: ClassVar[tuple[str, ...]] = (
        "005930",
        "000660",
        "035420",
        "005380",
        "068270",
    )
    _ENDPOINT: ClassVar[str] = (
        "https://apis.data.go.kr/1160100/service/GetStockSecuritiesInfoService/getStockPriceInfo"
    )

    async def fetch(
        self,
        client: httpx.AsyncClient,
        window: FetchWindow,
    ) -> list[NormalizedItem]:
        service_key = _read_service_key()
        if not service_key:
            raise SourceFetchError(
                source_name=self.name,
                message=(
                    f"{_ENV_SERVICE_KEY} or {_ENV_FALLBACK_SERVICE_KEY} not set; "
                    f"{self.name} adapter will not run"
                ),
                transient=False,
            )

        tickers = parse_symbol_list(_ENV_TICKERS, self._DEFAULT_TICKERS)
        results = await asyncio.gather(
            *(
                self._fetch_ticker(client, service_key, ticker, window.target_date)
                for ticker in tickers
            ),
            return_exceptions=True,
        )
        items: list[NormalizedItem] = []
        failures: list[SourceFetchError] = []
        for result in results:
            if isinstance(result, NormalizedItem):
                items.append(result)
            elif isinstance(result, SourceFetchError):
                failures.append(result)
            elif isinstance(result, BaseException):
                raise result
        if not items and failures:
            raise failures[0]
        return items

    async def _fetch_ticker(
        self,
        client: httpx.AsyncClient,
        service_key: str,
        ticker: str,
        target_date: date,
    ) -> NormalizedItem | None:
        normalized_ticker = ticker.strip()
        if not normalized_ticker:
            return None
        for bas_dt in _candidate_dates(target_date):
            rows = await self._fetch_date(client, service_key, normalized_ticker, bas_dt)
            for row in rows:
                if str(row.get("srtnCd") or "").strip() != normalized_ticker:
                    continue
                try:
                    return _row_to_item(row, source_name=self.name, target_date=target_date)
                except (TypeError, ValueError, ValidationError):
                    return None
        return None

    async def _fetch_date(
        self,
        client: httpx.AsyncClient,
        service_key: str,
        ticker: str,
        bas_dt: date,
    ) -> list[dict[str, Any]]:
        response = await retry_get(
            client,
            self._ENDPOINT,
            source_name=self.name,
            params={
                "serviceKey": service_key,
                "resultType": "json",
                "basDt": bas_dt.strftime("%Y%m%d"),
                "likeSrtnCd": ticker,
                "pageNo": "1",
                "numOfRows": "10",
            },
            config=_RETRY_CONFIG,
        )
        try:
            payload = response.json()
        except json.JSONDecodeError as exc:
            raise SourceFetchError(
                source_name=self.name,
                message=f"malformed JSON response: {exc}",
                transient=False,
                cause=exc,
            ) from exc
        return _extract_rows(payload, source_name=self.name)


def _read_service_key() -> str:
    return (
        os.environ.get(_ENV_SERVICE_KEY, "").strip()
        or os.environ.get(_ENV_FALLBACK_SERVICE_KEY, "").strip()
    )


def _candidate_dates(target_date: date) -> tuple[date, ...]:
    return tuple(target_date - timedelta(days=offset) for offset in range(_LOOKBACK_DAYS + 1))


def _extract_rows(payload: Any, *, source_name: str) -> list[dict[str, Any]]:
    response = payload.get("response") if isinstance(payload, dict) else None
    header = response.get("header") if isinstance(response, dict) else None
    if isinstance(header, dict):
        result_code = str(header.get("resultCode") or "").strip()
        if result_code and result_code != "00":
            result_msg = str(header.get("resultMsg") or "data.go.kr error").strip()
            raise SourceFetchError(
                source_name=source_name,
                message=f"data.go.kr resultCode {result_code}: {result_msg}",
                transient=False,
            )
    body = response.get("body") if isinstance(response, dict) else None
    items = body.get("items") if isinstance(body, dict) else None
    raw_rows: Any = items.get("item", []) if isinstance(items, dict) else items
    if isinstance(raw_rows, dict):
        raw_rows = [raw_rows]
    if raw_rows in (None, ""):
        return []
    if not isinstance(raw_rows, list):
        raise SourceFetchError(
            source_name=source_name,
            message="unexpected data.go.kr items shape",
            transient=False,
        )
    return [row for row in raw_rows if isinstance(row, dict)]


def _row_to_item(row: dict[str, Any], *, source_name: str, target_date: date) -> NormalizedItem:
    ticker = _required_str(row, "srtnCd")
    item_name = _required_str(row, "itmsNm")
    market = _required_str(row, "mrktCtg")
    bas_dt = _parse_bas_dt(_required_str(row, "basDt"))
    close = _parse_float(row.get("clpr"))
    change = _parse_float(row.get("vs"))
    pct_change = _parse_float(row.get("fltRt"))
    open_ = _parse_float(row.get("mkp"))
    high = _parse_float(row.get("hipr"))
    low = _parse_float(row.get("lopr"))
    volume = _parse_int(row.get("trqu"))
    trading_value = _parse_int(row.get("trPrc"))
    listed_shares = _parse_int(row.get("lstgStCnt"))
    market_cap = _parse_int(row.get("mrktTotAmt"))
    published_at = datetime.combine(bas_dt, _CLOSE_TIME_KST).astimezone(UTC)
    pct_prefix = "+" if pct_change > 0 else ""
    change_prefix = "+" if change > 0 else ""
    summary = (
        f"O:{open_:,.0f} H:{high:,.0f} L:{low:,.0f} C:{close:,.0f}; "
        f"거래량:{volume:,}; 거래대금:{trading_value:,}; 시총:{market_cap:,}"
    )
    if len(summary) > SUMMARY_MAX_LEN:
        summary = summary[: SUMMARY_MAX_LEN - 1].rstrip() + "…"
    title = (
        f"{item_name}[{ticker}] {close:,.0f}원 "
        f"({pct_prefix}{pct_change:.2f}%, {change_prefix}{change:,.0f})"
    )
    return NormalizedItem(
        source_name=source_name,
        category="price",
        title=title,
        summary=summary,
        url=_DATA_PAGE_URL,
        published_at=published_at,
        raw_metadata={
            "ticker": ticker,
            "isin": str(row.get("isinCd") or ""),
            "name": item_name,
            "market": market,
            "bas_dt": bas_dt.isoformat(),
            "open": format_float(open_),
            "high": format_float(high),
            "low": format_float(low),
            "close": format_float(close),
            "change": format_float(change),
            "pct_change": format_float(pct_change),
            "volume": format_int(volume),
            "trading_value": format_int(trading_value),
            "listed_shares": format_int(listed_shares),
            "market_cap": format_int(market_cap),
            "source_date_lag_days": format_int((target_date - bas_dt).days),
        },
    )


def _required_str(row: dict[str, Any], key: str) -> str:
    value = str(row.get(key) or "").strip()
    if not value:
        raise ValueError(f"missing {key}")
    return value


def _parse_bas_dt(value: str) -> date:
    return datetime.strptime(value, "%Y%m%d").date()


def _parse_float(value: Any) -> float:
    text = str(value or "").replace(",", "").strip()
    if not text:
        raise ValueError("missing float")
    return float(text)


def _parse_int(value: Any) -> int:
    text = str(value or "").replace(",", "").strip()
    if not text:
        raise ValueError("missing int")
    return int(float(text))

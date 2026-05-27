"""Binance public 24h crypto market adapter."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, ClassVar

import httpx
from pydantic import ValidationError

from investo.models import Category, NormalizedItem
from investo.sources._config import format_float, format_int, parse_symbol_list
from investo.sources._fanout import gather_with_error_isolation
from investo.sources._parse import (
    parse_float,
    parse_int,
    parse_json_response,
    required_str,
)
from investo.sources._registry import register
from investo.sources._retry import retry_get
from investo.sources._window import FetchWindow

_ENV_SYMBOLS = "INVESTO_CRYPTO_MARKET_SYMBOLS"
_DATA_PAGE_URL = "https://www.binance.com/en/markets/overview"


@register
class BinanceCryptoMarketAdapter:
    """Adapter for Binance public 24h ticker market data."""

    name: ClassVar[str] = "binance-crypto-market"
    category: ClassVar[Category] = "price"

    _DEFAULT_SYMBOLS: ClassVar[tuple[str, ...]] = ("BTCUSDT", "ETHUSDT", "SOLUSDT")
    _ENDPOINT: ClassVar[str] = "https://api.binance.com/api/v3/ticker/24hr"

    async def fetch(
        self,
        client: httpx.AsyncClient,
        window: FetchWindow,
    ) -> list[NormalizedItem]:
        symbols = parse_symbol_list(_ENV_SYMBOLS, self._DEFAULT_SYMBOLS)
        return await gather_with_error_isolation(
            (self._fetch_symbol(client, symbol, window) for symbol in symbols),
            source_name=self.name,
            raise_if_all_failed=True,
        )

    async def _fetch_symbol(
        self,
        client: httpx.AsyncClient,
        symbol: str,
        window: FetchWindow,
    ) -> NormalizedItem | None:
        normalized_symbol = symbol.strip().upper()
        if not normalized_symbol:
            return None
        response = await retry_get(
            client,
            self._ENDPOINT,
            source_name=self.name,
            params={"symbol": normalized_symbol},
        )
        payload = parse_json_response(
            response,
            source_name=self.name,
            message=f"malformed JSON for {normalized_symbol}",
        )
        try:
            return _payload_to_item(payload, source_name=self.name, fallback_utc=window.end_utc)
        except (TypeError, ValueError, ValidationError):
            return None


def _payload_to_item(payload: Any, *, source_name: str, fallback_utc: datetime) -> NormalizedItem:
    if not isinstance(payload, dict):
        raise ValueError("payload must be object")
    symbol = required_str(payload, "symbol")
    last = parse_float(payload.get("lastPrice"))
    pct_change = parse_float(payload.get("priceChangePercent"))
    quote_volume = parse_float(payload.get("quoteVolume"))
    base_volume = parse_float(payload.get("volume"))
    high = parse_float(payload.get("highPrice"))
    low = parse_float(payload.get("lowPrice"))
    open_ = parse_float(payload.get("openPrice"))
    weighted_avg = parse_float(payload.get("weightedAvgPrice"))
    trade_count = parse_int(payload.get("count"))
    open_time = _parse_epoch_ms(payload.get("openTime"))
    close_time = _parse_epoch_ms(payload.get("closeTime"))
    published_at = close_time or fallback_utc
    pct_prefix = "+" if pct_change > 0 else ""
    title = f"{symbol} 24h {last:,.2f} ({pct_prefix}{pct_change:.2f}%)"
    summary = (
        f"O:{open_:,.2f} H:{high:,.2f} L:{low:,.2f} "
        f"VWAP:{weighted_avg:,.2f}; quote vol:{quote_volume:,.0f}"
    )
    return NormalizedItem(
        source_name=source_name,
        category="price",
        title=title,
        summary=summary,
        url=_DATA_PAGE_URL,
        published_at=published_at,
        raw_metadata={
            "symbol": symbol,
            "last_price": format_float(last),
            "pct_change_24h": format_float(pct_change),
            "open": format_float(open_),
            "high": format_float(high),
            "low": format_float(low),
            "weighted_avg_price": format_float(weighted_avg),
            "base_volume": format_float(base_volume),
            "quote_volume": format_float(quote_volume),
            "trade_count": format_int(trade_count),
            "open_time": open_time.isoformat() if open_time else "",
            "close_time": close_time.isoformat() if close_time else "",
        },
    )


def _parse_epoch_ms(value: Any) -> datetime | None:
    if value is None:
        return None
    try:
        milliseconds = int(value)
    except (TypeError, ValueError):
        return None
    return datetime.fromtimestamp(milliseconds / 1000, tz=UTC)

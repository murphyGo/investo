"""Nasdaq Trader symbol directory adapter."""

from __future__ import annotations

import os
from datetime import UTC
from typing import Any, ClassVar, Final

import httpx
from pydantic import ValidationError

from investo.models import Category, NormalizedItem
from investo.sources._registry import register
from investo.sources._retry import retry_get
from investo.sources._sanitize import strip_html
from investo.sources._window import FetchWindow

_ENV_SYMBOLS: Final[str] = "INVESTO_NASDAQ_SYMBOLS"
_MAX_SYMBOLS: Final[int] = 16
_DEFAULT_SYMBOLS: Final[frozenset[str]] = frozenset(
    {"AAPL", "MSFT", "GOOGL", "META", "AMZN", "NVDA", "TSLA", "QQQ", "SPY"}
)
_NASDAQ_LISTED_URL: Final[str] = "https://www.nasdaqtrader.com/dynamic/SymDir/nasdaqlisted.txt"
_OTHER_LISTED_URL: Final[str] = "https://www.nasdaqtrader.com/dynamic/SymDir/otherlisted.txt"
_USER_AGENT: Final[str] = "Investo/1.0 (+https://murphygo.github.io/investo)"


@register
class NasdaqSymbolDirectoryAdapter:
    """Adapter for official Nasdaq Trader symbol directory files."""

    name: ClassVar[str] = "nasdaq-symbol-directory"
    category: ClassVar[Category] = "macro"

    async def fetch(
        self,
        client: httpx.AsyncClient,
        window: FetchWindow,
    ) -> list[NormalizedItem]:
        wanted = _configured_symbols()
        rows: list[dict[str, str]] = []
        for url, listing_type in (
            (_NASDAQ_LISTED_URL, "nasdaq"),
            (_OTHER_LISTED_URL, "other"),
        ):
            response = await retry_get(
                client,
                url,
                source_name=self.name,
                headers={"User-Agent": _USER_AGENT, "Accept": "text/plain"},
            )
            rows.extend(
                _parse_directory(
                    response.content.decode("utf-8", errors="replace"),
                    listing_type,
                )
            )

        items: list[NormalizedItem] = []
        for row in rows:
            symbol = row.get("symbol", "")
            if symbol not in wanted:
                continue
            item = self._normalize_row(row, published_at=window.start_utc)
            if item is not None:
                items.append(item)
        return items[:_MAX_SYMBOLS]

    def _normalize_row(self, row: dict[str, str], *, published_at: Any) -> NormalizedItem | None:
        symbol = row.get("symbol", "")
        security_name = strip_html(row.get("security_name", ""))
        if not symbol or not security_name:
            return None
        listing_type = row.get("listing_type", "")
        exchange = row.get("exchange", "")
        etf = row.get("etf", "")
        test_issue = row.get("test_issue", "")
        financial_status = row.get("financial_status", "")
        title = f"{symbol} listing metadata: {security_name}"
        summary = (
            f"listing_type={listing_type}; exchange={exchange or 'NASDAQ'}; "
            f"etf={etf}; test_issue={test_issue}; financial_status={financial_status or 'N/A'}"
        )
        raw_metadata = {
            "symbol": symbol,
            "security_name": security_name,
            "listing_type": listing_type,
            "exchange": exchange,
            "etf": etf,
            "test_issue": test_issue,
            "financial_status": financial_status,
            "official_source": "true",
        }
        try:
            return NormalizedItem(
                source_name=self.name,
                category=self.category,
                title=title,
                summary=summary,
                url=_NASDAQ_LISTED_URL if listing_type == "nasdaq" else _OTHER_LISTED_URL,
                published_at=published_at.astimezone(UTC),
                raw_metadata=raw_metadata,
            )
        except ValidationError:
            return None


def _configured_symbols() -> frozenset[str]:
    raw = os.environ.get(_ENV_SYMBOLS, "").strip()
    if not raw:
        return frozenset(sorted(_DEFAULT_SYMBOLS)[:_MAX_SYMBOLS])
    symbols = [symbol.strip().upper() for symbol in raw.split(",") if symbol.strip()]
    return frozenset(symbols[:_MAX_SYMBOLS]) or frozenset(sorted(_DEFAULT_SYMBOLS)[:_MAX_SYMBOLS])


def _parse_directory(text: str, listing_type: str) -> list[dict[str, str]]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return []
    header = lines[0].split("|")
    rows: list[dict[str, str]] = []
    for line in lines[1:]:
        if line.startswith("File Creation Time:"):
            continue
        parts = line.split("|")
        if len(parts) != len(header):
            continue
        raw = dict(zip(header, parts, strict=True))
        if listing_type == "nasdaq":
            rows.append(
                {
                    "symbol": raw.get("Symbol", "").strip().upper(),
                    "security_name": raw.get("Security Name", "").strip(),
                    "listing_type": listing_type,
                    "exchange": "NASDAQ",
                    "etf": raw.get("ETF", "").strip(),
                    "test_issue": raw.get("Test Issue", "").strip(),
                    "financial_status": raw.get("Financial Status", "").strip(),
                }
            )
        else:
            rows.append(
                {
                    "symbol": raw.get("ACT Symbol", "").strip().upper(),
                    "security_name": raw.get("Security Name", "").strip(),
                    "listing_type": listing_type,
                    "exchange": raw.get("Exchange", "").strip(),
                    "etf": raw.get("ETF", "").strip(),
                    "test_issue": raw.get("Test Issue", "").strip(),
                    "financial_status": "",
                }
            )
    return rows

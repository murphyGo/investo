"""Yonhap market RSS adapter for deterministic Korean index closes."""

from __future__ import annotations

import re
from datetime import UTC, date, datetime, time
from typing import ClassVar, Final
from zoneinfo import ZoneInfo

import httpx
from defusedxml.ElementTree import ParseError, fromstring
from pydantic import ValidationError

from investo.models import Category, NormalizedItem
from investo.sources._config import SUMMARY_MAX_LEN, format_float
from investo.sources._core_fact_map import core_fact_for_ticker, core_fact_metadata_key
from investo.sources._registry import register
from investo.sources._retry import retry_get
from investo.sources._window import FetchWindow
from investo.sources.protocol import SourceFetchError

_KST = ZoneInfo("Asia/Seoul")
_KR_CLOSE_KST = time(15, 30, tzinfo=_KST)
_USER_AGENT = "Investo/1.0 (https://murphygo.github.io/investo)"
_FEED_URL: Final[str] = "https://www.yna.co.kr/rss/market.xml"
_PAGE_URL: Final[str] = "https://www.yna.co.kr/market-plus/all"
_DISPLAY: Final[dict[str, str]] = {
    "^KOSPI": "코스피",
    "^KOSDAQ": "코스닥",
}
_NUM = r"([0-9]{1,3}(?:,[0-9]{3})*(?:\.[0-9]+)?)"
_INDEX_PATTERNS: Final[dict[str, re.Pattern[str]]] = {
    "^KOSPI": re.compile(rf"코스피[^0-9]{{0,40}}{_NUM}"),
    "^KOSDAQ": re.compile(rf"코스닥[^0-9]{{0,40}}{_NUM}"),
}


@register
class YonhapIndexCloseAdapter:
    """Parse KOSPI and KOSDAQ closes from one Yonhap market RSS request."""

    name: ClassVar[str] = "yonhap-index-close"
    category: ClassVar[Category] = "price"
    _TICKERS: ClassVar[tuple[str, ...]] = ("^KOSPI", "^KOSDAQ")

    async def fetch(
        self,
        client: httpx.AsyncClient,
        window: FetchWindow,
    ) -> list[NormalizedItem]:
        response = await retry_get(
            client,
            _FEED_URL,
            source_name=self.name,
            headers={"User-Agent": _USER_AGENT},
        )
        try:
            root = fromstring(response.content)
        except ParseError as exc:
            raise SourceFetchError(
                source_name=self.name,
                message="malformed Yonhap XML",
                transient=False,
                cause=exc,
            ) from exc

        entries: list[tuple[str, str, str]] = []
        for entry in root.iter("item"):
            title = (entry.findtext("title") or "").strip()
            description = (entry.findtext("description") or "").strip()
            link = (entry.findtext("link") or "").strip()
            entries.append((title, description, link))

        items: list[NormalizedItem] = []
        for ticker in self._TICKERS:
            match = _first_index_match(_INDEX_PATTERNS[ticker], entries)
            if match is None:
                continue
            close, headline, link = match
            item = _build_item(
                source_name=self.name,
                ticker=ticker,
                close=close,
                source_headline=headline,
                source_date=window.target_date,
                url=link or _PAGE_URL,
            )
            if item is not None:
                items.append(item)
        return items


def _first_index_match(
    pattern: re.Pattern[str],
    entries: list[tuple[str, str, str]],
) -> tuple[float, str, str] | None:
    for title, description, link in entries:
        for text in (title, description):
            match = pattern.search(text)
            if match is None:
                continue
            try:
                value = float(match.group(1).replace(",", ""))
            except ValueError:
                continue
            if value >= 100.0:
                return value, title or text, link
    return None


def _build_item(
    *,
    source_name: str,
    ticker: str,
    close: float,
    source_headline: str,
    source_date: date,
    url: str,
) -> NormalizedItem | None:
    display = _DISPLAY[ticker]
    raw_metadata = {
        "ticker": ticker,
        "display_name": display,
        "close": format_float(close),
        "provenance": "yonhap-rss",
        "source_date": source_date.isoformat(),
        "source_headline": source_headline,
    }
    fact = core_fact_for_ticker(ticker)
    if fact is not None:
        raw_metadata[core_fact_metadata_key(fact)] = format_float(close)

    summary = f"C:{close:,.2f}; 출처:yonhap-rss"
    try:
        return NormalizedItem(
            source_name=source_name,
            category="price",
            title=f"{display} {close:,.2f}",
            summary=summary[:SUMMARY_MAX_LEN],
            url=url,
            published_at=datetime.combine(source_date, _KR_CLOSE_KST).astimezone(UTC),
            raw_metadata=raw_metadata,
        )
    except ValidationError:
        return None


__all__ = ["YonhapIndexCloseAdapter"]

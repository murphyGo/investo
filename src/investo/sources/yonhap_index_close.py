"""Yonhap market RSS adapter for deterministic Korean index closes."""

from __future__ import annotations

import re
from datetime import datetime
from typing import ClassVar, Final
from zoneinfo import ZoneInfo

import httpx
from defusedxml.ElementTree import ParseError, fromstring
from pydantic import ValidationError

from investo.models import Category, NormalizedItem
from investo.sources._config import SUMMARY_MAX_LEN, format_float, parse_rfc822_to_utc
from investo.sources._core_fact_map import core_fact_for_ticker, core_fact_metadata_key
from investo.sources._registry import register
from investo.sources._retry import retry_get
from investo.sources._window import FetchWindow
from investo.sources.protocol import SourceFetchError

_KST = ZoneInfo("Asia/Seoul")
_USER_AGENT = "Investo/1.0 (https://murphygo.github.io/investo)"
_FEED_URL: Final[str] = "https://www.yna.co.kr/rss/market.xml"
_PAGE_URL: Final[str] = "https://www.yna.co.kr/market-plus/all"
_DISPLAY: Final[dict[str, str]] = {
    "^KOSPI": "코스피",
    "^KOSDAQ": "코스닥",
}
_NUMBER_RE: Final[re.Pattern[str]] = re.compile(
    r"(?<![0-9])(?P<value>[0-9]{1,3}(?:,[0-9]{3})*(?:\.[0-9]+)?)(?![0-9])"
)
_INDEX_PATTERNS: Final[dict[str, re.Pattern[str]]] = {
    "^KOSPI": re.compile(r"코스피"),
    "^KOSDAQ": re.compile(r"코스닥"),
}
_ANY_INDEX_RE: Final[re.Pattern[str]] = re.compile(r"코스피|코스닥")
_CLOSE_RE: Final[re.Pattern[str]] = re.compile(
    r"거래를\s+마쳤(?:다|습니다)?|장을\s+마쳤(?:다|습니다)?|장종료|종가|마감"
)
_NON_CLOSE_SUFFIX_RE: Final[re.Pattern[str]] = re.compile(
    r"^\s*(?:%|\uff05|p(?:t)?\b|포인트|선|대)",
    re.IGNORECASE,
)
_DERIVATIVES_RE: Final[re.Pattern[str]] = re.compile(r"(?:선물|옵션|코스피\s*200)")
_MAX_ALIAS_DISTANCE: Final[int] = 120
_MAX_CLOSE_DISTANCE: Final[int] = 24


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

        entries: list[tuple[str, str, str, datetime]] = []
        for entry in root.iter("item"):
            title = (entry.findtext("title") or "").strip()
            description = (entry.findtext("description") or "").strip()
            link = (entry.findtext("link") or "").strip()
            pubdate = (entry.findtext("pubDate") or "").strip()
            try:
                published_at = parse_rfc822_to_utc(pubdate)
            except (TypeError, ValueError):
                continue
            if published_at.astimezone(_KST).date() != window.target_date:
                continue
            entries.append((title, description, link, published_at))

        items: list[NormalizedItem] = []
        for ticker in self._TICKERS:
            match = _first_index_match(_INDEX_PATTERNS[ticker], entries)
            if match is None:
                continue
            close, headline, link, published_at = match
            item = _build_item(
                source_name=self.name,
                ticker=ticker,
                close=close,
                source_headline=headline,
                published_at=published_at,
                url=link or _PAGE_URL,
            )
            if item is not None:
                items.append(item)
        return items


def _first_index_match(
    pattern: re.Pattern[str],
    entries: list[tuple[str, str, str, datetime]],
) -> tuple[float, str, str, datetime] | None:
    for title, description, link, published_at in entries:
        for text in (title, description):
            value = _extract_close_coupled_value(pattern, text)
            if value is None:
                continue
            if value >= 100.0:
                return value, title or text, link, published_at
    return None


def _extract_close_coupled_value(
    index_pattern: re.Pattern[str],
    text: str,
) -> float | None:
    """Return one unambiguous number coupled to an index close phrase."""

    if _DERIVATIVES_RE.search(text):
        return None
    aliases = tuple(index_pattern.finditer(text))
    all_index_aliases = tuple(_ANY_INDEX_RE.finditer(text))
    close_phrases = tuple(_CLOSE_RE.finditer(text))
    if not aliases or not close_phrases:
        return None
    matching_alias_spans = {alias.span() for alias in aliases}
    alias_windows = tuple(
        (
            alias.start(),
            (
                all_index_aliases[index + 1].start()
                if index + 1 < len(all_index_aliases)
                else len(text)
            ),
        )
        for index, alias in enumerate(all_index_aliases)
        if alias.span() in matching_alias_spans
    )

    ranked: list[tuple[int, str]] = []
    for number in _NUMBER_RE.finditer(text):
        if _NON_CLOSE_SUFFIX_RE.match(text[number.end() :]):
            continue
        nearest_alias = min(
            (_span_distance(number.span(), alias.span()) for alias in aliases),
            default=_MAX_ALIAS_DISTANCE + 1,
        )
        if nearest_alias > _MAX_ALIAS_DISTANCE:
            continue
        owner_window = next(
            (
                (window_start, window_end)
                for window_start, window_end in alias_windows
                if window_start <= number.start() < window_end
            ),
            None,
        )
        if owner_window is None:
            continue
        window_start, window_end = owner_window
        owned_close_phrases = tuple(
            close for close in close_phrases if window_start <= close.start() < window_end
        )
        if not owned_close_phrases:
            continue
        nearest_close = min(
            (_span_distance(number.span(), close.span()) for close in owned_close_phrases),
            default=_MAX_CLOSE_DISTANCE + 1,
        )
        if nearest_close > _MAX_CLOSE_DISTANCE:
            continue
        ranked.append((nearest_close, number.group("value")))

    if not ranked:
        return None
    best_distance = min(distance for distance, _ in ranked)
    best_values = {value for distance, value in ranked if distance == best_distance}
    if len(best_values) != 1:
        return None
    try:
        return float(best_values.pop().replace(",", ""))
    except ValueError:
        return None


def _span_distance(left: tuple[int, int], right: tuple[int, int]) -> int:
    if left[1] <= right[0]:
        return right[0] - left[1]
    if right[1] <= left[0]:
        return left[0] - right[1]
    return 0


def _build_item(
    *,
    source_name: str,
    ticker: str,
    close: float,
    source_headline: str,
    published_at: datetime,
    url: str,
) -> NormalizedItem | None:
    display = _DISPLAY[ticker]
    source_date = published_at.astimezone(_KST).date()
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
            published_at=published_at,
            raw_metadata=raw_metadata,
        )
    except ValidationError:
        return None


__all__ = ["YonhapIndexCloseAdapter"]

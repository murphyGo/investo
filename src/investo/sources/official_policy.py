"""Official U.S. crypto-policy source adapters.

u58 adds three official source surfaces for crypto-regulation events:

* Congress.gov bill actions (optional ``CONGRESS_API_KEY``).
* Senate Banking official hearing/news HTML pages.
* House Financial Services official RSS feed.

All three emit only crypto-policy relevant rows and stamp
``raw_metadata["policy_priority"] = "crypto_regulation"`` so routing
and LLM candidate selection can preserve high-signal legislative
events even when they do not mention BTC/ETH or prices.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
from datetime import UTC, date, datetime, time, timedelta
from email.utils import parsedate_to_datetime
from typing import Any, ClassVar, Final
from urllib.parse import urlparse

import httpx
from defusedxml.ElementTree import ParseError, fromstring
from pydantic import ValidationError

from investo.models import Category, NormalizedItem
from investo.sources._config import SUMMARY_MAX_LEN, parse_symbol_list
from investo.sources._registry import register
from investo.sources._retry import retry_get
from investo.sources._sanitize import strip_html
from investo.sources._window import FetchWindow
from investo.sources.protocol import SourceFetchError

_USER_AGENT: Final[str] = "Investo/1.0 (+https://murphygo.github.io/investo)"
_POLICY_PRIORITY: Final[str] = "crypto_regulation"
_OFFICIAL_SOURCE: Final[str] = "true"
_RECENCY_DAYS: Final[int] = 7
_LOOKAHEAD_DAYS: Final[int] = 30
_MAX_ITEMS: Final[int] = 12
_ALLOWED_SCHEMES: Final[tuple[str, ...]] = ("http", "https")

_ENV_CONGRESS_KEY: Final[str] = "CONGRESS_API_KEY"
_ENV_CONGRESS_BILLS: Final[str] = "INVESTO_CONGRESS_BILLS"
_ENV_SENATE_URLS: Final[str] = "INVESTO_SENATE_BANKING_WATCH_URLS"
_ENV_HOUSE_RSS_URLS: Final[str] = "INVESTO_HOUSE_FINANCIAL_SERVICES_RSS_URLS"

_DEFAULT_CONGRESS_BILLS: Final[tuple[str, ...]] = ("119/hr/3633",)
_DEFAULT_SENATE_URLS: Final[tuple[str, ...]] = (
    "https://www.banking.senate.gov/hearings/05/08/2026/executive-session",
    "https://www.banking.senate.gov/newsroom/majority/"
    "chairman-scott-senators-lummis-tillis-release-market-structure-bill-text-"
    "ahead-of-banking-committee-markup",
)
_DEFAULT_HOUSE_RSS_URLS: Final[tuple[str, ...]] = (
    "https://financialservices.house.gov/news/rss.aspx",
)

_POLICY_TERMS: Final[tuple[str, ...]] = (
    "clarity act",
    "digital asset",
    "digital assets",
    "crypto",
    "cryptocurrency",
    "stablecoin",
    "stable coin",
    "market structure",
    "committee markup",
    "markup",
    "blockchain",
    "genius act",
)
_BROAD_POLICY_TERMS: Final[tuple[str, ...]] = ("sec", "cftc")
_MONTHS: Final[dict[str, int]] = {
    "january": 1,
    "february": 2,
    "march": 3,
    "april": 4,
    "may": 5,
    "june": 6,
    "july": 7,
    "august": 8,
    "september": 9,
    "october": 10,
    "november": 11,
    "december": 12,
}
_DATE_RE = re.compile(
    r"\b("
    r"January|February|March|April|May|June|July|August|September|October|November|December"
    r")\s+(\d{1,2}),\s+(\d{4})\b",
    re.IGNORECASE,
)


@register
class CongressGovBillActionsAdapter:
    """Adapter for configured Congress.gov v3 bill-action streams."""

    name: ClassVar[str] = "congress-gov-bill-actions"
    category: ClassVar[Category] = "news"
    _ENDPOINT_TEMPLATE: ClassVar[str] = "https://api.congress.gov/v3/bill/{}/{}/{}/actions"

    async def fetch(
        self,
        client: httpx.AsyncClient,
        window: FetchWindow,
    ) -> list[NormalizedItem]:
        api_key = os.environ.get(_ENV_CONGRESS_KEY, "").strip()
        if not api_key:
            raise SourceFetchError(
                source_name=self.name,
                message=f"{_ENV_CONGRESS_KEY} not set; {self.name} adapter will not run",
                transient=False,
            )

        bill_ids = parse_symbol_list(_ENV_CONGRESS_BILLS, _DEFAULT_CONGRESS_BILLS)
        results = await asyncio.gather(
            *(
                self._fetch_bill(
                    client,
                    bill_id=bill_id,
                    api_key=api_key,
                    window=window,
                )
                for bill_id in bill_ids
            ),
            return_exceptions=True,
        )
        items: list[NormalizedItem] = []
        failures: list[SourceFetchError] = []
        for result in results:
            if isinstance(result, SourceFetchError):
                failures.append(result)
                continue
            if isinstance(result, BaseException):
                raise result
            items.extend(result)
        if not items and failures and len(failures) == len(bill_ids):
            raise failures[0]
        return _dedupe_and_sort(items)

    async def _fetch_bill(
        self,
        client: httpx.AsyncClient,
        *,
        bill_id: str,
        api_key: str,
        window: FetchWindow,
    ) -> list[NormalizedItem]:
        parsed = _parse_bill_id(bill_id)
        if parsed is None:
            raise SourceFetchError(
                source_name=self.name,
                message=f"unsupported bill id: {bill_id}",
                transient=False,
            )
        congress, bill_type, bill_number = parsed
        response = await retry_get(
            client,
            self._ENDPOINT_TEMPLATE.format(congress, bill_type, bill_number),
            source_name=self.name,
            headers={"User-Agent": _USER_AGENT, "Accept": "application/json"},
            params={"api_key": api_key, "format": "json", "limit": "20"},
        )
        try:
            payload = response.json()
        except json.JSONDecodeError as exc:
            raise SourceFetchError(
                source_name=self.name,
                message=f"malformed JSON for bill {bill_id}",
                transient=False,
                cause=exc,
            ) from exc
        actions = payload.get("actions") if isinstance(payload, dict) else None
        if not isinstance(actions, list):
            return []
        items: list[NormalizedItem] = []
        for action in actions:
            normalized = self._normalize_action(
                action,
                bill_id=bill_id,
                congress=congress,
                bill_type=bill_type,
                bill_number=bill_number,
                window=window,
            )
            if normalized is not None:
                items.append(normalized)
        return items

    def _normalize_action(
        self,
        action: Any,
        *,
        bill_id: str,
        congress: str,
        bill_type: str,
        bill_number: str,
        window: FetchWindow,
    ) -> NormalizedItem | None:
        if not isinstance(action, dict):
            return None
        text = strip_html(str(action.get("text") or ""))
        action_date = _parse_iso_date(str(action.get("actionDate") or ""))
        if not text or action_date is None or not _is_crypto_policy_text(text):
            return None
        if not _within_policy_window(action_date, window.target_date):
            return None
        action_type = strip_html(str(action.get("type") or "")) or "bill action"
        title = f"H.R. {bill_number} CLARITY action — {action_type}"
        summary = _cap_summary(text)
        url = (
            f"https://www.congress.gov/bill/{congress}th-congress/house-bill/{bill_number}/actions"
        )
        try:
            return NormalizedItem(
                source_name=self.name,
                category=self.category,
                title=title,
                summary=summary,
                url=url,
                published_at=datetime.combine(action_date, time.min, tzinfo=UTC),
                raw_metadata={
                    "policy_priority": _POLICY_PRIORITY,
                    "official_source": _OFFICIAL_SOURCE,
                    "bill_id": bill_id,
                    "congress": congress,
                    "bill_type": bill_type,
                    "bill_number": bill_number,
                    "committee": "Congress.gov",
                    "event_type": action_type,
                },
            )
        except ValidationError:
            return None


@register
class SenateBankingPolicyAdapter:
    """Adapter for official Senate Banking crypto-policy watch pages."""

    name: ClassVar[str] = "senate-banking-policy"
    category: ClassVar[Category] = "news"

    async def fetch(
        self,
        client: httpx.AsyncClient,
        window: FetchWindow,
    ) -> list[NormalizedItem]:
        urls = parse_symbol_list(_ENV_SENATE_URLS, _DEFAULT_SENATE_URLS)
        results = await asyncio.gather(
            *(self._fetch_page(client, url=url, window=window) for url in urls),
            return_exceptions=True,
        )
        items: list[NormalizedItem] = []
        failures: list[SourceFetchError] = []
        for result in results:
            if isinstance(result, SourceFetchError):
                failures.append(result)
                continue
            if isinstance(result, BaseException):
                raise result
            if result is not None:
                items.append(result)
        if not items and failures and len(failures) == len(urls):
            raise failures[0]
        return _dedupe_and_sort(items)

    async def _fetch_page(
        self,
        client: httpx.AsyncClient,
        *,
        url: str,
        window: FetchWindow,
    ) -> NormalizedItem | None:
        _validate_url(url, self.name)
        response = await retry_get(
            client,
            url,
            source_name=self.name,
            headers={"User-Agent": _USER_AGENT, "Accept": "text/html, */*"},
        )
        html = response.content.decode("utf-8", errors="replace")
        return self._normalize_page(html, url=url, window=window)

    def _normalize_page(
        self,
        html: str,
        *,
        url: str,
        window: FetchWindow,
    ) -> NormalizedItem | None:
        text = strip_html(html)
        if not _is_crypto_policy_text(text):
            return None
        title = _extract_title(html) or "Senate Banking crypto-policy item"
        event_date = _extract_date(text)
        if event_date is None or not _within_policy_window(event_date, window.target_date):
            return None
        is_calendar = "executive session" in text.lower() or "hearing" in url.lower()
        lowered = text.lower()
        event_type = (
            "committee_markup"
            if "markup" in lowered or "executive session to consider" in lowered
            else "hearing"
        )
        if not is_calendar:
            event_type = "news_release"
        scheduled_at = datetime.combine(event_date, time.min, tzinfo=UTC) if is_calendar else None
        published_at = (
            datetime.combine(window.target_date, time.min, tzinfo=UTC)
            if is_calendar
            else datetime.combine(event_date, time.min, tzinfo=UTC)
        )
        try:
            return NormalizedItem(
                source_name=self.name,
                category="calendar" if is_calendar else "news",
                title=title,
                summary=_cap_summary(text),
                url=url,
                published_at=published_at,
                scheduled_at=scheduled_at,
                raw_metadata={
                    "policy_priority": _POLICY_PRIORITY,
                    "official_source": _OFFICIAL_SOURCE,
                    "bill_id": _extract_bill_id(text) or "",
                    "committee": "Senate Banking",
                    "event_type": event_type,
                },
            )
        except ValidationError:
            return None


@register
class HouseFinancialServicesPolicyAdapter:
    """Adapter for House Financial Services official crypto-policy RSS."""

    name: ClassVar[str] = "house-financial-services-policy"
    category: ClassVar[Category] = "news"

    async def fetch(
        self,
        client: httpx.AsyncClient,
        window: FetchWindow,
    ) -> list[NormalizedItem]:
        feed_urls = parse_symbol_list(_ENV_HOUSE_RSS_URLS, _DEFAULT_HOUSE_RSS_URLS)
        results = await asyncio.gather(
            *(self._fetch_feed(client, feed_url=feed_url, window=window) for feed_url in feed_urls),
            return_exceptions=True,
        )
        items: list[NormalizedItem] = []
        failures: list[SourceFetchError] = []
        for result in results:
            if isinstance(result, SourceFetchError):
                failures.append(result)
                continue
            if isinstance(result, BaseException):
                raise result
            items.extend(result)
        if not items and failures and len(failures) == len(feed_urls):
            raise failures[0]
        return _dedupe_and_sort(items)

    async def _fetch_feed(
        self,
        client: httpx.AsyncClient,
        *,
        feed_url: str,
        window: FetchWindow,
    ) -> list[NormalizedItem]:
        _validate_url(feed_url, self.name)
        response = await retry_get(
            client,
            feed_url,
            source_name=self.name,
            headers={"User-Agent": _USER_AGENT, "Accept": "application/rss+xml, text/xml, */*"},
        )
        try:
            root = fromstring(response.content)
        except ParseError as exc:
            raise SourceFetchError(
                source_name=self.name,
                message=f"malformed XML: {exc}",
                transient=False,
                cause=exc,
            ) from exc
        items: list[NormalizedItem] = []
        for entry in root.iter("item"):
            normalized = self._normalize_entry(entry, feed_url=feed_url, window=window)
            if normalized is not None:
                items.append(normalized)
        return items

    def _normalize_entry(
        self,
        entry: Any,
        *,
        feed_url: str,
        window: FetchWindow,
    ) -> NormalizedItem | None:
        title = strip_html(entry.findtext("title") or "")
        description = strip_html(entry.findtext("description") or "")
        link = (entry.findtext("link") or "").strip()
        pubdate = (entry.findtext("pubDate") or "").strip()
        if not title or not link or not pubdate:
            return None
        if urlparse(link).scheme not in _ALLOWED_SCHEMES:
            return None
        body = f"{title} {description}"
        if not _is_crypto_policy_text(body):
            return None
        try:
            published = parsedate_to_datetime(pubdate)
        except (TypeError, ValueError):
            return None
        if published is None or published.tzinfo is None:
            return None
        published_date = published.astimezone(UTC).date()
        if not _within_policy_window(published_date, window.target_date):
            return None
        event_type = "committee_markup" if "markup" in body.lower() else "news_release"
        try:
            return NormalizedItem(
                source_name=self.name,
                category=self.category,
                title=title,
                summary=_cap_summary(description),
                url=link,
                published_at=published.astimezone(UTC),
                raw_metadata={
                    "policy_priority": _POLICY_PRIORITY,
                    "official_source": _OFFICIAL_SOURCE,
                    "bill_id": _extract_bill_id(body) or "",
                    "committee": "House Financial Services",
                    "event_type": event_type,
                    "feed_url": feed_url,
                },
            )
        except ValidationError:
            return None


def _dedupe_and_sort(items: list[NormalizedItem]) -> list[NormalizedItem]:
    seen: set[str] = set()
    deduped: list[NormalizedItem] = []
    for item in items:
        key = str(item.url) if item.url is not None else item.title
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return sorted(deduped, key=lambda item: item.published_at, reverse=True)[:_MAX_ITEMS]


def _parse_bill_id(value: str) -> tuple[str, str, str] | None:
    parts = [part.strip().lower() for part in value.split("/") if part.strip()]
    if len(parts) != 3:
        return None
    congress, bill_type, bill_number = parts
    if not congress.isdigit() or not bill_number.isdigit():
        return None
    if bill_type not in {"hr", "s", "hjres", "sjres", "hres", "sres"}:
        return None
    return congress, bill_type, bill_number


def _parse_iso_date(value: str) -> date | None:
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def _extract_title(html: str) -> str | None:
    for pattern in (
        r"<h1[^>]*>(.*?)</h1>",
        r"<h2[^>]*>(.*?)</h2>",
        r"<title[^>]*>(.*?)</title>",
    ):
        match = re.search(pattern, html, flags=re.IGNORECASE | re.DOTALL)
        if match:
            title = strip_html(match.group(1))
            if title:
                return title
    return None


def _extract_date(text: str) -> date | None:
    match = _DATE_RE.search(text)
    if match is None:
        return None
    month_name, day_text, year_text = match.groups()
    month = _MONTHS.get(month_name.lower())
    if month is None:
        return None
    try:
        return date(int(year_text), month, int(day_text))
    except ValueError:
        return None


def _extract_bill_id(text: str) -> str | None:
    match = re.search(r"\bH\.?\s*R\.?\s*(\d{3,5})\b", text, flags=re.IGNORECASE)
    if match is None:
        return None
    return f"hr{match.group(1)}"


def _within_policy_window(value: date, target_date: date) -> bool:
    return (
        target_date - timedelta(days=_RECENCY_DAYS)
        <= value
        <= target_date + timedelta(days=_LOOKAHEAD_DAYS)
    )


def _is_crypto_policy_text(text: str) -> bool:
    lowered = text.lower()
    if any(term in lowered for term in _POLICY_TERMS):
        return True
    if any(term in lowered for term in _BROAD_POLICY_TERMS):
        return any(context in lowered for context in ("digital asset", "crypto", "stablecoin"))
    return False


def _cap_summary(text: str) -> str | None:
    cleaned = strip_html(text)
    if not cleaned:
        return None
    return cleaned[:SUMMARY_MAX_LEN]


def _validate_url(url: str, source_name: str) -> None:
    if urlparse(url).scheme not in _ALLOWED_SCHEMES:
        raise SourceFetchError(
            source_name=source_name,
            message=f"unsupported URL scheme: {url}",
            transient=False,
        )


__all__ = [
    "CongressGovBillActionsAdapter",
    "HouseFinancialServicesPolicyAdapter",
    "SenateBankingPolicyAdapter",
]

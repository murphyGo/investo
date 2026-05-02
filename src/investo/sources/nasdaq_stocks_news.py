"""Nasdaq Stocks RSS adapter — official exchange-side ``news`` source.

Consumes Nasdaq's official category RSS endpoint for the ``Stocks``
topic. The source is useful for daily market briefings because it
surfaces broad US equity, index, commodity, FX, and single-name market
commentary syndicated on Nasdaq.com.

Design choices:

* **Official RSS endpoint** — Nasdaq documents category RSS feeds at
  ``https://www.nasdaq.com/nasdaq-RSS-Feeds``. This adapter uses the
  ``Stocks`` category URL exposed by that page:
  ``https://www.nasdaq.com/feed/rssoutbound?category=Stocks``.
* **Browser-compatible User-Agent** — local fixture recording showed
  Nasdaq can hang or fail without a browser-compatible UA. The adapter
  sends the same fixed, non-secret UA shape used to record the fixture;
  no API key is used.
* **RSS 2.0 + Dublin Core + Nasdaq namespace** — required fields use
  unprefixed RSS names. ``dc:creator`` and ``nasdaq:tickers`` are
  optional metadata fields and are looked up by fully-qualified names.
* **Strict R7** — the feed publishes throughout US market/news hours.
  Window filtering uses the half-open :class:`FetchWindow` interval.

Pins NFR-007 ACs:

* AC-7.2 — title and summary HTML stripped via :mod:`_sanitize`
* AC-7.3 — items with non-http/https URLs are dropped
* AC-7.4 — ``<pubDate>`` parsed to a tz-aware UTC datetime
* AC-7.6 — XML parsed via ``defusedxml`` (never stdlib ElementTree)
"""

from __future__ import annotations

from datetime import UTC
from email.utils import parsedate_to_datetime
from typing import Any, ClassVar
from urllib.parse import urlparse

import httpx
from defusedxml.ElementTree import ParseError, fromstring
from pydantic import ValidationError

from investo.models import Category, NormalizedItem
from investo.sources._config import SUMMARY_MAX_LEN
from investo.sources._registry import register
from investo.sources._retry import retry_get
from investo.sources._sanitize import strip_html
from investo.sources._window import FetchWindow
from investo.sources._xml_namespaces import DC_CREATOR, NASDAQ_TICKERS
from investo.sources.protocol import SourceFetchError

_ALLOWED_SCHEMES = ("http", "https")
_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/124 Safari/537.36"
)


@register
class NasdaqStocksNewsAdapter:
    """Adapter for Nasdaq's official Stocks RSS 2.0 feed."""

    name: ClassVar[str] = "nasdaq-stocks-news"
    category: ClassVar[Category] = "news"

    _FEED_URL: ClassVar[str] = "https://www.nasdaq.com/feed/rssoutbound?category=Stocks"

    async def fetch(
        self,
        client: httpx.AsyncClient,
        window: FetchWindow,
    ) -> list[NormalizedItem]:
        response = await retry_get(
            client,
            self._FEED_URL,
            source_name=self.name,
            headers={"User-Agent": _USER_AGENT},
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
            normalized = self._normalize_entry(entry)
            if normalized is None:
                continue
            if window.contains(normalized.published_at):
                items.append(normalized)
        return items

    def _normalize_entry(self, entry: Any) -> NormalizedItem | None:
        # ``entry`` is returned by defusedxml. Keep it typed as Any to
        # avoid stdlib XML imports under src/investo/sources.
        title_raw = (entry.findtext("title") or "").strip()
        link_raw = (entry.findtext("link") or "").strip()
        pubdate_raw = (entry.findtext("pubDate") or "").strip()
        if not title_raw or not link_raw or not pubdate_raw:
            return None

        if urlparse(link_raw).scheme not in _ALLOWED_SCHEMES:
            return None

        try:
            published = parsedate_to_datetime(pubdate_raw)
        except (TypeError, ValueError):
            return None
        if published is None or published.tzinfo is None:
            return None
        published_utc = published.astimezone(UTC)

        title = strip_html(title_raw)
        if not title:
            return None
        description_raw = (entry.findtext("description") or "").strip()
        summary = strip_html(description_raw) or None
        if summary and len(summary) > SUMMARY_MAX_LEN:
            summary = summary[:SUMMARY_MAX_LEN]

        raw_metadata: dict[str, str] = {}
        guid = (entry.findtext("guid") or "").strip()
        if guid:
            raw_metadata["guid"] = guid
        creator_raw = entry.findtext(DC_CREATOR)
        if creator_raw is not None:
            creator = creator_raw.strip()
            if creator:
                raw_metadata["creator"] = creator
        category_raw = (entry.findtext("category") or "").strip()
        if category_raw:
            raw_metadata["category"] = category_raw
        tickers_raw = entry.findtext(NASDAQ_TICKERS)
        if tickers_raw is not None:
            tickers = ",".join(part.strip() for part in tickers_raw.split(",") if part.strip())
            if tickers:
                raw_metadata["tickers"] = tickers

        try:
            return NormalizedItem(
                source_name=self.name,
                category=self.category,
                title=title,
                summary=summary,
                url=link_raw,
                published_at=published_utc,
                raw_metadata=raw_metadata,
            )
        except ValidationError:
            return None

"""Official CFTC policy/news RSS adapter."""

from __future__ import annotations

from typing import Any, ClassVar, Final
from urllib.parse import urlparse

import httpx
from defusedxml.ElementTree import ParseError, fromstring
from pydantic import ValidationError

from investo.models import Category, NormalizedItem
from investo.sources._config import SUMMARY_MAX_LEN, parse_rfc822_to_utc
from investo.sources._registry import register
from investo.sources._retry import retry_get
from investo.sources._sanitize import strip_html
from investo.sources._window import FetchWindow
from investo.sources.protocol import SourceFetchError

_ALLOWED_SCHEMES: Final[tuple[str, ...]] = ("http", "https")
_OFFICIAL_SOURCE: Final[str] = "true"
_POLICY_PRIORITY: Final[str] = "crypto_regulation"
_POLICY_SOURCE: Final[str] = "cftc"
_USER_AGENT: Final[str] = "Investo/1.0 (+https://murphygo.github.io/investo)"
_MAX_ITEMS: Final[int] = 12
_DC_CREATOR: Final[str] = "{http://purl.org/dc/elements/1.1/}creator"
_FEEDS: Final[tuple[tuple[str, str], ...]] = (
    ("general_press", "https://www.cftc.gov/RSS/RSSGP/rssgp.xml"),
    ("enforcement_press", "https://www.cftc.gov/RSS/RSSENF/rssenf.xml"),
    ("speech_testimony", "https://www.cftc.gov/RSS/RSSST/rssst.xml"),
)
_CRYPTO_POLICY_DIRECT_TERMS: Final[tuple[str, ...]] = (
    "bitcoin",
    "blockchain",
    "crypto",
    "cryptocurrency",
    "digital asset",
    "digital assets",
    "event contract",
    "event contracts",
    "ethereum",
    "prediction market",
    "prediction markets",
    "stable coin",
    "stablecoin",
    "virtual currency",
)
_CRYPTO_POLICY_CONTEXTUAL_TERMS: Final[tuple[str, ...]] = (
    "market structure",
    "swap",
    "swaps",
)
_CRYPTO_POLICY_CONTEXT_TERMS: Final[tuple[str, ...]] = (
    "blockchain",
    "crypto",
    "digital asset",
    "digital assets",
    "prediction market",
    "prediction markets",
    "stablecoin",
)


@register
class CftcPolicyRssAdapter:
    """Adapter for CFTC general, enforcement, and speech/testimony RSS feeds."""

    name: ClassVar[str] = "cftc-policy-rss"
    category: ClassVar[Category] = "news"

    async def fetch(
        self,
        client: httpx.AsyncClient,
        window: FetchWindow,
    ) -> list[NormalizedItem]:
        items: list[NormalizedItem] = []
        failures: list[SourceFetchError] = []
        for feed_type, url in _FEEDS:
            try:
                response = await retry_get(
                    client,
                    url,
                    source_name=self.name,
                    headers={"User-Agent": _USER_AGENT, "Accept": "application/rss+xml, */*"},
                )
                items.extend(self._parse_feed(response.content, feed_type=feed_type, window=window))
            except SourceFetchError as exc:
                failures.append(exc)
        if failures and len(failures) == len(_FEEDS):
            raise failures[0]
        return _dedupe_sort_cap(items)

    def _parse_feed(
        self,
        body: bytes,
        *,
        feed_type: str,
        window: FetchWindow,
    ) -> list[NormalizedItem]:
        try:
            root = fromstring(body)
        except ParseError as exc:
            raise SourceFetchError(
                source_name=self.name,
                message=f"malformed XML: {exc}",
                transient=False,
                cause=exc,
            ) from exc

        items: list[NormalizedItem] = []
        for entry in root.iter("item"):
            normalized = self._normalize_entry(entry, feed_type=feed_type)
            if normalized is not None and window.contains(normalized.published_at):
                items.append(normalized)
        return items

    def _normalize_entry(self, entry: Any, *, feed_type: str) -> NormalizedItem | None:
        title_raw = (entry.findtext("title") or "").strip()
        link_raw = (entry.findtext("link") or "").strip()
        pubdate_raw = (entry.findtext("pubDate") or "").strip()
        if not title_raw or not link_raw or not pubdate_raw:
            return None
        if urlparse(link_raw).scheme not in _ALLOWED_SCHEMES:
            return None
        try:
            published_utc = parse_rfc822_to_utc(pubdate_raw)
        except (TypeError, ValueError):
            return None

        title = strip_html(title_raw)
        if not title:
            return None
        summary = _clean_summary(entry.findtext("description") or "")
        raw_metadata: dict[str, str] = {
            "feed_type": feed_type,
            "official_source": _OFFICIAL_SOURCE,
        }
        guid = (entry.findtext("guid") or "").strip()
        if guid:
            raw_metadata["guid"] = guid
        creator = (entry.findtext(_DC_CREATOR) or "").strip()
        if creator:
            raw_metadata["creator"] = strip_html(creator)[:80]
        if _is_crypto_policy_text(f"{title} {summary or ''}"):
            raw_metadata["policy_priority"] = _POLICY_PRIORITY
            raw_metadata["policy_source"] = _POLICY_SOURCE

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


def _is_crypto_policy_text(text: str) -> bool:
    lowered = text.lower()
    if any(term in lowered for term in _CRYPTO_POLICY_DIRECT_TERMS):
        return True
    return any(term in lowered for term in _CRYPTO_POLICY_CONTEXTUAL_TERMS) and any(
        term in lowered for term in _CRYPTO_POLICY_CONTEXT_TERMS
    )


def _clean_summary(text: str) -> str | None:
    summary = strip_html(text)
    if not summary:
        return None
    return summary[:SUMMARY_MAX_LEN]


def _dedupe_sort_cap(items: list[NormalizedItem]) -> list[NormalizedItem]:
    seen_urls: set[str] = set()
    seen_titles: set[str] = set()
    deduped: list[NormalizedItem] = []
    for item in items:
        url_key = str(item.url).rstrip("/").lower()
        title_key = item.title.casefold()
        if url_key in seen_urls or title_key in seen_titles:
            continue
        seen_urls.add(url_key)
        seen_titles.add(title_key)
        deduped.append(item)
    deduped.sort(key=lambda item: (item.published_at, item.title), reverse=True)
    return deduped[:_MAX_ITEMS]

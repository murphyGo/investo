"""SEC newsroom press-release and speech RSS adapter."""

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
_POLICY_PRIORITY: Final[str] = "crypto_regulation"
_OFFICIAL_SOURCE: Final[str] = "true"
_USER_AGENT: Final[str] = "investo investo@example.com"
_FEEDS: Final[tuple[tuple[str, str], ...]] = (
    ("press_release", "https://www.sec.gov/news/pressreleases.rss"),
    ("speech_statement", "https://www.sec.gov/news/speeches-statements.rss"),
)
_CRYPTO_POLICY_DIRECT_TERMS: Final[tuple[str, ...]] = (
    "clarity act",
    "digital asset",
    "digital assets",
    "crypto",
    "cryptocurrency",
    "stablecoin",
    "stable coin",
    "blockchain",
    "genius act",
)
_CRYPTO_POLICY_CONTEXTUAL_TERMS: Final[tuple[str, ...]] = ("market structure",)
_CRYPTO_POLICY_CONTEXT_TERMS: Final[tuple[str, ...]] = (
    "digital asset",
    "digital assets",
    "crypto",
    "cryptocurrency",
    "stablecoin",
    "stable coin",
    "blockchain",
)


@register
class SecNewsroomRssAdapter:
    """Adapter for official SEC newsroom RSS feeds."""

    name: ClassVar[str] = "sec-newsroom-rss"
    category: ClassVar[Category] = "news"

    async def fetch(
        self,
        client: httpx.AsyncClient,
        window: FetchWindow,
    ) -> list[NormalizedItem]:
        items: list[NormalizedItem] = []
        for feed_type, url in _FEEDS:
            response = await retry_get(
                client,
                url,
                source_name=self.name,
                headers={"User-Agent": _USER_AGENT},
            )
            items.extend(self._parse_feed(response.content, feed_type=feed_type, window=window))
        return items

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
        if _is_crypto_policy_text(f"{title} {summary or ''}"):
            raw_metadata["policy_priority"] = _POLICY_PRIORITY

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

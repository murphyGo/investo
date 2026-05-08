"""Official Korean financial-policy RSS adapter."""

from __future__ import annotations

import asyncio
from datetime import UTC
from email.utils import parsedate_to_datetime
from typing import Any, ClassVar
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

_ALLOWED_SCHEMES = ("http", "https")
_ENV_FEED_URLS = "INVESTO_KOREA_POLICY_RSS_URLS"
_MAX_ITEMS = 12


@register
class KoreaPolicyRssAdapter:
    """Adapter for official Korean financial-policy RSS feeds."""

    name: ClassVar[str] = "korea-policy-rss"
    category: ClassVar[Category] = "news"

    # 금융위원회 RSS 서비스 안내:
    # https://www.fsc.go.kr/ut060101
    _DEFAULT_FEED_URLS: ClassVar[tuple[str, ...]] = (
        "http://www.fsc.go.kr/about/fsc_bbs_rss/?fid=0111",
    )

    async def fetch(
        self,
        client: httpx.AsyncClient,
        window: FetchWindow,
    ) -> list[NormalizedItem]:
        feed_urls = parse_symbol_list(_ENV_FEED_URLS, self._DEFAULT_FEED_URLS)
        results = await _gather_feeds(self, client, feed_urls, window)
        items: list[NormalizedItem] = []
        failures: list[SourceFetchError] = []
        seen: set[str] = set()
        for result in results:
            if isinstance(result, SourceFetchError):
                failures.append(result)
                continue
            if isinstance(result, BaseException):
                raise result
            for item in result:
                dedupe_key = str(item.url) if item.url is not None else item.title
                if dedupe_key in seen:
                    continue
                seen.add(dedupe_key)
                items.append(item)
        if not items and failures and len(failures) == len(feed_urls):
            raise failures[0]
        return sorted(items, key=lambda item: item.published_at, reverse=True)[:_MAX_ITEMS]

    async def _fetch_feed(
        self,
        client: httpx.AsyncClient,
        feed_url: str,
        window: FetchWindow,
    ) -> list[NormalizedItem]:
        if urlparse(feed_url).scheme not in _ALLOWED_SCHEMES:
            raise SourceFetchError(
                source_name=self.name,
                message=f"unsupported feed URL scheme: {feed_url}",
                transient=False,
            )
        response = await retry_get(client, feed_url, source_name=self.name)
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
            normalized = self._normalize_entry(entry, feed_url)
            if normalized is None:
                continue
            if window.contains(normalized.published_at):
                items.append(normalized)
        return items

    def _normalize_entry(self, entry: Any, feed_url: str) -> NormalizedItem | None:
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
        title = strip_html(title_raw)
        if not title:
            return None
        description_raw = (entry.findtext("description") or "").strip()
        summary = strip_html(description_raw) or None
        if summary and len(summary) > SUMMARY_MAX_LEN:
            summary = summary[:SUMMARY_MAX_LEN]
        raw_metadata: dict[str, str] = {"feed_url": feed_url}
        guid = (entry.findtext("guid") or "").strip()
        if guid:
            raw_metadata["guid"] = guid
        try:
            return NormalizedItem(
                source_name=self.name,
                category=self.category,
                title=title,
                summary=summary,
                url=link_raw,
                published_at=published.astimezone(UTC),
                raw_metadata=raw_metadata,
            )
        except ValidationError:
            return None


async def _gather_feeds(
    adapter: KoreaPolicyRssAdapter,
    client: httpx.AsyncClient,
    feed_urls: tuple[str, ...],
    window: FetchWindow,
) -> list[list[NormalizedItem] | BaseException]:
    return list(
        await asyncio.gather(
            *(adapter._fetch_feed(client, feed_url, window) for feed_url in feed_urls),
            return_exceptions=True,
        )
    )

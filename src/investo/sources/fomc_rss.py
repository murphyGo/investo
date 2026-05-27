"""FOMC press-release RSS adapter — first concrete Source Adapter.

Implements the algorithm from
``aidlc-docs/construction/u1-sources/functional-design/business-logic-model.md``
L6 (FOMC RSS PoC) and ``business-rules.md`` R8 (NormalizedItem field
rules). The live feed is **RSS 2.0** (not Atom 1.0 as the FD prediction
listed); see ``aidlc-docs/audit.md`` Step 8 for the divergence
ratification.

Pins NFR-007 ACs:

* AC-7.2 — title and summary HTML stripped via :mod:`_sanitize`
* AC-7.3 — items with non-http/https URLs are dropped (not stored)
* AC-7.4 — ``<pubDate>`` parsed to a tz-aware UTC datetime
* AC-7.6 — XML parsed via ``defusedxml`` (never stdlib ElementTree)
"""

from __future__ import annotations

from typing import Any, ClassVar
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

_ALLOWED_SCHEMES = ("http", "https")


@register
class FomcRssAdapter:
    """Adapter for the Federal Reserve press-release RSS 2.0 feed.

    Stateless per FD R3 — the adapter holds no per-call state and the
    shared :class:`httpx.AsyncClient` is injected by the aggregator.
    """

    name: ClassVar[str] = "fomc-rss"
    # FOMC press releases announce scheduled-event outcomes (rate
    # decisions, stress-test publication windows). The Category
    # taxonomy treats these as "calendar" rather than "news" because
    # downstream briefing layout slots them under the schedule
    # section. See aidlc-docs/inception/application-design/.
    category: ClassVar[Category] = "calendar"

    _FEED_URL: ClassVar[str] = "https://www.federalreserve.gov/feeds/press_all.xml"

    async def fetch(
        self,
        client: httpx.AsyncClient,
        window: FetchWindow,
    ) -> list[NormalizedItem]:
        response = await retry_get(client, self._FEED_URL, source_name=self.name)
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
        # `entry` is an :class:`xml.etree.ElementTree.Element` returned
        # by the safe ``defusedxml`` parser. Typed as ``Any`` because
        # importing the concrete class would mean either touching the
        # stdlib XML module (forbidden by NFR-007 AC-7.6 grep) or
        # adding a TYPE_CHECKING import that the same grep would flag.
        # The methods used below (``findtext``) are stable and covered
        # by every test in ``tests/unit/sources/test_fomc_rss.py``.
        # Required RSS 2.0 fields. Missing any → silently drop the
        # entry (per-item validation; sibling entries unaffected).
        title_raw = (entry.findtext("title") or "").strip()
        link_raw = (entry.findtext("link") or "").strip()
        pubdate_raw = (entry.findtext("pubDate") or "").strip()
        if not title_raw or not link_raw or not pubdate_raw:
            return None

        # AC-7.3: only http/https URLs accepted; other schemes
        # (file://, javascript:, ...) are dropped, not stored.
        if urlparse(link_raw).scheme not in _ALLOWED_SCHEMES:
            return None

        # AC-7.4: <pubDate> is RFC 822 ("Fri, 24 Apr 2026 20:00:00 GMT").
        # parse_rfc822_to_utc returns a tz-aware UTC datetime when the
        # input carries a timezone (GMT/UTC); a naive or unparseable
        # input raises and is dropped.
        try:
            published_utc = parse_rfc822_to_utc(pubdate_raw)
        except (TypeError, ValueError):
            return None

        # AC-7.2: strip HTML from feed-derived text fields.
        title = strip_html(title_raw)
        if not title:
            return None
        description_raw = (entry.findtext("description") or "").strip()
        summary = strip_html(description_raw) or None
        if summary and len(summary) > SUMMARY_MAX_LEN:
            summary = summary[:SUMMARY_MAX_LEN]

        # raw_metadata: provenance bag (R8 — strings only, no nesting).
        raw_metadata: dict[str, str] = {}
        guid = (entry.findtext("guid") or "").strip()
        if guid:
            raw_metadata["guid"] = guid
        rss_category = (entry.findtext("category") or "").strip()
        if rss_category:
            raw_metadata["rss_category"] = rss_category

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
            # Per-entry pydantic rejection (e.g. URL host issues that
            # passed the scheme guard but failed HttpUrl validation).
            # Drop the entry; sibling entries continue.
            return None

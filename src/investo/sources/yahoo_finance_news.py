"""Yahoo Finance top-stories RSS adapter — first ``news`` category source.

Implements the algorithm from
``aidlc-docs/construction/u1-sources/functional-design/business-logic-model.md``
L6.5 (added 2026-05-01 — Extension #2). Single-URL RSS 2.0 feed with
no per-symbol parameter, no compliance header, and no env-var override.
The simplest adapter in u1.

Design choices (audit log 2026-05-01T04:00:00Z):

* **No ``<description>`` element on the rssindex feed** → emitted
  :class:`NormalizedItem` carries ``summary=None``. Synthesizing a
  summary from the title would be a synthetic-content R8 violation.
* **<pubDate> is ISO 8601 with `Z` suffix** on items (different from
  L6.1 FOMC's RFC 822 form). We parse via :meth:`datetime.fromisoformat`
  (Python 3.11+ accepts the `Z` suffix and offset forms natively).
  The FD prediction that ``email.utils.parsedate_to_datetime`` accepts
  ISO 8601 was wrong against the live 3.11 behaviour — it raises
  ``ValueError`` on `Z`-suffixed input. Divergence ratified at
  implementation time; sibling FOMC adapter sticks with
  ``parsedate_to_datetime`` because its feed is RFC 822.
* **Strict R7** — Yahoo's news feed publishes continuously across all
  weekdays / weekends; no cadence gap, so R11's relaxation clause does
  NOT apply.
* **<source> element** is OPTIONAL — some items omit it (Yahoo allows
  internally-authored stories without a syndication source). Adapter
  defaults ``rss_source=""`` rather than dropping the entry.

Pins NFR-007 ACs:

* AC-7.2 — title HTML stripped via :mod:`_sanitize`
* AC-7.3 — items with non-http/https URLs are dropped (not stored)
* AC-7.4 — ``<pubDate>`` parsed to a tz-aware UTC datetime
* AC-7.6 — XML parsed via ``defusedxml`` (never stdlib ElementTree)
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, ClassVar
from urllib.parse import urlparse

import httpx
from defusedxml.ElementTree import ParseError, fromstring
from pydantic import ValidationError

from investo.models import Category, NormalizedItem
from investo.sources._registry import register
from investo.sources._retry import retry_get
from investo.sources._sanitize import strip_html
from investo.sources._window import FetchWindow
from investo.sources.protocol import SourceFetchError

_ALLOWED_SCHEMES = ("http", "https")
_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/124 Safari/537.36"
)


@register
class YahooFinanceNewsAdapter:
    """Adapter for the Yahoo Finance top-stories RSS 2.0 feed (FD L6.5).

    Stateless per FD R3 — no per-call state and the shared
    :class:`httpx.AsyncClient` is injected by the aggregator.
    """

    name: ClassVar[str] = "yahoo-finance-news"
    category: ClassVar[Category] = "news"

    _FEED_URL: ClassVar[str] = "https://finance.yahoo.com/news/rssindex"

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
        # ``entry`` is an :class:`xml.etree.ElementTree.Element` returned
        # by the safe ``defusedxml`` parser. Typed ``Any`` to avoid
        # importing the stdlib XML module under ``src/investo/sources``
        # (NFR-007 AC-7.6 grep).
        title_raw = (entry.findtext("title") or "").strip()
        link_raw = (entry.findtext("link") or "").strip()
        pubdate_raw = (entry.findtext("pubDate") or "").strip()
        if not title_raw or not link_raw or not pubdate_raw:
            return None

        # AC-7.3: only http/https URLs accepted.
        if urlparse(link_raw).scheme not in _ALLOWED_SCHEMES:
            return None

        # AC-7.4: <pubDate> in Yahoo's rssindex is ISO 8601 with `Z`
        # suffix (e.g. "2026-04-29T14:01:13Z"). ``datetime.fromisoformat``
        # in Python 3.11+ accepts both `Z` and explicit-offset forms;
        # naive ISO 8601 (no offset) parses successfully but yields
        # ``tzinfo is None`` and is defensively dropped. Non-ISO input
        # (RFC 822, garbage) raises ``ValueError`` and is also dropped.
        try:
            published = datetime.fromisoformat(pubdate_raw)
        except (TypeError, ValueError):
            return None
        if published.tzinfo is None:
            return None
        published_utc = published.astimezone(UTC)

        # AC-7.2: strip HTML defensively (Yahoo titles are plain text in
        # practice, but feed authors sometimes escape entities).
        title = strip_html(title_raw)
        if not title:
            return None

        # raw_metadata: provenance bag (R8 — strings only, no nesting).
        # <guid> may be missing; <source> is OPTIONAL on Yahoo and
        # defaults to "" when absent (per L6.5 edge-case note).
        guid = (entry.findtext("guid") or "").strip()
        source_elem = entry.find("source")
        rss_source = ""
        if source_elem is not None and source_elem.text:
            rss_source = source_elem.text.strip()

        raw_metadata: dict[str, str] = {
            "guid": guid,
            "rss_source": rss_source,
        }

        try:
            return NormalizedItem(
                source_name=self.name,
                category=self.category,
                title=title,
                # Per L6.5: summary=None — feed has no <description>.
                summary=None,
                url=link_raw,
                published_at=published_utc,
                raw_metadata=raw_metadata,
            )
        except ValidationError:
            # Per-entry pydantic rejection (e.g. URL host issues that
            # passed the scheme guard but failed HttpUrl validation).
            return None

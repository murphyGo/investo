"""Yonhap 마켓+ RSS adapter — first Korean-language ``news`` source.

Implements the algorithm from
``aidlc-docs/construction/u1-sources/functional-design/business-logic-model.md``
L6.7 (added 2026-05-01 — Extension #3). Single-URL RSS 2.0 feed of the
Yonhap News Agency 마켓+ desk; no per-symbol parameter, no compliance
header, no env-var override. The canonical pattern reference is
:mod:`investo.sources.fomc_rss` (FD L6.1) — same RSS 2.0 + RFC-822
``<pubDate>`` shape.

Design choices (audit log 2026-05-01T06:00:00Z):

* **CDATA-wrapped Korean text** in ``<title>`` and ``<description>`` —
  :func:`defusedxml.ElementTree.fromstring` returns the inner text
  transparently (CDATA wrappers are unwrapped by the XML parser before
  ``findtext`` ever sees the value). :func:`_sanitize.strip_html`
  additionally removes any embedded HTML tags inside the CDATA payload.
* **``<dc:creator>`` is OPTIONAL** — fully-qualified namespace lookup
  (``{http://purl.org/dc/elements/1.1/}creator``). When the element is
  present, the trimmed text is mapped to ``raw_metadata["creator"]``;
  when absent, the ``creator`` key is OMITTED entirely (NOT emitted as
  empty string — see FD L6.7 edge case + business-rules R8).
* **``<pubDate>`` is RFC-822 with ``+0900`` (KST) offset** —
  :func:`email.utils.parsedate_to_datetime` handles the offset natively
  and returns a tz-aware datetime. We convert to UTC before stamping
  :attr:`NormalizedItem.published_at` (R8).
* **Strict R7** — Yonhap publishes Korean market news continuously
  during KST trading hours and through the evening; no cadence gap, so
  R11's relaxation clause does NOT apply. Window filter is the
  half-open ``[start_utc, end_utc)`` from :class:`FetchWindow`.
* **Namespaced child elements ignored** — ``<media:content>`` and any
  other ``xmlns:*`` element under ``<item>`` is naturally not matched
  by ``findtext("local_name")`` (which uses unprefixed local names),
  so no string-substitution namespace stripping is needed.
* **No ``_USER_AGENT`` constant** — Yonhap does not require a
  compliance header; R14 does NOT apply to this source. The
  ``investo-fixture-recorder@example.com`` UA visible in
  ``meta.json`` is purely for fixture-provenance audit and is NOT used
  by the production adapter.

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
from investo.sources._xml_namespaces import DC_CREATOR
from investo.sources.protocol import SourceFetchError

_ALLOWED_SCHEMES = ("http", "https")


@register
class YonhapMarketAdapter:
    """Adapter for the Yonhap News Agency 마켓+ RSS 2.0 feed (FD L6.7).

    Stateless per FD R3 — no per-call state and the shared
    :class:`httpx.AsyncClient` is injected by the aggregator.
    """

    name: ClassVar[str] = "yonhap-market"
    category: ClassVar[Category] = "news"

    _FEED_URL: ClassVar[str] = "https://www.yna.co.kr/rss/market.xml"

    async def fetch(
        self,
        client: httpx.AsyncClient,
        window: FetchWindow,
    ) -> list[NormalizedItem]:
        response = await retry_get(client, self._FEED_URL, source_name=self.name)
        try:
            # Pass response.content (bytes) so the parser honours the
            # XML-declared UTF-8 encoding rather than relying on httpx's
            # response.text str-decoding heuristic.
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
        # by the safe ``defusedxml`` parser. Typed as ``Any`` to avoid
        # touching the stdlib XML module under ``src/investo/sources``
        # (NFR-007 AC-7.6 grep).
        title_raw = (entry.findtext("title") or "").strip()
        link_raw = (entry.findtext("link") or "").strip()
        pubdate_raw = (entry.findtext("pubDate") or "").strip()
        if not title_raw or not link_raw or not pubdate_raw:
            return None

        # AC-7.3: only http/https URLs accepted.
        if urlparse(link_raw).scheme not in _ALLOWED_SCHEMES:
            return None

        # AC-7.4: <pubDate> is RFC-822 with +0900 offset
        # (e.g. "Fri, 1 May 2026 23:53:48 +0900"). parse_rfc822_to_utc
        # returns a tz-aware UTC datetime when the input carries an
        # offset; naive or unparseable input raises and is dropped.
        try:
            published_utc = parse_rfc822_to_utc(pubdate_raw)
        except (TypeError, ValueError):
            return None

        # AC-7.2: strip HTML from feed-derived text fields. CDATA
        # wrappers around Korean text are unwrapped by the XML parser
        # itself; strip_html additionally removes any embedded tags.
        title = strip_html(title_raw)
        if not title:
            return None
        description_raw = (entry.findtext("description") or "").strip()
        summary = strip_html(description_raw) or None
        if summary and len(summary) > SUMMARY_MAX_LEN:
            summary = summary[:SUMMARY_MAX_LEN]

        # raw_metadata: provenance bag (R8 — strings only, no nesting).
        # <dc:creator> is OPTIONAL per FD L6.7 — the key is OMITTED
        # entirely when absent (do NOT emit empty string).
        raw_metadata: dict[str, str] = {}
        guid = (entry.findtext("guid") or "").strip()
        if guid:
            raw_metadata["guid"] = guid
        creator_raw = entry.findtext(DC_CREATOR)
        if creator_raw is not None:
            creator = creator_raw.strip()
            if creator:
                raw_metadata["creator"] = creator

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

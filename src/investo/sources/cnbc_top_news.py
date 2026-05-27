"""CNBC US Top News RSS adapter — third Extension #3 ``news`` source.

Implements the algorithm from
``aidlc-docs/construction/u1-sources/functional-design/business-logic-model.md``
L6.9 (added 2026-05-01 — Extension #3). Single-URL RSS 2.0 feed of the
CNBC "US Top News and Analysis" channel; no per-symbol parameter, no
compliance header, no env-var override. The canonical pattern reference
is :mod:`investo.sources.fomc_rss` (FD L6.1) — same RSS 2.0 + RFC-822
``<pubDate>`` shape.

Design choices (audit log 2026-05-01T06:00:00Z):

* **Namespace-prefixed elements are EXPLICITLY IGNORED**. The CNBC feed
  declares ``xmlns:metadata``, ``xmlns:atom``, ``xmlns:content`` (and
  may add ``xmlns:media`` / ``xmlns:cn`` in future) at the ``<rss>``
  root and emits ``<metadata:type>``, ``<metadata:id>``,
  ``<metadata:sponsored>`` (etc.) children inside each ``<item>``.
  ``_normalize_entry`` reads ONLY the unprefixed local names (``title``,
  ``link``, ``pubDate``, ``description``, ``guid``) via
  :meth:`Element.findtext`, which natively does not match qualified
  names — so namespaced siblings are filtered out by the lookup itself.
  **No string-substitution namespace stripping** is used (same
  anti-pattern guard as FD L6.6). No ``metadata:*`` / ``media:*`` /
  ``cn:*`` key ever appears in :attr:`NormalizedItem.raw_metadata`.
* **No ``<creator>`` / ``<dc:creator>`` lookup**. The CNBC feed has NO
  creator element on any item; per FD L6.9 this is the spec-correct
  feed shape, not a bug, so the adapter does not even attempt the
  lookup. ``raw_metadata`` carries ``{"guid": str}`` only.
* **``<pubDate>`` is RFC-822 with ``GMT`` zone** (e.g.
  ``"Fri, 01 May 2026 14:29:59 GMT"``).
  :func:`email.utils.parsedate_to_datetime` treats ``GMT`` as ``+0000``
  and returns a tz-aware datetime; converting to UTC is then the
  identity. Naive results (defensive) are dropped.
* **Strict R7** — CNBC publishes 24/7 with no cadence gap, so R11's
  relaxation clause does NOT apply. Window filter is the half-open
  ``[start_utc, end_utc)`` from :class:`FetchWindow`.
* **No ``_USER_AGENT`` constant** — CNBC does not require a compliance
  header; R14 does NOT apply to this source. The
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
from investo.sources.protocol import SourceFetchError

_ALLOWED_SCHEMES = ("http", "https")


@register
class CnbcTopNewsAdapter:
    """Adapter for the CNBC US Top News RSS 2.0 feed (FD L6.9).

    Stateless per FD R3 — no per-call state and the shared
    :class:`httpx.AsyncClient` is injected by the aggregator.
    """

    name: ClassVar[str] = "cnbc-top-news"
    category: ClassVar[Category] = "news"

    _FEED_URL: ClassVar[str] = "https://www.cnbc.com/id/100003114/device/rss/rss.html"

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
        #
        # Per FD L6.9: read ONLY unprefixed local names. ``findtext``
        # does NOT match qualified namespace names (e.g.
        # ``{http://search.cnbc.com/rss/2.0/modules/siteContentMetadata}type``)
        # so ``<metadata:type>`` and any other namespaced sibling is
        # naturally ignored — no explicit filter needed, no string
        # namespace stripping.
        title_raw = (entry.findtext("title") or "").strip()
        link_raw = (entry.findtext("link") or "").strip()
        pubdate_raw = (entry.findtext("pubDate") or "").strip()
        if not title_raw or not link_raw or not pubdate_raw:
            return None

        # AC-7.3: only http/https URLs accepted.
        if urlparse(link_raw).scheme not in _ALLOWED_SCHEMES:
            return None

        # AC-7.4: <pubDate> is RFC-822 with GMT zone (e.g.
        # "Fri, 01 May 2026 14:29:59 GMT"). parse_rfc822_to_utc treats
        # GMT as +0000 and returns a tz-aware UTC datetime; naive or
        # unparseable input raises and is dropped.
        try:
            published_utc = parse_rfc822_to_utc(pubdate_raw)
        except (TypeError, ValueError):
            return None

        # AC-7.2: strip HTML defensively. CDATA wrappers are unwrapped
        # by the XML parser before findtext sees the value; strip_html
        # additionally removes any embedded markup.
        title = strip_html(title_raw)
        if not title:
            return None
        description_raw = (entry.findtext("description") or "").strip()
        summary = strip_html(description_raw) or None
        if summary and len(summary) > SUMMARY_MAX_LEN:
            summary = summary[:SUMMARY_MAX_LEN]

        # raw_metadata: provenance bag (R8 — strings only, no nesting).
        # Per FD L6.9: ``guid`` only. The CNBC feed has no <creator>
        # element; namespace-prefixed siblings are NOT surfaced.
        raw_metadata: dict[str, str] = {}
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
                published_at=published_utc,
                raw_metadata=raw_metadata,
            )
        except ValidationError:
            # Per-entry pydantic rejection (e.g. URL host issues that
            # passed the scheme guard but failed HttpUrl validation).
            # Drop the entry; sibling entries continue.
            return None

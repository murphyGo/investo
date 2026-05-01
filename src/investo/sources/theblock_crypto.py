"""The Block crypto RSS adapter — first crypto-narrative ``news`` source.

Implements the algorithm from
``aidlc-docs/construction/u1-sources/functional-design/business-logic-model.md``
L6.8 (added 2026-05-01 — Extension #3). Single-URL RSS 2.0 feed of
The Block (theblock.co), a crypto-native news outlet covering
Bitcoin / DeFi / blockchain markets. No per-symbol parameter, no
compliance header, no env-var override. The canonical pattern
reference is :mod:`investo.sources.fomc_rss` (FD L6.1) — same RSS 2.0
+ RFC-822 ``<pubDate>`` shape — and the immediate sibling is
:mod:`investo.sources.yonhap_market` (FD L6.7) which also reads
``<dc:creator>``.

Design choices (audit log 2026-05-01T06:00:00Z):

* **URL canonicalization** — every ``<link>`` in the recorded feed
  carries a ``?utm_source=rss&utm_medium=rss`` query suffix. The
  adapter strips all ``utm_*`` keys (``utm_source``, ``utm_medium``,
  ``utm_campaign``, ``utm_term``, ``utm_content``) via the
  module-private :func:`_strip_tracking_params` helper BEFORE the
  canonical URL is stamped on :class:`NormalizedItem`. The original
  tracked URL is NOT stored anywhere (no ``raw_metadata.original_url``
  — single source of truth, per FD L6.8). The helper is intentionally
  per-adapter (not promoted to ``_sanitize`` / ``_config``); if a
  second adapter ever needs the same logic, Planner extracts it
  behind a new R-rule.
* **``<content:encoded>`` is IGNORED** — the namespaced element is
  not read; only the unprefixed ``<description>`` is consumed (and
  truncated to 280 chars per R8). ``findtext("description")`` matches
  only unprefixed local names, so the namespaced sibling is naturally
  not picked up — no string-substitution namespace stripping needed.
* **``<dc:creator>`` is OPTIONAL** — fully-qualified namespace lookup
  (``{http://purl.org/dc/elements/1.1/}creator``). When present, the
  trimmed text is mapped to ``raw_metadata["creator"]``; when absent,
  the ``creator`` key is OMITTED entirely (NOT empty string — same
  invariant as L6.7).
* **``<category>`` is OPTIONAL and may repeat** — items typically
  carry several ``<category>`` elements (e.g. ``Markets``, ``DeFi``,
  ``Bitcoin``). When at least one is present, the trimmed text values
  are joined with ``,`` into ``raw_metadata["categories"]`` (a single
  string, R8 — flat ``dict[str, str]`` only). When zero ``<category>``
  elements are present, the ``categories`` key is OMITTED.
* **``<pubDate>`` is RFC-822 with ``-0400`` (US/Eastern EDT) offset**
  — :func:`email.utils.parsedate_to_datetime` handles the offset
  natively and returns a tz-aware datetime. We convert to UTC before
  stamping :attr:`NormalizedItem.published_at` (R8).
* **Strict R7** — The Block publishes intraday with weekend slowdown
  (not absence); no cadence gap, so R11's relaxation clause does NOT
  apply. Window filter is the half-open ``[start_utc, end_utc)``
  from :class:`FetchWindow`.
* **No ``_USER_AGENT`` constant** — The Block does not require a
  compliance header; R14 does NOT apply. The
  ``investo-fixture-recorder@example.com`` UA visible in
  ``meta.json`` is purely for fixture-provenance audit and is NOT
  used by the production adapter.

Pins NFR-007 ACs:

* AC-7.2 — title and summary HTML stripped via :mod:`_sanitize`
* AC-7.3 — items with non-http/https URLs are dropped (after
  ``utm_*`` stripping; the helper preserves scheme/netloc)
* AC-7.4 — ``<pubDate>`` parsed to a tz-aware UTC datetime
* AC-7.6 — XML parsed via ``defusedxml`` (never stdlib ElementTree)
"""

from __future__ import annotations

from datetime import UTC
from email.utils import parsedate_to_datetime
from typing import Any, ClassVar
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import httpx
from defusedxml.ElementTree import ParseError, fromstring
from pydantic import ValidationError

from investo.models import Category, NormalizedItem
from investo.sources._registry import register
from investo.sources._retry import retry_get
from investo.sources._sanitize import strip_html
from investo.sources._window import FetchWindow
from investo.sources.protocol import SourceFetchError

_SUMMARY_MAX_LEN = 280
_ALLOWED_SCHEMES = ("http", "https")
_NS_DC_CREATOR = "{http://purl.org/dc/elements/1.1/}creator"
_TRACKING_PARAM_KEYS = frozenset(
    {
        "utm_source",
        "utm_medium",
        "utm_campaign",
        "utm_term",
        "utm_content",
    }
)


def _strip_tracking_params(url: str) -> str:
    """Return ``url`` with all ``utm_*`` query parameters removed.

    Strips ``utm_source``, ``utm_medium``, ``utm_campaign``,
    ``utm_term``, ``utm_content`` from the query component (case
    sensitive — The Block emits all lowercase). All other query
    parameters are preserved in their original order. The URL
    fragment is preserved unchanged.

    If no query parameters remain after stripping, the rebuilt URL
    has no ``?`` at all (we pass ``""`` for the query component to
    :func:`urlunparse`, which omits the separator). Inputs without
    a parsable scheme/netloc are returned unchanged as a defensive
    no-op (the adapter's AC-7.3 scheme guard subsequently drops
    them).

    This helper is per-adapter (FD L6.8) — NOT promoted to
    ``_sanitize`` or ``_config``. If a second adapter ever needs
    the same logic, Planner extracts it behind a new R-rule.
    """
    parsed = urlparse(url)
    if not parsed.scheme or not parsed.netloc:
        return url
    pairs = parse_qsl(parsed.query, keep_blank_values=False)
    kept = [(k, v) for k, v in pairs if k not in _TRACKING_PARAM_KEYS]
    new_query = urlencode(kept)
    return urlunparse(
        (
            parsed.scheme,
            parsed.netloc,
            parsed.path,
            parsed.params,
            new_query,
            parsed.fragment,
        )
    )


@register
class TheBlockCryptoAdapter:
    """Adapter for The Block crypto-news RSS 2.0 feed (FD L6.8).

    Stateless per FD R3 — no per-call state and the shared
    :class:`httpx.AsyncClient` is injected by the aggregator.
    """

    name: ClassVar[str] = "theblock-crypto"
    category: ClassVar[Category] = "news"

    _FEED_URL: ClassVar[str] = "https://www.theblock.co/rss.xml"

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

        # FD L6.8: canonicalize the URL by stripping utm_* tracking
        # parameters BEFORE the AC-7.3 scheme check. The helper
        # preserves scheme / netloc / fragment, so a previously
        # http(s) URL stays http(s).
        canonical_url = _strip_tracking_params(link_raw)

        # AC-7.3: only http/https URLs accepted.
        if urlparse(canonical_url).scheme not in _ALLOWED_SCHEMES:
            return None

        # AC-7.4: <pubDate> is RFC-822 with -0400 offset
        # (e.g. "Fri, 01 May 2026 10:35:20 -0400"). parsedate_to_datetime
        # returns a tz-aware datetime when the input carries an offset;
        # naive results indicate malformed input — drop.
        try:
            published = parsedate_to_datetime(pubdate_raw)
        except (TypeError, ValueError):
            return None
        if published is None or published.tzinfo is None:
            return None
        published_utc = published.astimezone(UTC)

        # AC-7.2: strip HTML from feed-derived text fields. <title> on
        # The Block is plain text (no CDATA, no embedded markup) but we
        # apply strip_html defensively for entity decoding consistency.
        title = strip_html(title_raw)
        if not title:
            return None
        # IMPORTANT: we read ONLY <description>, never <content:encoded>
        # (FD L6.8). findtext("description") matches the unprefixed local
        # name — the content:encoded namespaced sibling is not picked up.
        description_raw = (entry.findtext("description") or "").strip()
        summary = strip_html(description_raw) or None
        if summary and len(summary) > _SUMMARY_MAX_LEN:
            summary = summary[:_SUMMARY_MAX_LEN]

        # raw_metadata: provenance bag (R8 — strings only, no nesting).
        # Optional keys (creator, categories) are OMITTED when absent
        # (do NOT emit empty string).
        raw_metadata: dict[str, str] = {}
        guid = (entry.findtext("guid") or "").strip()
        if guid:
            raw_metadata["guid"] = guid
        creator_raw = entry.findtext(_NS_DC_CREATOR)
        if creator_raw is not None:
            creator = creator_raw.strip()
            if creator:
                raw_metadata["creator"] = creator
        # <category> is repeated (one element per tag). entry.iter
        # walks all descendants which would also pull <category> from
        # nested namespaced elements; entry.findall("category") only
        # matches direct unprefixed <category> children, which is what
        # we want.
        category_values: list[str] = []
        for category_elem in entry.findall("category"):
            text = (category_elem.text or "").strip()
            if text:
                category_values.append(text)
        if category_values:
            raw_metadata["categories"] = ",".join(category_values)

        try:
            return NormalizedItem(
                source_name=self.name,
                category=self.category,
                title=title,
                summary=summary,
                url=canonical_url,
                published_at=published_utc,
                raw_metadata=raw_metadata,
            )
        except ValidationError:
            # Per-entry pydantic rejection (e.g. URL host issues that
            # passed the scheme guard but failed HttpUrl validation).
            # Drop the entry; sibling entries continue.
            return None

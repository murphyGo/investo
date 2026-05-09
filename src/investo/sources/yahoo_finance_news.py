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

u47 (added 2026-05-10 — content filter): the rssindex feed mixes
generic personal-finance product-comparison headlines (CD rates / HELOC
/ mortgage / savings / insurance / retirement) into the same channel as
market-signal news. The 2026-05-09 cron US-equity quality retro found
~10/24 in-window items were such noise. Filtering at the adapter layer
(*before* a :class:`NormalizedItem` is yielded, *after* the strict
window filter) is the cheapest cut: Stage 1 LLM never sees them, so
neither token budget nor Stage 2's candidate pool is contaminated.
A single batch-level INFO log emits the blocked count + matched
patterns as the canary; a 100%-block batch escalates to WARNING.

Pins NFR-007 ACs:

* AC-7.2 — title HTML stripped via :mod:`_sanitize`
* AC-7.3 — items with non-http/https URLs are dropped (not stored)
* AC-7.4 — ``<pubDate>`` parsed to a tz-aware UTC datetime
* AC-7.6 — XML parsed via ``defusedxml`` (never stdlib ElementTree)
"""

from __future__ import annotations

import logging
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

_logger = logging.getLogger(__name__)

_ALLOWED_SCHEMES = ("http", "https")
_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/124 Safari/537.36"
)

# u47 — personal-finance noise deny patterns (case-insensitive substring).
# Matched against the lowercased ``title`` first; for the "personal finance"
# fallback the haystack is widened to include the article URL path and the
# ``<source>`` text because Yahoo flags its product-comparison stories with
# the ``finance.yahoo.com/personal-finance/...`` URL prefix and a
# ``Yahoo Personal Finance`` source attribution rather than putting the
# phrase in the headline.
_PERSONAL_FINANCE_DENY_PATTERNS: tuple[str, ...] = (
    "cd rates",
    "heloc",
    "home equity loan rates",
    "mortgage and refinance",
    "mortgage and refi rates",
    "high-yield savings",
    "money market account rates",
    "long-term care insurance",
    "retirement costs",
    "personal finance",
)

# Patterns that should match against the broader haystack (title + URL +
# source text) rather than the title alone. Yahoo's personal-finance
# category prefix never appears in headline text, so a title-only match
# would miss every real instance.
_PERSONAL_FINANCE_BROAD_HAYSTACK_PATTERNS: frozenset[str] = frozenset({"personal finance"})


def _personal_finance_patterns_hit(
    title: str,
    url: str,
    rss_source: str,
) -> tuple[str, ...]:
    """Return the deny patterns matched by this entry, deduped + sorted.

    Empty tuple = entry is not personal-finance noise. The sort makes the
    canary log line stable for the same input, simplifying CI grep.
    """
    title_lower = title.lower()
    # In the URL+source haystack we normalise kebab-case path separators
    # to spaces so the deny pattern ``"personal finance"`` matches the
    # canonical Yahoo URL prefix ``finance.yahoo.com/personal-finance/...``
    # without requiring a parallel hyphenated pattern.
    broad_lower = f"{title_lower} {url.lower()} {rss_source.lower()}".replace("-", " ").replace(
        "/", " "
    )
    hits: set[str] = set()
    for pattern in _PERSONAL_FINANCE_DENY_PATTERNS:
        haystack = (
            broad_lower if pattern in _PERSONAL_FINANCE_BROAD_HAYSTACK_PATTERNS else title_lower
        )
        if pattern in haystack:
            hits.add(pattern)
    return tuple(sorted(hits))


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
        in_window_total = 0
        filtered_count = 0
        all_pattern_hits: set[str] = set()
        for entry in root.iter("item"):
            normalized = self._normalize_entry(entry)
            if normalized is None:
                continue
            if not window.contains(normalized.published_at):
                continue
            in_window_total += 1
            # u47: personal-finance noise filter. URL is reconstructed
            # from str(HttpUrl) — pydantic preserves scheme/host/path
            # verbatim, which is what the broad-haystack patterns need.
            # ``raw_metadata`` is a heterogeneous str|int|float bag per
            # the model contract, but this adapter always stores
            # ``rss_source`` as a string (defaulting to ``""``). ``str(...)``
            # both narrows for mypy and is a defensive coerce.
            rss_source_raw = normalized.raw_metadata.get("rss_source", "")
            patterns = _personal_finance_patterns_hit(
                normalized.title,
                str(normalized.url) if normalized.url is not None else "",
                str(rss_source_raw),
            )
            if patterns:
                filtered_count += 1
                all_pattern_hits.update(patterns)
                continue
            items.append(normalized)
        self._emit_filter_canary(filtered_count, in_window_total, all_pattern_hits)
        return items

    def _emit_filter_canary(
        self,
        filtered: int,
        total: int,
        patterns_hit: set[str],
    ) -> None:
        # No items entered the in-window pool → nothing to report; the
        # aggregator already logs zero-item collection separately.
        if total == 0:
            return
        # No noise blocked → quiet. The canary exists for tuning the deny
        # list; an all-clean batch is the desired steady state.
        if filtered == 0:
            return
        sorted_patterns = sorted(patterns_hit)
        message = (
            f"yahoo-finance-news: filtered {filtered}/{total} items as personal-finance "
            f"noise (patterns: {', '.join(sorted_patterns)})"
        )
        extra: dict[str, object] = {
            "source_name": self.name,
            "filtered": filtered,
            "total": total,
            "patterns_hit": sorted_patterns,
        }
        if filtered == total:
            # 100% block → either the deny list is too broad or the feed
            # is having a bad day. Operators should look.
            _logger.warning(message, extra=extra)
        else:
            _logger.info(message, extra=extra)

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

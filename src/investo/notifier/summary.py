"""Telegram channel summary formatter (FR-004).

This is the **formatting** half of the notifier summary split (u80).
It turns the structured data produced by
:mod:`investo.notifier._summary_extract` (conclusion / coverage /
market-snapshot / watchlist) and the imminent-event tag produced by
:mod:`investo.notifier._events` into Telegram-safe message strings:
percent / price formatting, markdown-token cleanup for the plain-text
fallback, watchlist price decoration, segment-block assembly, and the
UTF-16-bounded truncation.

``build_summary`` composes the single-briefing public-channel preview
text; ``build_segmented_summary`` composes the multi-segment message.

Telegram's ``sendMessage`` text-field limit is **4096 UTF-16 code
units**, NOT 4096 characters. Non-BMP characters (emoji like 📈,
certain CJK ideographs) consume 2 code units per Python codepoint,
so ``len(s)`` would under-count and risk exceeding the limit. The
truncation here uses the shared :mod:`investo._internal.text` helpers
(``utf16_units`` / ``utf16_truncate``, delivered in u79) — the same
formula the :class:`BriefingNotification` model validator enforces.

Reference:
    aidlc-docs/inception/application-design/component-methods.md (C4)
    aidlc-docs/construction/plans/u4-notifier-code-generation-plan.md
        (Step 3)
    aidlc-docs/construction/plans/u80-notifier-decomposition-and-dispatcher-base-code-generation-plan.md
"""

from __future__ import annotations

import os
import re
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import Final

from investo._internal.text import utf16_truncate as _utf16_truncate
from investo._internal.text import utf16_units as _utf16_units
from investo.models import Briefing, NormalizedItem
from investo.models.segments import (
    CRYPTO,
    DOMESTIC_EQUITY,
    SEGMENT_LABELS,
    US_EQUITY,
    MarketSegment,
    SegmentCoverage,
)
from investo.notifier import _summary_extract as _extract
from investo.notifier._events import imminent_event_tag
from investo.notifier._summary_extract import SnapshotEntry

# Telegram's hard cap. Mirrors the constant in
# ``investo.models.briefing`` (``TELEGRAM_MESSAGE_LIMIT``); kept local
# here so callers don't need to reach into models for a number they're
# already passing in.
DEFAULT_MAX_UNITS: Final[int] = 4096

# Truncation suffix. 1 UTF-16 unit (BMP character).
_TRUNCATION_SUFFIX: Final[str] = "…"
# Markdown→plain-text fallback regexes (formatting concern: used only by
# ``plain_text_summary`` when the Markdown parse_mode send is rejected).
_MARKDOWN_LINK_WITH_URL_RE: Final[re.Pattern[str]] = re.compile(r"!?\[([^\]]*)\]\(([^)]+)\)")
_MARKDOWN_TOKEN_RE: Final[re.Pattern[str]] = re.compile(r"[*_`~]+")
_SEGMENT_ICONS: Final[dict[MarketSegment, str]] = {
    DOMESTIC_EQUITY: "🇰🇷",
    US_EQUITY: "🇺🇸",
    CRYPTO: "₿",
}

# u30 Step 2 — segment toggle env var. Comma-separated list of segment
# names (``domestic-equity`` / ``us-equity`` / ``crypto``); empty / unset
# means all segments emit. Unknown tokens are dropped silently. The
# parser accepts both the canonical segment ids (matching
# :data:`investo.briefing.segments.MarketSegment`) and the legacy short
# aliases (``domestic`` / ``us`` / ``crypto``) so the operator can write
# either style without surprise.
_ENABLED_SEGMENTS_ENV: Final[str] = "INVESTO_TELEGRAM_ENABLED_SEGMENTS"
_SEGMENT_ALIASES: Final[dict[str, MarketSegment]] = {
    "domestic-equity": DOMESTIC_EQUITY,
    "domestic": DOMESTIC_EQUITY,
    "kr": DOMESTIC_EQUITY,
    "us-equity": US_EQUITY,
    "us": US_EQUITY,
    "crypto": CRYPTO,
}


def build_summary(
    briefing: Briefing,
    *,
    site_url: str,
    max_units: int = DEFAULT_MAX_UNITS,
) -> str:
    """Build the public-channel summary text for ``briefing``.

    Returns a string fitting within ``max_units`` UTF-16 code units.
    The footer (``상세보기: {site_url}``) is always preserved; the
    body (``briefing.market_summary``) is truncated with a "…"
    suffix when it would overflow.
    """
    header = f"📈 {briefing.target_date.isoformat()} 시황 요약\n\n"
    footer = f"\n\n{_detail_link(site_url)}"

    fixed_units = _utf16_units(header) + _utf16_units(footer)
    body_budget = max_units - fixed_units

    body = briefing.market_summary

    if _utf16_units(body) <= body_budget:
        return header + body + footer

    # Need to truncate. Leave room for the 1-unit suffix.
    truncated = _utf16_truncate(body, body_budget - _utf16_units(_TRUNCATION_SUFFIX))
    return header + truncated + _TRUNCATION_SUFFIX + footer


def build_segmented_summary(
    briefings: Mapping[MarketSegment, Briefing],
    *,
    site_urls: Mapping[MarketSegment, str],
    max_units: int = DEFAULT_MAX_UNITS,
    lookahead_items_by_segment: Mapping[MarketSegment, Sequence[NormalizedItem]] | None = None,
    now_utc: datetime | None = None,
    price_items: Sequence[NormalizedItem] = (),
    coverage_by_segment: Mapping[MarketSegment, SegmentCoverage] | None = None,
    enabled_segments: Sequence[MarketSegment] | None = None,
    missing_segments: Sequence[MarketSegment] = (),
) -> str:
    """Build one Telegram message with all segment summaries and links.

    The three URLs are repeated in the segment blocks and the fixed
    footer. The footer is always preserved; segment summary lines are
    truncated first if needed.

    u35 — when ``lookahead_items_by_segment`` is supplied, each
    segment's one-line summary is prepended with a deterministic
    imminent-event tag (e.g. ``📅 FOMC D-2``) computed from the
    forward-scheduled items in that segment. The tag is **not**
    LLM-generated; it is derived entirely from
    ``NormalizedItem.scheduled_at`` and ``now_utc`` (defaulting to the
    current time when ``None``). Absence of imminent items leaves the
    line unchanged.

    u30 Step 2 — when ``coverage_by_segment`` is supplied and the entry
    for a given segment reports ``status == "failed"`` (legacy
    ``insufficient`` mapped to ``failed`` per u54 enum migration),
    that segment's block collapses to a single line that combines the
    icon, label, ``[실패]`` tag, and the detail link. The conclusion
    line is omitted because the segment markdown itself is the data-
    limited fallback (``데이터 부족`` boilerplate). When omitted or
    when the segment is not present in the mapping, the legacy 3-line
    block rendering is preserved.

    u30 Step 2 — when ``enabled_segments`` is supplied (resolved
    upstream from ``INVESTO_TELEGRAM_ENABLED_SEGMENTS`` via
    :func:`resolve_enabled_segments`), only the listed segments emit
    bodies and footer entries. If the resolved list filters out every
    published segment, the function falls back to rendering all
    published segments — operator misconfiguration must not produce a
    completely link-less alert.
    """
    ordered_segments = (DOMESTIC_EQUITY, US_EQUITY, CRYPTO)
    all_published = tuple(segment for segment in ordered_segments if segment in briefings)
    if not all_published:
        raise ValueError("segmented summary requires at least one briefing")
    # u43 / DEBT-067 M1 — clock-explicit contract: when the caller
    # supplies ``lookahead_items_by_segment`` it must also pass
    # ``now_utc`` explicitly. Falling back to ``datetime.now(UTC)``
    # would couple the notifier to wall-clock time and make the
    # deterministic D-N selector non-reproducible. The invariant fires
    # before any rendering so tests see a clean ``ValueError`` rather
    # than a partially-built summary.
    if lookahead_items_by_segment is not None and now_utc is None:
        raise ValueError("now_utc required when lookahead_items_by_segment is supplied")
    if enabled_segments is not None:
        allowed = set(enabled_segments)
        filtered = tuple(segment for segment in all_published if segment in allowed)
        published_segments = filtered if filtered else all_published
    else:
        published_segments = all_published
    target_date = briefings[published_segments[0]].target_date
    snapshot = _market_snapshot_line(price_items)
    resolved_now = now_utc if now_utc is not None else datetime.now(tz=UTC)
    publish_label = _publish_time_label(resolved_now, target_date=target_date)
    header = f"📈 {target_date.isoformat()} 데일리 시황\n"
    header += f"{publish_label}\n"
    partial_line = _partial_publish_line(missing_segments)
    if partial_line:
        header += f"{partial_line}\n"
    if snapshot:
        header += f"{snapshot}\n\n"
    else:
        header += "\n"
    footer = "\n\n링크 모음:\n" + "\n".join(
        f"• {SEGMENT_LABELS[segment]}: {_detail_link(site_urls[segment])}"
        for segment in published_segments
    )
    price_index = _build_watchlist_price_index(price_items)
    body = "\n\n".join(
        _segment_summary_block(
            segment,
            briefings[segment],
            site_urls[segment],
            lookahead_items=(
                lookahead_items_by_segment.get(segment, ())
                if lookahead_items_by_segment is not None
                else ()
            ),
            now_utc=resolved_now,
            coverage=(
                coverage_by_segment.get(segment) if coverage_by_segment is not None else None
            ),
            watchlist_prices=price_index,
        )
        for segment in published_segments
    )

    fixed_units = _utf16_units(header) + _utf16_units(footer)
    if fixed_units > max_units:
        raise ValueError(
            f"segmented summary fixed content exceeds {max_units} UTF-16 units: {fixed_units}"
        )

    body_budget = max_units - fixed_units
    if _utf16_units(body) <= body_budget:
        return header + body + footer

    if body_budget <= _utf16_units(_TRUNCATION_SUFFIX):
        return header + footer

    truncated = _utf16_truncate(body, body_budget - _utf16_units(_TRUNCATION_SUFFIX))
    return header + truncated + _TRUNCATION_SUFFIX + footer


def plain_text_summary(markdown_summary: str) -> str:
    """Return a readable plain-text fallback for a Markdown-formatted summary."""
    text = _MARKDOWN_LINK_WITH_URL_RE.sub(r"\1: \2", markdown_summary)
    text = _MARKDOWN_TOKEN_RE.sub("", text)
    return "\n".join(line.rstrip() for line in text.splitlines()).strip()


def resolve_enabled_segments(
    raw: str | None = None,
) -> tuple[MarketSegment, ...] | None:
    """Resolve the per-channel ``enabled_segments`` toggle.

    Reads :data:`_ENABLED_SEGMENTS_ENV` when ``raw`` is ``None``. Empty
    / unset / all-tokens-unknown → returns ``None`` (caller emits every
    published segment, the historic behaviour). Otherwise the function
    returns a deterministic tuple in the canonical segment order
    (domestic-equity → us-equity → crypto). Tokens are case-insensitive
    and accept both canonical ids and short aliases (see
    :data:`_SEGMENT_ALIASES`).
    """
    text = raw if raw is not None else os.environ.get(_ENABLED_SEGMENTS_ENV, "")
    if not text:
        return None
    seen: set[MarketSegment] = set()
    for token in text.split(","):
        candidate = token.strip().lower()
        if not candidate:
            continue
        resolved = _SEGMENT_ALIASES.get(candidate)
        if resolved is not None:
            seen.add(resolved)
    if not seen:
        return None
    canonical_order = (DOMESTIC_EQUITY, US_EQUITY, CRYPTO)
    return tuple(segment for segment in canonical_order if segment in seen)


def _segment_summary_block(
    segment: MarketSegment,
    briefing: Briefing,
    site_url: str,
    *,
    lookahead_items: Sequence[NormalizedItem] = (),
    now_utc: datetime | None = None,
    coverage: SegmentCoverage | None = None,
    watchlist_prices: Mapping[str, str] | None = None,
) -> str:
    label = SEGMENT_LABELS[segment]
    icon = _SEGMENT_ICONS[segment]
    if coverage is not None and coverage.status == "failed":
        # u30 Step 2 collapsed shape — single line with status badge and
        # the detail link only. Skipping the conclusion line keeps the
        # alert dense when the segment markdown itself is the data-
        # limited fallback ("데이터 부족" boilerplate). u54 — legacy
        # ``insufficient`` enum migrated to ``failed``; label is now
        # ``[실패]``.
        return f"{icon} *{label}* [실패] · {_detail_link(site_url)}"
    status = _extract.coverage_label(briefing)
    status_tag = f" [{status}]" if status else ""
    one_line = _one_line_summary(briefing, watchlist_prices=watchlist_prices)
    imminent = imminent_event_tag(lookahead_items, now_utc=now_utc)
    if imminent:
        one_line = f"{imminent} · {one_line}"
    return f"{icon} *{label}*{status_tag}\n{_detail_link(site_url)}\n{one_line}"


def _partial_publish_line(missing_segments: Sequence[MarketSegment]) -> str:
    if not missing_segments:
        return ""
    labels = ", ".join(SEGMENT_LABELS[segment] for segment in missing_segments)
    return f"⚠️ 부분 발행: {labels} 생성 실패"


def _detail_link(site_url: str) -> str:
    return f"[상세보기]({site_url})"


def _market_snapshot_line(price_items: Sequence[NormalizedItem]) -> str:
    entries = _extract.market_snapshot_entries(price_items)
    parts = [_format_snapshot_entry(entry) for entry in entries]
    return "시장: " + " / ".join(parts) if parts else ""


def _format_snapshot_entry(entry: SnapshotEntry) -> str:
    if entry.with_price:
        if entry.price is not None and entry.pct is not None:
            return f"{entry.label} {_format_compact_price(entry.price)}({_format_pct(entry.pct)})"
        if entry.pct is not None:
            return f"{entry.label} {_format_pct(entry.pct)}"
        if entry.price is not None:
            return f"{entry.label} {_format_compact_price(entry.price)}"
        return entry.label
    return f"{entry.label} {_format_pct(entry.pct)}" if entry.pct is not None else entry.label


def _format_pct(value: float) -> str:
    return f"{value:+.1f}%"


def _format_compact_price(value: float) -> str:
    if abs(value) >= 1000:
        return f"{value / 1000:.1f}k"
    if abs(value) >= 100:
        return f"{value:.0f}"
    return f"{value:.2f}"


def _one_line_summary(
    briefing: Briefing,
    *,
    watchlist_prices: Mapping[str, str] | None = None,
) -> str:
    data = _extract.conclusion_data(briefing)
    conclusion = data.conclusion
    if data.coverage_label:
        conclusion = f"{data.coverage_label} — {conclusion}"
    if data.watchlist is not None:
        decorated = _decorate_watchlist_with_prices(data.watchlist, watchlist_prices)
        return f"{conclusion} / 관심: {decorated}"
    return conclusion


def _publish_time_label(now_utc: datetime, *, target_date: object) -> str:
    """Render the publish-time / 전 거래일 header line (u30 Step 4).

    Format::

        🕐 KST HH:MM · 전 거래일: YYYY-MM-DD

    The KST clock comes from converting ``now_utc`` to Asia/Seoul; the
    "전 거래일" label echoes ``target_date`` (the briefing's data-window
    anchor) so the reader sees both *when* the alert was sent and
    *which* trading day the briefing reflects. Pure: no clock read when
    ``now_utc`` is supplied.
    """
    from datetime import datetime as _dt
    from zoneinfo import ZoneInfo

    kst = ZoneInfo("Asia/Seoul")
    if not isinstance(now_utc, _dt) or now_utc.tzinfo is None:
        # Defensive — every callsite passes a tz-aware datetime, but the
        # public API leaves ``None`` as a fallback. Fail soft by
        # treating the missing value as UTC.
        now_kst_str = "--:--"
    else:
        now_kst = now_utc.astimezone(kst)
        now_kst_str = now_kst.strftime("%H:%M")
    return f"🕐 KST {now_kst_str} · 전 거래일: {target_date}"


def _build_watchlist_price_index(
    price_items: Sequence[NormalizedItem],
) -> dict[str, str]:
    """Index price items by ticker / symbol / asset name → ``"+1.2%"`` style suffix.

    Multiple alias keys map to the same item so the watchlist match-line
    decorator can find prices by the term the user wrote (``NVDA``,
    ``엔비디아``, ``BTC``, ``Bitcoin``). Keys are stored case-folded.
    The value is a price suffix in the shape ``"(+1.2%)"`` /
    ``"(-0.5%)"`` / ``"(108.2k, +0.4%)"`` for crypto rows that carry an
    absolute price too. Empty when no price candidate yields a percent
    change.
    """
    index: dict[str, str] = {}
    for item in price_items:
        if item.category != "price":
            continue
        pct = _extract.pct_change(item)
        price = _extract.price_value(item)
        if pct is None and price is None:
            continue
        suffix = _format_watchlist_suffix(pct=pct, price=price)
        if not suffix:
            continue
        for key in _extract.watchlist_index_keys(item):
            if key:
                index.setdefault(key, suffix)
    return index


def _format_watchlist_suffix(*, pct: float | None, price: float | None) -> str:
    """Format the per-match price suffix.

    Prefers percent change alone (``"(+1.2%)"``) — for tickers the pct
    move is the reader-actionable signal. Falls back to a compact
    absolute price (``"(108.2k)"``) only when no pct is available.
    """
    if pct is not None:
        return f"({_format_pct(pct)})"
    if price is not None:
        return f"({_format_compact_price(price)})"
    return ""


def _decorate_watchlist_with_prices(
    watchlist_text: str,
    prices: Mapping[str, str] | None,
) -> str:
    """Append a price suffix to each ``TERM:`` match in the watchlist line.

    ``watchlist_text`` is the cleaned watchlist body extracted from
    ``> **내 관심 자산 영향**:`` — typically of the form
    ``"1건 확인 — NVDA: NVDA rallies after earnings"`` (single match)
    or with ``"; "`` separators between matches. We append the price
    suffix to the term portion (``NVDA`` → ``NVDA(+1.2%)``) when a
    matching price exists in ``prices``; otherwise the term stays
    ticker-only (the safe fallback).
    """
    if not prices:
        return watchlist_text
    # Split at the "건 확인 — " boundary so we only decorate the body,
    # not the count prefix.
    sep = "건 확인 — "
    if sep in watchlist_text:
        prefix, _, body = watchlist_text.partition(sep)
        prefix = f"{prefix}{sep}"
    else:
        prefix, body = "", watchlist_text

    decorated_segments: list[str] = []
    for term, rest in _extract.watchlist_match_terms(body):
        if not term:
            # Unmatched segment — pass through unchanged.
            decorated_segments.append(rest)
            continue
        suffix = prices.get(term.casefold())
        if suffix is None:
            decorated_segments.append(f"{term}: {rest}")
        else:
            decorated_segments.append(f"{term}{suffix}: {rest}")
    return f"{prefix}{'; '.join(decorated_segments)}" if decorated_segments else watchlist_text


__all__ = [
    "DEFAULT_MAX_UNITS",
    "build_segmented_summary",
    "build_summary",
    "plain_text_summary",
    "resolve_enabled_segments",
]

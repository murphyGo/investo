"""Telegram channel summary builder (FR-004).

``build_summary`` composes the public-channel preview text from a
:class:`Briefing` and a site URL pointing at the archived markdown.

Telegram's ``sendMessage`` text-field limit is **4096 UTF-16 code
units**, NOT 4096 characters. Non-BMP characters (emoji like 📈,
certain CJK ideographs) consume 2 code units per Python codepoint,
so ``len(s)`` would under-count and risk exceeding the limit.
The truncation here uses ``len(s.encode("utf-16-le")) // 2`` for
accurate counting — the same formula the
:class:`BriefingNotification` model validator enforces (defense in
depth: this function truncates; the model validator rejects any
overflow that survives).

Layout::

    📈 {target_date.isoformat()} 시황 요약

    {truncated market_summary}

    상세보기: {site_url}

The footer URL is always preserved (it's the whole point of the
summary). Body text is truncated with a trailing "…" when it
overflows the budget.

Reference:
    aidlc-docs/inception/application-design/component-methods.md (C4)
    aidlc-docs/construction/plans/u4-notifier-code-generation-plan.md
        (Step 3)
"""

from __future__ import annotations

import os
import re
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime, timedelta
from typing import Final

from investo.briefing.market_anchor import anchor_label
from investo.briefing.segments import (
    CRYPTO,
    DOMESTIC_EQUITY,
    SEGMENT_LABELS,
    US_EQUITY,
    MarketSegment,
    SegmentCoverage,
)
from investo.models import Briefing, NormalizedItem

# Telegram's hard cap. Mirrors the constant in
# ``investo.models.briefing`` (``TELEGRAM_MESSAGE_LIMIT``); kept local
# here so callers don't need to reach into models for a number they're
# already passing in.
DEFAULT_MAX_UNITS: Final[int] = 4096

# Truncation suffix. 1 UTF-16 unit (BMP character).
_TRUNCATION_SUFFIX: Final[str] = "…"
_CONCLUSION_LINE_RE: Final[re.Pattern[str]] = re.compile(
    r"^>\s*\*\*오늘의 결론\*\*:\s*(.+)$",
    re.MULTILINE,
)
_COVERAGE_LINE_RE: Final[re.Pattern[str]] = re.compile(
    r"^>\s*\*\*데이터 상태\*\*:\s*(.+)$",
    re.MULTILINE,
)
_WATCHLIST_LINE_RE: Final[re.Pattern[str]] = re.compile(
    r"^>\s*\*\*내 관심 자산 영향\*\*:\s*(.+)$",
    re.MULTILINE,
)
_MARKDOWN_LINK_RE: Final[re.Pattern[str]] = re.compile(r"!?\[([^\]]*)\]\([^)]+\)")
_MARKDOWN_LINK_WITH_URL_RE: Final[re.Pattern[str]] = re.compile(r"!?\[([^\]]*)\]\(([^)]+)\)")
_MARKDOWN_TOKEN_RE: Final[re.Pattern[str]] = re.compile(r"[*_`~]+")
_LEADING_MARKDOWN_RE: Final[re.Pattern[str]] = re.compile(
    r"^(?:>\s*)?(?:#{1,6}\s*)?(?:(?:[-*+])|\d+[.)])\s*"
)
_MEANINGFUL_TEXT_RE: Final[re.Pattern[str]] = re.compile(r"[A-Za-z0-9가-힣]")
_SEGMENT_ICONS: Final[dict[MarketSegment, str]] = {
    DOMESTIC_EQUITY: "🇰🇷",
    US_EQUITY: "🇺🇸",
    CRYPTO: "₿",
}

# u35 — imminent-event horizon for the deterministic Telegram tag.
# Events scheduled within 72 hours of the run instant qualify; the tag
# is computed by D-distance arithmetic, not by the LLM (no hallucination
# surface). Capped at top-1 by deterministic ordering (earliest first).
_IMMINENT_HORIZON: Final[timedelta] = timedelta(hours=72)
# Source-name → emoji mapping for the imminent tag prefix. New
# adapters that emit ``scheduled_at`` should register an entry here so
# the deterministic tag stays terse and source-attributable. Sources
# not in this map fall back to a generic 📅 calendar icon.
_IMMINENT_TAG_ICON: Final[dict[str, str]] = {
    "fomc-rss": "📅",
    "nasdaq-earnings-calendar": "📊",
    "fred-macro": "📈",
    "coingecko-events": "🪙",
}
_IMMINENT_TAG_FALLBACK_ICON: Final[str] = "📅"

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


def _utf16_units(text: str) -> int:
    """Return the count of UTF-16 code units in ``text``.

    Equivalent to ``len(text.encode("utf-16-le")) // 2``. Non-BMP
    code points (emoji, certain CJK) count as 2 units.
    """
    return len(text.encode("utf-16-le")) // 2


def _utf16_truncate(text: str, max_units: int) -> str:
    """Truncate ``text`` to at most ``max_units`` UTF-16 code units.

    Surrogate-pair safe: a truncation that lands between the high
    and low halves of a non-BMP code point's UTF-16 encoding is
    rolled back by one unit so the result remains valid UTF-16.
    """
    encoded = text.encode("utf-16-le")
    if len(encoded) // 2 <= max_units:
        return text
    if max_units <= 0:
        return ""
    truncated_bytes = encoded[: max_units * 2]
    # If the final unit is a high surrogate (the first half of a
    # surrogate pair), drop it to avoid emitting half a code point.
    last_unit = int.from_bytes(truncated_bytes[-2:], "little")
    if 0xD800 <= last_unit <= 0xDBFF:
        truncated_bytes = truncated_bytes[:-2]
    return truncated_bytes.decode("utf-16-le", errors="ignore")


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
    status = _coverage_label(briefing)
    status_tag = f" [{status}]" if status else ""
    one_line = _one_line_summary(briefing, watchlist_prices=watchlist_prices)
    imminent = _imminent_event_tag(lookahead_items, now_utc=now_utc)
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
    parts = [
        part
        for part in (
            _snapshot_part_for_tickers(anchor_label("^GSPC").short, price_items, ("^GSPC",)),
            # u70 — ``^IXIC`` is the Nasdaq Composite, not the Nasdaq 100
            # (``^NDX``); the canonical registry supplies the correct short
            # label so this dense surface stops emitting the "NDX" mislabel.
            _snapshot_part_for_tickers(anchor_label("^IXIC").short, price_items, ("^IXIC",)),
            _snapshot_part_for_index("KOSPI", price_items, ("코스피",)),
            _snapshot_part_for_crypto("BTC", price_items, ("BTCUSDT", "btc", "BTC")),
        )
        if part
    ]
    return "시장: " + " / ".join(parts) if parts else ""


def _snapshot_part_for_tickers(
    label: str,
    items: Sequence[NormalizedItem],
    tickers: tuple[str, ...],
) -> str:
    wanted = {ticker.casefold() for ticker in tickers}
    for item in items:
        if item.category != "price":
            continue
        ticker = _metadata_text(item, "ticker").casefold()
        if ticker in wanted:
            pct = _pct_change(item)
            return f"{label} {_format_pct(pct)}" if pct is not None else label
    return ""


def _snapshot_part_for_index(
    label: str,
    items: Sequence[NormalizedItem],
    index_names: tuple[str, ...],
) -> str:
    wanted = {name.casefold() for name in index_names}
    for item in items:
        if item.category != "price":
            continue
        index_name = _metadata_text(item, "index_name").casefold()
        if index_name in wanted:
            pct = _pct_change(item)
            return f"{label} {_format_pct(pct)}" if pct is not None else label
    return ""


def _snapshot_part_for_crypto(
    label: str,
    items: Sequence[NormalizedItem],
    symbols: tuple[str, ...],
) -> str:
    wanted = {symbol.casefold() for symbol in symbols}
    for item in items:
        if item.category != "price":
            continue
        symbol = (
            _metadata_text(item, "symbol")
            or _metadata_text(item, "coin_id")
            or _metadata_text(item, "ticker")
        ).casefold()
        if symbol in wanted:
            price = _price_value(item)
            pct = _pct_change(item)
            if price is not None and pct is not None:
                return f"{label} {_format_compact_price(price)}({_format_pct(pct)})"
            if pct is not None:
                return f"{label} {_format_pct(pct)}"
            if price is not None:
                return f"{label} {_format_compact_price(price)}"
            return label
    return ""


def _metadata_text(item: NormalizedItem, key: str) -> str:
    value = item.raw_metadata.get(key)
    return value if isinstance(value, str) else ""


def _metadata_float(item: NormalizedItem, *keys: str) -> float | None:
    for key in keys:
        value = item.raw_metadata.get(key)
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str) and value:
            try:
                return float(value)
            except ValueError:
                continue
    return None


def _price_value(item: NormalizedItem) -> float | None:
    return _metadata_float(item, "last_price", "price_usd", "close")


def _pct_change(item: NormalizedItem) -> float | None:
    explicit = _metadata_float(item, "pct_change", "pct_24h", "pct_change_24h")
    if explicit is not None:
        return explicit
    close = _metadata_float(item, "close")
    prev_close = _metadata_float(item, "prev_close")
    if close is None or prev_close is None or prev_close == 0.0:
        return None
    return (close - prev_close) / prev_close * 100.0


def _format_pct(value: float) -> str:
    return f"{value:+.1f}%"


def _format_compact_price(value: float) -> str:
    if abs(value) >= 1000:
        return f"{value / 1000:.1f}k"
    if abs(value) >= 100:
        return f"{value:.0f}"
    return f"{value:.2f}"


def _coverage_label(briefing: Briefing) -> str | None:
    coverage_match = _COVERAGE_LINE_RE.search(briefing.rendered_markdown)
    if coverage_match is None:
        return None
    coverage_label = _clean_summary_text(coverage_match.group(1)).split("—", maxsplit=1)[0].strip()
    return coverage_label or None


def _one_line_summary(
    briefing: Briefing,
    *,
    watchlist_prices: Mapping[str, str] | None = None,
) -> str:
    conclusion_match = _CONCLUSION_LINE_RE.search(briefing.rendered_markdown)
    if conclusion_match is not None:
        conclusion = _clean_summary_text(conclusion_match.group(1))
        if conclusion:
            coverage_match = _COVERAGE_LINE_RE.search(briefing.rendered_markdown)
            if coverage_match is not None:
                coverage_label = _coverage_label(briefing)
                if coverage_label:
                    conclusion = f"{coverage_label} — {conclusion}"
            watchlist_match = _WATCHLIST_LINE_RE.search(briefing.rendered_markdown)
            if watchlist_match is not None:
                watchlist = _clean_summary_text(watchlist_match.group(1))
                if (
                    watchlist
                    # u28 — onboarding nudge stays site-only.
                    and not watchlist.startswith("관심 목록 미설정")
                    # u28 — coverage-hold branch is reader-side only; the
                    # Telegram suffix omits it so first-viewport one-liners
                    # do not say "관심: 데이터 수집 부족" alongside the segment
                    # coverage badge that already says the same thing.
                    and not watchlist.startswith("데이터 수집 부족으로 매칭 판단 보류")
                ):
                    decorated = _decorate_watchlist_with_prices(watchlist, watchlist_prices)
                    return f"{conclusion} / 관심: {decorated}"
            return conclusion

    for line in briefing.market_summary.splitlines():
        summary = _clean_summary_text(line)
        if summary:
            return summary
    return "데이터 부족"


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
        pct = _pct_change(item)
        price = _price_value(item)
        if pct is None and price is None:
            continue
        suffix = _format_watchlist_suffix(pct=pct, price=price)
        if not suffix:
            continue
        for key in _watchlist_index_keys(item):
            if key:
                index.setdefault(key, suffix)
    return index


def _watchlist_index_keys(item: NormalizedItem) -> tuple[str, ...]:
    """Return the case-folded keys a watchlist match could use."""
    candidates: list[str] = []
    for field in ("ticker", "symbol", "coin_id", "index_name", "asset_name"):
        value = _metadata_text(item, field)
        if value:
            candidates.append(value)
    # ``BTCUSDT`` → also expose the leading ticker portion (``BTC``) so
    # users who registered ``BTC`` instead of the full pair still hit.
    for candidate in tuple(candidates):
        if candidate.endswith("USDT") and len(candidate) > 4:
            candidates.append(candidate[:-4])
    return tuple(value.casefold() for value in candidates)


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


_WATCHLIST_MATCH_TERM_RE: Final[re.Pattern[str]] = re.compile(r"([^;,]+?):\s*([^;]+)")


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

    def _decorate_one(match_segment: str) -> str:
        match = _WATCHLIST_MATCH_TERM_RE.match(match_segment.strip())
        if match is None:
            return match_segment
        term = match.group(1).strip()
        rest = match.group(2).strip()
        suffix = prices.get(term.casefold()) if prices else None
        if suffix is None:
            return f"{term}: {rest}"
        return f"{term}{suffix}: {rest}"

    decorated_segments = [_decorate_one(segment) for segment in body.split(";") if segment.strip()]
    return f"{prefix}{'; '.join(decorated_segments)}" if decorated_segments else watchlist_text


def _imminent_event_tag(
    lookahead_items: Sequence[NormalizedItem],
    *,
    now_utc: datetime | None,
) -> str:
    """Compute a deterministic imminent-event tag from forward items.

    Selects the earliest item whose ``scheduled_at`` falls within
    :data:`_IMMINENT_HORIZON` of ``now_utc`` and emits a tag of the
    shape ``"📅 <label> D-<n>"`` (where ``n`` is the number of full
    UTC days between ``now_utc`` and ``scheduled_at``, rounded down,
    minimum 0). When nothing qualifies, returns an empty string and
    the caller leaves the line unchanged.

    Determinism: the function consults ``scheduled_at`` and
    ``source_name`` only — no LLM call, no network, no clock read
    when ``now_utc`` is supplied. The orchestrator passes a single
    ``now_utc`` for all segments so a multi-segment publish emits a
    consistent set of tags.
    """
    if not lookahead_items or now_utc is None:
        return ""
    horizon_end = now_utc + _IMMINENT_HORIZON
    candidates = [
        item
        for item in lookahead_items
        if item.scheduled_at is not None and now_utc <= item.scheduled_at < horizon_end
    ]
    if not candidates:
        return ""
    # Earliest first; ties broken by source then title for determinism.
    best = min(
        candidates,
        key=lambda item: (
            item.scheduled_at,
            item.source_name,
            item.title,
        ),
    )
    assert best.scheduled_at is not None
    delta = best.scheduled_at - now_utc
    days_to_event = max(int(delta.total_seconds() // 86400), 0)
    icon = _IMMINENT_TAG_ICON.get(best.source_name, _IMMINENT_TAG_FALLBACK_ICON)
    label = _imminent_event_label(best)
    return f"{icon} {label} D-{days_to_event}"


def _imminent_event_label(item: NormalizedItem) -> str:
    """Resolve a terse Korean/English label for the imminent tag.

    For earnings calendar rows we surface the ticker symbol so the
    Telegram preview reads ``📊 NVDA 실적 D-1`` instead of repeating
    the long company-name title. For other sources we fall back to
    the first 24 characters of the title — short enough that the
    surrounding "상세보기" footer still fits inside the UTF-16 budget.
    """
    if item.source_name == "nasdaq-earnings-calendar":
        symbol = item.raw_metadata.get("symbol")
        if isinstance(symbol, str) and symbol:
            return f"{symbol} 실적"
    title = item.title.strip()
    return title if len(title) <= 24 else title[:23] + "…"


def _clean_summary_text(text: str) -> str:
    cleaned = text.strip()
    if not cleaned:
        return ""
    cleaned = _LEADING_MARKDOWN_RE.sub("", cleaned).strip()
    cleaned = _MARKDOWN_LINK_RE.sub(r"\1", cleaned)
    cleaned = _MARKDOWN_TOKEN_RE.sub("", cleaned)
    cleaned = " ".join(cleaned.split())
    if not _MEANINGFUL_TEXT_RE.search(cleaned):
        return ""
    return cleaned


__all__ = [
    "DEFAULT_MAX_UNITS",
    "build_segmented_summary",
    "build_summary",
    "plain_text_summary",
    "resolve_enabled_segments",
]

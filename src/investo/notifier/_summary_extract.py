"""Briefing → structured-data extraction for the Telegram summary (u80).

This is the **extraction** half of the notifier summary split. It reads
a :class:`Briefing` (and, for the market snapshot / watchlist decorate,
``price`` :class:`NormalizedItem` rows) and returns plain Python data:
the one-line conclusion, the coverage label, the market-snapshot
entries, and the watchlist price index. It deliberately contains:

- regex extraction from ``rendered_markdown`` / ``market_summary``,
- numeric parsing of ``raw_metadata`` fields,
- markdown-token cleanup of *pulled* text (intrinsic to "what does the
  briefing say" — the cleaned text IS the extracted datum).

It deliberately contains NO Telegram presentation: no UTF-16 budget,
no percent/price string formatting, no block assembly, no markdown
link-to-plain rewriting for the fallback. Those live in the formatting
layer (:mod:`investo.notifier.summary`). Event detection lives in
:mod:`investo.notifier._events`.

Splitting this out lets the extraction be unit-tested against data
without asserting on Telegram byte layout (u80 ``test_summary_extract``).
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final

from investo.briefing.market_anchor import anchor_label
from investo.models import Briefing, NormalizedItem

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
_MARKDOWN_TOKEN_RE: Final[re.Pattern[str]] = re.compile(r"[*_`~]+")
_LEADING_MARKDOWN_RE: Final[re.Pattern[str]] = re.compile(
    r"^(?:>\s*)?(?:#{1,6}\s*)?(?:(?:[-*+])|\d+[.)])\s*"
)
_MEANINGFUL_TEXT_RE: Final[re.Pattern[str]] = re.compile(r"[A-Za-z0-9가-힣]")
_WATCHLIST_MATCH_TERM_RE: Final[re.Pattern[str]] = re.compile(r"([^;,]+?):\s*([^;]+)")


@dataclass(frozen=True, slots=True)
class SnapshotEntry:
    """One extracted market-snapshot datum (presentation-free).

    ``label`` is the short index/asset label (e.g. ``"S&P 500"``,
    ``"BTC"``). ``pct`` is the day's percent change (already in
    percent units, e.g. ``+1.2``) when available. ``price`` is a raw
    absolute price when available (currently only crypto rows carry
    one). ``with_price`` marks rows whose presentation should include
    the absolute price (crypto) versus index rows that show pct only.
    """

    label: str
    pct: float | None
    price: float | None
    with_price: bool


@dataclass(frozen=True, slots=True)
class ConclusionData:
    """Extracted one-line conclusion components (presentation-free).

    ``conclusion`` is the cleaned conclusion sentence (empty when the
    briefing has no usable conclusion / fallback). ``coverage_label``
    is the cleaned coverage prefix when one should be prepended.
    ``watchlist`` is the cleaned watchlist body when it should be
    appended (already filtered for the site-only nudge / coverage-hold
    cases). All three are raw data — the formatter joins them.
    """

    conclusion: str
    coverage_label: str | None
    watchlist: str | None


def clean_summary_text(text: str) -> str:
    """Strip markdown markers / leading list tokens from a pulled line.

    Returns ``""`` when the cleaned text has no meaningful (alphanumeric
    / Hangul) content. This cleaning is intrinsic to extraction: the
    *cleaned* text is the datum a caller means by "the conclusion".
    """
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


def coverage_label(briefing: Briefing) -> str | None:
    """Extract the cleaned coverage label (text before any ``—``)."""
    coverage_match = _COVERAGE_LINE_RE.search(briefing.rendered_markdown)
    if coverage_match is None:
        return None
    label = clean_summary_text(coverage_match.group(1)).split("—", maxsplit=1)[0].strip()
    return label or None


def conclusion_data(briefing: Briefing) -> ConclusionData:
    """Extract the one-line conclusion components from ``briefing``.

    Mirrors the legacy ``_one_line_summary`` extraction logic exactly,
    minus the watchlist *price decoration* (a formatting concern). The
    caller composes the final string and decorates the watchlist.

    When no conclusion line is present, falls back to the first
    meaningful ``market_summary`` line (or the ``"데이터 부족"``
    sentinel), surfaced via ``conclusion`` with no coverage/watchlist.
    """
    conclusion_match = _CONCLUSION_LINE_RE.search(briefing.rendered_markdown)
    if conclusion_match is not None:
        conclusion = clean_summary_text(conclusion_match.group(1))
        if conclusion:
            label: str | None = None
            coverage_match = _COVERAGE_LINE_RE.search(briefing.rendered_markdown)
            if coverage_match is not None:
                label = coverage_label(briefing)
            watchlist: str | None = None
            watchlist_match = _WATCHLIST_LINE_RE.search(briefing.rendered_markdown)
            if watchlist_match is not None:
                candidate = clean_summary_text(watchlist_match.group(1))
                if (
                    candidate
                    # u28 — onboarding nudge stays site-only.
                    and not candidate.startswith("관심 목록 미설정")
                    # u28 — coverage-hold branch is reader-side only; the
                    # Telegram suffix omits it so first-viewport one-liners
                    # do not say "관심: 데이터 수집 부족" alongside the segment
                    # coverage badge that already says the same thing.
                    and not candidate.startswith("데이터 수집 부족으로 매칭 판단 보류")
                ):
                    watchlist = candidate
            return ConclusionData(conclusion=conclusion, coverage_label=label, watchlist=watchlist)

    for line in briefing.market_summary.splitlines():
        summary = clean_summary_text(line)
        if summary:
            return ConclusionData(conclusion=summary, coverage_label=None, watchlist=None)
    return ConclusionData(conclusion="데이터 부족", coverage_label=None, watchlist=None)


def market_snapshot_entries(price_items: Sequence[NormalizedItem]) -> list[SnapshotEntry]:
    """Extract the ordered market-snapshot entries (presentation-free).

    Mirrors the legacy ``_market_snapshot_line`` selection order
    (S&P 500 → Nasdaq Composite → KOSPI → BTC) and the same lookup
    rules, but returns structured data instead of a formatted string.
    """
    entries = [
        entry
        for entry in (
            _entry_for_tickers(anchor_label("^GSPC").short, price_items, ("^GSPC",)),
            # u70 — ``^IXIC`` is the Nasdaq Composite, not the Nasdaq 100
            # (``^NDX``); the canonical registry supplies the correct short
            # label so this dense surface stops emitting the "NDX" mislabel.
            _entry_for_tickers(anchor_label("^IXIC").short, price_items, ("^IXIC",)),
            _entry_for_index("KOSPI", price_items, ("코스피",)),
            _entry_for_crypto("BTC", price_items, ("BTCUSDT", "btc", "BTC")),
        )
        if entry is not None
    ]
    return entries


def _entry_for_tickers(
    label: str,
    items: Sequence[NormalizedItem],
    tickers: tuple[str, ...],
) -> SnapshotEntry | None:
    wanted = {ticker.casefold() for ticker in tickers}
    for item in items:
        if item.category != "price":
            continue
        ticker = metadata_text(item, "ticker").casefold()
        if ticker in wanted:
            return SnapshotEntry(label=label, pct=pct_change(item), price=None, with_price=False)
    return None


def _entry_for_index(
    label: str,
    items: Sequence[NormalizedItem],
    index_names: tuple[str, ...],
) -> SnapshotEntry | None:
    wanted = {name.casefold() for name in index_names}
    for item in items:
        if item.category != "price":
            continue
        index_name = metadata_text(item, "index_name").casefold()
        if index_name in wanted:
            return SnapshotEntry(label=label, pct=pct_change(item), price=None, with_price=False)
    return None


def _entry_for_crypto(
    label: str,
    items: Sequence[NormalizedItem],
    symbols: tuple[str, ...],
) -> SnapshotEntry | None:
    wanted = {symbol.casefold() for symbol in symbols}
    for item in items:
        if item.category != "price":
            continue
        symbol = (
            metadata_text(item, "symbol")
            or metadata_text(item, "coin_id")
            or metadata_text(item, "ticker")
        ).casefold()
        if symbol in wanted:
            return SnapshotEntry(
                label=label,
                pct=pct_change(item),
                price=price_value(item),
                with_price=True,
            )
    return None


def metadata_text(item: NormalizedItem, key: str) -> str:
    value = item.raw_metadata.get(key)
    return value if isinstance(value, str) else ""


def metadata_float(item: NormalizedItem, *keys: str) -> float | None:
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


def price_value(item: NormalizedItem) -> float | None:
    return metadata_float(item, "last_price", "price_usd", "close")


def pct_change(item: NormalizedItem) -> float | None:
    explicit = metadata_float(item, "pct_change", "pct_24h", "pct_change_24h")
    if explicit is not None:
        return explicit
    close = metadata_float(item, "close")
    prev_close = metadata_float(item, "prev_close")
    if close is None or prev_close is None or prev_close == 0.0:
        return None
    return (close - prev_close) / prev_close * 100.0


def watchlist_index_keys(item: NormalizedItem) -> tuple[str, ...]:
    """Return the case-folded keys a watchlist match could use."""
    candidates: list[str] = []
    for field in ("ticker", "symbol", "coin_id", "index_name", "asset_name"):
        value = metadata_text(item, field)
        if value:
            candidates.append(value)
    # ``BTCUSDT`` → also expose the leading ticker portion (``BTC``) so
    # users who registered ``BTC`` instead of the full pair still hit.
    for candidate in tuple(candidates):
        if candidate.endswith("USDT") and len(candidate) > 4:
            candidates.append(candidate[:-4])
    return tuple(value.casefold() for value in candidates)


def watchlist_match_terms(body: str) -> list[tuple[str, str]]:
    """Split a watchlist match body into ``(term, rest)`` pairs.

    Returns the per-segment ``TERM: rest`` matches in order; segments
    that do not match the ``TERM:`` shape are returned as ``("", raw)``
    so the formatter can pass them through unchanged.
    """
    pairs: list[tuple[str, str]] = []
    for segment in body.split(";"):
        if not segment.strip():
            continue
        match = _WATCHLIST_MATCH_TERM_RE.match(segment.strip())
        if match is None:
            pairs.append(("", segment))
        else:
            pairs.append((match.group(1).strip(), match.group(2).strip()))
    return pairs


__all__ = [
    "ConclusionData",
    "SnapshotEntry",
    "clean_summary_text",
    "conclusion_data",
    "coverage_label",
    "market_snapshot_entries",
    "metadata_float",
    "metadata_text",
    "pct_change",
    "price_value",
    "watchlist_index_keys",
    "watchlist_match_terms",
]

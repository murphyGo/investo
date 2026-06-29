"""Deterministic market-anchor calculation — u49.

Derives "market facts" from price-history time-series that are
provable by code (no LLM judgement involved):

* **ATH (all-time high)** — today's close versus the historical max.
* **52-week range distance** — today's close relative to the
  trailing-window high / low.
* **MTD / YTD** — today's close versus the first-business-day close
  of the same calendar month / year.
* **Volume z-score** — today's volume versus the trailing 60-day
  mean / standard deviation.

These facts are stamped into the briefing header as a single
``> **시장 anchor**: ...`` line; the Stage 2 prompt requires the LLM
to *cite* anchors verbatim and forbids invention of new figures
(see ``briefing/prompts.py::STAGE2_SYSTEM`` "시장 anchor 인용 룰").
The u32 ``numeric_self_check`` haystack already contains the price
items the anchor was computed from, so the anchor figures pass the
existing numeric-trust gate naturally.

Design pins
~~~~~~~~~~~

* **Frozen pydantic v2 + slots + extra="forbid"** for ``OHLCRow`` and
  ``MarketAnchor`` so an over-supplied dict raises rather than silently
  drops fields. Identity is structural — same input rows ⇒ same anchor.
* **Decimal arithmetic** end to end (NOT float). Inputs land via
  ``Decimal(str(...))`` to dodge float-repr drift; percentages quantize
  to 2 decimal places.
* **Pure function**: :func:`compute_market_anchors` does no I/O, no
  ``datetime.now()``, no environment reads. The caller supplies
  ``today`` and the per-ticker history; identical inputs always yield
  identical outputs (FD R9 / NFR-006 PBT contract).
* **Module boundary**: this module imports only ``investo.models`` and
  stdlib. It does NOT import from ``sources/`` / ``notifier/`` /
  ``publisher/`` / ``orchestrator/`` (project rule 2).
* **Graceful degrade**: insufficient history (< 20 trading rows) →
  MTD / YTD / 52-week / z-score fields land as ``None``. Empty input
  ⇒ empty output tuple, no exception.
"""

from __future__ import annotations

import statistics
from collections.abc import Callable, Mapping, Sequence
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import Final

from pydantic import BaseModel, ConfigDict, Field

# Default trailing window for ATH / 52-week comparisons. ~1 calendar
# year of US trading days; crypto fixtures carry ~365 rows so the
# window slices to the last 252.
DEFAULT_HISTORY_WINDOW_DAYS: Final[int] = 252

# Volume z-score uses a shorter tail (60 trading days) so a single
# fresh outlier reads as an outlier rather than blending into a year
# of mean reversion.
_VOLUME_Z_WINDOW_DAYS: Final[int] = 60

# Below this row count we cannot trust 52-week / MTD / YTD math —
# return ``None`` for those fields rather than emit a misleading
# anchor. ATH still resolves (any non-empty history defines a max).
_MIN_HISTORY_FOR_RANGE: Final[int] = 20

# Quantize percentages to two decimal places (e.g. ``Decimal("12.34")``).
_PCT_QUANTUM: Final[Decimal] = Decimal("0.01")

# Quantize z-scores to one decimal place (matches reader expectation:
# "z=2.0" vs "z=2.04" — the extra digit reads as false precision).
_Z_QUANTUM: Final[Decimal] = Decimal("0.1")

# Trivial private typedef for the period-predicate inner functions
# used by MTD / YTD slicing. Defined here (top of module) so the
# annotation site in ``_period_pct`` lands without a forward ref.
_DatePredicate = Callable[[date], bool]


class OHLCRow(BaseModel):
    """One daily OHLCV bar — the unit of price history this module consumes.

    The shape mirrors the Yahoo Finance v8 chart payload (and any
    other free price-history source the orchestrator may wire in)
    but normalised: dates are :class:`datetime.date`, numerics are
    :class:`Decimal`. ``volume`` is optional — index series like
    ``^GSPC`` carry meaningful volume, but ``^VIX`` and a few
    international indices report zero / missing; the anchor module
    treats absent volume as "no z-score".
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    trading_date: date
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal | None = None


class MarketAnchor(BaseModel):
    """Deterministic anchor record for one ticker on one trading day.

    All fields except ``ticker``, ``close``, and ``is_ath`` may be
    ``None`` — graceful degrade when the per-ticker history is too
    short (e.g. a freshly-listed instrument) or volume is missing
    (e.g. ``^VIX``).
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    ticker: str = Field(min_length=1, max_length=32)
    close: Decimal
    prev_close: Decimal | None = None
    pct: Decimal | None = None
    is_ath: bool
    pct_from_52w_high: Decimal | None = None
    pct_from_52w_low: Decimal | None = None
    mtd_pct: Decimal | None = None
    ytd_pct: Decimal | None = None
    volume_z_score: Decimal | None = None


def compute_market_anchors(
    history_by_ticker: Mapping[str, Sequence[OHLCRow]],
    *,
    today: date,
    history_window_days: int = DEFAULT_HISTORY_WINDOW_DAYS,
) -> tuple[MarketAnchor, ...]:
    """Compute one :class:`MarketAnchor` per ticker, in input order.

    Parameters
    ----------
    history_by_ticker:
        Per-ticker daily-bar history. Rows for a given ticker MUST be
        sorted ascending by ``trading_date`` (callers fetch from
        Yahoo / Stooq with that property already). The most recent row
        is treated as "today's" close — ``today`` is supplied
        separately and only used for MTD / YTD month/year boundaries
        (so a Saturday cron with the most-recent bar = Friday still
        slices MTD against the same May 1st boundary the reader
        expects).
    today:
        Reference calendar date for MTD / YTD slicing. Pass the
        publish day (`target_date`); the anchor module never reads a
        clock itself.
    history_window_days:
        Trailing-window size for ATH / 52-week / range calculations.
        Defaults to 252 (~1 trading year). Test seam.

    Returns
    -------
    tuple[MarketAnchor, ...]
        One anchor per non-empty ticker history, in iteration order
        of ``history_by_ticker``. Tickers with empty rows are
        silently skipped — an empty mapping yields an empty tuple.
    """
    anchors: list[MarketAnchor] = []
    for ticker, rows in history_by_ticker.items():
        anchor = _compute_one(ticker, rows, today=today, window=history_window_days)
        if anchor is not None:
            anchors.append(anchor)
    return tuple(anchors)


def _compute_one(
    ticker: str,
    rows: Sequence[OHLCRow],
    *,
    today: date,
    window: int,
) -> MarketAnchor | None:
    if not rows:
        return None

    last = rows[-1]
    close = last.close

    prev_close = rows[-2].close if len(rows) >= 2 else None
    pct = _pct_change(close, prev_close)

    range_window = rows[-window:] if window > 0 else rows
    have_range = len(range_window) >= _MIN_HISTORY_FOR_RANGE

    # ATH against the *full* supplied history excluding today —
    # equality-or-higher counts as an ATH (today's close re-tests the
    # prior peak). A single-row history qualifies as ATH trivially.
    historical = rows[:-1]
    is_ath = bool(not historical or close >= max(row.close for row in historical))

    if have_range:
        window_max = max(row.close for row in range_window)
        window_min = min(row.close for row in range_window)
        pct_from_high = _signed_pct(close, window_max)  # ≤ 0
        pct_from_low = _signed_pct(close, window_min)  # ≥ 0
    else:
        pct_from_high = None
        pct_from_low = None

    if have_range:
        mtd_pct = _period_pct(rows, close, _is_same_month_as(today))
        ytd_pct = _period_pct(rows, close, _is_same_year_as(today))
    else:
        mtd_pct = None
        ytd_pct = None

    volume_z = _volume_z_score(rows)

    return MarketAnchor(
        ticker=ticker,
        close=close,
        prev_close=prev_close,
        pct=pct,
        is_ath=is_ath,
        pct_from_52w_high=pct_from_high,
        pct_from_52w_low=pct_from_low,
        mtd_pct=mtd_pct,
        ytd_pct=ytd_pct,
        volume_z_score=volume_z,
    )


def _pct_change(current: Decimal, previous: Decimal | None) -> Decimal | None:
    if previous is None or previous == 0:
        return None
    return _quantize_pct((current - previous) / previous * Decimal(100))


def _signed_pct(current: Decimal, reference: Decimal) -> Decimal:
    if reference == 0:
        return _quantize_pct(Decimal(0))
    return _quantize_pct((current - reference) / reference * Decimal(100))


def _period_pct(
    rows: Sequence[OHLCRow],
    close: Decimal,
    in_period: _DatePredicate,
) -> Decimal | None:
    """Return percentage change versus the period's first close.

    ``in_period`` is a predicate that returns ``True`` for trading
    dates within the period (same calendar month for MTD; same
    calendar year for YTD). The first row whose date matches becomes
    the baseline. Empty period (no rows match) ⇒ ``None``.
    """
    for row in rows:
        if in_period(row.trading_date):
            baseline = row.close
            if baseline == 0:
                return None
            return _quantize_pct((close - baseline) / baseline * Decimal(100))
    return None


def _volume_z_score(rows: Sequence[OHLCRow]) -> Decimal | None:
    last = rows[-1]
    today_volume = last.volume
    if today_volume is None or today_volume <= 0:
        return None
    sample = [row.volume for row in rows[-_VOLUME_Z_WINDOW_DAYS:] if row.volume is not None]
    sample = [v for v in sample if v > 0]
    if len(sample) < 2:
        return None
    floats = [float(v) for v in sample]
    mean = statistics.fmean(floats)
    stdev = statistics.pstdev(floats)
    if stdev == 0:
        return None
    z = (float(today_volume) - mean) / stdev
    return Decimal(str(z)).quantize(_Z_QUANTUM, rounding=ROUND_HALF_UP)


def _quantize_pct(value: Decimal) -> Decimal:
    return value.quantize(_PCT_QUANTUM, rounding=ROUND_HALF_UP)


def _is_same_month_as(reference: date) -> _DatePredicate:
    def predicate(value: date) -> bool:
        return value.year == reference.year and value.month == reference.month

    return predicate


def _is_same_year_as(reference: date) -> _DatePredicate:
    def predicate(value: date) -> bool:
        return value.year == reference.year

    return predicate


# ---------------------------------------------------------------------------
# u70 — canonical symbol / display-label registry
# ---------------------------------------------------------------------------
#
# A single source of truth for how each core anchor ticker is named for the
# reader. Before u70 each surface (anchor table, chart card, Telegram
# snapshot line) inlined its own label string; the Telegram line in
# particular mislabelled ``^IXIC`` (Nasdaq Composite) as ``NDX`` — the
# Nasdaq 100 ticker, a *different* index. Centralising the mapping here
# means every consumer renders the same label for the same symbol.
#
# Pins
# ~~~~
# * ``^IXIC`` is the **Nasdaq Composite**. The Nasdaq 100 is a separate
#   index (``^NDX``); the pipeline does not currently fetch it, so it has
#   no registry entry until that anchor exists (Plan Step 3). Adding a
#   ``^IXIC -> "Nasdaq 100"`` entry would re-introduce the reviewed bug.
# * Korean labels mirror the reader-facing prose vocabulary; the short
#   alias (e.g. ``"S&P500"``) is what compact surfaces (Telegram) prefer.


class AnchorLabel(BaseModel):
    """Canonical display naming for one anchor symbol (u70).

    ``short`` is the compact alias used by dense surfaces (Telegram
    snapshot line); ``ko`` is the Korean reader-facing name; ``display``
    defaults to the raw symbol so the anchor table keeps its existing
    ticker-first rendering while still routing through one registry.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    symbol: str = Field(min_length=1, max_length=32)
    short: str = Field(min_length=1)
    ko: str = Field(min_length=1)
    display: str = Field(min_length=1)


_ANCHOR_LABELS: Final[dict[str, AnchorLabel]] = {}


def _register_label(symbol: str, *, short: str, ko: str, display: str | None = None) -> None:
    _ANCHOR_LABELS[symbol] = AnchorLabel(
        symbol=symbol,
        short=short,
        ko=ko,
        display=display if display is not None else symbol,
    )


# Order is documentation only; lookup is by symbol key.
_register_label("^GSPC", short="S&P500", ko="S&P 500")
_register_label("^IXIC", short="Nasdaq", ko="나스닥 종합")  # NOT Nasdaq 100 (^NDX)
_register_label("^DJI", short="Dow", ko="다우존스")
_register_label("^NDX", short="NDX", ko="나스닥 100")
_register_label("AAPL", short="AAPL", ko="애플")
_register_label("MSFT", short="MSFT", ko="마이크로소프트")
_register_label("NVDA", short="NVDA", ko="엔비디아")
_register_label("TSLA", short="TSLA", ko="테슬라")
_register_label("GOOGL", short="GOOGL", ko="알파벳")
_register_label("META", short="META", ko="메타")
_register_label("AMZN", short="AMZN", ko="아마존")
_register_label("BTC-USD", short="BTC", ko="비트코인")
_register_label("ETH-USD", short="ETH", ko="이더리움")
_register_label("^KOSPI", short="KOSPI", ko="코스피")
_register_label("^KOSDAQ", short="KOSDAQ", ko="코스닥")
_register_label("KRW=X", short="USD/KRW", ko="원/달러")
_register_label("005930.KS", short="005930", ko="삼성전자")
_register_label("000660.KS", short="000660", ko="SK하이닉스")


def anchor_label(symbol: str) -> AnchorLabel:
    """Return the canonical :class:`AnchorLabel` for ``symbol`` (u70).

    Unknown symbols (e.g. an ad-hoc ticker not in the core basket) fall
    back to a label whose every field is the raw symbol, so callers can
    always render *something* deterministic without a missing-key guard.
    """
    existing = _ANCHOR_LABELS.get(symbol)
    if existing is not None:
        return existing
    return AnchorLabel(symbol=symbol, short=symbol, ko=symbol, display=symbol)


# ---------------------------------------------------------------------------
# Header rendering
# ---------------------------------------------------------------------------

# Selection priority for the brief header line. Indices first
# (broadest market signal), big-tech bellwethers next, crypto last.
# Tickers not in this list still render if supplied, after the
# ranked entries.
_HEADER_PRIORITY: Final[tuple[str, ...]] = (
    "^GSPC",
    "^IXIC",
    "^DJI",
    "AAPL",
    "MSFT",
    "NVDA",
    "TSLA",
    "GOOGL",
    "META",
    "AMZN",
    "BTC-USD",
    "ETH-USD",
)
_HEADER_MAX_ANCHORS: Final[int] = 5

# Threshold for surfacing MTD / YTD figures as a follow-up phrase.
# Below this absolute value the figure is too small to anchor a
# narrative and would clutter the header. Threshold is a Decimal so
# the comparison is exact.
_MTD_YTD_DISPLAY_THRESHOLD: Final[Decimal] = Decimal("5.00")


def render_market_anchor_line(anchors: Sequence[MarketAnchor]) -> str:
    """Render the brief-header ``> **시장 anchor**: ...`` blockquote line.

    Empty input ⇒ empty string (caller omits the whole line). The
    selection picks at most :data:`_HEADER_MAX_ANCHORS` anchors using
    the :data:`_HEADER_PRIORITY` ranking; ties resolve in input
    order. Each anchor renders as one of:

    * ``^GSPC 5,820.40 ATH 경신`` (when ``is_ath``)
    * ``AAPL 195.30 (-2.4% from 52w high)`` (close to the high)
    * ``BTC-USD 80,808.65 (+28.9% from 52w low)`` (off the low)

    A trailing MTD / YTD phrase is appended when ``|mtd_pct|`` or
    ``|ytd_pct|`` exceeds :data:`_MTD_YTD_DISPLAY_THRESHOLD` — the
    larger absolute value wins; ties prefer MTD (fresher signal).
    """
    if not anchors:
        return ""
    selected = _select_header_anchors(anchors)
    if not selected:
        return ""
    parts = [_render_anchor_chunk(anchor) for anchor in selected]
    return f"> **시장 anchor**: {', '.join(parts)}\n"


def _select_header_anchors(anchors: Sequence[MarketAnchor]) -> tuple[MarketAnchor, ...]:
    by_ticker = {anchor.ticker: anchor for anchor in anchors}
    ordered: list[MarketAnchor] = []
    for ticker in _HEADER_PRIORITY:
        if ticker in by_ticker:
            ordered.append(by_ticker[ticker])
    # Append anchors not in the priority list, preserving input order.
    for anchor in anchors:
        if anchor.ticker not in _HEADER_PRIORITY and anchor not in ordered:
            ordered.append(anchor)
    return tuple(ordered[:_HEADER_MAX_ANCHORS])


def _render_anchor_chunk(anchor: MarketAnchor) -> str:
    price = _format_price(anchor.close)
    parts = [f"{anchor.ticker} {price}"]
    if anchor.is_ath:
        parts.append("ATH 경신")
    else:
        range_phrase = _render_range_phrase(anchor)
        if range_phrase is not None:
            parts.append(range_phrase)
    extra = _render_period_phrase(anchor)
    if extra is not None:
        parts.append(extra)
    return " ".join(parts)


def _render_range_phrase(anchor: MarketAnchor) -> str | None:
    high = anchor.pct_from_52w_high
    low = anchor.pct_from_52w_low
    if high is None or low is None:
        return None
    # Prefer the closer reference: if the close is nearer the high
    # than the low (in absolute %), report the high distance; else
    # the low distance.
    if abs(high) <= low:
        return f"({_format_signed(high)}% from 52w high)"
    return f"({_format_signed(low)}% from 52w low)"


def _render_period_phrase(anchor: MarketAnchor) -> str | None:
    candidates: list[tuple[str, Decimal]] = []
    if anchor.mtd_pct is not None and abs(anchor.mtd_pct) >= _MTD_YTD_DISPLAY_THRESHOLD:
        candidates.append(("MTD", anchor.mtd_pct))
    if anchor.ytd_pct is not None and abs(anchor.ytd_pct) >= _MTD_YTD_DISPLAY_THRESHOLD:
        candidates.append(("YTD", anchor.ytd_pct))
    if not candidates:
        return None
    label, pct = max(candidates, key=lambda pair: abs(pair[1]))
    return f"{_format_signed(pct)}% {label}"


def _format_price(value: Decimal) -> str:
    # Two decimal places with thousands separators; integer-valued
    # prices still render as ``5,820.40`` for display consistency
    # rather than ``5820`` to avoid reading as a count.
    quantized = value.quantize(_PCT_QUANTUM, rounding=ROUND_HALF_UP)
    return f"{quantized:,.2f}"


def _format_signed(value: Decimal) -> str:
    if value > 0:
        return f"+{value}"
    return str(value)


__all__ = [
    "DEFAULT_HISTORY_WINDOW_DAYS",
    "AnchorLabel",
    "MarketAnchor",
    "OHLCRow",
    "anchor_label",
    "compute_market_anchors",
    "render_market_anchor_line",
]

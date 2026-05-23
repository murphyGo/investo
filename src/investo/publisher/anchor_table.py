"""Anchor table renderer for u51 (replaces the prose anchor blockquote).

The u49 ``> **시장 anchor**: ...`` single-line blockquote works for a few
anchors but collapses into a 250-char prose wall once five indices +
big-tech are stacked together (2026-05-11 audit). u51 promotes that line
to a 4-column markdown table:

::

    | 종목    | 종가       | 변동      | 비고                     |
    |---------|-----------|-----------|--------------------------|
    | ^GSPC   | 7,412.84  | +0.37%    | ATH 경신                 |
    | ^IXIC   | 26,274.13 | +0.53%    | ATH 경신 · +13.08% YTD   |
    | AAPL    | 292.68    | -0.22%    | -0.22% from 52w high     |

Selection / ordering reuses the same priority list as
:func:`render_market_anchor_line` so the table contents are identical to
what the blockquote used to render — only the visual surface differs.

Module boundary
~~~~~~~~~~~~~~~
* Imports :mod:`investo.briefing.market_anchor` for :class:`MarketAnchor`
  and the existing ``_format_signed`` / ``_format_price`` helpers' shape
  (we re-implement them as private helpers here so ``market_anchor.py``
  stays the authority over the prose-line semantics and ``anchor_table.py``
  is the table-only authority).
* Does NOT import from ``orchestrator/`` / ``notifier/`` / ``sources/``.
"""

from __future__ import annotations

from collections.abc import Sequence
from decimal import ROUND_HALF_UP, Decimal
from typing import Final, Literal

from investo.briefing.market_anchor import MarketAnchor

# u66 — crypto trades 24/7; the close-recap column header ("종가") is
# misleading for the crypto segment. The crypto anchor table labels the
# value column as a UTC 24h snapshot instead. Equity/domestic tables keep
# the "종가" (close) framing. ``None`` (default) preserves the legacy
# equity header for backward compatibility.
_EQUITY_PRICE_HEADER: Final[str] = "종가"
_CRYPTO_PRICE_HEADER: Final[str] = "스냅샷(UTC 24h)"
_EQUITY_HEADER: Final[str] = "| 종목 | 종가 | 변동 | 비고 |"
_CRYPTO_HEADER: Final[str] = "| 종목 | 스냅샷(UTC 24h) | 구간 변동 | 비고 |"

# Same priority order as ``market_anchor._HEADER_PRIORITY`` — reused
# verbatim so the table and the deprecated blockquote stay byte-faithful
# in their selection (only the rendering differs).
_TABLE_PRIORITY: Final[tuple[str, ...]] = (
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
    # u67 — domestic index close + 원/달러 (close-only anchors).
    "^KOSPI",
    "^KOSDAQ",
    "KRW=X",
)
# Cap: 4 rows for US-equity (3 indices + 1 ticker), 2 for crypto, 2 for
# domestic — but the rendering helper itself doesn't know the segment,
# only the supplied anchor count. The caller (orchestrator) decides
# which anchors to pass; we cap defensively at this absolute ceiling.
_TABLE_MAX_ROWS: Final[int] = 5

_PRICE_QUANTUM: Final[Decimal] = Decimal("0.01")
_MTD_YTD_DISPLAY_THRESHOLD: Final[Decimal] = Decimal("5.00")


def render_anchor_table(
    anchors: Sequence[MarketAnchor],
    *,
    segment: Literal["domestic-equity", "us-equity", "crypto"] | None = None,
) -> str:
    """Render the anchor block as a markdown table.

    Empty input ⇒ empty string (caller omits the whole block).

    ``segment`` selects the column header framing (u66): ``"crypto"``
    uses UTC 24h snapshot wording; all other values (and ``None``) keep
    the equity close ("종가") framing for byte-compatibility.
    """
    if not anchors:
        return ""
    selected = _select(anchors)
    if not selected:
        return ""
    rows = [_render_row(anchor) for anchor in selected]
    header = _CRYPTO_HEADER if segment == "crypto" else _EQUITY_HEADER
    divider = "|------|------|------|------|"
    return "\n".join([header, divider, *rows]) + "\n"


def _select(anchors: Sequence[MarketAnchor]) -> tuple[MarketAnchor, ...]:
    by_ticker = {anchor.ticker: anchor for anchor in anchors}
    ordered: list[MarketAnchor] = []
    for ticker in _TABLE_PRIORITY:
        if ticker in by_ticker:
            ordered.append(by_ticker[ticker])
    for anchor in anchors:
        if anchor.ticker not in _TABLE_PRIORITY and anchor not in ordered:
            ordered.append(anchor)
    return tuple(ordered[:_TABLE_MAX_ROWS])


def _render_row(anchor: MarketAnchor) -> str:
    price = _format_price(anchor.close)
    pct = _format_pct(anchor.pct)
    note = _render_note(anchor)
    # Escape pipes that might appear inside note strings — defensive even
    # though our derived fields don't currently produce them.
    note_safe = note.replace("|", "\\|")
    return f"| {anchor.ticker} | {price} | {pct} | {note_safe} |"


def _format_price(value: Decimal) -> str:
    quantized = value.quantize(_PRICE_QUANTUM, rounding=ROUND_HALF_UP)
    return f"{quantized:,.2f}"


def _format_pct(value: Decimal | None) -> str:
    if value is None:
        return "—"
    if value > 0:
        return f"+{value}%"
    return f"{value}%"


def _format_signed(value: Decimal) -> str:
    if value > 0:
        return f"+{value}"
    return str(value)


def _render_note(anchor: MarketAnchor) -> str:
    parts: list[str] = []
    if anchor.is_ath:
        parts.append("ATH 경신")
    else:
        high = anchor.pct_from_52w_high
        low = anchor.pct_from_52w_low
        if high is not None and low is not None:
            if abs(high) <= low:
                parts.append(f"{_format_signed(high)}% from 52w high")
            else:
                parts.append(f"{_format_signed(low)}% from 52w low")
    period = _render_period(anchor)
    if period is not None:
        parts.append(period)
    if not parts:
        return "—"
    return " · ".join(parts)


def _render_period(anchor: MarketAnchor) -> str | None:
    candidates: list[tuple[str, Decimal]] = []
    if anchor.mtd_pct is not None and abs(anchor.mtd_pct) >= _MTD_YTD_DISPLAY_THRESHOLD:
        candidates.append(("MTD", anchor.mtd_pct))
    if anchor.ytd_pct is not None and abs(anchor.ytd_pct) >= _MTD_YTD_DISPLAY_THRESHOLD:
        candidates.append(("YTD", anchor.ytd_pct))
    if not candidates:
        return None
    label, pct = max(candidates, key=lambda pair: abs(pair[1]))
    return f"{_format_signed(pct)}% {label}"


__all__ = ["render_anchor_table"]

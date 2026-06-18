"""Channel-depth v2 native-anchor presentation contract — u74.

u66 (crypto-native indicators) and u67 (domestic KOSPI/KOSDAQ/FX/sector)
each landed their own collection + framing. u74 does NOT reopen either:
it standardises the *reader-facing presentation contract* so every
segment exposes a deterministic native-anchor block whose missing rows
render an **explicit reason** instead of a silent omission.

What this module owns
~~~~~~~~~~~~~~~~~~~~~~
* The minimal per-segment anchor row schema (the table in the u74 plan,
  not a newly invented row set).
* Explicit ``데이터 없음`` / ``미수집`` / ``아직 미제공`` rows with a
  bounded reason enum.
* The rule that a missing row is NEVER a numeric fact (it carries no
  value the LLM/verifier could cite).

What this module consumes (never re-implements)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
* Domestic / US rows read :class:`MarketAnchor` values produced by the
  u49/u55/u67 anchor pipeline. Source precedence is owned upstream; this
  module only reads the reconciled anchors it is handed.
* Crypto indicator rows read the same u66 ``indicator`` raw_metadata
  contract that :mod:`investo.briefing.crypto_indicators` consumes
  (``fear_greed`` / ``global_market`` / ``btc_funding`` / ``btc_oi``).
  A crypto indicator u66 has not yet landed renders ``아직 미제공``
  (``not_yet_available``) rather than an invented value.

Module boundary
~~~~~~~~~~~~~~~
Imports only :mod:`investo.briefing.market_anchor` (MarketAnchor +
anchor_label) and :mod:`investo.models`. Does NOT import from
``orchestrator`` / ``notifier`` / ``sources``.

Determinism: same anchors + same items ⇒ byte-identical block (R9).
"""

from __future__ import annotations

from collections.abc import Sequence
from decimal import ROUND_HALF_UP, Decimal
from enum import StrEnum
from typing import Final, Literal

from investo.briefing.market_anchor import MarketAnchor, anchor_label
from investo.models import NormalizedItem

ChannelSegment = Literal["domestic-equity", "us-equity", "crypto"]

CHANNEL_ANCHOR_HEADER: Final[str] = "## ⓪-B 채널 기준선"

_PRICE_QUANTUM: Final[Decimal] = Decimal("0.01")


class MissingReason(StrEnum):
    """Bounded reason enum for an absent native anchor row (u74 schema).

    Values are the schema enum from the plan. The rendered Korean label
    is intentionally compact and non-alarmist.
    """

    SOURCE_EMPTY = "source_empty"
    MARKET_CLOSED = "market_closed"
    NOT_COLLECTED = "not_collected"
    INSUFFICIENT_ITEMS = "insufficient_items"
    STALE = "stale"
    NOT_YET_AVAILABLE = "not_yet_available"


_REASON_LABELS: Final[dict[MissingReason, str]] = {
    MissingReason.SOURCE_EMPTY: "데이터 없음",
    MissingReason.MARKET_CLOSED: "휴장",
    MissingReason.NOT_COLLECTED: "미수집",
    MissingReason.INSUFFICIENT_ITEMS: "항목 부족",
    MissingReason.STALE: "지연",
    MissingReason.NOT_YET_AVAILABLE: "아직 미제공",
}


# Per-segment row schema: (row_key, Korean label, default missing reason
# when the producer yields no value). Order is the reader-facing order
# from the u74 plan table. ``sector_depth`` / ``macro_yield_or_event`` /
# ``fear_greed`` / ``funding_oi_liquidation`` are non-numeric context
# rows (they never count as a numeric fact even when present).
_ANCHOR_ROW_TICKER: Final[dict[str, str]] = {
    "kospi_close": "^KOSPI",
    "kosdaq_close": "^KOSDAQ",
    "usd_krw": "KRW=X",
    "sp500": "^GSPC",
    "nasdaq_composite": "^IXIC",
    "dow": "^DJI",
    "btc_price_24h": "BTC-USD",
    "eth_price_24h": "ETH-USD",
}

# Schema: segment -> ordered list of (row_key, missing_reason). Labels are
# resolved per row below.
_DOMESTIC_ROWS: Final[tuple[tuple[str, MissingReason], ...]] = (
    ("kospi_close", MissingReason.NOT_COLLECTED),
    ("kosdaq_close", MissingReason.NOT_COLLECTED),
    ("usd_krw", MissingReason.NOT_COLLECTED),
)
_US_ROWS: Final[tuple[tuple[str, MissingReason], ...]] = (
    ("sp500", MissingReason.NOT_COLLECTED),
    ("nasdaq_composite", MissingReason.NOT_COLLECTED),
    ("dow", MissingReason.NOT_COLLECTED),
)
# Crypto indicator rows consumed from u66 raw_metadata. The two index
# rows (BTC/ETH 24h) come from MarketAnchor; the indicator rows come
# from the u66 ``indicator`` contract. ``not_yet_available`` is the
# default reason — u66 may not have landed a given indicator yet.
_CRYPTO_PRICE_ROWS: Final[tuple[tuple[str, MissingReason], ...]] = (
    ("btc_price_24h", MissingReason.NOT_YET_AVAILABLE),
    ("eth_price_24h", MissingReason.NOT_YET_AVAILABLE),
)

_ROW_LABELS: Final[dict[str, str]] = {
    "kospi_close": "KOSPI",
    "kosdaq_close": "KOSDAQ",
    "usd_krw": "원/달러",
    "sp500": "S&P 500",
    "nasdaq_composite": "Nasdaq Composite",
    "dow": "Dow",
    "btc_price_24h": "BTC 24h",
    "eth_price_24h": "ETH 24h",
    "btc_dominance": "BTC 도미넌스",
    "fear_greed": "공포·탐욕",
    "funding_oi_liquidation": "펀딩/OI/청산",
    "cftc_positioning": "CFTC 포지셔닝",
    "cftc_crypto_positioning": "CFTC 코인 포지셔닝",
}

_CFTC_SOURCE_NAME: Final[str] = "cftc-cot-positioning"
_US_CFTC_GROUPS: Final[frozenset[str]] = frozenset(
    {"equity_index", "rates", "fx", "energy", "metals", "volatility"}
)
_CRYPTO_CFTC_GROUPS: Final[frozenset[str]] = frozenset({"crypto"})


def _format_price(value: Decimal) -> str:
    quantized = value.quantize(_PRICE_QUANTUM, rounding=ROUND_HALF_UP)
    return f"{quantized:,.2f}"


def _format_pct(value: Decimal | None) -> str:
    if value is None:
        return "—"
    if value > 0:
        return f"+{value}%"
    return f"{value}%"


def _missing_cell(reason: MissingReason) -> str:
    return _REASON_LABELS[reason]


def _anchor_value_cell(anchor: MarketAnchor) -> str:
    """Render the value cell for a present numeric anchor: ``close (pct)``."""
    return f"{_format_price(anchor.close)} ({_format_pct(anchor.pct)})"


def _meta(item: NormalizedItem, key: str) -> str | None:
    value = item.raw_metadata.get(key)
    return value if isinstance(value, str) and value.strip() else None


def _find_indicator(items: Sequence[NormalizedItem], indicator: str) -> NormalizedItem | None:
    for item in items:
        if _meta(item, "indicator") == indicator:
            return item
    return None


def _dominance_cell(items: Sequence[NormalizedItem]) -> str | None:
    item = _find_indicator(items, "global_market")
    if item is None:
        return None
    pct = _meta(item, "btc_dominance_pct")
    return f"{pct}%" if pct is not None else None


def _fear_greed_cell(items: Sequence[NormalizedItem]) -> str | None:
    item = _find_indicator(items, "fear_greed")
    if item is None:
        return None
    value = _meta(item, "value")
    if value is None:
        return None
    # Value-only: the ⓪-A crypto-indicator block already carries the
    # ``(분류)`` parenthetical gloss. Repeating it here would trip the
    # reader-format gloss-dedupe (which strips a repeated parenthetical),
    # making the chain non-idempotent. The channel block is a compact
    # cross-segment-comparable anchor grid, so the bare score suffices.
    return value


def _funding_oi_cell(items: Sequence[NormalizedItem]) -> str | None:
    """Combined funding/OI cell. 24h liquidation has no free source (u66)."""
    funding_item = _find_indicator(items, "btc_funding")
    oi_item = _find_indicator(items, "btc_oi")
    parts: list[str] = []
    if funding_item is not None:
        rate = _meta(funding_item, "btc_funding_rate")
        if rate is not None:
            parts.append(f"펀딩 {rate}")
    if oi_item is not None and _meta(oi_item, "btc_oi_usd") is not None:
        parts.append("OI 수집됨")
    if not parts:
        return None
    return " · ".join(parts)


def _cftc_positioning_cell(
    items: Sequence[NormalizedItem],
    *,
    groups: frozenset[str],
) -> str | None:
    rows: list[str] = []
    for item in items:
        if item.source_name != _CFTC_SOURCE_NAME:
            continue
        group = _meta(item, "contract_group")
        if group not in groups:
            continue
        label = _meta(item, "contract_label")
        net = _meta(item, "net_contracts")
        pct = _meta(item, "net_pct_open_interest")
        as_of = _meta(item, "as_of_date")
        release = _meta(item, "release_date")
        if None in (label, net, pct, as_of, release):
            continue
        rows.append(f"{label} 순포지션 {net}계약 ({pct}% OI), {as_of} 기준/{release} 공개")
    if not rows:
        return None
    return " · ".join(rows[:3]) + " · 주간 지연"


def _row_line(label: str, value_cell: str) -> str:
    safe = value_cell.replace("|", "\\|")
    return f"| {label} | {safe} |"


def _row_label(row_key: str) -> str:
    """Resolve a row's reader label.

    Index/FX rows route through the u70 canonical :func:`anchor_label`
    registry (single label authority) so the channel block never drifts
    from the anchor table / chart card naming. Non-ticker rows
    (도미넌스 / 공포·탐욕 / 펀딩) fall back to the local schema label.
    """
    ticker = _ANCHOR_ROW_TICKER.get(row_key)
    if ticker is not None:
        ko = anchor_label(ticker).ko
        # ``anchor_label`` falls back to the raw symbol for unknown
        # tickers; prefer the schema label in that degenerate case.
        if ko != ticker:
            return ko
    return _ROW_LABELS[row_key]


def _anchor_rows(
    rows: Sequence[tuple[str, MissingReason]],
    anchors_by_ticker: dict[str, MarketAnchor],
) -> tuple[list[str], bool]:
    """Render the anchor rows; return (lines, any_present)."""
    lines: list[str] = []
    any_present = False
    for row_key, default_reason in rows:
        ticker = _ANCHOR_ROW_TICKER[row_key]
        label = _row_label(row_key)
        anchor = anchors_by_ticker.get(ticker)
        if anchor is not None:
            lines.append(_row_line(label, _anchor_value_cell(anchor)))
            any_present = True
        else:
            lines.append(_row_line(label, _missing_cell(default_reason)))
    return lines, any_present


def render_channel_anchor_block(
    segment: ChannelSegment,
    *,
    anchors: Sequence[MarketAnchor] = (),
    crypto_items: Sequence[NormalizedItem] = (),
    source_items: Sequence[NormalizedItem] = (),
) -> str:
    """Render the deterministic native-anchor block for ``segment`` (u74).

    Every schema row for the segment is rendered. A row whose producer
    yielded no value renders an explicit missing-reason cell — never an
    invented value and never a silent omission.

    * domestic-equity → KOSPI / KOSDAQ / 원/달러 (consumes u67 anchors).
    * us-equity → S&P 500 / Nasdaq Composite / Dow (consumes u49/u55).
    * crypto → BTC/ETH 24h (u66/u49 anchors) + BTC 도미넌스 /
      공포·탐욕 / 펀딩·OI·청산 (u66 indicator contract). Indicators u66
      has not yet supplied render ``아직 미제공``.

    Returns the full ``## ⓪-B`` block (header + 2-column table). The
    block is deterministic for fixed inputs and idempotent at the
    injection layer (the header sentinel guards re-injection).

    When the segment has **no** present native value at all (every row
    would be a missing-reason cell), an all-empty grid is noise — the
    segment's data-limited state is already surfaced by the coverage
    badges — so the renderer returns an empty string and the caller omits
    the block. A block renders as soon as ≥ 1 native value is present,
    and the missing rows in that block render explicit reasons (AC-74.2).
    """
    anchors_by_ticker = {a.ticker: a for a in anchors}
    body: list[str] = []
    any_present = False

    if segment == "domestic-equity":
        body, any_present = _anchor_rows(_DOMESTIC_ROWS, anchors_by_ticker)
    elif segment == "us-equity":
        body, any_present = _anchor_rows(_US_ROWS, anchors_by_ticker)
        cftc_cell = _cftc_positioning_cell(source_items, groups=_US_CFTC_GROUPS)
        if cftc_cell is not None:
            any_present = True
        body.append(
            _row_line(
                _ROW_LABELS["cftc_positioning"],
                cftc_cell if cftc_cell is not None else _missing_cell(MissingReason.NOT_COLLECTED),
            )
        )
    else:  # crypto
        crypto_source_items = source_items or crypto_items
        body, any_present = _anchor_rows(_CRYPTO_PRICE_ROWS, anchors_by_ticker)
        # u66 indicator rows — a value u66 has not yet supplied renders the
        # not_yet_available reason rather than an invented figure.
        nya = MissingReason.NOT_YET_AVAILABLE
        for row_key, cell in (
            ("btc_dominance", _dominance_cell(crypto_items)),
            ("fear_greed", _fear_greed_cell(crypto_items)),
            ("funding_oi_liquidation", _funding_oi_cell(crypto_items)),
        ):
            if cell is not None:
                any_present = True
            value = cell if cell is not None else _missing_cell(nya)
            body.append(_row_line(_ROW_LABELS[row_key], value))
        cftc_cell = _cftc_positioning_cell(crypto_source_items, groups=_CRYPTO_CFTC_GROUPS)
        if cftc_cell is not None:
            any_present = True
        body.append(
            _row_line(
                _ROW_LABELS["cftc_crypto_positioning"],
                cftc_cell if cftc_cell is not None else _missing_cell(MissingReason.NOT_COLLECTED),
            )
        )

    if not any_present:
        return ""

    lines = [CHANNEL_ANCHOR_HEADER, "", "| 기준선 | 값 |", "|------|------|", *body]
    return "\n".join(lines) + "\n"


def inject_channel_anchor_block(text: str, block: str) -> str:
    """Insert the channel anchor block (idempotent).

    Placed before the first ``## ①`` section so it sits in the header
    band alongside the macro / crypto-indicator blocks. Re-injection is a
    no-op (header sentinel guard).
    """
    if not block:
        return text
    if CHANNEL_ANCHOR_HEADER in text:
        return text
    rendered = f"{block.strip()}\n\n"
    first_section = text.find("## ①")
    if first_section != -1:
        return text[:first_section] + rendered + text[first_section:]
    return f"{text.rstrip()}\n\n{rendered}"


__all__ = [
    "CHANNEL_ANCHOR_HEADER",
    "ChannelSegment",
    "MissingReason",
    "inject_channel_anchor_block",
    "render_channel_anchor_block",
]

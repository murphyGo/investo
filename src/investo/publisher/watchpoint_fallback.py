"""u135 — deterministic §⑥ fallback rows from reconciled public inputs.

This module is a pure publisher sibling of :mod:`watchpoint_matrix`. It reads
only the immutable value payload already supplied to the publisher, emits at
most two existing-shape ``WatchpointRow`` values, performs no I/O, and makes no
LLM call. Rendering and compliance remain owned by the existing matrix and
segment-reader chain.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Final

from investo.models.market_anchor import MarketAnchor, anchor_label
from investo.models.segments import MarketSegment
from investo.publisher.watchpoint_matrix import (
    ConfidenceLabel,
    WatchpointItemSnapshot,
    WatchpointRow,
    WatchpointValuePayload,
    resolve_watchpoint_currents,
)

MAX_SYNTHESIZED_ROWS: Final[int] = 2


@dataclass(frozen=True, slots=True)
class ClosedWatchpointTemplate:
    signal: str
    current: str
    upside: str
    downside: str
    confidence: ConfidenceLabel
    implication: str
    source: str


RANGE_TEMPLATE: Final[ClosedWatchpointTemplate] = ClosedWatchpointTemplate(
    signal="{label} 가격 구간",
    current="{current}",
    upside="{upper} 상회 시 단기 회복 흐름 관찰",
    downside="{lower} 이탈 시 방어적 수급 관찰",
    confidence="높음",
    implication="본문 §⑤ 가격 동향과 연계 점검.",
    source="{source}",
)
CFTC_TEMPLATE: Final[ClosedWatchpointTemplate] = ClosedWatchpointTemplate(
    signal="{contract} 포지셔닝",
    current="{current}",
    upside="순매도 축소 전환 관찰",
    downside="순매도 확대 지속 관찰",
    confidence="보통",
    implication="가격과 포지셔닝 괴리 지속 여부 점검.",
    source="CFTC",
)
FEAR_GREED_TEMPLATE: Final[ClosedWatchpointTemplate] = ClosedWatchpointTemplate(
    signal="공포·탐욕 지수",
    current="{value} ({band})",
    upside="20 상회 시 심리 회복 관찰",
    downside="10 이탈 시 극단 공포 심화 관찰",
    confidence="높음",
    implication="반등 지속성 판단 보조 지표.",
    source="Alternative.me",
)
GREED_TEMPLATE: Final[ClosedWatchpointTemplate] = ClosedWatchpointTemplate(
    signal="공포·탐욕 지수",
    current="{value} ({band})",
    upside="90 상회 시 심리 과열 심화 관찰",
    downside="80 이탈 시 심리 과열 완화 관찰",
    confidence="높음",
    implication="반등 지속성 판단 보조 지표.",
    source="Alternative.me",
)

_MAX_NUMERIC_CHARS: Final[int] = 64
_MAX_MAGNITUDE: Final[int] = 18
_PRICE_QUANTUM: Final[Decimal] = Decimal("0.01")
_CRYPTO_ANCHOR_PRIORITY: Final[tuple[str, ...]] = ("BTC-USD", "ETH-USD", "SOL-USD")
_US_ANCHOR_PRIORITY: Final[tuple[str, ...]] = ("^GSPC", "^IXIC", "^DJI", "^NDX")
_DOMESTIC_ANCHOR_PRIORITY: Final[tuple[str, ...]] = ("^KOSPI", "^KOSDAQ", "KRW=X")
_CFTC_US_GROUPS: Final[frozenset[str]] = frozenset(
    {"equity_index", "rates", "fx", "energy", "metals", "volatility"}
)
_CFTC_CRYPTO_GROUPS: Final[frozenset[str]] = frozenset({"crypto"})


def _decimal(raw: object) -> Decimal | None:
    text = str(raw).strip()
    if not text or len(text) > _MAX_NUMERIC_CHARS:
        return None
    try:
        value = Decimal(text)
    except InvalidOperation:
        return None
    if not value.is_finite() or abs(value.adjusted()) > _MAX_MAGNITUDE:
        return None
    return value


def _price_prefix(anchor: MarketAnchor, segment: MarketSegment) -> str:
    if segment == "crypto":
        return "$"
    if segment == "us-equity" and not anchor.ticker.startswith("^"):
        return "$"
    if segment == "domestic-equity" and anchor.ticker.endswith((".KS", ".KQ")):
        return "₩"
    return ""


def _format_price(value: Decimal, *, prefix: str) -> str | None:
    if not value.is_finite() or value <= 0 or abs(value.adjusted()) > _MAX_MAGNITUDE:
        return None
    try:
        quantized = value.quantize(_PRICE_QUANTUM, rounding=ROUND_HALF_UP)
    except InvalidOperation:
        return None
    if quantized <= 0:
        return None
    return f"{prefix}{quantized:,.2f}"


def _ordered_anchors(payload: WatchpointValuePayload) -> tuple[MarketAnchor, ...]:
    priority = {
        "crypto": _CRYPTO_ANCHOR_PRIORITY,
        "us-equity": _US_ANCHOR_PRIORITY,
        "domestic-equity": _DOMESTIC_ANCHOR_PRIORITY,
    }[payload.segment]
    by_ticker = {anchor.ticker: anchor for anchor in payload.anchors}
    ordered = [by_ticker[ticker] for ticker in priority if ticker in by_ticker]
    ordered.extend(anchor for anchor in payload.anchors if anchor not in ordered)
    return tuple(ordered)


def _crypto_range(
    anchor: MarketAnchor,
    items: tuple[WatchpointItemSnapshot, ...],
) -> tuple[Decimal, Decimal] | None:
    symbol = anchor.ticker.removesuffix("-USD").casefold()
    for item in items:
        if item.source_name != "coingecko-price":
            continue
        if (item.get("symbol") or "").casefold() != symbol:
            continue
        upper = _decimal(item.get("high_24h"))
        lower = _decimal(item.get("low_24h"))
        if upper is not None and lower is not None and upper >= anchor.close >= lower > 0:
            return upper, lower
    return None


def _equity_range(anchor: MarketAnchor) -> tuple[Decimal, Decimal] | None:
    high_pct = anchor.pct_from_52w_high
    low_pct = anchor.pct_from_52w_low
    if (
        high_pct is None
        or low_pct is None
        or not high_pct.is_finite()
        or not low_pct.is_finite()
        or high_pct > 0
        or low_pct < 0
    ):
        return None
    high_denominator = Decimal(1) + (high_pct / Decimal(100))
    low_denominator = Decimal(1) + (low_pct / Decimal(100))
    if high_denominator <= 0 or low_denominator <= 0:
        return None
    upper = anchor.close / high_denominator
    lower = anchor.close / low_denominator
    if upper < anchor.close or lower > anchor.close or lower <= 0:
        return None
    return upper, lower


def _format_template_row(
    template: ClosedWatchpointTemplate,
    **values: object,
) -> WatchpointRow:
    strings = {key: str(value) for key, value in values.items()}
    return WatchpointRow(
        signal=template.signal.format(**strings),
        source=template.source.format(**strings),
        current=template.current.format(**strings),
        bullish_trigger=template.upside.format(**strings),
        bearish_trigger=template.downside.format(**strings),
        confidence=template.confidence,
        implication=template.implication.format(**strings),
    )


def _range_row(payload: WatchpointValuePayload) -> WatchpointRow | None:
    for anchor in _ordered_anchors(payload):
        range_values = (
            _crypto_range(anchor, payload.item_snapshots)
            if payload.segment == "crypto"
            else _equity_range(anchor)
        )
        if range_values is None:
            continue
        upper, lower = range_values
        prefix = _price_prefix(anchor, payload.segment)
        upper_text = _format_price(upper, prefix=prefix)
        lower_text = _format_price(lower, prefix=prefix)
        if upper_text is None or lower_text is None:
            continue
        label = anchor_label(anchor.ticker).ko
        unresolved = _format_template_row(
            RANGE_TEMPLATE,
            label=label,
            current="시장 앵커",
            upper=upper_text,
            lower=lower_text,
            source="CoinGecko" if payload.segment == "crypto" else "검증된 시장 앵커",
        )
        resolved = resolve_watchpoint_currents((unresolved,), payload)
        if resolved:
            return resolved[0]
    return None


def _cftc_row(payload: WatchpointValuePayload) -> WatchpointRow | None:
    if payload.segment == "domestic-equity":
        return None
    groups = _CFTC_CRYPTO_GROUPS if payload.segment == "crypto" else _CFTC_US_GROUPS
    for item in payload.item_snapshots:
        if item.source_name != "cftc-cot-positioning" or item.get("contract_group") not in groups:
            continue
        contract = item.get("contract_label")
        net = _decimal(item.get("net_contracts"))
        oi_pct = _decimal(item.get("net_pct_open_interest"))
        if (
            contract is None
            or net is None
            or net >= 0
            or net != net.to_integral_value()
            or oi_pct is None
            or oi_pct >= 0
        ):
            continue
        unresolved = _format_template_row(
            CFTC_TEMPLATE,
            contract=contract,
            current="CFTC",
        )
        resolved = resolve_watchpoint_currents((unresolved,), payload)
        if resolved:
            return resolved[0]
    return None


def _fear_greed_row(payload: WatchpointValuePayload) -> WatchpointRow | None:
    if payload.segment != "crypto":
        return None
    for item in payload.item_snapshots:
        if item.get("indicator") != "fear_greed":
            continue
        value = _decimal(item.get("value"))
        if (
            value is None
            or value != value.to_integral_value()
            or not Decimal(0) <= value <= Decimal(100)
            or Decimal(20) < value < Decimal(80)
        ):
            continue
        is_fear = value <= Decimal(20)
        band = "극단 공포" if is_fear else "극단 탐욕"
        return _format_template_row(
            FEAR_GREED_TEMPLATE if is_fear else GREED_TEMPLATE,
            value=int(value),
            band=band,
        )
    return None


def synthesize_watchpoint_rows(payload: WatchpointValuePayload) -> tuple[WatchpointRow, ...]:
    """Return at most two rows in the pinned range → CFTC → F&G priority."""

    candidates = (_range_row(payload), _cftc_row(payload), _fear_greed_row(payload))
    return tuple(row for row in candidates if row is not None)[:MAX_SYNTHESIZED_ROWS]


__all__ = [
    "CFTC_TEMPLATE",
    "FEAR_GREED_TEMPLATE",
    "GREED_TEMPLATE",
    "MAX_SYNTHESIZED_ROWS",
    "RANGE_TEMPLATE",
    "ClosedWatchpointTemplate",
    "synthesize_watchpoint_rows",
]

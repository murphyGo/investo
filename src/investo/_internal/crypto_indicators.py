"""Pure crypto-native indicator table renderer."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Final

from investo.models import NormalizedItem

CRYPTO_INDICATOR_HEADER: Final[str] = "## ⓪-A 크립토 지표 (UTC 24h 스냅샷)"

_NOT_COLLECTED: Final[str] = "수집 안 됨"
_NO_FREE_SOURCE: Final[str] = "무료 검증 소스 미확정"


def _meta(item: NormalizedItem, key: str) -> str | None:
    value = item.raw_metadata.get(key)
    return value if isinstance(value, str) and value.strip() else None


def _find_by_indicator(items: Sequence[NormalizedItem], indicator: str) -> NormalizedItem | None:
    for item in items:
        if _meta(item, "indicator") == indicator:
            return item
    return None


def _find_by_metric(items: Sequence[NormalizedItem], metric: str) -> NormalizedItem | None:
    for item in items:
        if _meta(item, "metric") == metric:
            return item
    return None


def _format_usd_compact(raw: str | None) -> str | None:
    if raw is None:
        return None
    try:
        value = float(raw)
    except ValueError:
        return None
    abs_value = abs(value)
    if abs_value >= 1e12:
        return f"${value / 1e12:.2f}T"
    if abs_value >= 1e9:
        return f"${value / 1e9:.1f}B"
    if abs_value >= 1e6:
        return f"${value / 1e6:.1f}M"
    return f"${value:,.0f}"


def _fear_greed_row(items: Sequence[NormalizedItem]) -> str:
    item = _find_by_indicator(items, "fear_greed")
    if item is None:
        return _NOT_COLLECTED
    value = _meta(item, "value")
    classification = _meta(item, "classification")
    if value is None:
        return _NOT_COLLECTED
    if classification:
        return f"{value} ({classification})"
    return value


def _dominance_row(items: Sequence[NormalizedItem]) -> str:
    item = _find_by_indicator(items, "global_market")
    if item is None:
        return _NOT_COLLECTED
    pct = _meta(item, "btc_dominance_pct")
    return f"{pct}%" if pct is not None else _NOT_COLLECTED


def _total_market_cap_row(items: Sequence[NormalizedItem]) -> str:
    item = _find_by_indicator(items, "global_market")
    if item is None:
        return _NOT_COLLECTED
    mcap = _format_usd_compact(_meta(item, "total_market_cap_usd"))
    if mcap is None:
        return _NOT_COLLECTED
    change = _meta(item, "market_cap_change_24h_pct")
    if change is not None:
        try:
            change_f = float(change)
        except ValueError:
            return mcap
        sign = "+" if change_f >= 0 else ""
        return f"{mcap} ({sign}{change_f:.2f}% 24h)"
    return mcap


def _funding_row(items: Sequence[NormalizedItem]) -> str:
    item = _find_by_indicator(items, "btc_funding")
    if item is None:
        return _NOT_COLLECTED
    rate = _meta(item, "btc_funding_rate")
    if rate is None:
        return _NOT_COLLECTED
    source = _meta(item, "funding_source")
    return f"{rate} ({source})" if source else rate


def _oi_row(items: Sequence[NormalizedItem]) -> str:
    item = _find_by_indicator(items, "btc_oi")
    if item is None:
        return _NOT_COLLECTED
    oi = _format_usd_compact(_meta(item, "btc_oi_usd"))
    if oi is None:
        return _NOT_COLLECTED
    source = _meta(item, "oi_source")
    return f"{oi} ({source})" if source else oi


def _defi_tvl_row(items: Sequence[NormalizedItem]) -> str:
    item = _find_by_metric(items, "chain_tvl")
    if item is None:
        return _NOT_COLLECTED
    tvl = _format_usd_compact(_meta(item, "total_tvl_usd"))
    return tvl if tvl is not None else _NOT_COLLECTED


def _stablecoin_row(items: Sequence[NormalizedItem]) -> str:
    item = _find_by_metric(items, "stablecoin_supply")
    if item is None:
        return _NOT_COLLECTED
    supply = _format_usd_compact(_meta(item, "total_supply_usd"))
    return supply if supply is not None else _NOT_COLLECTED


def render_crypto_indicator_block(items: Sequence[NormalizedItem]) -> str:
    """Render the deterministic crypto indicator markdown table."""
    rows: list[tuple[str, str]] = [
        ("공포·탐욕", _fear_greed_row(items)),
        ("BTC 도미넌스", _dominance_row(items)),
        ("전체 시총", _total_market_cap_row(items)),
        ("BTC 펀딩비", _funding_row(items)),
        ("BTC 미결제약정", _oi_row(items)),
        ("DeFi TVL", _defi_tvl_row(items)),
        ("스테이블코인 공급", _stablecoin_row(items)),
        ("24h 청산 / 거래소 순유출입", _NO_FREE_SOURCE),
    ]
    lines = [CRYPTO_INDICATOR_HEADER, "", "| 지표 | 값 |", "|------|------|"]
    for label, value in rows:
        safe = value.replace("|", "\\|")
        lines.append(f"| {label} | {safe} |")
    return "\n".join(lines) + "\n"


__all__ = [
    "CRYPTO_INDICATOR_HEADER",
    "render_crypto_indicator_block",
]

"""Pure crypto-native indicator table renderer."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Final

from investo._internal.decimal_format import shortest_exact_decimal
from investo.models import NormalizedItem
from investo.models.exchange_flows import ExchangeFlow

CRYPTO_INDICATOR_HEADER: Final[str] = "## ⓪-A 크립토 지표"

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
    rate = shortest_exact_decimal(rate)
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


def validated_exchange_flows(items: Sequence[NormalizedItem]) -> tuple[ExchangeFlow, ...]:
    """Only validated source observations may enter either publication format."""
    flows: dict[str, ExchangeFlow] = {}
    for item in items:
        if item.source_name != "coinmetrics-exchange-flows":
            continue
        try:
            flow = ExchangeFlow.from_metadata(item.raw_metadata)
        except (ValueError, TypeError, OverflowError):
            continue
        if flow.asset not in flows or flows[flow.asset].day < flow.day:
            flows[flow.asset] = flow
    return tuple(flows[asset] for asset in sorted(flows))


def _exchange_flow_rows(flows: Sequence[ExchangeFlow]) -> list[tuple[str, str]]:
    by_asset = {flow.asset: flow for flow in flows}
    rows = []
    for asset in ("btc", "eth"):
        selected = by_asset.get(asset)
        value = _NOT_COLLECTED
        if selected is not None:
            value = (
                f"{selected.netflow} {asset.upper()} · {selected.day} UTC 일별 · "
                f"{selected.status_label}"
            )
        rows.append((f"{asset.upper()} 거래소 일별 순유입", value))
    return rows


_FLOW_ATTRIBUTION = (
    "일별 순유입 출처: [Coin Metrics Community](https://github.com/coinmetrics/data) · "
    "[CC BY-NC 4.0](https://creativecommons.org/licenses/by-nc/4.0/). "
    "Investo가 유입 - 유출로 계산(양수: 유입 초과, 음수: 유출 초과). "
    "추적 거래소 주소 기준이며 거래소 간 이체 제외. "
    "실시간·전체 거래소·매매 체결량이 아니며, 잠정/검토/수정 상태는 향후 변경될 수 있음."
)


def render_exchange_flow_reference(flows: Sequence[ExchangeFlow]) -> str:
    """Native edition supplemental panel, using the same values and attribution."""
    if not flows:
        return ""
    lines = ["### 일별 거래소 순유입", "", "| 지표 | 값 |", "|------|------|"]
    lines.extend(f"| {label} | {value} |" for label, value in _exchange_flow_rows(flows))
    return "\n".join([*lines, "", _FLOW_ATTRIBUTION, ""])


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
        ("24h 청산", _NO_FREE_SOURCE),
    ]
    flows = validated_exchange_flows(items)
    rows.extend(_exchange_flow_rows(flows))
    lines = [CRYPTO_INDICATOR_HEADER, "", "| 지표 | 값 |", "|------|------|"]
    for label, value in rows:
        safe = value.replace("|", "\\|")
        lines.append(f"| {label} | {safe} |")
    if flows:
        lines.extend(["", _FLOW_ATTRIBUTION])
    return "\n".join(lines) + "\n"


__all__ = [
    "CRYPTO_INDICATOR_HEADER",
    "render_crypto_indicator_block",
]

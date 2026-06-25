"""Tests for the u66 crypto indicator block (render + inject + contract).

Covers Step 5 (deterministic render, full/partial/missing rows,
idempotent inject) and the u74 raw_metadata contract pin (Step 8): the
renderer consumes exactly the ``indicator`` / key names / units that the
adapters emit.
"""

from __future__ import annotations

from datetime import UTC, datetime

from investo._internal.crypto_indicators import (
    CRYPTO_INDICATOR_HEADER,
    render_crypto_indicator_block,
)
from investo.briefing import crypto_indicators as legacy_crypto_indicators
from investo.models import NormalizedItem
from investo.publisher.crypto_indicators import inject_crypto_indicator_block


def _item(raw_metadata: dict[str, str], *, title: str = "x") -> NormalizedItem:
    return NormalizedItem(
        source_name="alternative-fng",
        category="macro",
        title=title,
        published_at=datetime(2026, 5, 23, tzinfo=UTC),
        raw_metadata=raw_metadata,
    )


def _full_items() -> list[NormalizedItem]:
    return [
        _item({"indicator": "fear_greed", "value": "28", "classification": "Fear"}),
        _item(
            {
                "indicator": "global_market",
                "btc_dominance_pct": "58.07",
                "total_market_cap_usd": "2623499078661",
                "market_cap_change_24h_pct": "0.2501",
            }
        ),
        _item(
            {
                "indicator": "btc_funding",
                "btc_funding_rate": "0.00003545",
                "funding_source": "bybit",
            }
        ),
        _item({"indicator": "btc_oi", "btc_oi_usd": "4103494620", "oi_source": "bybit"}),
        _item({"metric": "chain_tvl", "total_tvl_usd": "98000000000"}),
        _item({"metric": "stablecoin_supply", "total_supply_usd": "165000000000"}),
    ]


def test_full_block_renders_all_rows() -> None:
    block = render_crypto_indicator_block(_full_items())
    assert CRYPTO_INDICATOR_HEADER in block
    assert "| 공포·탐욕 | 28 (Fear) |" in block
    assert "| BTC 도미넌스 | 58.07% |" in block
    assert "$2.62T" in block
    assert "(+0.25% 24h)" in block
    assert "| BTC 펀딩비 | 0.00003545 (bybit) |" in block
    assert "$4.1B (bybit)" in block
    assert "$98.0B" in block  # DeFi TVL
    assert "$165.0B" in block  # stablecoin
    assert "무료 검증 소스 미확정" in block  # scope-out row


def test_missing_indicators_render_not_collected() -> None:
    block = render_crypto_indicator_block([])
    # All data rows show 수집 안 됨; the scope-out row shows the no-source label.
    assert block.count("수집 안 됨") == 7
    assert block.count("무료 검증 소스 미확정") == 1


def test_partial_block_only_some_rows() -> None:
    items = [_item({"indicator": "fear_greed", "value": "50", "classification": "Neutral"})]
    block = render_crypto_indicator_block(items)
    assert "| 공포·탐욕 | 50 (Neutral) |" in block
    assert "| BTC 도미넌스 | 수집 안 됨 |" in block


def test_render_is_deterministic() -> None:
    items = _full_items()
    assert render_crypto_indicator_block(items) == render_crypto_indicator_block(items)


def test_legacy_briefing_crypto_indicator_import_reexports_renderer() -> None:
    assert legacy_crypto_indicators.CRYPTO_INDICATOR_HEADER is CRYPTO_INDICATOR_HEADER
    assert legacy_crypto_indicators.render_crypto_indicator_block is render_crypto_indicator_block


def test_never_invents_values_for_scope_out_rows() -> None:
    block = render_crypto_indicator_block(_full_items())
    # The liquidation / netflow row must NEVER carry a numeric value.
    line = next(ln for ln in block.splitlines() if "24h 청산" in ln)
    assert "무료 검증 소스 미확정" in line
    assert "$" not in line


# ---------------------------------------------------------------------------
# Injection
# ---------------------------------------------------------------------------

_DOC = "# 제목\n\n## 한눈에 보기\n\n- a\n\n## ① 요약\n\n본문\n"


def test_inject_places_block_before_section_one() -> None:
    block = render_crypto_indicator_block(_full_items())
    out = inject_crypto_indicator_block(_DOC, block)
    assert CRYPTO_INDICATOR_HEADER in out
    assert out.index(CRYPTO_INDICATOR_HEADER) < out.index("## ① 요약")
    assert out.index("## 한눈에 보기") < out.index(CRYPTO_INDICATOR_HEADER)


def test_inject_after_shared_macro_block() -> None:
    doc = "# 제목\n\n## 한눈에 보기\n\n- a\n\n## ⓪ 오늘의 매크로\n\n- macro\n\n## ① 요약\n\n본문\n"
    block = render_crypto_indicator_block(_full_items())
    out = inject_crypto_indicator_block(doc, block)
    assert out.index("## ⓪ 오늘의 매크로") < out.index(CRYPTO_INDICATOR_HEADER)
    assert out.index(CRYPTO_INDICATOR_HEADER) < out.index("## ① 요약")


def test_inject_is_idempotent() -> None:
    block = render_crypto_indicator_block(_full_items())
    once = inject_crypto_indicator_block(_DOC, block)
    twice = inject_crypto_indicator_block(once, block)
    assert once == twice


def test_inject_empty_block_is_noop() -> None:
    assert inject_crypto_indicator_block(_DOC, "") == _DOC
    assert inject_crypto_indicator_block(_DOC, None) == _DOC


# ---------------------------------------------------------------------------
# u74 contract pin — exact indicator tags / key names / units
# ---------------------------------------------------------------------------


def test_u74_contract_keys_consumed() -> None:
    """The renderer must key off exactly the u74 indicator tags / keys."""
    # fear_greed: value + classification
    fg = render_crypto_indicator_block(
        [_item({"indicator": "fear_greed", "value": "10", "classification": "Extreme Fear"})]
    )
    assert "10 (Extreme Fear)" in fg
    # global_market: btc_dominance_pct + total_market_cap_usd
    gm = render_crypto_indicator_block(
        [
            _item(
                {
                    "indicator": "global_market",
                    "btc_dominance_pct": "60.00",
                    "total_market_cap_usd": "1000000000000",
                }
            )
        ]
    )
    assert "60.00%" in gm
    assert "$1.00T" in gm
    # btc_funding: btc_funding_rate + funding_source (okx)
    fund = render_crypto_indicator_block(
        [
            _item(
                {"indicator": "btc_funding", "btc_funding_rate": "-0.0001", "funding_source": "okx"}
            )
        ]
    )
    assert "-0.0001 (okx)" in fund
    # btc_oi: btc_oi_usd + oi_source
    oi = render_crypto_indicator_block(
        [_item({"indicator": "btc_oi", "btc_oi_usd": "5000000000", "oi_source": "okx"})]
    )
    assert "$5.0B (okx)" in oi

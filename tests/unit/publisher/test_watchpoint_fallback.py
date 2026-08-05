"""u135 deterministic watchpoint fallback tests."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from investo.models.compliance_phrases import (
    BANNED_P0_ACTION,
    BANNED_P0_CERTAINTY,
    BANNED_P0_CRYPTO_ONLY,
    BANNED_P0_QUANTIFIED_OUTCOME,
)
from investo.models.items import NormalizedItem
from investo.models.market_anchor import MarketAnchor
from investo.publisher.compliance_language import scan_compliance
from investo.publisher.reader_format import (
    _WATCHPOINT_IMPLICATION_RE,
    _WATCHPOINT_SOURCE_RE,
    _WATCHPOINT_TRIGGER_RE,
)
from investo.publisher.watchpoint_fallback import (
    CFTC_TEMPLATE,
    DOMESTIC_CLOSE_TEMPLATE,
    FEAR_GREED_TEMPLATE,
    GREED_TEMPLATE,
    MAX_SYNTHESIZED_ROWS,
    RANGE_TEMPLATE,
    synthesize_watchpoint_rows,
)
from investo.publisher.watchpoint_matrix import WatchpointValuePayload, render_matrix_table


def _item(source_name: str, metadata: dict[str, str]) -> NormalizedItem:
    return NormalizedItem(
        source_name=source_name,
        category="price" if source_name == "coingecko-price" else "macro",
        title=f"{source_name} fallback fixture",
        published_at=datetime(2026, 6, 30, tzinfo=UTC),
        raw_metadata=metadata,
    )


def _us_anchor() -> MarketAnchor:
    return MarketAnchor(
        ticker="^GSPC",
        close=Decimal("7000"),
        prev_close=Decimal("6930.69"),
        pct=Decimal("1.00"),
        is_ath=False,
        pct_from_52w_high=Decimal("-5.00"),
        pct_from_52w_low=Decimal("20.00"),
    )


def _btc_anchor() -> MarketAnchor:
    return MarketAnchor(
        ticker="BTC-USD",
        close=Decimal("60284"),
        prev_close=Decimal("58969.09"),
        pct=Decimal("2.23"),
        is_ath=False,
        pct_from_52w_high=Decimal("-10.00"),
        pct_from_52w_low=Decimal("30.00"),
    )


def _cftc(group: str = "equity_index", *, net: str = "-451586") -> NormalizedItem:
    return _item(
        "cftc-cot-positioning",
        {
            "contract_label": "E-mini S&P 500" if group != "crypto" else "Bitcoin CME",
            "contract_group": group,
            "net_contracts": net,
            "net_pct_open_interest": "-20.50" if group != "crypto" else "-4.20",
        },
    )


def _fear_greed(value: str) -> NormalizedItem:
    return _item(
        "alternative-fng",
        {"indicator": "fear_greed", "value": value, "classification": "fixture"},
    )


def _coingecko() -> NormalizedItem:
    return _item(
        "coingecko-price",
        {
            "coin_id": "bitcoin",
            "symbol": "btc",
            "price_usd": "60284",
            "pct_24h": "2.23",
            "high_24h": "60644",
            "low_24h": "58935",
        },
    )


def test_closed_templates_are_existing_card_field_payloads() -> None:
    assert MAX_SYNTHESIZED_ROWS == 2
    assert RANGE_TEMPLATE.signal == "{label} 가격 구간"
    assert RANGE_TEMPLATE.upside == "{upper} 상회 시 단기 회복 흐름 관찰"
    assert DOMESTIC_CLOSE_TEMPLATE.signal == "{label} 종가 기준선"
    assert CFTC_TEMPLATE.confidence == "보통"
    assert FEAR_GREED_TEMPLATE.downside == "10 이탈 시 극단 공포 심화 관찰"
    assert GREED_TEMPLATE.downside == "80 이탈 시 심리 과열 완화 관찰"


def test_us_fallback_synthesizes_range_then_cftc_in_pinned_order() -> None:
    payload = WatchpointValuePayload.from_inputs(
        "us-equity",
        anchors=(_us_anchor(),),
        items=(_cftc(),),
    )

    rows = synthesize_watchpoint_rows(payload)

    assert [row.signal for row in rows] == ["S&P 500 가격 구간", "E-mini S&P 500 포지셔닝"]
    assert rows[0].current == "7,000.00 (+1%)"
    assert rows[0].bullish_trigger == "7,368.42 상회 시 단기 회복 흐름 관찰"
    assert rows[0].bearish_trigger == "5,833.33 이탈 시 방어적 수급 관찰"
    assert rows[0].confidence == "높음"
    assert rows[1].current == "순포지션 -451,586계약 (-20.5% OI, 주간 지연)"
    assert rows[1].confidence == "보통"
    assert "데이터부족" not in render_matrix_table(list(rows))


def test_crypto_fallback_caps_range_cftc_fng_candidates_at_two() -> None:
    payload = WatchpointValuePayload.from_inputs(
        "crypto",
        anchors=(_btc_anchor(),),
        items=(_coingecko(), _cftc("crypto", net="-2400"), _fear_greed("18")),
    )

    first = synthesize_watchpoint_rows(payload)
    second = synthesize_watchpoint_rows(payload)

    assert first == second
    assert len(first) == MAX_SYNTHESIZED_ROWS
    assert [row.signal for row in first] == ["비트코인 가격 구간", "Bitcoin CME 포지셔닝"]
    assert first[0].current == "$60,284.00 (+2.23%)"
    assert first[0].bullish_trigger.startswith("$60,644.00 상회")
    assert first[0].bearish_trigger.startswith("$58,935.00 이탈")
    assert all(row.confidence != "근거 제한" for row in first)


def test_fear_greed_extremes_are_third_priority_and_midrange_is_not_resolvable() -> None:
    low_payload = WatchpointValuePayload.from_inputs("crypto", items=(_fear_greed("18"),))
    high_payload = WatchpointValuePayload.from_inputs("crypto", items=(_fear_greed("85"),))
    mid_payload = WatchpointValuePayload.from_inputs("crypto", items=(_fear_greed("50"),))

    low = synthesize_watchpoint_rows(low_payload)
    high = synthesize_watchpoint_rows(high_payload)

    assert [row.current for row in low] == ["18 (극단 공포)"]
    assert [row.current for row in high] == ["85 (극단 탐욕)"]
    assert low[0].bullish_trigger == "20 상회 시 심리 회복 관찰"
    assert high[0].bullish_trigger == "90 상회 시 심리 과열 심화 관찰"
    assert high[0].bearish_trigger == "80 이탈 시 심리 과열 완화 관찰"
    assert synthesize_watchpoint_rows(mid_payload) == ()


def test_missing_range_and_non_short_cftc_do_not_invent_fallbacks() -> None:
    no_range = MarketAnchor(
        ticker="^GSPC",
        close=Decimal("7000"),
        pct=Decimal("1.00"),
        is_ath=False,
    )
    payload = WatchpointValuePayload.from_inputs(
        "us-equity",
        anchors=(no_range,),
        items=(_cftc(net="1200"),),
    )

    assert synthesize_watchpoint_rows(payload) == ()
    assert synthesize_watchpoint_rows(WatchpointValuePayload(segment="domestic-equity")) == ()


def test_domestic_close_only_anchor_synthesizes_truthful_reference_level() -> None:
    payload = WatchpointValuePayload.from_inputs(
        "domestic-equity",
        anchors=(MarketAnchor(ticker="^KOSPI", close=Decimal("2650.50"), is_ath=False),),
    )

    rows = synthesize_watchpoint_rows(payload)

    assert [row.signal for row in rows] == ["코스피 종가 기준선"]
    assert rows[0].current == "2,650.50"
    assert rows[0].bullish_trigger == "2,650.50 상회 시 단기 회복 흐름 관찰"
    assert rows[0].bearish_trigger == "2,650.50 이탈 시 방어적 수급 관찰"
    assert rows[0].source == "검증된 시장 앵커"


def test_cross_segment_or_malformed_payload_cannot_synthesize() -> None:
    domestic = WatchpointValuePayload.from_inputs(
        "domestic-equity",
        anchors=(_btc_anchor(),),
        items=(_coingecko(), _fear_greed("18"), _cftc()),
    )
    malformed_crypto = WatchpointValuePayload.from_inputs(
        "crypto",
        anchors=(_btc_anchor(),),
        items=(
            _item(
                "coingecko-price",
                {
                    "coin_id": "bitcoin",
                    "symbol": "btc",
                    "price_usd": "60284",
                    "pct_24h": "2.23",
                    "high_24h": "NaN",
                    "low_24h": "-1",
                },
            ),
        ),
    )

    assert synthesize_watchpoint_rows(domestic) == ()
    assert synthesize_watchpoint_rows(malformed_crypto) == ()


def test_cftc_sign_mismatch_and_zero_quantized_equity_bound_fail_closed() -> None:
    inconsistent_cftc = _item(
        "cftc-cot-positioning",
        {
            "contract_label": "E-mini S&P 500",
            "contract_group": "equity_index",
            "net_contracts": "-100",
            "net_pct_open_interest": "20.00",
        },
    )
    malformed_range = MarketAnchor(
        ticker="^GSPC",
        close=Decimal("1"),
        pct=Decimal("1"),
        is_ath=False,
        pct_from_52w_high=Decimal("-1"),
        pct_from_52w_low=Decimal("1e18"),
    )
    payload = WatchpointValuePayload.from_inputs(
        "us-equity",
        anchors=(malformed_range,),
        items=(inconsistent_cftc,),
    )

    assert synthesize_watchpoint_rows(payload) == ()


def test_every_closed_template_passes_u64_structure_and_p0_compliance_contracts() -> None:
    payloads = (
        WatchpointValuePayload.from_inputs(
            "us-equity",
            anchors=(_us_anchor(),),
            items=(_cftc(),),
        ),
        WatchpointValuePayload.from_inputs(
            "domestic-equity",
            anchors=(MarketAnchor(ticker="^KOSPI", close=Decimal("2650.50"), is_ath=False),),
        ),
        WatchpointValuePayload.from_inputs("crypto", items=(_fear_greed("18"),)),
        WatchpointValuePayload.from_inputs("crypto", items=(_fear_greed("85"),)),
    )
    banned_literals = (*BANNED_P0_ACTION, *BANNED_P0_CERTAINTY, *BANNED_P0_CRYPTO_ONLY)

    rendered_cards = []
    for payload in payloads:
        for row in synthesize_watchpoint_rows(payload):
            card = render_matrix_table([row])
            rendered_cards.append(card)
            assert _WATCHPOINT_SOURCE_RE.search(card)
            assert _WATCHPOINT_TRIGGER_RE.search(card)
            assert _WATCHPOINT_IMPLICATION_RE.search(card)
            assert not any(phrase in card for phrase in banned_literals)
            assert not any(pattern.search(card) for pattern in BANNED_P0_QUANTIFIED_OUTCOME)
            assert scan_compliance(card, payload.segment).p0_hits == ()

    assert len(rendered_cards) == 5

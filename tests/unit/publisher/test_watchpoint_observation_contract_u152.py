"""Independent u152 observation-contract fixtures; all values are synthetic.

Exercise public payload/resolution/rendering boundaries without mocking private
candidate selection. Finalizer/notification integration is covered separately.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal
from itertools import permutations

import pytest

from investo.models.items import NormalizedItem
from investo.models.market_anchor import MarketAnchor
from investo.publisher.watchpoint_matrix import (
    DATA_LIMITED_NOTE,
    WatchpointRow,
    WatchpointValuePayload,
    build_watchpoint_rows,
    render_matrix_table,
    render_watchpoint_matrix_result,
    resolve_watchpoint_currents,
)


def _row(
    signal: str = "ETH 가격", *, current: str = "미확인", source: str = "CoinGecko"
) -> WatchpointRow:
    return WatchpointRow(
        signal=signal,
        source=source,
        current=current,
        bullish_trigger="$2,523.23 상회하면 회복 흐름 관찰",
        bearish_trigger="$2,450 이탈하면 약화 흐름 관찰",
        confidence="높음",
        implication="본문 가격 흐름과 연계 점검",
    )


def _item(source: str, metadata: dict[str, str]) -> NormalizedItem:
    return NormalizedItem(
        source_name=source,
        category="price" if source == "coingecko-price" else "macro",
        title=f"{source} synthetic observation",
        url="https://example.invalid/observation",
        published_at=datetime(2026, 9, 4, tzinfo=UTC),
        raw_metadata=metadata,
    )


def _price(symbol: str = "eth", value: str = "2480") -> NormalizedItem:
    return _item(
        "coingecko-price",
        {
            "symbol": symbol,
            "coin_id": "ethereum" if symbol == "eth" else "bitcoin",
            "price_usd": value,
            "pct_24h": "1.25",
        },
    )


def _cftc(**changes: str) -> NormalizedItem:
    return _item(
        "cftc-cot-positioning",
        {
            "contract_label": "Ether CME",
            "contract_group": "crypto",
            "net_contracts": "-2400",
            "net_pct_open_interest": "-4.20",
            "as_of_date": "2026-09-01",
            "release_date": "2026-09-04",
            **changes,
        },
    )


def _payload(*items: NormalizedItem) -> WatchpointValuePayload:
    return WatchpointValuePayload.from_inputs("crypto", items=items)


def _section(content: str) -> str:
    return f"## ① 요약\n본문 보존\n\n## ⑥ 오늘의 관전 포인트\n\n{content}\n"


@pytest.mark.parametrize(
    "current",
    (
        "ETH가 24h 고가 $2,523.23을 상회하면 강세 흐름 관찰",
        "소스 2026",
        "2026-09-03 기준",
        "$9,999.00",
    ),
)
def test_digits_without_observation_payload_never_resolve(current: str) -> None:
    assert resolve_watchpoint_currents((_row(current=current),), _payload()) == []


@pytest.mark.parametrize("current", ("$9,999.00 (+99%)", "2026-09-03 기준", "미확인"))
def test_every_current_is_replaced_by_exact_payload_observation(current: str) -> None:
    original = _row(current=current)
    resolved = resolve_watchpoint_currents((original,), _payload(_price()))
    assert len(resolved) == 1
    assert resolved[0].current == "$2,480.00 (+1.25%)"
    assert resolved[0].bullish_trigger == original.bullish_trigger
    assert resolved[0].bearish_trigger == original.bearish_trigger
    assert resolved[0].implication == original.implication


@pytest.mark.parametrize("signal", ("ETH funding", "ETH 펀딩", "ETH OI", "ETH 미결제약정"))
def test_eth_derivative_metric_cannot_borrow_price_or_btc_indicator(signal: str) -> None:
    payload = _payload(
        _price(),
        _item("okx-derivatives", {"indicator": "btc_funding", "btc_funding_rate": "0.0001"}),
        _item("bybit-derivatives", {"indicator": "btc_oi", "btc_oi_usd": "100000000"}),
    )
    assert resolve_watchpoint_currents((_row(signal),), payload) == []


@pytest.mark.parametrize(
    ("signal", "source"),
    (
        ("ETH 가격 및 BTC 가격", "CoinGecko"),
        ("ETH 가격", "CoinGecko BTC"),
        ("BTC 가격 및 펀딩", "OKX"),
        ("BTC 펀딩 OI", "OKX"),
        ("BTC 가격", "OKX funding"),
        ("ETH TVL", "DeFiLlama"),
        ("BTC 거래량", "CoinGecko"),
        ("ETH 해시레이트", "CoinGecko"),
        ("ETH 가스비", "CoinGecko"),
        ("ETH 가격과 가스비", "CoinGecko"),
        ("ETH", "Etherscan 가스비"),
        ("ETH", "ETH 해시레이트"),
        ("ETH", "ETH 가스비"),
    ),
)
def test_ambiguous_assets_metrics_and_unsupported_metrics_reject(signal: str, source: str) -> None:
    payload = _payload(
        _price(),
        _price("btc", "60000"),
        _item("okx-derivatives", {"indicator": "btc_funding", "btc_funding_rate": "0.0001"}),
        _item("bybit-derivatives", {"indicator": "btc_oi", "btc_oi_usd": "100000000"}),
    )
    assert resolve_watchpoint_currents((_row(signal, source=source),), payload) == []


def test_bare_asset_defaults_to_price_and_thresholds_do_not_select_metric() -> None:
    row = replace(
        _row("BTC", source="CoinGecko"),
        bullish_trigger="ETH 펀딩 0.001 상회 시 관련 흐름 관찰",
        bearish_trigger="ETH OI 100 이탈 시 관련 흐름 관찰",
    )
    resolved = resolve_watchpoint_currents((row,), _payload(_price("btc", "60000")))
    assert [item.current for item in resolved] == ["$60,000.00 (+1.25%)"]
    assert resolved[0].bullish_trigger == row.bullish_trigger
    assert resolved[0].bearish_trigger == row.bearish_trigger


@pytest.mark.parametrize(
    ("source", "metadata", "expected"),
    [
        ("OKX 펀딩", {"indicator": "btc_funding", "btc_funding_rate": "0.0001"}, "펀딩 0.0001"),
        ("Bybit OI", {"indicator": "btc_oi", "btc_oi_usd": "100000000"}, "OI $100,000,000.00"),
    ],
)
def test_source_metric_can_complete_an_exact_signal_asset(
    source: str, metadata: dict[str, str], expected: str
) -> None:
    payload = _payload(_item("okx-derivatives", metadata))
    resolved = resolve_watchpoint_currents((_row("BTC", source=source),), payload)
    assert [row.current for row in resolved] == [expected]
    assert resolve_watchpoint_currents((_row("ETH", source=source),), payload) == []
    assert resolve_watchpoint_currents((_row("확인", source=source),), payload) == []


@pytest.mark.parametrize(
    ("signal", "source"),
    (("ETH BTC 가격", "CoinGecko"), ("ETH 가격", "CoinGecko BTC")),
)
def test_missing_second_asset_payload_does_not_erase_ambiguous_identity(
    signal: str, source: str
) -> None:
    assert resolve_watchpoint_currents((_row(signal, source=source),), _payload(_price())) == []


def test_conflicting_equal_best_observations_reject_every_input_permutation() -> None:
    items = (_price(value="2480"), _price(value="2490"), _price(value="2480"))
    for ordered in permutations(items):
        assert resolve_watchpoint_currents((_row(),), _payload(*ordered)) == []


def test_identical_duplicate_observations_collapse_stably() -> None:
    items = (_price(), _price(value="2480.00"), _price("btc", "60000"))
    expected = resolve_watchpoint_currents((_row(),), _payload(_price()))
    assert len(expected) == 1
    for ordered in permutations(items):
        assert resolve_watchpoint_currents((_row(),), _payload(*ordered)) == expected


def test_conflicting_reconciled_anchor_values_reject_independent_of_order() -> None:
    anchors = tuple(
        MarketAnchor(ticker="ETH-USD", close=Decimal(value), pct=Decimal("1.25"), is_ath=False)
        for value in ("2480", "2490")
    )
    for ordered in permutations(anchors):
        payload = WatchpointValuePayload.from_inputs("crypto", anchors=ordered)
        assert resolve_watchpoint_currents((_row(source="검증된 시장 앵커"),), payload) == []


def test_exact_source_precedence_remains_within_one_price_identity() -> None:
    anchor = MarketAnchor(ticker="ETH-USD", close=Decimal("2470"), pct=Decimal("1.0"), is_ath=False)
    payload = WatchpointValuePayload.from_inputs("crypto", anchors=(anchor,), items=(_price(),))
    assert [row.current for row in resolve_watchpoint_currents((_row(),), payload)] == [
        "$2,480.00 (+1.25%)"
    ]


def test_nasdaq_source_name_does_not_create_a_second_asset() -> None:
    payload = WatchpointValuePayload.from_inputs(
        "us-equity",
        anchors=(
            MarketAnchor(ticker="AAPL", close=Decimal("100"), pct=Decimal("1"), is_ath=False),
        ),
    )
    assert [
        row.current
        for row in resolve_watchpoint_currents((_row("AAPL 가격", source="Nasdaq"),), payload)
    ] == ["$100.00 (+1%)"]


def test_cftc_exact_contract_beats_broad_asset_price_and_caps_confidence() -> None:
    row = _row("Ether CME CFTC 순포지션", current="999계약", source="CFTC")
    resolved = resolve_watchpoint_currents((row,), _payload(_price(), _cftc()))
    assert len(resolved) == 1
    assert "순포지션 -2,400계약" in resolved[0].current
    assert "-4.2%" in resolved[0].current
    assert "2026-09-01 기준/2026-09-04 공개" in resolved[0].current
    assert "주간 지연" in resolved[0].current
    assert resolved[0].confidence == "보통"
    assert resolved[0].bullish_trigger == row.bullish_trigger


@pytest.mark.parametrize(
    "changes",
    (
        {"as_of_date": ""},
        {"release_date": ""},
        {"as_of_date": "2026-02-30"},
        {"release_date": "2026-09-04T10:00:00Z"},
        {"as_of_date": "2026-09-05"},
    ),
)
def test_cftc_missing_invalid_or_reversed_dates_never_fall_back_to_price(
    changes: dict[str, str],
) -> None:
    row = _row("Ether CME CFTC 순포지션", current="999계약", source="CFTC")
    assert resolve_watchpoint_currents((row,), _payload(_price(), _cftc(**changes))) == []


def test_cftc_old_valid_dates_remain_explicit_delayed_observations() -> None:
    payload = _payload(_cftc(as_of_date="2026-08-18", release_date="2026-08-21"))
    resolved = resolve_watchpoint_currents((_row("Ether CME CFTC", source="CFTC"),), payload)
    assert len(resolved) == 1
    assert "2026-08-18 기준/2026-08-21 공개" in resolved[0].current
    assert resolved[0].confidence == "보통"


def test_explicit_parser_slots_keep_current_direction_and_impact_separate() -> None:
    bullet = (
        "관찰 신호: ETH 가격; 출처: CoinGecko; 현재: $9,999.00; "
        "상방: $2,523.23 상회하면 회복 관찰; 하방: $2,450 이탈하면 약화 관찰; "
        "관심 영향: 변동성 확대 여부 점검"
    )
    parsed = build_watchpoint_rows([bullet])
    assert len(parsed) == 1
    assert parsed[0].signal == "ETH 가격"
    assert parsed[0].current == "$9,999.00"
    assert parsed[0].source == "CoinGecko"
    assert parsed[0].bullish_trigger == "$2,523.23 상회하면 회복 관찰"
    assert parsed[0].bearish_trigger == "$2,450 이탈하면 약화 관찰"
    assert parsed[0].implication == "변동성 확대 여부 점검"
    resolved = resolve_watchpoint_currents(parsed, _payload(_price()))
    assert resolved[0].current == "$2,480.00 (+1.25%)"


def test_missing_current_never_copies_conditional_paragraph() -> None:
    bullet = (
        "확인 소스: CoinGecko · ETH가 24h 고가 $2,523.23을 상회하면 회복 관찰; "
        "$2,450 이탈하면 약화 관찰; 관심 영향: 변동성 확대 여부 점검"
    )
    parsed = build_watchpoint_rows([bullet])
    assert len(parsed) == 1
    assert all(token not in parsed[0].current for token in ("상회", "이탈", "관심 영향", "2,523"))
    resolved = resolve_watchpoint_currents(parsed, _payload(_price()))
    assert len(resolved) == 1
    assert resolved[0].current == "$2,480.00 (+1.25%)"
    assert all(token not in resolved[0].signal for token in ("상회", "이탈", "관심 영향"))


def test_unsafe_signal_uses_canonical_label_without_copying_future_clause() -> None:
    row = _row("ETH 가격; 현재: $9,999; 상방: $2,523 상회하면 변동성 확대 관찰")
    resolved = resolve_watchpoint_currents((row,), _payload(_price()))
    assert len(resolved) == 1
    assert len(resolved[0].signal) <= 30
    assert "ETH" in resolved[0].signal or "이더리움" in resolved[0].signal
    assert all(token not in resolved[0].signal for token in ("현재", "상방", "상회", "9,999"))


def test_unsupported_domestic_flow_is_removed_without_modifying_body_evidence() -> None:
    body = "## ② 주요 이슈\n외국인 순매수 +123억원이라는 본문 근거는 유지한다.\n\n"
    row = _row("외국인 순매수", current="+123억원", source="KRX")
    result = render_watchpoint_matrix_result(
        body + _section(render_matrix_table([row])),
        segment="domestic-equity",
        value_payload=WatchpointValuePayload(segment="domestic-equity"),
    )
    assert result.state == "limited" and result.usable_card_count == 0
    assert DATA_LIMITED_NOTE in result.markdown
    assert result.markdown.startswith(body)
    assert "- 현재: +123억원" not in result.markdown


def test_canonical_numeric_card_revalidates_and_is_byte_stable() -> None:
    original = _section(render_matrix_table([_row(current="$9,999.00")]))
    payload = _payload(_price())
    first = render_watchpoint_matrix_result(original, segment="crypto", value_payload=payload)
    second = render_watchpoint_matrix_result(
        first.markdown, segment="crypto", value_payload=payload
    )
    assert first.state == "rendered" and first.usable_card_count == 1
    assert "- 현재: $2,480.00 (+1.25%)" in first.markdown
    assert "$9,999.00" not in first.markdown
    assert second.markdown == first.markdown
    assert second.usable_card_count == first.usable_card_count

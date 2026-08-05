"""u135 exact incident regressions for the 2026-06-29/30 bundle family."""

from __future__ import annotations

import json
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, cast

from investo.briefing.disclaimer import DISCLAIMER
from investo.models import Briefing, NormalizedItem
from investo.models.market_anchor import MarketAnchor
from investo.models.segments import MarketSegment
from investo.publisher.segment_reader_format import apply_reader_format_to_segments
from investo.publisher.watchpoint_matrix import (
    WatchpointValuePayload,
    render_watchpoint_matrix_result,
)

_FIXTURE_PATH = Path(__file__).parents[2] / "fixtures" / "u135" / "watchpoint-incidents.json"


def _fixtures() -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(_FIXTURE_PATH.read_text(encoding="utf-8")))


def _item(
    source_name: str,
    metadata: dict[str, str],
    *,
    target_date: date,
) -> NormalizedItem:
    return NormalizedItem(
        source_name=source_name,
        category="price" if source_name == "coingecko-price" else "macro",
        title=f"{source_name} {target_date.isoformat()} incident fixture",
        published_at=datetime.combine(target_date, datetime.min.time(), tzinfo=UTC),
        raw_metadata=metadata,
    )


def _briefing(target_date: date, watchpoint_body: str) -> Briefing:
    markdown = (
        f"# {target_date.isoformat()} 미국 증시 시황\n\n"
        "> **오늘의 결론**: 지수와 포지셔닝 괴리를 확인합니다.\n"
        "> **핵심 동인**: 칩메이커 강세가 지수를 견인했습니다.\n"
        "> **주의할 점**: 주간 지연 포지셔닝을 함께 봅니다.\n\n"
        "## ① 요약\n시장 요약입니다.\n\n"
        "## ⑤ 주요 종목\n가격 동향입니다.\n\n"
        f"## ⑥ 오늘의 관전 포인트\n\n{watchpoint_body}\n\n"
        f"{DISCLAIMER}\n"
    )
    return Briefing(
        target_date=target_date,
        market_summary="지수와 포지셔닝 괴리를 확인합니다.",
        key_issues="핵심 이슈",
        sector_flow="수급",
        indicators_events="지표",
        notable_tickers="가격 동향",
        today_watch="관전",
        disclaimer=DISCLAIMER,
        rendered_markdown=markdown,
    )


def test_crypto_2026_06_29_source_shaped_current_uses_coingecko_snapshot() -> None:
    fixture = _fixtures()["crypto_2026_06_29"]
    target_date = date.fromisoformat(fixture["target_date"])
    anchor_data = fixture["anchor"]
    payload = WatchpointValuePayload.from_inputs(
        cast(MarketSegment, fixture["segment"]),
        anchors=(
            MarketAnchor(
                ticker=anchor_data["ticker"],
                close=Decimal(anchor_data["close"]),
                pct=Decimal(anchor_data["pct"]),
                is_ath=False,
            ),
        ),
        items=(
            _item(
                "coingecko-price",
                fixture["coingecko"],
                target_date=target_date,
            ),
        ),
    )

    result = render_watchpoint_matrix_result(
        fixture["legacy_markdown"],
        segment=fixture["segment"],
        value_payload=payload,
    )

    assert result.state == "rendered"
    assert f"- 현재: {fixture['expected_current']}" in result.markdown
    assert "- 현재: CoinGecko BTC" not in result.markdown


def test_us_equity_2026_06_30_payload_synthesizes_range_then_cftc() -> None:
    fixture = _fixtures()["us_equity_2026_06_30"]
    target_date = date.fromisoformat(fixture["target_date"])
    anchor_data = fixture["anchor"]
    anchor = MarketAnchor(
        ticker=anchor_data["ticker"],
        close=Decimal(anchor_data["close"]),
        prev_close=Decimal(anchor_data["prev_close"]),
        pct=Decimal(anchor_data["pct"]),
        is_ath=False,
        pct_from_52w_high=Decimal(anchor_data["pct_from_52w_high"]),
        pct_from_52w_low=Decimal(anchor_data["pct_from_52w_low"]),
    )
    cftc = _item(
        "cftc-cot-positioning",
        fixture["cftc"],
        target_date=target_date,
    )
    observed = []

    output = apply_reader_format_to_segments(
        {
            cast(MarketSegment, fixture["segment"]): _briefing(
                target_date,
                fixture["watchpoint_body"],
            )
        },
        anchors_by_segment={cast(MarketSegment, fixture["segment"]): (anchor,)},
        items_by_segment={cast(MarketSegment, fixture["segment"]): (cftc,)},
        _watchpoint_result_observer=lambda _segment, result: observed.append(result),
    )[cast(MarketSegment, fixture["segment"])].rendered_markdown

    first, second = fixture["expected_signals"]
    assert output.index(f"#### 관찰 신호: {first}") < output.index(f"#### 관찰 신호: {second}")
    assert "- 현재: 7,499.36 (**+0.79%**)" in output
    assert "순포지션 -373,468계약 (**-18.86%** OI, 주간 지연)" in output
    assert len(observed) == 1
    assert observed[0].synthesized_card_count == 2


def test_empty_payload_preserves_existing_bounded_note_byte_identically() -> None:
    fixture = _fixtures()["empty_payload"]
    markdown = fixture["markdown"]

    result = render_watchpoint_matrix_result(
        markdown,
        segment=fixture["segment"],
        value_payload=WatchpointValuePayload(segment=fixture["segment"]),
    )

    assert result.state == "limited"
    assert result.markdown == markdown
    assert result.synthesized_card_count == 0


def test_domestic_close_only_payload_renders_reference_card_without_invented_pct() -> None:
    fixture = _fixtures()["domestic_equity_close_only"]
    target_date = date.fromisoformat(fixture["target_date"])
    anchor_data = fixture["anchor"]
    segment = cast(MarketSegment, fixture["segment"])
    observed = []

    output = apply_reader_format_to_segments(
        {segment: _briefing(target_date, fixture["watchpoint_body"])},
        anchors_by_segment={
            segment: (
                MarketAnchor(
                    ticker=anchor_data["ticker"],
                    close=Decimal(anchor_data["close"]),
                    is_ath=False,
                ),
            )
        },
        _watchpoint_result_observer=lambda _segment, result: observed.append(result),
    )[segment].rendered_markdown

    assert f"#### 관찰 신호: {fixture['expected_signal']}" in output
    assert f"- 현재: {fixture['expected_current']}" in output
    assert f"상방 {fixture['expected_current']} 상회" in output
    assert f"하방 {fixture['expected_current']} 이탈" in output
    assert "+" not in output.split(f"- 현재: {fixture['expected_current']}", 1)[1].splitlines()[0]
    assert observed[0].synthesized_card_count == 1

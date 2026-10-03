"""u152 observations traverse the actual public finalizer and terminal gates.

Synthetic source/anchor values are independently pinned below. No resolver,
numeric, entity, compliance, surface, or notification gate is replaced.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from investo._internal.disclaimer import DISCLAIMER, DISCLAIMER_CRYPTO
from investo.models import Briefing, NormalizedItem, SourceOutcome
from investo.models.facts import VerifiedFactBundle
from investo.models.market_anchor import MarketAnchor
from investo.models.segments import (
    CRYPTO,
    DOMESTIC_EQUITY,
    US_EQUITY,
    MarketSegment,
    SegmentCoverage,
)
from investo.publisher.compliance_language import scan_compliance
from investo.publisher.public_document import (
    FinalizedPublicBundle,
    PublicDocumentContext,
    PublicDocumentSupplement,
    _render_supplement_block,
    finalize_public_bundle,
)
from investo.publisher.watchpoint_matrix import DATA_LIMITED_NOTE

_TARGET = date(2026, 9, 25)
_OBSERVED = datetime(2026, 9, 26, 6, tzinfo=UTC)
_CONCLUSION = "공개된 시장 근거를 확인했습니다."
_WATCHLIST = "BTC: 가격 구간을 확인합니다."
_FLOW_EVIDENCE = (
    "외국인 순매수 동향은 [KRX](https://data.krx.co.kr/contents/market-flow) "
    "공개 자료에서 확인했습니다."
)


def _item(source_name: str, metadata: dict[str, str]) -> NormalizedItem:
    return NormalizedItem(
        source_name=source_name,
        category="price" if source_name == "coingecko-price" else "macro",
        title="합성 시장 관측 자료",
        published_at=datetime(2026, 9, 25, 12, tzinfo=UTC),
        raw_metadata=metadata,
    )


def _coin() -> NormalizedItem:
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


def _btc_anchor() -> MarketAnchor:
    return MarketAnchor(
        ticker="BTC-USD", close=Decimal("60284.41"), pct=Decimal("1.26"), is_ath=False
    )


def _card(
    *,
    signal: str = "BTC 가격 구간",
    source: str = "CoinGecko",
    current: str = "$999,999.00 (+99.99%)",
    confidence: str = "높음",
    implication: str = "가격 변동 흐름을 확인합니다.",
) -> str:
    return (
        f"#### 관찰 신호: {signal}\n\n"
        f"- 출처: {source}\n"
        f"- 현재: {current}\n"
        "- 확인 조건: 상방 직전 고가 상회 여부; 하방 직전 저가 이탈 여부\n"
        f"- 신뢰도: {confidence}\n"
        f"- 관심 영향: {implication}\n"
    )


def _bullet(current: str | None) -> str:
    current_field = f"현재: {current}; " if current is not None else ""
    return (
        "- BTC 가격 구간; 출처: CoinGecko; "
        f"{current_field}"
        "상방: 직전 고가를 상회하면 가격 흐름 확인; "
        "하방: 직전 저가를 이탈하면 변동성 확인; "
        "관심 영향: 가격 변동 흐름을 확인합니다."
    )


def _briefing(
    segment: MarketSegment,
    watchpoint: str,
    *,
    body: str = "핵심 발표의 후속 내용을 확인합니다.",
    supplement: str = "",
) -> Briefing:
    disclaimer = DISCLAIMER_CRYPTO if segment == CRYPTO else DISCLAIMER
    markdown = (
        f"# {_TARGET.isoformat()} 시장 시황\n\n"
        f"> **오늘의 결론**: {_CONCLUSION}\n"
        "> **핵심 동인**: 공개된 지표와 발표 내용을 확인합니다.\n"
        "> **주의할 점**: 추가 자료의 공개 여부를 확인합니다.\n"
        f"> **내 관심 자산 영향**: {_WATCHLIST}\n\n"
        "<details><summary>수집/품질 진단</summary>\n합성 자료 수집\n</details>\n\n"
        "## ① 요약\n시장 근거를 확인했습니다.\n\n"
        f"## ② 전일 핵심 이슈\n{body}\n\n"
        "## ③ 섹터/수급 동향\n수급 흐름을 확인합니다.\n\n"
        "## ④ 지표·이벤트\n추가 공개 일정을 확인합니다.\n\n"
        "## ⑤ 주요 종목\n가격 변동 흐름을 확인합니다.\n\n"
        f"## ⑥ 오늘의 관전 포인트\n\n{watchpoint}\n\n{supplement}\n\n"
        f"{disclaimer}\n"
    )
    return Briefing(
        target_date=_TARGET,
        market_summary="생성 단계의 요약은 알림 입력이 아닙니다.",
        key_issues=body,
        sector_flow="수급 흐름",
        indicators_events="추가 공개 일정",
        notable_tickers="가격 흐름",
        today_watch=watchpoint,
        disclaimer=disclaimer,
        rendered_markdown=markdown,
    )


def _context(
    briefings: Mapping[MarketSegment, Briefing],
    *,
    anchors: Mapping[MarketSegment, tuple[MarketAnchor, ...]] | None = None,
    items: Mapping[MarketSegment, tuple[NormalizedItem, ...]] | None = None,
    supplements: Mapping[MarketSegment, tuple[PublicDocumentSupplement, ...]] | None = None,
) -> PublicDocumentContext:
    ordered = tuple(s for s in (DOMESTIC_EQUITY, US_EQUITY, CRYPTO) if s in briefings)
    return PublicDocumentContext(
        target_date=_TARGET,
        expected_segments=ordered,
        input_absences={},
        anchors_by_segment=anchors or {},
        items_by_segment=items or {},
        coverage_by_segment={
            segment: SegmentCoverage(
                segment=segment,
                status="normal",
                item_count=1,
                source_count=1,
                categories=("news",),
                missing_categories=(),
            )
            for segment in ordered
        },
        source_outcomes=(SourceOutcome.ok("krx-investor-flow", "macro", 1),),
        bundle_context=None,
        fact_bundle=VerifiedFactBundle(target_date=_TARGET),
        entity_observed_at_utc=_OBSERVED,
        supplements_by_segment=supplements or {},
    )


def _watchpoints(markdown: str) -> str:
    return markdown.split("## ⑥ 오늘의 관전 포인트", 1)[1].split("## ⑦ 면책조항", 1)[0]


def _current_values(markdown: str) -> list[str]:
    return [
        line.removeprefix("- 현재: ").replace("**", "")
        for line in _watchpoints(markdown).splitlines()
        if line.startswith("- 현재: ")
    ]


@pytest.mark.parametrize(
    "current", ["$999,999.00 (+99.99%)", "CoinGecko BTC", "상회하면 회복 확인", None]
)
def test_generated_current_is_replaced_from_the_matching_observation(current: str | None) -> None:
    briefings = {CRYPTO: _briefing(CRYPTO, _bullet(current))}
    bundle = finalize_public_bundle(
        briefings,
        context=_context(briefings, anchors={CRYPTO: (_btc_anchor(),)}, items={CRYPTO: (_coin(),)}),
    )
    (document,) = bundle.documents
    assert _current_values(document.briefing.rendered_markdown) == ["$60,284.00 (+2.23%)"]
    watchpoints = _watchpoints(document.briefing.rendered_markdown)
    assert "가격 변동 흐름을 확인합니다." in watchpoints
    assert "직전 고가를 상회하면 가격 흐름 확인" in watchpoints
    assert "직전 저가를 이탈하면 변동성 확인" in watchpoints
    assert document.notification_summary.conclusion == _CONCLUSION
    assert document.notification_summary.watchlist == _WATCHLIST
    assert "생성 단계" not in repr(document.notification_summary)


@pytest.mark.parametrize(
    "current", ["$999,999.00 (+99.99%)", "CoinGecko BTC", "$60,284.00 (+2.23%)"]
)
def test_pre_rendered_cards_cannot_bypass_canonical_payload(current: str) -> None:
    briefings = {CRYPTO: _briefing(CRYPTO, _card(current=current))}
    context = _context(briefings, anchors={CRYPTO: (_btc_anchor(),)}, items={CRYPTO: (_coin(),)})
    bundle = finalize_public_bundle(briefings, context=context)
    (document,) = bundle.documents
    assert _current_values(document.briefing.rendered_markdown) == ["$60,284.00 (+2.23%)"]
    assert "999,999" not in document.briefing.rendered_markdown
    assert document.watchpoint_synthesized == 0


@pytest.mark.parametrize("watchpoint", [_bullet("$999,999.00 (+99.99%)"), _card()])
def test_no_payload_yields_only_the_canonical_limitation(watchpoint: str) -> None:
    briefings = {CRYPTO: _briefing(CRYPTO, watchpoint)}
    bundle = finalize_public_bundle(briefings, context=_context(briefings))
    (document,) = bundle.documents
    body = _watchpoints(document.briefing.rendered_markdown)
    assert body.strip() == DATA_LIMITED_NOTE
    assert _current_values(document.briefing.rendered_markdown) == []
    assert document.watchpoint_synthesized == 0
    assert document.notification_summary.conclusion == _CONCLUSION


@pytest.mark.parametrize("has_anchor", [False, True])
def test_unsupported_domestic_flow_preserves_body_and_uses_only_supported_fallback(
    has_anchor: bool,
) -> None:
    unsupported = _card(signal="외국인 순매수 동향", source="KRX", current="순매수 1234억원")
    briefings = {DOMESTIC_EQUITY: _briefing(DOMESTIC_EQUITY, unsupported, body=_FLOW_EVIDENCE)}
    anchors = (
        (MarketAnchor(ticker="^KOSPI", close=Decimal("2650.50"), is_ath=False),)
        if has_anchor
        else ()
    )
    flow = _item("krx-investor-flow", {"market": "KOSPI", "investor": "foreign"})
    bundle = finalize_public_bundle(
        briefings,
        context=_context(
            briefings,
            anchors={DOMESTIC_EQUITY: anchors},
            items={DOMESTIC_EQUITY: (flow,)},
        ),
    )
    (document,) = bundle.documents
    markdown = document.briefing.rendered_markdown
    assert _FLOW_EVIDENCE in markdown
    assert "외국인 순매수 동향" not in _watchpoints(markdown)
    assert "1234억원" not in markdown
    if has_anchor:
        assert "#### 관찰 신호: 코스피 종가 기준선" in markdown
        assert _current_values(markdown) == ["2,650.50"]
        assert document.watchpoint_synthesized == 1
    else:
        assert _watchpoints(markdown).strip() == DATA_LIMITED_NOTE
        assert document.watchpoint_synthesized == 0


@pytest.mark.parametrize("signal", ["ETH 해시레이트", "ETH 가스비"])
def test_unknown_metric_cannot_publish_a_price_as_its_observation(signal: str) -> None:
    price = _item(
        "coingecko-price",
        {"coin_id": "ethereum", "symbol": "eth", "price_usd": "2480", "pct_24h": "1.25"},
    )
    briefings = {CRYPTO: _briefing(CRYPTO, _card(signal=signal))}
    bundle = finalize_public_bundle(
        briefings, context=_context(briefings, items={CRYPTO: (price,)})
    )
    (document,) = bundle.documents
    assert _watchpoints(document.briefing.rendered_markdown).strip() == DATA_LIMITED_NOTE
    assert _current_values(document.briefing.rendered_markdown) == []


@pytest.mark.parametrize("with_payload", [False, True])
def test_conversion_preserves_supplement_disclaimer_and_repeated_bytes(
    with_payload: bool,
) -> None:
    supplement = PublicDocumentSupplement(
        supplement_id="crypto.visual.observation",
        kind="visual",
        markdown="![관찰 자료](observation.svg)",
        stable_order=1,
    )
    fragment = _render_supplement_block(supplement)
    briefings = {CRYPTO: _briefing(CRYPTO, _card(), supplement=fragment)}
    context = _context(
        briefings,
        anchors={CRYPTO: (_btc_anchor(),)} if with_payload else {},
        items={CRYPTO: (_coin(),)} if with_payload else {},
        supplements={CRYPTO: (supplement,)},
    )
    first = finalize_public_bundle(briefings, context=context)
    second = finalize_public_bundle({CRYPTO: first.documents[0].briefing}, context=context)
    first_document, second_document = first.documents[0], second.documents[0]
    assert _current_values(first_document.briefing.rendered_markdown) == (
        ["$60,284.00 (+2.23%)"] if with_payload else []
    )
    if not with_payload:
        assert DATA_LIMITED_NOTE in _watchpoints(first_document.briefing.rendered_markdown)
    assert first_document.briefing.rendered_markdown.count(fragment) == 1
    assert first_document.briefing.rendered_markdown.count(DISCLAIMER_CRYPTO) == 1
    assert first_document.briefing.rendered_markdown == second_document.briefing.rendered_markdown
    assert first_document.markdown_sha256 == second_document.markdown_sha256
    assert first_document.notification_summary == second_document.notification_summary


def test_source_and_metric_select_funding_while_future_price_thresholds_stay_conditions() -> None:
    card = _card(signal="BTC 펀딩", source="OKX", current="$60,284.00 (+2.23%)")
    card = card.replace(
        "상방 직전 고가 상회 여부; 하방 직전 저가 이탈 여부",
        "상방 ETH가 $4,000을 상회하면 동반 흐름 확인; 하방 ETH가 $3,000을 이탈하면 괴리 확인",
    )
    briefings = {CRYPTO: _briefing(CRYPTO, card)}
    funding = _item("okx-derivatives", {"indicator": "btc_funding", "btc_funding_rate": "0.0001"})
    bundle = finalize_public_bundle(
        briefings,
        context=_context(
            briefings, anchors={CRYPTO: (_btc_anchor(),)}, items={CRYPTO: (_coin(), funding)}
        ),
    )
    markdown = bundle.documents[0].briefing.rendered_markdown
    assert _current_values(markdown) == ["펀딩 0.0001"]
    assert "ETH가 $4,000을 상회하면 동반 흐름 확인" in _watchpoints(markdown).replace("**", "")
    assert "ETH가 $3,000을 이탈하면 괴리 확인" in _watchpoints(markdown).replace("**", "")


def test_cftc_observation_retains_both_dates_and_weekly_lag_with_moderate_confidence() -> None:
    card = _card(signal="E-mini S&P 500 COT 순포지션", source="CFTC", current="순포지션 999계약")
    briefings = {US_EQUITY: _briefing(US_EQUITY, card)}
    positioning = _item(
        "cftc-cot-positioning",
        {
            "contract_group": "equity_index",
            "contract_label": "E-mini S&P 500",
            "net_contracts": "-373468",
            "net_pct_open_interest": "-18.86",
            "as_of_date": "2026-09-22",
            "release_date": "2026-09-25",
        },
    )
    bundle = finalize_public_bundle(
        briefings, context=_context(briefings, items={US_EQUITY: (positioning,)})
    )
    markdown = bundle.documents[0].briefing.rendered_markdown
    assert _current_values(markdown) == [
        "순포지션 -373,468계약 (-18.86% OI, 2026-09-22 기준/2026-09-25 공개 · 주간 지연)"
    ]
    assert "- 신뢰도: 보통" in _watchpoints(markdown)
    assert "- 신뢰도: 높음" not in _watchpoints(markdown)


def test_existing_compliance_repair_remains_authoritative_before_watchpoint_conversion() -> None:
    briefings = {
        CRYPTO: _briefing(
            CRYPTO,
            _card(implication="비중 확대 여부를 검토합니다."),
            body="가격 흐름을 확인합니다.",
        )
    }
    bundle = finalize_public_bundle(
        briefings, context=_context(briefings, items={CRYPTO: (_coin(),)})
    )
    markdown = bundle.documents[0].briefing.rendered_markdown
    assert _current_values(markdown) == ["$60,284.00 (+2.23%)"]
    assert "비중 확대" not in markdown
    assert "노출 변화 점검 여부를 검토합니다." in _watchpoints(markdown)
    assert scan_compliance(markdown, CRYPTO).p0_hits == ()


def _blocked_bundle(body: str) -> FinalizedPublicBundle:
    briefings = {
        US_EQUITY: _briefing(
            US_EQUITY, _card(signal="S&P 500 가격 구간", source="Yahoo"), body=body
        ),
        CRYPTO: _briefing(CRYPTO, _card()),
    }
    return finalize_public_bundle(
        briefings,
        context=_context(briefings, items={CRYPTO: (_coin(),)}),
    )


@pytest.mark.parametrize(
    ("unsafe_body", "issue_code"),
    [
        ("파월 의장 기자회견을 확인합니다.", "entity.fact_contradiction"),
        ("### S&P 500 9.99% 상승", "numeric.anchor_assertion"),
    ],
)
def test_watchpoint_limitation_cannot_erase_hard_gate_and_valid_sibling_survives(
    unsafe_body: str, issue_code: str
) -> None:
    bundle = _blocked_bundle(unsafe_body)
    assert tuple(document.segment for document in bundle.documents) == (CRYPTO,)
    blocked, surviving = bundle.segment_outcomes
    assert blocked.segment == US_EQUITY
    assert blocked.state == "trust_blocked"
    assert issue_code in blocked.issue_codes
    assert surviving.segment == CRYPTO
    assert surviving.state in {"finalized", "finalized_degraded"}
    (document,) = bundle.documents
    assert _current_values(document.briefing.rendered_markdown) == ["$60,284.00 (+2.23%)"]
    assert document.notification_summary.segment == CRYPTO
    assert "미국 증시(미발행)" in document.briefing.rendered_markdown

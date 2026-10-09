"""Live price as-of remains visible after actual public finalization."""

from datetime import UTC, date, datetime

from investo.models import NormalizedItem, SourceOutcome
from investo.models.facts import VerifiedFactBundle
from investo.models.segments import CRYPTO, SegmentCoverage
from investo.publisher.price_time_basis import insert_price_time_basis
from investo.publisher.public_document import PublicDocumentContext, finalize_public_bundle
from tests._helpers.briefings import build_briefing

_DATE = date(2026, 10, 8)
_CLOCK = datetime(2026, 10, 9, 0, 6, tzinfo=UTC)


def _item():
    return NormalizedItem(
        source_name="coingecko-price",
        category="price",
        title="조회 시점 가격 · BTC $123.45",
        published_at=_CLOCK,
        raw_metadata={
            "symbol": "btc",
            "coin_id": "bitcoin",
            "price_usd": "123.450000",
            "price_time_basis": "live_snapshot",
            "price_as_of": _CLOCK.isoformat(),
        },
    )


def test_note_is_idempotent_and_preserves_fenced_heading_and_note():
    protected = "```\n## ④ 지표·이벤트\n> **가격 기준**: 코드 예시\n```\n"
    text = protected + "## ④ 지표·이벤트\n\n이벤트를 살핍니다.\n## ⑤ 주요 종목\n"
    actual = insert_price_time_basis(text, [_item()])
    assert actual.startswith(protected)
    assert actual.count("조회 시점 가격") == 1
    assert "2026-10-09 00:06 UTC" in actual
    assert insert_price_time_basis(actual, [_item()]) == actual
    assert insert_price_time_basis(text, []) == text


def test_real_finalizer_retains_explicit_basis_with_true_as_of():
    markdown = (
        f"# {_DATE} 크립토 시황\n\n"
        "> **오늘의 결론**: 시장 흐름을 확인합니다.\n"
        "> **핵심 동인**: 금리 경로를 살핍니다.\n"
        "> **주의할 점**: 변동성을 확인합니다.\n\n"
        + "\n\n".join(
            f"## {heading}\n\n시장 흐름을 살핍니다."
            for heading in (
                "① 요약",
                "② 전일 핵심 이슈",
                "③ 섹터/수급 동향",
                "④ 지표·이벤트",
                "⑤ 주요 종목",
                "⑥ 오늘의 관전 포인트",
            )
        )
        + "\n\n<details><summary>수집/품질 진단</summary>\n가격 수집\n</details>\n"
        + "\n## ⑦ 면책조항\n면책 문구\n"
    )
    outcome = SourceOutcome.ok("coingecko-price", "price", 1, latest_item_at=_CLOCK)
    coverage = SegmentCoverage(
        segment=CRYPTO,
        status="limited",
        item_count=1,
        source_count=1,
        categories=("price",),
        missing_categories=("news",),
        source_outcomes=(outcome,),
    )
    context = PublicDocumentContext(
        target_date=_DATE,
        expected_segments=(CRYPTO,),
        input_absences={},
        anchors_by_segment={},
        items_by_segment={CRYPTO: (_item(),)},
        coverage_by_segment={CRYPTO: coverage},
        source_outcomes=(outcome,),
        bundle_context=None,
        fact_bundle=VerifiedFactBundle(target_date=_DATE),
        entity_observed_at_utc=_CLOCK,
    )
    briefing = build_briefing(target_date=_DATE).model_copy(update={"rendered_markdown": markdown})
    result = finalize_public_bundle({CRYPTO: briefing}, context=context)
    assert len(result.documents) == 1
    text = result.documents[0].briefing.rendered_markdown
    assert "조회 시점 가격 · 2026-10-09 00:06 UTC" in text
    assert "전일 종가" not in text and "+0.00%" not in text
    assert text.count("> **가격 기준**:") == 1
    repeated = finalize_public_bundle({CRYPTO: result.documents[0].briefing}, context=context)
    assert repeated.documents[0].markdown_sha256 == result.documents[0].markdown_sha256

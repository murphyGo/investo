"""Run numeric presentation repairs through the real public bundle finalizer."""

from datetime import UTC, date, datetime

import pytest

from investo.models import Briefing
from investo.models.facts import VerifiedFactBundle
from investo.models.segments import (
    CRYPTO,
    DOMESTIC_EQUITY,
    US_EQUITY,
    MarketSegment,
    SegmentCoverage,
)
from investo.publisher.public_document import (
    PublicDocumentContext,
    PublicDocumentSupplement,
    _apply_pre_finalization_supplements,
    finalize_public_bundle,
)
from investo.publisher.reader_format import wrap_numbers_bold
from tests._helpers.briefings import build_briefing

_DATE = date(2026, 10, 8)
_SEGMENTS = (DOMESTIC_EQUITY, US_EQUITY, CRYPTO)


@pytest.mark.parametrize(
    "value", ("**-$100**", "**$1,234.50**", "**$100.12**", "**+2.3%**", "**-$2.3T**", "**-$100원**")
)
def test_number_style_does_not_rewrap_a_prefix_inside_valid_emphasis(value: str) -> None:
    assert wrap_numbers_bold(value) == value


def _briefing(segment: MarketSegment, value: str) -> Briefing:
    markdown = (
        f"# {_DATE.isoformat()} {segment} 시황\n\n"
        f"> **오늘의 결론**: 형식 예시 {value}를 확인합니다.\n"
        "> **핵심 동인**: 금리 경로를 점검합니다.\n"
        "> **주의할 점**: 변동성을 살핍니다.\n\n"
        "## ① 요약\n\n시장 흐름을 확인합니다.\n\n"
        f"## ② 전일 핵심 이슈\n\n표시 예시 {value}를 확인합니다.\n\n"
        "## ③ 섹터/수급 동향\n\n수급을 점검합니다.\n\n"
        "## ④ 지표·이벤트\n\n지표 발표를 살핍니다.\n\n"
        "## ⑤ 주요 종목\n\n종목별 흐름을 점검합니다.\n\n"
        "## ⑥ 오늘의 관전 포인트\n\n변동성을 확인합니다.\n\n"
        "<details><summary>수집/품질 진단</summary>\n정상 수집\n</details>\n\n"
        "## ⑦ 면책조항\n면책 문구\n"
    )
    return build_briefing(target_date=_DATE).model_copy(update={"rendered_markdown": markdown})


def _context(*, supplement: bool = False) -> PublicDocumentContext:
    return PublicDocumentContext(
        target_date=_DATE,
        expected_segments=_SEGMENTS,
        input_absences={},
        anchors_by_segment={},
        items_by_segment={},
        coverage_by_segment={
            segment: SegmentCoverage(
                segment=segment,
                status="normal",
                item_count=1,
                source_count=1,
                categories=("news",),
                missing_categories=(),
            )
            for segment in _SEGMENTS
        },
        source_outcomes=(),
        bundle_context=None,
        fact_bundle=VerifiedFactBundle(target_date=_DATE),
        entity_observed_at_utc=datetime(2026, 10, 9, tzinfo=UTC),
        supplements_by_segment=(
            {
                US_EQUITY: (
                    PublicDocumentSupplement(
                        supplement_id="u163-supplement",
                        kind="carryover",
                        markdown="## Watchlist Carryover\n추가 형식 예시 **-**$100을 확인합니다.",
                        stable_order=0,
                    ),
                )
            }
            if supplement
            else {}
        ),
    )


@pytest.mark.parametrize("supplement", (False, True))
def test_full_real_bundle_repairs_final_text_and_summary(supplement: bool) -> None:
    briefings = {segment: _briefing(segment, "**+**2.3%") for segment in _SEGMENTS}
    context = _context(supplement=supplement)
    if supplement:
        briefings[US_EQUITY] = _apply_pre_finalization_supplements(
            briefings[US_EQUITY],
            supplements=context.supplements_by_segment[US_EQUITY],
            place=lambda text, blocks: text.replace(
                "## ⑦ 면책조항", "\n".join(blocks) + "\n## ⑦ 면책조항"
            ),
        )
    result = finalize_public_bundle(briefings, context=context)
    assert tuple(document.segment for document in result.documents) == _SEGMENTS
    for document in result.documents:
        assert "**+**2.3%" not in document.briefing.rendered_markdown
        assert "+2.3%" in document.briefing.rendered_markdown
        assert "+2.3%" in document.notification_summary.conclusion
    if supplement:
        assert "**-**$100" not in result.documents[1].briefing.rendered_markdown
        assert "-$100" in result.documents[1].briefing.rendered_markdown
    repeated = finalize_public_bundle(
        {document.segment: document.briefing for document in result.documents}, context=context
    )
    assert result.segment_outcomes == repeated.segment_outcomes
    for first, second in zip(result.documents, repeated.documents, strict=True):
        assert first.briefing.rendered_markdown == second.briefing.rendered_markdown
        assert first.markdown_sha256 == second.markdown_sha256
        assert first.notification_summary == second.notification_summary


def test_mixed_real_bundle_preserves_repaired_and_valid_siblings() -> None:
    briefings = {
        DOMESTIC_EQUITY: _briefing(DOMESTIC_EQUITY, "**+**2.3%"),
        US_EQUITY: _briefing(US_EQUITY, "**+**2..3%"),
        CRYPTO: _briefing(CRYPTO, "**+2.3%**"),
    }
    result = finalize_public_bundle(briefings, context=_context())
    assert tuple(document.segment for document in result.documents) == (DOMESTIC_EQUITY, CRYPTO)
    assert result.segment_outcomes[1].state == "trust_blocked"
    assert "markdown.broken_numeric_bold" in result.segment_outcomes[1].issue_codes
    assert "+2.3%" in result.documents[0].notification_summary.conclusion
    assert "**+2.3%**" in result.documents[1].briefing.rendered_markdown

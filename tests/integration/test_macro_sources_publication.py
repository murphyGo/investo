"""Actual finalizer paths retain reference facts, source notices and news separation."""

from dataclasses import replace

import pytest

from investo._internal.macro_reference import validated_macro_observations
from investo.briefing.segments import build_segment_coverage
from investo.models.event_document import (
    EditionAvailability,
    EditorialPlan,
    EventEditionDraft,
    MarketReferencePanel,
)
from investo.models.facts import VerifiedFactBundle
from investo.publisher.channel_anchor_block import inject_channel_anchor_block
from investo.publisher.public_document import finalize_public_bundle
from tests.unit.publisher.test_public_document_assembly_u144 import (
    _finalizer_context,
    _phase_one_briefing,
    _with_finalizer_diagnostics,
)
from tests.unit.sources.test_macro_sources_20261030 import ADAPTERS, AS_OF, WINDOW, fetch, recorded


@pytest.mark.parametrize("native", [False, True])
@pytest.mark.parametrize("forged", [False, True])
async def test_finalizer_renders_three_sources_and_overwrites_generated_numbers(native, forged):
    items = []
    for adapter in ADAPTERS:
        items += await fetch(adapter, body=recorded(adapter.name))
    if native:
        observation = replace(validated_macro_observations(items)[0], value="999999")
        draft = EventEditionDraft(
            segment="us-equity",
            target_date=WINDOW.target_date,
            availability=EditionAvailability(status="quiet"),
            editorial_plan=EditorialPlan(),
            market_reference=MarketReferencePanel(macro_observations=(observation,)),
        )
    else:
        base = _with_finalizer_diagnostics(_phase_one_briefing())
        draft = base.model_copy(
            update={
                "target_date": WINDOW.target_date,
                "rendered_markdown": base.rendered_markdown.replace(
                    "2026-07-21", str(WINDOW.target_date)
                ).replace("크립토 시황", "미국 증시 시황"),
            }
        )
        if forged:
            text = draft.rendered_markdown.replace(
                "## ① 요약",
                "## ⓪-B 채널 기준선\n\n| TGA 잔액 | 999,999 백만 USD |\n\n## ① 요약",
            )
            draft = draft.model_copy(update={"rendered_markdown": text})
    context = replace(
        _finalizer_context(),
        target_date=WINDOW.target_date,
        expected_segments=("us-equity",),
        active_segments=("us-equity",),
        coverage_by_segment={"us-equity": build_segment_coverage("us-equity", tuple(items))},
        items_by_segment={"us-equity": tuple(items)},
        anchors_by_segment={"us-equity": ()},
        fact_bundle=VerifiedFactBundle(target_date=WINDOW.target_date),
        entity_observed_at_utc=AS_OF,
    )
    result = finalize_public_bundle({"us-equity": draft}, context=context)
    assert result.documents
    document = result.documents[0]
    text = document.rendered_markdown
    assert "999,999" not in text
    assert "TGA 잔액" in text and "1,015,632" in text and "백만 USD" in text
    assert "1.28" in text and "관측 2026-09-30" in text and "발표 버전 2026-10" in text
    assert "-1.913" in text and "2영업일 지연" in text
    assert "Federal Reserve Bank of New York" in text and "privacy/termsofuse" in text
    assert "연준의 공식 추정치가 아님" in text and "이후 수정 가능" in text
    assert "TGA" not in document.notification_summary.conclusion


def test_legacy_forged_rows_disappear_when_no_collected_reference_survives():
    base = _with_finalizer_diagnostics(_phase_one_briefing())
    text = base.rendered_markdown.replace("2026-07-21", str(WINDOW.target_date))
    text = text.replace("크립토 시황", "미국 증시 시황").replace(
        "## ① 요약",
        "## ⓪-B 채널 기준선\n\n| TGA 잔액 | 999,999 백만 USD |\n\n## ① 요약",
    )
    draft = base.model_copy(update={"target_date": WINDOW.target_date, "rendered_markdown": text})
    context = replace(
        _finalizer_context(),
        target_date=WINDOW.target_date,
        expected_segments=("us-equity",),
        active_segments=("us-equity",),
        coverage_by_segment={"us-equity": build_segment_coverage("us-equity", ())},
        items_by_segment={"us-equity": ()},
        anchors_by_segment={"us-equity": ()},
        fact_bundle=VerifiedFactBundle(target_date=WINDOW.target_date),
        entity_observed_at_utc=AS_OF,
    )
    result = finalize_public_bundle({"us-equity": draft}, context=context)
    assert result.documents
    assert "999,999" not in result.documents[0].rendered_markdown
    assert "TGA 잔액" not in result.documents[0].rendered_markdown


@pytest.mark.parametrize(
    "suffix",
    [
        "<!-- investo:block chart:sample -->\nchart\n<!-- /investo:block chart:sample -->\n",
        "<!-- investo:block visual:sample -->\nvisual\n<!-- /investo:block visual:sample -->\n",
        "<!-- investo:block carryover:sample -->\ncarry\n"
        "<!-- /investo:block carryover:sample -->\n",
        "> **오늘의 결론**: 그대로 유지\n",
        "**기준 시각**: 그대로 유지\n",
        "**세그먼트**: 그대로 유지\n",
        "</details>\n<!-- /investo:market-data -->\n",
    ],
)
def test_reference_refresh_preserves_adjacent_owned_content_and_is_idempotent(suffix):
    source = "## ⓪-B 채널 기준선\n\n| TGA 잔액 | forged |\n\n" + suffix + "## ① 요약\n본문\n"
    block = "## ⓪-B 채널 기준선\n\n| TGA 잔액 | correct |\n"
    result = inject_channel_anchor_block(source, block, refresh=True)
    assert suffix in result and "forged" not in result
    assert inject_channel_anchor_block(result, block, refresh=True) == result
    removed = inject_channel_anchor_block(source, "", refresh=True)
    assert suffix in removed and "forged" not in removed

"""Network counts reach both finalizer paths with attribution and real USD validation."""

from dataclasses import replace
from datetime import date

import pytest

from investo.briefing.segments import build_segment_coverage
from investo.models.event_document import (
    EditionAvailability,
    EditorialPlan,
    EventEditionDraft,
    MarketReferencePanel,
)
from investo.models.facts import VerifiedFactBundle
from investo.models.network_activity import NetworkActivity
from investo.models.segments import CRYPTO
from investo.publisher.public_document import finalize_public_bundle
from tests.unit.publisher.test_public_document_assembly_u144 import (
    _finalizer_context,
    _phase_one_briefing,
    _with_finalizer_diagnostics,
)
from tests.unit.sources.test_data_expansion_20261029 import fetch as fetch_flows
from tests.unit.sources.test_data_expansion_20261029 import row
from tests.unit.sources.test_data_priorities_20261030 import AS_OF, WINDOW, activity_rows, fetch


@pytest.mark.parametrize("native", [False, True])
async def test_activity_and_flows_coexist_in_final_publication(native):
    items = await fetch({"data": activity_rows()})
    items += await fetch_flows({"data": [row(), row("eth")]})
    if native:
        draft = EventEditionDraft(
            segment=CRYPTO,
            target_date=WINDOW.target_date,
            availability=EditionAvailability(status="quiet"),
            editorial_plan=EditorialPlan(),
            market_reference=MarketReferencePanel(
                daily_network_activity=(
                    NetworkActivity(
                        "btc", "AdrActCnt", date(2026, 10, 27), "99999", (), AS_OF, AS_OF
                    ),
                )
            ),
        )
    else:
        base = _with_finalizer_diagnostics(_phase_one_briefing())
        draft = base.model_copy(
            update={
                "target_date": WINDOW.target_date,
                "rendered_markdown": base.rendered_markdown.replace(
                    "2026-07-21", str(WINDOW.target_date)
                ),
            }
        )
    context = replace(
        _finalizer_context(),
        target_date=WINDOW.target_date,
        expected_segments=(CRYPTO,),
        active_segments=(CRYPTO,),
        coverage_by_segment={CRYPTO: build_segment_coverage(CRYPTO, tuple(items))},
        items_by_segment={CRYPTO: tuple(items)},
        anchors_by_segment={CRYPTO: ()},
        fact_bundle=VerifiedFactBundle(target_date=WINDOW.target_date),
        entity_observed_at_utc=AS_OF,
    )
    result = finalize_public_bundle({CRYPTO: draft}, context=context)
    assert result.documents
    document = result.documents[0]
    markdown = document.rendered_markdown
    assert "99,999개" not in markdown
    assert "2,700개 · 2026-10-27 UTC · 직전 7일 평균 2,300.0개" in markdown
    assert "ETH 일별 거래 건수" in markdown
    assert "검토 상태 미제공" in markdown and "ETH는 L1" in markdown
    assert "creativecommons.org/licenses/by-nc/4.0/" in markdown
    assert "유입 잠정 / 유출 검토됨" in markdown
    assert "-0.999999999999999999999999999999 BTC" in markdown
    assert "일별 네트워크 활동" not in document.notification_summary.conclusion

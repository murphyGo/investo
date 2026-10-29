"""Daily flows survive the complete public document finalizer."""

from dataclasses import replace
from datetime import UTC, date, datetime

import httpx

from investo.briefing.segments import build_segment_coverage
from investo.models.facts import VerifiedFactBundle
from investo.models.segments import CRYPTO
from investo.publisher.public_document import finalize_public_bundle
from investo.sources import FetchWindow
from investo.sources.coinmetrics_exchange_flows import CoinMetricsExchangeFlowsAdapter
from tests.unit.publisher.test_public_document_assembly_u144 import (
    _finalizer_context,
    _phase_one_briefing,
    _with_finalizer_diagnostics,
)
from tests.unit.sources.test_data_expansion_20261029 import row


async def test_flow_numbers_status_and_license_survive_final_publication():
    target = date(2026, 10, 28)
    now = datetime(2026, 10, 28, 8, tzinfo=UTC)
    window = replace(FetchWindow.from_kst_date(target), evidence_received_at=now)
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(200, json={"data": [row(), row("eth")]})
        )
    ) as client:
        items = await CoinMetricsExchangeFlowsAdapter().fetch(client, window)
    base = _with_finalizer_diagnostics(_phase_one_briefing())
    briefing = base.model_copy(
        update={
            "target_date": target,
            "rendered_markdown": base.rendered_markdown.replace("2026-07-21", str(target)),
        }
    )
    context = replace(
        _finalizer_context(),
        target_date=target,
        items_by_segment={CRYPTO: tuple(items)},
        fact_bundle=VerifiedFactBundle(target_date=target),
        entity_observed_at_utc=now,
    )
    result = finalize_public_bundle({CRYPTO: briefing}, context=context)
    assert result.documents
    markdown = result.documents[0].briefing.rendered_markdown
    assert "-0.999999999999999999999999999999 BTC" in markdown
    assert "-0.999999999999999999999999999999 ETH" in markdown
    assert "2026-10-27 UTC 일별" in markdown
    assert "유입 잠정 / 유출 검토됨" in markdown
    assert "https://github.com/coinmetrics/data" in markdown
    assert "https://creativecommons.org/licenses/by-nc/4.0/" in markdown
    assert "Investo가 유입 - 유출" in markdown


async def test_native_active_editions_display_only_segment_source_backed_references():
    from investo.models.event_document import EditionAvailability, EditorialPlan, EventEditionDraft
    from investo.models.segments import DOMESTIC_EQUITY
    from investo.sources.krx_option_expiry import KrxOptionExpiryAdapter

    target = date(2026, 10, 28)
    now = datetime(2026, 10, 28, 8, tzinfo=UTC)
    window = replace(FetchWindow.from_kst_date(target), evidence_received_at=now)
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(200, json={"data": [row(), row("eth")]})
        )
    ) as client:
        flow_items = await CoinMetricsExchangeFlowsAdapter().fetch(client, window)
        expiry_items = await KrxOptionExpiryAdapter().fetch(client, window)
    for segment, items in ((CRYPTO, flow_items), (DOMESTIC_EQUITY, expiry_items)):
        draft = EventEditionDraft(
            segment=segment,
            target_date=target,
            availability=EditionAvailability(status="quiet"),
            editorial_plan=EditorialPlan(),
        )
        context = replace(
            _finalizer_context(),
            target_date=target,
            expected_segments=(segment,),
            active_segments=(segment,),
            coverage_by_segment={segment: build_segment_coverage(segment, tuple(items))},
            items_by_segment={segment: tuple(items)},
            anchors_by_segment={segment: ()},
            fact_bundle=VerifiedFactBundle(target_date=target),
            entity_observed_at_utc=now,
        )
        result = finalize_public_bundle({segment: draft}, context=context)
        assert result.documents
        document = result.documents[0]
        markdown = document.rendered_markdown
        assert "## 시장 기준 자료" in markdown
        assert "## ⓪-A" not in markdown
        if segment == CRYPTO:
            assert "-0.999999999999999999999999999999 BTC" in markdown
            assert "유입 잠정 / 유출 검토됨" in markdown
            assert "creativecommons.org/licenses/by-nc/4.0/" in markdown
            assert "KOSPI 200 월물" not in markdown
        else:
            assert "2026-11-12 15:20 KST" in markdown
            assert "규칙 기반 계산" in markdown
            assert "Coin Metrics" not in markdown
        assert "일별 순유입" not in document.notification_summary.conclusion
        from investo.notifier.summary import build_segmented_summary

        detail_url = f"https://example.com/{segment}/2026-10-28.html"
        notice = build_segmented_summary(
            {segment: document.notification_summary},
            site_urls={segment: detail_url},
            max_units=700,
            now_utc=now,
        )
        assert detail_url in notice
        assert "-0.999999999999999999999999999999" not in notice


async def test_native_flow_rows_do_not_override_usd_price_verification():
    from investo._internal.crypto_indicators import (
        render_exchange_flow_reference,
        validated_exchange_flows,
    )
    from investo._internal.numeric_verify import verify_core_facts
    from investo.models import NormalizedItem

    now = datetime(2026, 10, 28, 8, tzinfo=UTC)
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(200, json={"data": [row(), row("eth")]})
        )
    ) as client:
        items = await CoinMetricsExchangeFlowsAdapter().fetch(
            client, replace(FetchWindow.from_kst_date(date(2026, 10, 28)), evidence_received_at=now)
        )
    block = render_exchange_flow_reference(validated_exchange_flows(items))
    assert verify_core_facts(block, items).actions == {}
    prices = NormalizedItem(
        source_name="test-price",
        category="price",
        title="USD prices",
        published_at=now,
        raw_metadata={"core_fact:btc_usd": "65000.00", "core_fact:eth_usd": "2500.00"},
    )
    report = verify_core_facts(block + "\nBTC 65000.00 USD\nETH 2500.00 USD", [*items, prices])
    assert set(report.verified) == {"btc_usd", "eth_usd"}
    assert not report.conflicts and not report.unverified
    tampered = block.replace("-0.999999999999999999999999999999 BTC", "99999.0 USD BTC")
    assert verify_core_facts(tampered, [*items, prices]).conflicts


async def test_active_collection_passes_one_cutoff_through_to_native_reference(monkeypatch):
    from pydantic import HttpUrl, TypeAdapter

    from investo._internal.market_reference import source_market_reference
    from investo.models import SourceCollectionReport
    from investo.models.event_config import EventExecutionConfig
    from investo.orchestrator import pipeline
    from investo.orchestrator.stages import PipelineContext

    clock = datetime(2026, 10, 28, 8, tzinfo=UTC)
    captured = []

    async def collect(target_date, **kwargs):
        assert kwargs["evidence_received_at"] == clock
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(
                lambda request: httpx.Response(200, json={"data": [row()]})
            )
        ) as client:
            items = await CoinMetricsExchangeFlowsAdapter().fetch(
                client,
                replace(
                    FetchWindow.from_kst_date(target_date),
                    evidence_received_at=kwargs["evidence_received_at"],
                ),
            )
        captured.extend(items)
        return SourceCollectionReport(items=tuple(items), outcomes=())

    monkeypatch.setattr(pipeline, "_default_collect_sources", collect)
    context = PipelineContext(
        target_date=date(2026, 10, 28),
        run_started_at=clock,
        site_url_base=TypeAdapter(HttpUrl).validate_python("https://example.com"),
        event_config=EventExecutionConfig(mode="active", document_schema=3),
    )
    result = await pipeline.CollectStage().execute(context, {})
    assert result.status == "ok"
    reference = source_market_reference(
        captured, anchors=(), segment=CRYPTO, target_date=context.target_date, observed_at=clock
    )
    assert len(reference.daily_exchange_flows) == 1
    assert reference.daily_exchange_flows[0].as_of == clock

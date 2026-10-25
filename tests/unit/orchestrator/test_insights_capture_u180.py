from pathlib import Path

import pytest
from pydantic import HttpUrl

from investo.models.coverage import SourceCollectionReport, SourceOutcome
from investo.models.insights import InsightRunOutcome
from investo.models.items import NormalizedItem
from investo.models.news_window import NewsWindowConfig
from investo.models.publication import PublishReceipt
from investo.models.results import PipelineResult, PipelineStatus
from investo.orchestrator import pipeline
from investo.orchestrator.insights import InsightsConfig
from investo.orchestrator.stages import PipelineContext
from investo.sources import aggregator
from tests._helpers.insights import NOW, capture


def item(envelope=None):
    return NormalizedItem(
        source_name="bybit-derivatives",
        category="macro",
        title="legacy",
        published_at=NOW,
        insight_envelope=envelope,
    )


async def test_collector_stamps_actual_origin_and_opt_in(monkeypatch):
    requested = []

    class Adapter:
        name = "bybit-derivatives"
        category = "macro"

        async def fetch(self, client, window):
            requested.append(window.insights_enabled)
            forged = capture().envelopes[0].model_copy(update={"origin_adapter_name": "forged"})
            return [item(forged)]

    monkeypatch.setattr(aggregator, "list_sources", lambda: [Adapter()])
    monkeypatch.setattr(aggregator, "source_skip_reasons", lambda **kwargs: {})
    for enabled in (False, True):
        report = await aggregator.collect_sources(NOW.date(), insights_enabled=enabled)
        assert len(report.outcomes) == 1
        if enabled:
            assert report.items[0].insight_envelope.origin_adapter_name == Adapter.name
        else:
            assert report.items[0].insight_envelope is None
    assert requested == [False, True]


async def test_report_sink_before_empty_guard(monkeypatch):
    report = SourceCollectionReport(items=(), outcomes=(SourceOutcome.zero("fixture", "macro"),))

    async def collect(*args, **kwargs):
        return report

    monkeypatch.setattr(pipeline, "_default_collect_sources", collect)
    received = []
    with pytest.raises(pipeline.EmptyCollectError):
        await pipeline._stage_collect(NOW.date(), report_sink=received.append)
    assert received == [report]


@pytest.mark.parametrize(
    "news_active,empty", [(False, False), (True, False), (False, True), (True, True)]
)
async def test_both_collect_paths_publish_before_enrichment_and_preserve_empty_outcomes(
    monkeypatch, news_active, empty
):
    calls = []
    envelope = capture().envelopes[0]
    report = SourceCollectionReport(
        items=() if empty else (item(envelope),),
        outcomes=(SourceOutcome.zero("bybit-derivatives", "macro"),)
        if empty
        else capture().outcomes,
    )

    async def collect(*args, **kwargs):
        assert kwargs["insights_enabled"] is True
        calls.append("collect")
        return report

    async def publish(config, captured, **kwargs):
        calls.append("insights")
        assert captured.outcomes == report.outcomes
        return InsightRunOutcome(mode="shadow", modules=("crypto",), status="shadow")

    monkeypatch.setattr(pipeline, "_default_collect_sources", collect)
    monkeypatch.setattr(pipeline, "run_insights_phase", publish)
    monkeypatch.setattr(pipeline, "_is_dry_run", lambda: True)
    ctx = PipelineContext(
        target_date=NOW.date(),
        site_url_base=HttpUrl("https://example.invalid/"),
        run_started_at=NOW,
        insights_config=InsightsConfig("shadow", ("crypto",)),
        news_window_config=NewsWindowConfig(mode="active") if news_active else NewsWindowConfig(),
    )
    result = await pipeline.CollectStage().execute(ctx, {})
    assert calls == ["collect", "insights"]
    assert result.status == ("failed" if empty else "ok")
    assert result.data["insights"].status == "shadow"
    assert result.data["source_outcomes"] == report.outcomes
    if not empty:
        assert all(i.insight_envelope is None for i in result.data["items"])


async def test_legacy_item_only_injection_does_not_invent_truth(monkeypatch):
    async def fetch(*args):
        return [item(capture().envelopes[0].model_copy(update={"origin_adapter_name": None}))]

    async def publish(config, captured, **kwargs):
        assert captured.envelopes == () and captured.outcomes == ()
        return InsightRunOutcome(mode="shadow", modules=("crypto",), status="shadow")

    monkeypatch.setattr(pipeline, "run_insights_phase", publish)
    ctx = PipelineContext(
        target_date=NOW.date(),
        site_url_base=HttpUrl("https://example.invalid/"),
        fetch=fetch,
        insights_config=InsightsConfig("shadow", ("crypto",)),
    )
    result = await pipeline.CollectStage().execute(ctx, {})
    assert result.data["items"][0].insight_envelope is None


def test_github_outputs_from_confirmed_receipt_even_on_briefing_failure(tmp_path, monkeypatch):
    from investo.__main__ import _write_github_outputs

    output = tmp_path / "outputs"
    monkeypatch.setenv("GITHUB_OUTPUT", str(output))
    receipt = PublishReceipt(
        run_id="fixture",
        local_sha="a" * 40,
        remote_ref="refs/heads/main",
        baseline_metadata_hash="0" * 64,
        status="remote_confirmed",
    )
    result = PipelineResult(
        target_date=NOW.date(),
        status=PipelineStatus.FAILED,
        duration_seconds=0,
        insights=InsightRunOutcome(
            mode="active", modules=("crypto",), status="remote_confirmed", receipt=receipt
        ),
    )
    _write_github_outputs(result)
    text = output.read_text()
    assert "publication_committed=false\n" in text
    assert "insights_publication_committed=true\n" in text
    assert f"insights_published_sha={receipt.local_sha}\n" in text


def test_private_runtime_pages_or_retains_exit_code():
    root = Path(__file__).resolve().parents[3]
    template = (root / "ops/private-runtime/production-briefing.yml").read_text()
    assert (
        "steps.pipeline.outputs.publication_committed == 'true' || "
        "steps.pipeline.outputs.insights_publication_committed == 'true'" in template
    )
    assert "|| steps.pipeline.outputs.insights_published_sha" in template
    assert "process_exit_code=$pipeline_rc" in template


async def test_confirmed_insights_survives_later_generation_failure(monkeypatch):
    from investo.briefing.errors import BriefingGenerationError
    from investo.models.results import SendResult
    from investo.orchestrator.stages import StageResult

    receipt = PublishReceipt(
        run_id="fixture",
        local_sha="a" * 40,
        remote_ref="refs/heads/main",
        baseline_metadata_hash="0" * 64,
        status="remote_confirmed",
    )
    order = []

    async def collect(*args, **kwargs):
        order.append("collect")
        return SourceCollectionReport(
            items=(item(capture().envelopes[0]),), outcomes=capture().outcomes
        )

    async def publish(*args, **kwargs):
        order.append("insights")
        return InsightRunOutcome(
            mode="active", modules=("crypto",), status="remote_confirmed", receipt=receipt
        )

    class FailingGeneration:
        name = "generate"

        async def execute(self, ctx, accumulated):
            order.append("generate")
            assert accumulated["items"][0].insight_envelope is None
            return StageResult(
                status="failed",
                error=BriefingGenerationError(
                    stage="stage2", attempt_count=1, last_stderr=None, cause=None
                ),
                stage_notes={"generate": "failed"},
            )

    class Alerter:
        async def alert(self, *args, **kwargs):
            return SendResult(ok=True)

    monkeypatch.setenv("INVESTO_INSIGHTS_MODE", "active")
    monkeypatch.setenv("INVESTO_INSIGHTS_MODULES", "crypto")
    monkeypatch.setattr(pipeline, "_default_collect_sources", collect)
    monkeypatch.setattr(pipeline, "run_insights_phase", publish)
    result = await pipeline.run_pipeline(
        publisher=object(),
        alerter=Alerter(),
        site_url_base=HttpUrl("https://example.invalid/"),
        run_started_at=NOW,
        stages=(pipeline.CollectStage(), FailingGeneration()),
    )
    assert order == ["collect", "insights", "generate"]
    assert result.status == PipelineStatus.FAILED and not result.publication_committed
    assert result.insights.status == "remote_confirmed"

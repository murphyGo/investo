"""Scheduled collection grants snapshot permission; explicit replay does not."""

from datetime import UTC, date, datetime

import pytest
from pydantic import HttpUrl, TypeAdapter

from investo.models import NormalizedItem, SourceCollectionReport
from investo.orchestrator import pipeline as pipeline_module
from investo.orchestrator.pipeline import CollectStage
from investo.orchestrator.stages import PipelineContext


@pytest.mark.parametrize("replay", (False, True))
async def test_collection_keeps_explicit_replay_origin(monkeypatch, replay):
    clock = datetime(2026, 10, 9, tzinfo=UTC)
    received = []
    item = NormalizedItem(source_name="example", category="news", title="뉴스", published_at=clock)

    async def collect(target_date, **kwargs):
        received.append(kwargs)
        return SourceCollectionReport(items=(item,), outcomes=())

    monkeypatch.setattr(pipeline_module, "_default_collect_sources", collect)
    context = PipelineContext(
        target_date=date(2026, 10, 8),
        site_url_base=TypeAdapter(HttpUrl).validate_python("https://example.com"),
        run_started_at=clock,
        news_replay=replay,
    )
    result = await CollectStage().execute(context, {})
    assert result.status == "ok"
    assert received == ([{}] if replay else [{"price_snapshot_at": clock}])


async def test_injected_collection_seam_keeps_its_original_callable_shape():
    clock = datetime(2026, 10, 9, tzinfo=UTC)
    calls = []

    async def fetch(target_date):
        calls.append(target_date)
        return [
            NormalizedItem(source_name="example", category="news", title="뉴스", published_at=clock)
        ]

    context = PipelineContext(
        target_date=date(2026, 10, 8),
        site_url_base=TypeAdapter(HttpUrl).validate_python("https://example.com"),
        run_started_at=clock,
        fetch=fetch,
    )
    assert (await CollectStage().execute(context, {})).status == "ok"
    assert calls == [context.target_date]

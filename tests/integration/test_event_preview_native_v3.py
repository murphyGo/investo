"""Recorded native preview crosses both stages and the seal with public writes forbidden."""

import json
import subprocess

import pytest

from investo.briefing.generation_contract import GenerationInput
from investo.briefing.watchlist import WatchlistConfig
from investo.models.event_config import EventGenerationPolicy
from investo.models.event_context import ContextClassificationResult
from investo.models.event_document import EventEditionContent
from investo.orchestrator.event_preview import preview_event_briefing
from tests._helpers.event_context_v3 import NOW
from tests._helpers.event_document_v3 import native_case


@pytest.mark.asyncio
@pytest.mark.parametrize("market", ["domestic-equity", "us-equity", "crypto"])
async def test_native_preview_uses_two_stages_and_never_publishes(monkeypatch, tmp_path, market):
    item, draft = native_case(market)
    outputs = [
        ContextClassificationResult(
            schema_version=3, events=(draft.editorial_plan.events[0].source_event,)
        ).model_dump_json(),
        EventEditionContent(articles=draft.articles).model_dump_json(),
    ]
    calls = []

    def runner(args, **kwargs):
        calls.append(kwargs["input"])
        return subprocess.CompletedProcess(args, 0, outputs[len(calls) - 1], "")

    def forbidden(*args, **kwargs):
        pytest.fail("native preview invoked public I/O")

    monkeypatch.chdir(tmp_path)
    before = tuple(tmp_path.rglob("*"))
    monkeypatch.setattr("subprocess.run", forbidden)
    for name in ("CollectStage", "PublishStage", "NotifyStage"):
        monkeypatch.setattr(f"investo.orchestrator.pipeline.{name}.execute", forbidden)
    from pathlib import Path

    monkeypatch.setattr(Path, "write_text", forbidden)
    monkeypatch.setattr(Path, "write_bytes", forbidden)
    monkeypatch.setattr(Path, "mkdir", forbidden)
    result = await preview_event_briefing(
        GenerationInput(
            target_date=draft.target_date,
            segment=market,
            items=(item,),
            watchlist_config=WatchlistConfig(),
            runner=runner,
            event_observed_at=NOW,
            event_generation_policy=EventGenerationPolicy(mode="preview", document_schema=3),
        )
    )
    assert len(calls) == 2 and len(result.finalized.documents) == 1
    sealed = result.finalized.documents[0]
    assert sealed.edition_view is not None
    assert sealed.surviving_event_ids == (draft.articles[0].event_id,)
    assert sealed.notification_summary.events[0].event_id == draft.articles[0].event_id
    assert tuple(tmp_path.rglob("*")) == before
    assert json.loads(outputs[0])["schema_version"] == 3

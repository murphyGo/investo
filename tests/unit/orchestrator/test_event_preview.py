"""The private preview reaches the real finalizer without publication I/O."""

from dataclasses import replace
from datetime import datetime
from pathlib import Path

import pytest

from investo._internal.event_rendering import COLLECTION_LIMITED_EVENTS
from investo.briefing.generation_contract import GenerationInput
from investo.briefing.watchlist import WatchlistConfig
from investo.orchestrator.event_preview import preview_event_briefing
from tests.integration.test_event_generation import _case, _ReplayRunner, _request
from tests.unit.briefing.test_event_evidence import NOW


def request() -> GenerationInput:
    return GenerationInput(
        target_date=NOW.date(),
        items=(),
        watchlist_config=WatchlistConfig(),
        segment="us-equity",
        event_observed_at=NOW,
        data_limited=True,
    )


@pytest.mark.asyncio
async def test_empty_preview_is_honest_and_never_writes_or_calls_pipeline_stages(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    def forbidden(*args: object, **kwargs: object) -> None:
        pytest.fail("preview invoked an I/O stage")

    monkeypatch.chdir(tmp_path)
    for name in ("CollectStage", "GenerateStage", "PublishStage", "NotifyStage"):
        monkeypatch.setattr(f"investo.orchestrator.pipeline.{name}.execute", forbidden)
    monkeypatch.setattr("subprocess.run", forbidden)
    before = tuple(tmp_path.rglob("*"))
    with monkeypatch.context() as no_writes:
        no_writes.setattr(Path, "write_text", forbidden)
        no_writes.setattr(Path, "write_bytes", forbidden)
        no_writes.setattr(Path, "mkdir", forbidden)
        result = await preview_event_briefing(replace(request(), runner=forbidden))
    assert result.generation.event_payload is not None
    assert result.generation.event_payload.collection_limited
    assert COLLECTION_LIMITED_EVENTS in result.generation.briefing.key_issues
    assert len(result.finalized.documents) == 1
    document = result.finalized.documents[0]
    assert COLLECTION_LIMITED_EVENTS in document.briefing.rendered_markdown
    assert document.surviving_event_ids == ()
    assert document.event_identity_receipts == ()
    assert document.notification_summary.events == ()
    assert result.event_coverage is not None
    assert result.event_coverage.collected_candidate_count is None
    assert result.event_coverage.selected_count is None
    assert result.event_coverage.selection_coverage is None
    assert tuple(tmp_path.rglob("*")) == before


@pytest.mark.parametrize(
    "changes",
    [
        {"segment": None},
        {"event_observed_at": None},
        {"event_observed_at": datetime(2026, 9, 21)},
    ],
)
@pytest.mark.asyncio
async def test_preview_requires_a_captured_segment_and_clock(changes: dict[str, object]) -> None:
    with pytest.raises(ValueError, match="segment and a timezone-aware"):
        await preview_event_briefing(replace(request(), **changes))


@pytest.mark.asyncio
async def test_two_stage_preview_seals_grounded_event_without_publication(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    case = _case()
    runner = _ReplayRunner([case.classification, case.synthesis])

    def forbidden(*args: object, **kwargs: object) -> None:
        pytest.fail("preview invoked publication I/O")

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("subprocess.run", forbidden)
    before = tuple(tmp_path.rglob("*"))
    with monkeypatch.context() as no_writes:
        no_writes.setattr(Path, "write_text", forbidden)
        no_writes.setattr(Path, "write_bytes", forbidden)
        no_writes.setattr(Path, "mkdir", forbidden)
        result = await preview_event_briefing(_request(case, runner))
    assert len(runner.prompts) == 2
    assert len(result.finalized.documents) == 1
    document = result.finalized.documents[0]
    assert document.surviving_event_ids == (case.event_id,)
    assert document.notification_summary.events[0].event_id == case.event_id
    assert "123.45" in document.notification_summary.events[0].fact_summary
    assert result.event_coverage is not None
    assert result.event_coverage.selected_count == 1
    assert result.event_coverage.qualified_coverage == 1.0
    assert all(receipt.stage != "published" for receipt in result.event_coverage.receipts)
    assert tuple(tmp_path.rglob("*")) == before

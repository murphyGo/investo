"""Event publication consumes sealed survivors and confirmed remote receipts."""

from __future__ import annotations

import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock

import pytest
from pydantic import HttpUrl

from investo.briefing.generation_contract import GenerationResult
from investo.models import SendResult
from investo.models.event_config import EventExecutionConfig
from investo.models.event_quality import EventStageReceipt
from investo.models.publication import PublicationRequest, PublishReceipt
from investo.models.segments import US_EQUITY
from investo.orchestrator import pipeline
from investo.orchestrator.event_publication import (
    load_remote_event_baseline,
    persist_event_quality_trace,
)
from investo.orchestrator.event_receipts import (
    EVENT_RECEIPT_PATH,
    EventReceiptBaseline,
    EventReceiptLedger,
)
from investo.orchestrator.stages import PipelineContext, StageResult
from investo.publisher.errors import PublisherGitError
from investo.publisher.publication_receipts import PublicationReceiptError
from tests.integration.test_event_finalization import _briefing, _context
from tests.unit.briefing.test_event_narrative import payload_for


def _inputs() -> tuple[PipelineContext, dict[str, object]]:
    payload = payload_for()
    context = _context({US_EQUITY: payload})
    briefing = _briefing(payload)
    stages = tuple(
        EventStageReceipt(stage=stage, status="completed", count=1)
        for stage in (
            "collected",
            "routed",
            "candidate",
            "classified",
            "selected",
            "prompted",
            "generated",
        )
    )
    return PipelineContext(
        target_date=context.target_date,
        site_url_base=HttpUrl("https://example.invalid"),
        event_config=EventExecutionConfig("active"),
        event_observed_at=context.entity_observed_at_utc,
    ), {
        "segmented_mode": True,
        "items": [],
        "source_outcomes": (),
        "segment_briefings": {US_EQUITY: briefing},
        "briefing": briefing,
        "macro_lineage_by_segment": {},
        "public_document_context": context,
        "visual_asset_paths": (),
        "segment_generation_failures": {},
        "event_results": {
            US_EQUITY: GenerationResult(
                briefing=briefing,
                event_plan=payload.plan,
                event_payload=payload,
                event_stage_receipts=stages,
            )
        },
        "event_baseline": EventReceiptBaseline("a" * 40, "b" * 64, ()),
    }


@pytest.mark.asyncio
async def test_publish_stage_wires_terminal_metrics_ledger_and_remote_confirmation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ctx, accumulated = _inputs()
    captured: dict[str, Any] = {}

    async def publish(*args: object, **kwargs: Any) -> dict[str, Path]:
        captured.update(kwargs)
        request: PublicationRequest = kwargs["publication_request"]
        kwargs["publication_receipts"].append(
            PublishReceipt(
                run_id=request.run_id,
                local_sha="c" * 40,
                remote_ref=request.remote_ref,
                baseline_metadata_hash=request.baseline_metadata_hash,
                status="remote_confirmed",
            )
        )
        return {}

    monkeypatch.setattr(pipeline, "_stage_publish_segments", publish)
    monkeypatch.setattr(pipeline, "_is_dry_run", lambda: False)
    result = await pipeline.PublishStage().execute(ctx, accumulated)
    assert result.status == "ok" and result.data is not None
    assert result.data["publication_committed"] is True
    aggregate = result.data["published_event_coverage"]
    assert aggregate.included_segments == (US_EQUITY,)
    assert aggregate.selected_count == aggregate.qualified_event_count == 1
    assert set(aggregate.excluded_segments) == {"domestic-equity", "crypto"}
    bundle = result.data["finalized_bundle"]
    ledger = EventReceiptLedger.model_validate_json(
        captured["transactional_metadata"][EVENT_RECEIPT_PATH]
    )
    assert ledger.receipts == bundle.documents[0].event_identity_receipts
    metrics = result.data["event_coverage"][US_EQUITY]
    assert metrics.receipts[-1].stage == "published"
    assert metrics.receipts[-1].trace[0].reason == "published"


@pytest.mark.asyncio
@pytest.mark.parametrize("status", ["definitely_unpublished", "outcome_unknown"])
async def test_unconfirmed_push_never_claims_published_coverage(
    monkeypatch: pytest.MonkeyPatch, status: str
) -> None:
    ctx, accumulated = _inputs()

    async def fail(*args: object, **kwargs: Any) -> None:
        request = kwargs["publication_request"]
        receipt = PublishReceipt(
            run_id=request.run_id,
            local_sha="c" * 40,
            remote_ref=request.remote_ref,
            baseline_metadata_hash=request.baseline_metadata_hash,
            status=status,
        )
        kwargs["publication_receipts"].append(receipt)
        raise PublicationReceiptError(
            receipt=receipt,
            phase="post_commit",
            receipts=(receipt,),
            attempt_count=1,
            diagnostic="synthetic push failure",
        )

    monkeypatch.setattr(pipeline, "_stage_publish_segments", fail)
    monkeypatch.setattr(pipeline, "_is_dry_run", lambda: False)
    result = await pipeline.PublishStage().execute(ctx, accumulated)
    assert result.status == "failed" and result.data is not None
    assert result.stage_notes["notify_briefing"] == "skipped"
    assert result.data["published_event_coverage"] is None
    assert result.data["event_coverage"][US_EQUITY].terminal_event_count == 1
    assert result.data["publication_receipts"][-1].status == status


@pytest.mark.asyncio
async def test_missing_baseline_refuses_publish_before_any_writes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ctx, accumulated = _inputs()
    accumulated["event_baseline"] = None

    async def forbidden(*args: object, **kwargs: object) -> None:
        pytest.fail("unknown baseline must not enter transaction")

    monkeypatch.setattr(pipeline, "_stage_publish_segments", forbidden)
    monkeypatch.setattr(pipeline, "_is_dry_run", lambda: False)
    result = await pipeline.PublishStage().execute(ctx, accumulated)
    assert result.status == "failed" and isinstance(result.error, PublisherGitError)


@pytest.mark.asyncio
async def test_all_blocked_finalization_retains_attributed_hard_reason(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ctx, accumulated = _inputs()
    briefing = accumulated["briefing"]
    altered = briefing.model_copy(
        update={
            "rendered_markdown": briefing.rendered_markdown.replace(
                "https://example.com/", "https://invalid.example/"
            )
        }
    )
    # Use a canonical source label mutation, independent of the fixture URL.
    if altered.rendered_markdown == briefing.rendered_markdown:
        altered = briefing.model_copy(
            update={
                "rendered_markdown": briefing.rendered_markdown.replace(
                    "- 출처: [", "- 출처: [변조 ", 1
                )
            }
        )
    accumulated["segment_briefings"] = {US_EQUITY: altered}
    monkeypatch.setattr(pipeline, "_is_dry_run", lambda: False)

    async def forbidden(*args: object, **kwargs: object) -> None:
        pytest.fail("zero survivors must not publish")

    monkeypatch.setattr(pipeline, "_stage_publish_segments", forbidden)
    result = await pipeline.PublishStage().execute(ctx, accumulated)
    assert result.status == "failed" and result.data is not None
    metrics = result.data["event_coverage"][US_EQUITY]
    assert metrics.state == "hard_trust_blocked"
    assert "event.evidence_invalid" in metrics.issue_codes
    assert metrics.terminal_event_count is None and metrics.selected_count == 1
    assert result.data["event_coverage"]["crypto"].state == "classification_unavailable"


@pytest.mark.asyncio
async def test_dry_run_has_terminal_metrics_but_no_event_metadata_or_published_counts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ctx, accumulated = _inputs()

    async def dry(*args: object, **kwargs: Any) -> dict[str, Path]:
        assert "publication_request" not in kwargs
        assert "transactional_metadata" not in kwargs
        assert kwargs["event_coverage"][US_EQUITY].qualified_event_count == 1
        return {}

    monkeypatch.setattr(pipeline, "_stage_publish_segments", dry)
    monkeypatch.setattr(pipeline, "_is_dry_run", lambda: True)
    result = await pipeline.PublishStage().execute(ctx, accumulated)
    assert result.data is not None and not result.data["publication_committed"]
    assert result.data["published_event_coverage"].selected_count is None


def _git(*args: str, cwd: Path) -> str:
    return subprocess.run(
        ["git", *args], cwd=cwd, capture_output=True, text=True, check=True, timeout=10
    ).stdout.strip()


def test_remote_baseline_ignores_later_local_commit_and_dirty_ledger(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    remote = tmp_path / "remote.git"
    work = tmp_path / "work"
    work.mkdir()
    _git("init", "--bare", str(remote), cwd=tmp_path)
    _git("init", "-b", "main", cwd=work)
    _git("config", "user.name", "Synthetic Test", cwd=work)
    _git("config", "user.email", "test@example.invalid", cwd=work)
    _git("remote", "add", "origin", str(remote), cwd=work)
    (work / "seed").write_text("seed")
    _git("add", "seed", cwd=work)
    _git("commit", "-m", "baseline", cwd=work)
    _git("push", "origin", "main", cwd=work)
    committed = _git("rev-parse", "HEAD", cwd=work)
    ledger = work / EVENT_RECEIPT_PATH
    ledger.parent.mkdir(parents=True)
    ledger.write_text("private dirty invalid ledger")
    _git("add", str(EVENT_RECEIPT_PATH), cwd=work)
    _git("commit", "-m", "unpublished local", cwd=work)
    ledger.write_text("new uncommitted invalid ledger")
    monkeypatch.chdir(work)
    loaded = load_remote_event_baseline(observed_at=datetime(2026, 9, 27, tzinfo=UTC))
    assert loaded.baseline_sha == committed
    assert loaded.receipts == ()
    assert ledger.read_text() == "new uncommitted invalid ledger"


def test_remote_baseline_failure_is_source_free() -> None:
    def fail(args: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(args, 1, "private stdout", "private token")

    with pytest.raises(PublisherGitError) as caught:
        load_remote_event_baseline(observed_at=datetime(2026, 9, 27, tzinfo=UTC), runner=fail)
    assert caught.value.last_stderr == "event baseline unavailable"
    assert "private" not in str(caught.value)


@pytest.mark.asyncio
async def test_notification_failure_keeps_pipeline_confirmed_event_coverage(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ctx, accumulated = _inputs()
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("investo.models.event_config.EVENT_ACTIVE_READY", True)
    monkeypatch.setattr(pipeline, "_is_dry_run", lambda: False)

    class Generated:
        name = "generate"

        async def execute(
            self, ctx: PipelineContext, values: dict[str, object]
        ) -> StageResult[dict[str, object]]:
            return StageResult(status="ok", data=accumulated)

    class FailedNotification:
        name = "notify_briefing"

        async def execute(
            self, ctx: PipelineContext, values: dict[str, object]
        ) -> StageResult[dict[str, object]]:
            return StageResult(
                status="ok",
                data={
                    "notify_result": SendResult(ok=False, error="synthetic outage"),
                    "briefing_url": HttpUrl("https://example.invalid/day"),
                    "visual_assets_failed": False,
                },
            )

    async def publish(*args: object, **kwargs: Any) -> dict[str, Path]:
        request = kwargs["publication_request"]
        kwargs["publication_receipts"].append(
            PublishReceipt(
                run_id=request.run_id,
                local_sha="c" * 40,
                remote_ref=request.remote_ref,
                baseline_metadata_hash=request.baseline_metadata_hash,
                status="remote_confirmed",
            )
        )
        return {}

    monkeypatch.setattr(pipeline, "_stage_publish_segments", publish)
    alerter = AsyncMock()
    alerter.alert.return_value = SendResult(ok=True)
    result = await pipeline.run_pipeline(
        ctx.target_date,
        publisher=AsyncMock(),
        alerter=alerter,
        site_url_base=ctx.site_url_base,
        event_config=ctx.event_config,
        stages=(Generated(), pipeline.PublishStage(), FailedNotification()),
    )
    assert result.status.value == "partial" and result.publication_committed
    assert result.content_completeness == "complete"
    assert result.published_event_coverage is not None
    assert result.published_event_coverage.included_segments == (US_EQUITY,)
    assert result.published_event_coverage.qualified_coverage == 1.0
    assert result.publication_receipts[-1].status == "remote_confirmed"
    assert list((tmp_path / ".tmp/event-traces").glob("*.json"))


@pytest.mark.asyncio
async def test_private_quality_trace_contains_only_public_metrics_and_hash_receipts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ctx, accumulated = _inputs()

    async def dry(*args: object, **kwargs: Any) -> dict[str, Path]:
        return {}

    monkeypatch.setattr(pipeline, "_stage_publish_segments", dry)
    monkeypatch.setattr(pipeline, "_is_dry_run", lambda: True)
    result = await pipeline.PublishStage().execute(ctx, accumulated)
    assert result.data is not None
    root = tmp_path / "private"
    persist_event_quality_trace(result.data["event_coverage"], root=root)
    (path,) = root.iterdir()
    raw = path.read_text()
    assert payload_for().narratives[0].what_happened not in raw
    parsed = json.loads(raw)
    assert parsed[US_EQUITY]["receipts"]
    assert "receipts" not in parsed[US_EQUITY]["coverage"]

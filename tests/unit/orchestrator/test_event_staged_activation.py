"""Mixed rollout preserves legacy crypto inputs, publication and rollback."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from investo._internal.data_limited_segment import build_data_limited_briefing
from investo.briefing.event_routing import share_official_event_candidates
from investo.briefing.generation_contract import GenerationInput, GenerationResult
from investo.models import NormalizedItem
from investo.models.event_config import EventExecutionConfig
from investo.models.publication import PublishReceipt
from investo.models.segments import (
    CRYPTO,
    DOMESTIC_EQUITY,
    US_EQUITY,
    MarketSegment,
    SegmentCoverage,
)
from investo.orchestrator import pipeline
from investo.orchestrator.event_receipts import EVENT_RECEIPT_PATH, EventReceiptLedger
from investo.publisher.public_document import finalize_public_bundle
from tests.unit.briefing.test_event_evidence import NOW
from tests.unit.orchestrator.test_event_publication import _inputs
from tests.unit.orchestrator.test_run_pipeline import _three_segment_items


def test_active_only_promotes_reviewed_markets_and_shadow_rolls_back_all() -> None:
    active = EventExecutionConfig.from_env({"INVESTO_EVENT_BRIEFING_MODE": "active"})
    active.validate_publication()
    assert active.v2_segments == (DOMESTIC_EQUITY, US_EQUITY)
    assert active.for_segment(CRYPTO).mode == "shadow"
    for segment in (DOMESTIC_EQUITY, US_EQUITY, CRYPTO):
        assert EventExecutionConfig("shadow").for_segment(segment).mode == "shadow"
        assert EventExecutionConfig("off").for_segment(segment).mode == "off"
        assert EventExecutionConfig("preview").for_segment(segment).mode == "preview"
    assert EventExecutionConfig("shadow").v2_segments == ()
    assert EventExecutionConfig.from_env({}).mode == "off"


def test_staged_routing_preserves_native_crypto_rows_and_order() -> None:
    official = NormalizedItem(
        source_name="fomc-rss",
        category="news",
        title="Official monetary statement",
        url="https://www.federalreserve.gov/newsevents/pressreleases/monetary20260921a.htm",
        published_at=NOW,
    )
    crypto = tuple(_three_segment_items())
    native = {DOMESTIC_EQUITY: (), US_EQUITY: (official,), CRYPTO: crypto}
    selected = share_official_event_candidates(
        (official,), native, recipients=EventExecutionConfig("active").v2_segments
    )
    assert selected[DOMESTIC_EQUITY] == selected[US_EQUITY] == (official,)
    assert selected[CRYPTO] == native[CRYPTO]
    assert [item.model_dump_json() for item in selected[CRYPTO]] == [
        item.model_dump_json() for item in crypto
    ]


@pytest.mark.asyncio
async def test_segment_runner_receives_v2_only_for_reviewed_markets(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[MarketSegment, GenerationInput] = {}

    async def generate(request: GenerationInput) -> GenerationResult:
        assert request.segment is not None
        captured[request.segment] = request
        return GenerationResult(
            briefing=build_data_limited_briefing(request.target_date, request.segment)
        )

    monkeypatch.setattr(pipeline, "_u2_generate_from_input", generate)
    briefings, failures, *_ = await pipeline._stage_generate_segments(
        NOW.date(), _three_segment_items(), event_config=EventExecutionConfig("active")
    )
    assert failures == {} and set(briefings) == {DOMESTIC_EQUITY, US_EQUITY, CRYPTO}
    for segment, mode in ((DOMESTIC_EQUITY, "active"), (US_EQUITY, "active"), (CRYPTO, "shadow")):
        request = captured[segment]
        assert request.generation_policy is not None
        assert request.generation_policy.event_mode == mode
        assert (request.event_observed_at is not None) == (mode == "active")
    assert captured[CRYPTO].event_baseline_available


@pytest.mark.asyncio
async def test_mixed_confirmed_publication_keeps_legacy_crypto_and_scopes_event_receipts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ctx, accumulated = _inputs()
    crypto_coverage = SegmentCoverage(
        segment=CRYPTO,
        status="limited",
        item_count=0,
        source_count=0,
        categories=(),
        missing_categories=("price", "news"),
    )
    context = replace(
        accumulated["public_document_context"],
        expected_segments=(US_EQUITY, CRYPTO),
        active_segments=None,
        coverage_by_segment={
            **accumulated["public_document_context"].coverage_by_segment,
            CRYPTO: crypto_coverage,
        },
    )
    legacy = build_data_limited_briefing(ctx.target_date, CRYPTO)
    legacy_bundle_crypto = next(
        doc
        for doc in finalize_public_bundle(
            {**accumulated["segment_briefings"], CRYPTO: legacy},
            context=replace(context, event_payloads_by_segment={}),
        ).documents
        if doc.segment == CRYPTO
    )
    accumulated["public_document_context"] = context
    accumulated["segment_briefings"][CRYPTO] = legacy
    captured: dict[str, Any] = {}

    async def publish(*args: object, **kwargs: Any) -> dict[str, Path]:
        captured.update(kwargs)
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
    monkeypatch.setattr(pipeline, "_is_dry_run", lambda: False)
    result = await pipeline.PublishStage().execute(ctx, accumulated)
    assert result.status == "ok" and result.data is not None
    assert result.data["publication_committed"] is True
    docs = {doc.segment: doc for doc in result.data["finalized_bundle"].documents}
    assert set(docs) == {US_EQUITY, CRYPTO}
    assert (
        docs[CRYPTO].briefing.rendered_markdown == legacy_bundle_crypto.briefing.rendered_markdown
    )
    assert docs[CRYPTO].notification_summary.events == ()
    assert docs[CRYPTO].event_identity_receipts == ()
    assert CRYPTO not in result.data["event_coverage"]
    assert result.data["event_coverage"][US_EQUITY].receipts[-1].stage == "published"
    ledger = EventReceiptLedger.model_validate_json(
        captured["transactional_metadata"][EVENT_RECEIPT_PATH]
    )
    assert ledger.receipts == docs[US_EQUITY].event_identity_receipts
    aggregate = result.data["published_event_coverage"]
    assert aggregate.included_segments == (US_EQUITY,)
    assert CRYPTO in aggregate.excluded_segments

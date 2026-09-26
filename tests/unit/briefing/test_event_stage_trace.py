"""Observed generation stages retain unknown failure denominators and privacy."""

from __future__ import annotations

from dataclasses import replace

import pytest

from investo.briefing.errors import BriefingGenerationError
from investo.briefing.event_trace import collection_stage_receipt, input_stage_receipt
from investo.briefing.pipeline import generate_briefing_from_input
from investo.models import SourceOutcome
from tests.integration.test_event_generation import _case, _ReplayRunner, _request


@pytest.mark.asyncio
async def test_success_records_ordered_stages_without_source_prose() -> None:
    case = _case()
    result = await generate_briefing_from_input(
        _request(case, _ReplayRunner([case.classification, case.synthesis]))
    )
    receipts = result.event_stage_receipts
    assert tuple(r.stage for r in receipts) == (
        "collected",
        "routed",
        "candidate",
        "classified",
        "selected",
        "prompted",
        "generated",
    )
    assert all(r.count == 1 for r in receipts)
    serialized = "".join(r.model_dump_json() for r in receipts)
    assert case.item.title not in serialized
    assert case.item.summary not in serialized
    assert result.event_plan is not None
    assert receipts[-1].trace[0].hash_id == result.event_plan.selected[0].event_id


@pytest.mark.asyncio
async def test_classification_failure_has_no_fake_selected_or_prompted_zero() -> None:
    case = _case()
    with pytest.raises(BriefingGenerationError) as caught:
        await generate_briefing_from_input(_request(case, _ReplayRunner(["{}", "{}"])))
    receipts = {r.stage: r for r in caught.value.event_stage_receipts}
    assert receipts["collected"].count == 1
    assert receipts["classified"].status == "failed"
    assert receipts["classified"].count is None
    assert "selected" not in receipts and "prompted" not in receipts


@pytest.mark.asyncio
async def test_synthesis_failure_keeps_selected_denominator() -> None:
    case = _case()
    with pytest.raises(BriefingGenerationError) as caught:
        await generate_briefing_from_input(
            _request(case, _ReplayRunner([case.classification, "{}", "{}"]))
        )
    receipts = {r.stage: r for r in caught.value.event_stage_receipts}
    assert receipts["selected"].count == receipts["prompted"].count == 1
    assert receipts["generated"].status == "failed"
    assert receipts["generated"].count is None


@pytest.mark.asyncio
@pytest.mark.parametrize("status,known", [("failed", False), ("zero", True)])
async def test_empty_collection_failure_and_observed_zero_are_distinct(
    status: str, known: bool
) -> None:
    case = _case()
    request = replace(
        _request(case, _ReplayRunner([])),
        items=(),
        data_limited=True,
        source_outcomes=(
            SourceOutcome.from_failure("fomc-rss", "news", message="unavailable", transient=True)
            if status == "failed"
            else SourceOutcome.zero("fomc-rss", "news"),
        ),
    )
    result = await generate_briefing_from_input(request)
    receipts = {r.stage: r for r in result.event_stage_receipts}
    assert receipts["collected"].count == (0 if known else None)
    assert ("selected" in receipts) is known
    if known:
        assert receipts["selected"].count == receipts["prompted"].count == 0


def test_candidate_cap_trace_is_bounded_and_collection_count_is_not_capped() -> None:
    item = _case().item
    items = tuple(
        item.model_copy(
            update={"title": f"Synthetic event {i}", "url": None, "event_evidence": None}
        )
        for i in range(600)
    )
    receipt = input_stage_receipt("candidate", items[:96], excluded_from=items)
    assert receipt.count == 96
    assert len(receipt.trace) == 512
    assert any(entry.reason == "candidate_cap" for entry in receipt.trace)
    assert collection_stage_receipt(items, ()).count == 600


def test_partial_source_failure_is_retained_even_without_generated_payload() -> None:
    from investo.publisher.event_quality import evaluate_event_quality

    item = _case().item
    receipt = collection_stage_receipt(
        (item,),
        (
            SourceOutcome.from_failure(
                "fomc-rss", "news", message="private failure prose", transient=True
            ),
        ),
    )
    assert receipt.count == 1 and receipt.status == "completed"
    assert any(entry.reason == "source_unavailable" for entry in receipt.trace)
    assert "private failure prose" not in receipt.model_dump_json()
    coverage = evaluate_event_quality(None, payload=None, receipts=(receipt,))
    assert "source_limited" in coverage.reasons


@pytest.mark.asyncio
@pytest.mark.parametrize("failed", [True, False])
async def test_other_market_news_does_not_complete_recipient_collection(failed: bool) -> None:
    case = _case()
    foreign = case.item.model_copy(
        update={"source_name": "foreign-crypto-news", "event_evidence": None}
    )
    outcome = (
        SourceOutcome.from_failure("fomc-rss", "news", message="unavailable", transient=True)
        if failed
        else SourceOutcome.zero("fomc-rss", "news")
    )
    request = replace(
        _request(case, _ReplayRunner([])),
        items=(),
        event_collection_items=(foreign,),
        data_limited=True,
        source_outcomes=(outcome,),
    )
    result = await generate_briefing_from_input(request)
    receipts = {receipt.stage: receipt for receipt in result.event_stage_receipts}
    assert receipts["collected"].count == (None if failed else 0)
    assert ("selected" in receipts) is (not failed)

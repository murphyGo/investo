"""Review regressions at the event producer's existing two-stage boundary."""

import json

import pytest

from investo.briefing.event_input import event_collection_limited
from investo.briefing.numeric_self_check import find_unverified
from investo.briefing.pipeline import _event_numeric_evidence, generate_briefing_from_input
from investo.models import SourceOutcome
from investo.models.event_narratives import EventGenerationPayload
from investo.models.events import EventSelectionPlan
from tests.integration.test_event_generation import _case, _ReplayRunner, _request
from tests.unit.briefing.test_event_narrative import output_for, payload_for


@pytest.mark.asyncio
async def test_missing_prices_do_not_claim_news_collection_failed() -> None:
    case = _case()
    runner = _ReplayRunner([case.classification, case.synthesis])
    result = await generate_briefing_from_input(_request(case, runner))
    assert result.event_payload is not None
    assert not result.event_payload.collection_limited
    assert "뉴스 수집이 제한되어" not in result.briefing.rendered_markdown


def test_observed_empty_news_is_distinct_from_no_collection_evidence() -> None:
    assert not event_collection_limited((), (SourceOutcome.zero("news-feed", "news"),))
    assert event_collection_limited((), ())
    assert event_collection_limited(
        (_case().item,),
        (SourceOutcome.from_failure("news-feed", "news", message="timeout", transient=True),),
    )


@pytest.mark.asyncio
async def test_short_valid_v2_output_uses_schema_without_legacy_markdown_floor() -> None:
    case = _case()
    empty = EventGenerationPayload(plan=EventSelectionPlan(), narratives=())
    output = output_for(empty).model_dump(mode="json")
    output["sections"] = {key: "확인했습니다." for key in output["sections"]}
    synthesis = json.dumps(output, ensure_ascii=False, separators=(",", ":"))
    assert len(synthesis) < 200
    classification = '{"schema_version":2,"assignments":{"1":2},"unassigned":[],"events":[]}'
    runner = _ReplayRunner([classification, synthesis])
    result = await generate_briefing_from_input(_request(case, runner))
    assert result.event_payload is not None and result.event_payload.narratives == ()
    assert len(runner.prompts) == 2


def test_verified_reaction_spans_and_typed_dates_are_numeric_evidence() -> None:
    payload = payload_for(reaction=True)
    # No source items: only validated event refs and typed date metadata can
    # ground these numbers, including a reaction absent from change_facts.
    assert (
        find_unverified(
            "2026년 9월 21일. 주가가 2% 상승했습니다.",
            (),
            additional_evidence=_event_numeric_evidence(payload),
        )
        == ()
    )

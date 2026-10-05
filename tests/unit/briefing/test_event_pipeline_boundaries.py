"""Review regressions at the event producer's existing two-stage boundary."""

import json
from dataclasses import replace

import pytest

from investo.briefing.errors import BriefingGenerationError
from investo.briefing.event_input import event_collection_limited
from investo.briefing.event_narrative import event_synthesis_diagnostics
from investo.briefing.numeric_self_check import find_unverified
from investo.briefing.pipeline import _event_numeric_evidence, generate_briefing_from_input
from investo.models import NormalizedItem, SourceOutcome
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


@pytest.mark.asyncio
async def test_synthesis_diagnostics_survive_retry_without_changing_feedback() -> None:
    case = _case()
    runner = _ReplayRunner([case.classification, "PRIVATE_NOT_JSON", "PRIVATE_NOT_JSON"])
    with pytest.raises(BriefingGenerationError) as error:
        await generate_briefing_from_input(_request(case, runner))
    assert error.value.stage == "synthesis" and error.value.attempt_count == 2
    assert str(error.value.cause) == "event.output_invalid"
    assert event_synthesis_diagnostics(error.value.cause) == ("synthesis.invalid_json",)
    assert len(runner.prompts) == 3
    assert "Validation code: event.output_invalid" in runner.prompts[-1]
    assert "PRIVATE" not in runner.prompts[-1]
    assert error.value.last_stdout is None and error.value.last_stderr is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("function", "diagnostic"),
    [
        ("parse_six_sections", "synthesis.invalid_sections"),
        ("_validate_required_macro_mentions", "synthesis.required_macro_missing"),
    ],
)
async def test_post_assembly_diagnostics_do_not_retain_source_labels(
    monkeypatch: pytest.MonkeyPatch, function: str, diagnostic: str
) -> None:
    from investo.briefing._core import orchestration

    def reject(*args: object, **kwargs: object) -> None:
        raise ValueError("PRIVATE_SOURCE_LABEL")

    monkeypatch.setattr(orchestration, function, reject)
    case = _case()
    runner = _ReplayRunner([case.classification, case.synthesis, case.synthesis])
    with pytest.raises(BriefingGenerationError) as error:
        await generate_briefing_from_input(_request(case, runner))
    assert str(error.value.cause) == "event.output_invalid"
    assert event_synthesis_diagnostics(error.value.cause) == (diagnostic,)
    assert len(runner.prompts) == 3
    assert "PRIVATE" not in runner.prompts[-1]


@pytest.mark.asyncio
async def test_omitted_macro_retry_restores_exact_identifier_with_existing_budget() -> None:
    case = _case()
    macro = NormalizedItem(
        source_name="fred-macro",
        category="macro",
        title="CPIAUCSL latest observation",
        url="https://fred.stlouisfed.org/series/CPIAUCSL",
        published_at=case.item.published_at,
        raw_metadata={"series_id": "CPIAUCSL", "value": "314.12", "release_date": "2026-09-21"},
    )
    empty = EventGenerationPayload(plan=EventSelectionPlan(), narratives=())
    missing = output_for(empty).model_dump(mode="json")
    corrected = output_for(empty).model_dump(mode="json")
    corrected["sections"]["indicators_events"] = (
        "CPIAUCSL latest observation 실제값은 314.12입니다."
    )
    runner = _ReplayRunner(
        [
            '{"schema_version":2,"assignments":{"1":4},"unassigned":[],"events":[]}',
            json.dumps(missing),
            json.dumps(corrected),
        ]
    )
    result = await generate_briefing_from_input(replace(_request(case, runner), items=(macro,)))
    assert len(runner.prompts) == 3
    hint = "A required macro actual was omitted."
    assert hint not in runner.prompts[1] and hint in runner.prompts[2]
    assert "exact supplied label or complete source URL" in runner.prompts[2]
    assert "CPIAUCSL latest observation" in result.briefing.rendered_markdown
    assert "314.12" in result.briefing.rendered_markdown

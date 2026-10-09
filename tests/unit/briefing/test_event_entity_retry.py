"""Entity correction reuses the strict validator and existing synthesis budget."""

from __future__ import annotations

import json

import pytest

from investo.briefing._assembly.markdown_render import _stage2_retry_feedback
from investo.briefing._core.orchestration import GenerationPolicy, _synthesize
from investo.briefing._core.section_planning import SectionPlan
from investo.briefing.claude_code import RetryBudget
from investo.briefing.errors import BriefingGenerationError
from investo.briefing.event_prompt import EventPromptEvidence
from investo.models.event_narratives import EventGenerationPayload
from tests.integration.test_event_generation import _ReplayRunner
from tests.unit.briefing.test_event_evidence import NOW
from tests.unit.briefing.test_event_narrative import output_for, payload_for


async def _generate(payload: EventGenerationPayload, runner: _ReplayRunner) -> str:
    return await _synthesize(
        SectionPlan(target_date=NOW.date(), items_by_section={}, unassigned=()),
        runner=runner,
        budget=RetryBudget(total_budget_s=30),
        policy=GenerationPolicy(event_mode="preview", timeout_s=3, max_attempts=2),
        segment_context="",
        event_evidence=EventPromptEvidence(
            event_plan=payload.plan,
            grouped_sections="",
            unassigned="",
            row_count=payload.plan.evidence_row_count,
            section_two_row_count=payload.plan.evidence_row_count,
            prompted_items=(),
        ),
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "invalid_text",
    [
        "Acme는 신제품을 출시했습니다. 출시 대상은 Product A입니다.",
        "애크미는 Product A를 정식 출시했습니다.",
        "AcmeCorp는 Product A를 정식 출시했습니다.",
        "PRIVATE_INVENTED_ACTOR는 Product A를 출시했습니다.",
    ],
)
async def test_exact_first_sentence_entities_recover_with_existing_retry(invalid_text: str) -> None:
    payload = payload_for()
    invalid = output_for(payload).model_dump(mode="json")
    invalid["events"][0]["what_happened"] = invalid_text
    runner = _ReplayRunner([json.dumps(invalid), output_for(payload).model_dump_json()])
    body = await _generate(payload, runner)
    assert len(runner.prompts) == 2
    assert "Validation code:" not in runner.prompts[0]
    feedback = runner.prompts[1].removeprefix(runner.prompts[0])
    assert "Validation code: event.entity_unsupported" in feedback
    assert "each nonempty actor_refs and object_refs group" in feedback
    assert "first complete sentence of what_happened" in feedback
    assert invalid_text not in feedback and "PRIVATE_INVENTED_ACTOR" not in feedback
    assert "Acme는 Product A를 정식 출시했습니다." in body
    assert invalid_text not in body


@pytest.mark.asyncio
async def test_repeated_entity_failure_exhausts_budget_without_fallback() -> None:
    payload = payload_for()
    invalid = output_for(payload).model_dump(mode="json")
    invalid["events"][0]["what_happened"] = "PRIVATE_INVENTED_ACTOR는 Product A를 출시했습니다."
    runner = _ReplayRunner([json.dumps(invalid), json.dumps(invalid)])
    with pytest.raises(BriefingGenerationError) as caught:
        await _generate(payload, runner)
    assert len(runner.prompts) == 2
    assert caught.value.stage == "synthesis" and caught.value.attempt_count == 2
    assert str(caught.value.cause) == "event.entity_unsupported"
    assert caught.value.last_stdout is None and caught.value.last_stderr is None
    assert "PRIVATE_INVENTED_ACTOR" not in str(caught.value)


@pytest.mark.asyncio
async def test_empty_object_group_does_not_require_an_invented_object() -> None:
    payload = payload_for("public_statement")
    assert not payload.plan.selected[0].object_refs
    runner = _ReplayRunner([output_for(payload).model_dump_json()])
    assert payload.narratives[0].what_happened in await _generate(payload, runner)
    assert len(runner.prompts) == 1


def test_entity_feedback_does_not_echo_exception_context_or_change_other_codes() -> None:
    feedback = _stage2_retry_feedback(
        ValueError("event.entity_unsupported: PRIVATE_SOURCE"), schema_version=2
    )
    assert "PRIVATE_SOURCE" not in feedback
    for code in ("event.fact_unsupported", "event.output_invalid"):
        other = _stage2_retry_feedback(ValueError(code), schema_version=2)
        assert other.endswith(f"Validation code: {code}\n")
        assert "each nonempty" not in other
    assert _stage2_retry_feedback(None, schema_version=2) == ""

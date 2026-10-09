"""Frozen input/context handoff and legacy serialization compatibility."""

from investo.briefing.generation_contract import GenerationInput
from investo.briefing.watchlist import WatchlistConfig
from investo.models.event_config import EventGenerationPolicy
from investo.models.items import NormalizedItem
from tests._helpers.event_context_v3 import NOW, document


def test_generation_input_freezes_context_and_explicit_schema_policy() -> None:
    docs = [document()]
    item = NormalizedItem(source_name="official", category="news", title="Acme", published_at=NOW)
    policy = EventGenerationPolicy(mode="shadow", document_schema=3)
    request = GenerationInput(
        target_date=NOW.date(),
        items=(item,),
        watchlist_config=WatchlistConfig(),
        event_generation_policy=policy,
        event_context_documents=docs,
    )
    docs.clear()
    assert len(request.event_context_documents) == 1
    assert request.event_generation_policy is policy
    assert "event_context" not in item.model_dump_json()
    legacy = GenerationInput(
        target_date=NOW.date(), items=(item,), watchlist_config=WatchlistConfig()
    )
    assert legacy.event_generation_policy is None and legacy.event_context_documents == ()


async def test_schema_three_shadow_consumes_context_without_changing_output_or_calls() -> None:
    from dataclasses import replace

    from investo.briefing.pipeline import generate_briefing_from_input
    from tests._helpers.briefing_pipeline import valid_classification_stdout, valid_stage2_markdown
    from tests.integration.test_event_generation import _case, _ReplayRunner, _request

    case = _case()
    runners = [
        _ReplayRunner([valid_classification_stdout(1), valid_stage2_markdown()]) for _ in range(2)
    ]
    off = await generate_briefing_from_input(_request(case, runners[0], mode="off"))
    request = replace(
        _request(case, runners[1], mode="off"),
        event_generation_policy=EventGenerationPolicy(mode="shadow", document_schema=3),
    )
    shadow = await generate_briefing_from_input(request)
    assert shadow.context_preparation is not None
    assert shadow.context_preparation.rule_code is None
    assert shadow.context_preparation.retained_count == 1
    assert shadow.context_classification is None and shadow.event_support_vectors == ()
    assert off.briefing.model_dump() == shadow.briefing.model_dump()
    assert runners[0].prompts == runners[1].prompts and len(runners[1].prompts) == 2


async def test_actual_stage_one_context_reaches_protected_stage_two_buffer() -> None:
    from investo.briefing._core.orchestration import GenerationPolicy, classify_context
    from investo.briefing.claude_code import RetryBudget
    from investo.briefing.event_context import (
        build_context_prompt_buffer,
        build_protected_context_buffer,
    )
    from investo.models.event_context import ContextClassificationResult
    from tests._helpers.event_context_v3 import draft
    from tests.integration.test_event_generation import _ReplayRunner

    doc = document()
    buffer = build_context_prompt_buffer((doc,), required_item_ids=frozenset({1}))
    runner = _ReplayRunner(
        [ContextClassificationResult(schema_version=3, events=(draft(doc),)).model_dump_json()]
    )
    result = await classify_context(
        buffer,
        runner=runner,
        budget=RetryBudget(total_budget_s=30),
        policy=GenerationPolicy(timeout_s=3, max_attempts=1),
        segment="us-equity",
        observed_at=NOW,
    )
    protected = build_protected_context_buffer(
        result.events, buffer.documents, required_event_indices=frozenset({0})
    )
    assert result.events[0].meaning_refs[0] in protected.refs
    assert result.events[0].reaction_refs[0] in protected.refs
    assert buffer.text in runner.prompts[0]
    assert len(runner.prompts) == 1


async def test_shadow_source_attachment_failure_is_a_private_diagnostic() -> None:
    from dataclasses import replace

    from investo.briefing.pipeline import generate_briefing_from_input
    from tests._helpers.briefing_pipeline import valid_classification_stdout, valid_stage2_markdown
    from tests.integration.test_event_generation import _case, _ReplayRunner, _request

    case = _case()
    bad = case.item.model_copy(
        update={"event_evidence": case.document.model_copy(update={"source_name": "other"})}
    )
    results, prompts = [], []
    for config in (
        EventGenerationPolicy(),
        EventGenerationPolicy(mode="shadow", document_schema=3),
    ):
        runner = _ReplayRunner([valid_classification_stdout(1), valid_stage2_markdown()])
        request = replace(
            _request(case, runner, mode="off"), items=(bad,), event_generation_policy=config
        )
        results.append(await generate_briefing_from_input(request))
        prompts.append(runner.prompts)
    assert prompts[0] == prompts[1] and len(prompts[1]) == 2
    assert results[0].briefing == results[1].briefing
    assert results[1].context_preparation.rule_code == "context.invalid_schema"


async def test_explicit_policy_is_the_only_mode_authority() -> None:
    from dataclasses import replace

    from investo.briefing.pipeline import generate_briefing_from_input
    from tests.integration.test_event_generation import _case, _ReplayRunner, _request

    case = _case()
    runner = _ReplayRunner([case.classification, case.synthesis])
    request = replace(
        _request(case, runner, mode="off"),
        event_generation_policy=EventGenerationPolicy(mode="preview"),
    )
    result = await generate_briefing_from_input(request)
    assert result.event_plan is not None and len(runner.prompts) == 2

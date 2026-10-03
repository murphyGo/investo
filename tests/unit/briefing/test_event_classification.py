"""Versioned classification, compatibility and bounded failure contracts."""

import json
import subprocess
from collections.abc import Iterator
from dataclasses import replace
from datetime import timedelta

import pytest

from investo.briefing._core.classification import parse_event_classification
from investo.briefing._core.orchestration import GenerationPolicy, _classify
from investo.briefing.claude_code import RetryBudget
from investo.briefing.errors import BriefingGenerationError
from investo.briefing.event_evidence import build_event_candidates, make_evidence_document
from investo.briefing.event_selection import select_events
from investo.briefing.generation_contract import GenerationInput
from investo.briefing.pipeline import generate_briefing_from_input
from investo.briefing.watchlist import WatchlistConfig
from investo.models.event_config import EventExecutionConfig
from investo.models.events import EventCandidateDraft, EventFactDraft
from tests._helpers.briefing_pipeline import valid_classification_stdout, valid_stage2_markdown
from tests.unit.briefing.test_event_evidence import NOW, document, draft, item, ref


@pytest.mark.parametrize(
    ("kind", "predicate", "title", "actor", "action"),
    [
        ("geopolitical", "agreement", "두 국가가 휴전에 합의했다.", "두 국가", "휴전에 합의했다"),
        (
            "public_statement",
            "statement",
            "총재가 긴축 유지를 시사했다.",
            "총재",
            "긴축 유지를 시사했다",
        ),
    ],
)
def test_important_events_do_not_require_price_numbers(
    kind: str,
    predicate: str,
    title: str,
    actor: str,
    action: str,
) -> None:
    doc = make_evidence_document(
        source_name="official",
        title=title,
        summary=title,
        url="https://example.invalid/statement",
        published_at=NOW - timedelta(hours=1),
        received_at=NOW,
        event_time=NOW.date(),
        event_time_basis="source_date",
    )
    proposal = EventCandidateDraft.model_validate(
        dict(
            item_ids=(1,),
            event_kind=kind,
            actor_refs=(ref(doc, actor),),
            action_refs=(ref(doc, action),),
            relation_refs=(ref(doc, actor),),
            impact_refs=(ref(doc, action),),
            timing="announced",
            relation="linked",
            impact="systemic",
            facts=(
                EventFactDraft.model_validate(
                    dict(
                        predicate=predicate,
                        evidence_ref=ref(doc, title),
                        status="quoted_opinion" if kind == "public_statement" else "actual",
                    )
                ),
            ),
        )
    )
    candidates = build_event_candidates([proposal], [item(doc)], [doc], observed_at=NOW)
    plan = select_events(
        candidates, [doc], segment="us-equity", window_start=NOW - timedelta(days=1), window_end=NOW
    )
    assert len(plan.selected) == 1
    assert plan.selected[0].required_fact_ids
    assert title in plan.protected_block


@pytest.mark.parametrize(
    "payload",
    [
        {"assignments": {}, "unassigned": []},
        {"schema_version": 2, "assignments": {}, "unassigned": []},
        {"schema_version": 1, "assignments": {}, "unassigned": [], "events": []},
        {"schema_version": 2, "assignments": {"99": 2}, "events": []},
        {"schema_version": 2, "events": [], "private_text": "RAW_SOURCE_SENTINEL"},
    ],
)
def test_v2_missing_or_invalid_is_unavailable(payload: dict[str, object]) -> None:
    with pytest.raises(ValueError, match="event_classification_unavailable") as raised:
        parse_event_classification(json.dumps(payload), 1)
    assert "RAW_SOURCE_SENTINEL" not in str(raised.value)


def test_valid_zero_events_is_distinct_from_missing_events() -> None:
    result = parse_event_classification(
        '{"schema_version":2,"assignments":{"1":2},"unassigned":[],"events":[]}', 1
    )
    assert result.events == ()


@pytest.mark.asyncio
async def test_bad_evidence_uses_existing_retry_without_leaking_output(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    doc = document()
    proposal = draft(doc).model_dump(mode="json")
    proposal["actor_refs"][0]["end"] = 200
    response = json.dumps(
        {"schema_version": 2, "assignments": {"1": 2}, "unassigned": [], "events": [proposal]}
    )
    calls: list[str | None] = []

    def runner(args: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        calls.append(kwargs.get("input"))
        return subprocess.CompletedProcess(args, 0, response, "RAW_SOURCE_SENTINEL")

    async def no_sleep(_: float) -> None:
        pass

    monkeypatch.setattr("investo.briefing._core.orchestration.asyncio.sleep", no_sleep)
    with pytest.raises(BriefingGenerationError) as raised:
        await _classify(
            [item(doc)],
            runner=runner,
            budget=RetryBudget(total_budget_s=100),
            policy=GenerationPolicy(event_mode="preview", timeout_s=1, max_attempts=2),
            segment_context="test",
            evidence_documents=(doc,),
        )
    assert len(calls) == 2
    assert raised.value.attempt_count == 2
    assert raised.value.last_stdout is None and raised.value.last_stderr is None
    assert "invalid_evidence" in str(raised.value.cause)
    assert "RAW_SOURCE_SENTINEL" not in caplog.text


@pytest.mark.asyncio
async def test_shadow_preserves_v1_prompts_public_bytes_and_call_count() -> None:
    doc = document()
    captures: list[list[str | None]] = []
    results = []
    for mode in ("off", "shadow"):
        prompts: list[str | None] = []
        responses = iter([valid_classification_stdout(1), valid_stage2_markdown()])

        def runner(
            args: list[str],
            *,
            prompts: list[str | None] = prompts,
            responses: Iterator[str] = responses,
            **kwargs: object,
        ) -> subprocess.CompletedProcess[str]:
            prompts.append(kwargs.get("input"))
            return subprocess.CompletedProcess(args, 0, next(responses), "")

        request = GenerationInput(
            target_date=NOW.date(),
            items=[item(doc)],
            watchlist_config=WatchlistConfig(),
            runner=runner,
            generation_policy=replace(GenerationPolicy(), event_mode=mode),
        )
        results.append(await generate_briefing_from_input(request))
        captures.append(prompts)
    assert len(captures[0]) == len(captures[1]) == 2
    assert captures[0] == captures[1]
    assert results[0].briefing.model_dump() == results[1].briefing.model_dump()
    assert results[0].event_observation is None
    assert results[1].event_observation is not None
    assert results[1].event_observation.news_count == 1


@pytest.mark.parametrize("mode", ["active"])
@pytest.mark.asyncio
async def test_unready_consumers_reject_before_generation(mode: str) -> None:
    def forbidden(*args: object, **kwargs: object) -> None:
        pytest.fail("unready event consumer invoked LLM")

    with pytest.raises(ValueError, match="requires"):
        await generate_briefing_from_input(
            GenerationInput(
                target_date=NOW.date(),
                items=[],
                watchlist_config=WatchlistConfig(),
                runner=forbidden,
                generation_policy=replace(GenerationPolicy(), event_mode=mode),
            )
        )


def test_item_serialization_preserves_old_null_fields() -> None:
    plain = item(document()).model_copy(
        update={"event_evidence": None, "summary": None, "url": None}
    )
    payload = plain.model_dump(mode="json")
    assert "event_evidence" not in payload
    assert payload["summary"] is None and payload["url"] is None
    assert payload["scheduled_at"] is None
    assert EventExecutionConfig.from_env({}).mode == "off"
    with pytest.raises(ValueError):
        EventExecutionConfig.from_env({"INVESTO_EVENT_BRIEFING_MODE": "invalid"})

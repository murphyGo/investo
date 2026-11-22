"""Synthetic regressions for u157/u158 strict, source-free event retry repair.

Production logs retain failure codes, not failed model payloads. These inputs
exercise those validators without claiming to replay the original LLM output.
"""

from __future__ import annotations

import json

import pytest

from investo.briefing._assembly.markdown_render import _stage2_retry_feedback
from investo.briefing._core.classification import (
    EventClassificationError,
    event_classification_retry_feedback,
)
from investo.briefing._core.orchestration import GenerationPolicy, _classify
from investo.briefing.claude_code import RetryBudget
from investo.briefing.errors import BriefingGenerationError
from tests.integration.test_event_generation import _ReplayRunner
from tests.unit.briefing.test_event_entity_retry import _generate
from tests.unit.briefing.test_event_evidence import NOW, document, draft, item
from tests.unit.briefing.test_event_narrative import output_for, payload_for


@pytest.fixture(autouse=True)
def _no_retry_sleep(monkeypatch: pytest.MonkeyPatch) -> None:
    async def no_sleep(_: float) -> None:
        pass

    monkeypatch.setattr("investo.briefing._core.orchestration.asyncio.sleep", no_sleep)


def _classification_output(fault: str = "") -> str:
    doc = document()
    proposal = draft(doc).model_dump(mode="json")
    output = {
        "schema_version": 2,
        "assignments": {"1": 2, "2": 2},
        "unassigned": [],
        "events": [proposal],
    }
    if fault == "span":
        proposal["actor_refs"][0]["end"] = len(doc.title) + 1
    elif fault == "revision":
        proposal["actor_refs"][0]["revision_id"] = "0" * len(doc.revision_id)
    elif fault == "blank":
        proposal["actor_refs"][0].update(start=4, end=5)
    elif fault == "ownership":
        proposal["item_ids"] = [2]
    elif fault in ("relation", "impact", "object"):
        proposal[f"{fault}_refs"] = []
    elif fault == "items":
        output["assignments"] = {"99": 2}
    elif fault == "schema":
        proposal["actor_refs"][0]["document_id"] = "PRIVATE_MODEL_VALUE"
    return json.dumps(output)


async def _classify_outputs(runner: _ReplayRunner, *, attempts: int = 2) -> object:
    docs = (document(), document(path="two"))
    return await _classify(
        [item(doc) for doc in docs],
        runner=runner,
        budget=RetryBudget(total_budget_s=30),
        policy=GenerationPolicy(event_mode="preview", timeout_s=1, max_attempts=attempts),
        segment_context="",
        segment="domestic-equity",
        evidence_documents=docs,
        observed_at=NOW,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "fault,diagnostic,hint",
    [
        ("span", "evidence.span_out_of_bounds", "Unicode codepoints"),
        ("revision", "evidence.item_mismatch", "document/revision"),
        ("blank", "evidence.blank_span", "non-whitespace"),
        ("ownership", "evidence.item_mismatch", "event's item_ids"),
        ("relation", "evidence.relation_missing", "relation_refs"),
        ("impact", "evidence.impact_missing", "impact_refs"),
        ("object", "evidence.object_missing", "requires object_refs"),
        ("items", "classification.invalid_items", "required macro item ID"),
        ("schema", "schema.string_pattern_mismatch.document_id", "supplied JSON schema"),
    ],
)
async def test_invalid_classification_gets_specific_feedback_then_validates(
    fault: str, diagnostic: str, hint: str, caplog: pytest.LogCaptureFixture
) -> None:
    runner = _ReplayRunner([_classification_output(fault), _classification_output()])
    result = await _classify_outputs(runner)
    assert len(runner.prompts) == 2
    feedback = runner.prompts[1].removeprefix(runner.prompts[0])
    assert feedback.startswith("\nPrevious Stage 1 JSON failed validation.")
    assert diagnostic in feedback and hint in feedback
    assert len(feedback) < 4096
    assert "PRIVATE_MODEL_VALUE" not in feedback + caplog.text
    assert "RAW_EVENT_RESPONSE_MUST_NOT_ESCAPE" not in caplog.text
    assert f"attempt=1 diagnostics={diagnostic}" in caplog.text
    assert result.events == (draft(document()),)


@pytest.mark.asyncio
async def test_classification_feedback_uses_latest_failure_without_accumulating() -> None:
    runner = _ReplayRunner(
        [
            _classification_output("span"),
            _classification_output("revision"),
            _classification_output(),
        ]
    )
    await _classify_outputs(runner, attempts=3)
    base, second, third = runner.prompts
    assert second.startswith(base) and third.startswith(base)
    assert "evidence.span_out_of_bounds" in second.removeprefix(base)
    assert "evidence.span_out_of_bounds" not in third.removeprefix(base)
    assert third.count("Previous Stage 1 JSON failed validation.") == 1
    assert "evidence.item_mismatch" in third.removeprefix(base)


@pytest.mark.asyncio
async def test_repeated_invalid_classification_stays_blocked() -> None:
    bad = _classification_output("span")
    runner = _ReplayRunner([bad, bad])
    with pytest.raises(BriefingGenerationError) as caught:
        await _classify_outputs(runner)
    assert len(runner.prompts) == 2
    assert caught.value.stage == "classification" and caught.value.attempt_count == 2
    assert "invalid_evidence" in str(caught.value.cause)
    assert caught.value.last_stdout is None and caught.value.last_stderr is None


def test_classification_hint_boundary_filters_forged_diagnostics_and_raw_errors() -> None:
    assert event_classification_retry_feedback(None) == ""
    assert event_classification_retry_feedback(ValueError("PRIVATE_RAW_ERROR")) == ""
    cause = EventClassificationError(
        "PRIVATE_RAW_ERROR",
        (
            "evidence.span_out_of_bounds",
            "evidence.span_out_of_bounds",
            "evidence.private_secret",
            "schema.private_secret.events",
            "schema.missing.private_secret",
            "schema.missing.events",
        ),
    )
    feedback = event_classification_retry_feedback(cause)
    assert "PRIVATE" not in feedback and "private_secret" not in feedback
    assert feedback.count("evidence.span_out_of_bounds") == 1
    assert "schema.missing.events" in feedback


def test_classification_hints_cover_date_and_metadata_without_inference() -> None:
    cause = EventClassificationError(
        "invalid_evidence",
        (
            "evidence.date_conflict",
            "evidence.future_occurred",
            "evidence.fact_metadata_missing",
            "evidence.invalid",
            "evidence.item_mismatch",
            "evidence.span_out_of_bounds",
            "evidence.unknown_document",
            "schema.missing.events",
        ),
    )
    feedback = event_classification_retry_feedback(cause)
    assert len(feedback) < 4096
    assert "event dates disagree" in feedback
    assert "Future scheduled evidence is not an occurred event" in feedback
    assert "Use null when absent" in feedback
    assert "actual/forecast status unchanged" in feedback


@pytest.mark.asyncio
@pytest.mark.parametrize("fault", ["missing_fact", "invented_number", "wrong_role", "evidence"])
async def test_synthesis_grounding_failure_gets_repair_hint_then_validates(
    fault: str, caplog: pytest.LogCaptureFixture
) -> None:
    payload = payload_for("earnings_result" if fault == "wrong_role" else "product_service")
    valid = output_for(payload)
    invalid = valid.model_dump(mode="json")
    event = invalid["events"][0]
    code = "event.fact_unsupported"
    if fault == "missing_fact":
        event["fact_ids"] = []
    elif fault == "invented_number":
        event["what_happened"] = "Acme는 Product A를 999개 출시했습니다."
    elif fault == "wrong_role":
        event["what_happened"] = "Acme는 실제 매출 12억 달러를 발표했습니다."
    else:
        event["source_refs"] = [event["source_refs"][0]]
        code = "event.evidence_invalid"
    runner = _ReplayRunner([json.dumps(invalid), valid.model_dump_json()])
    body = await _generate(payload, runner)
    assert len(runner.prompts) == 2
    feedback = runner.prompts[1].removeprefix(runner.prompts[0])
    assert f"Validation code: {code}" in feedback
    assert ("source_refs" if fault == "evidence" else "required_fact_ids") in feedback
    assert "999" not in feedback
    assert f"code={code}" in caplog.text
    assert payload.narratives[0].what_happened in body


@pytest.mark.asyncio
async def test_repeated_unsupported_facts_remain_blocked() -> None:
    payload = payload_for()
    invalid = output_for(payload).model_dump(mode="json")
    invalid["events"][0]["what_happened"] = "Acme는 Product A를 999개 출시했습니다."
    runner = _ReplayRunner([json.dumps(invalid), json.dumps(invalid)])
    with pytest.raises(BriefingGenerationError) as caught:
        await _generate(payload, runner)
    assert str(caught.value.cause) == "event.fact_unsupported"
    assert len(runner.prompts) == caught.value.attempt_count == 2
    assert caught.value.last_stdout is None and caught.value.last_stderr is None
    assert "999" not in str(caught.value)


@pytest.mark.asyncio
async def test_arbitrary_event_prefixed_errors_never_reach_feedback_or_logs(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    secret_code = "event.private_token_leak"

    def reject(*args: object, **kwargs: object) -> None:
        raise ValueError(secret_code + ": PRIVATE_RAW_ERROR")

    monkeypatch.setattr("investo.briefing._core.orchestration.parse_event_synthesis", reject)
    runner = _ReplayRunner(["{}", "{}"])
    with pytest.raises(BriefingGenerationError) as caught:
        await _generate(payload_for(), runner)
    feedback = runner.prompts[1].removeprefix(runner.prompts[0])
    assert "Validation code: event.output_invalid" in feedback
    assert str(caught.value.cause) == "event.output_invalid"
    assert secret_code not in feedback + caplog.text + str(caught.value)
    assert "PRIVATE_RAW_ERROR" not in feedback + caplog.text + str(caught.value)
    assert _stage2_retry_feedback(ValueError(secret_code), schema_version=2) == (
        _stage2_retry_feedback(ValueError("event.output_invalid"), schema_version=2)
    )

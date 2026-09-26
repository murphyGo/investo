"""Synthetic annotated event cases through the real v2 parser and renderer."""

import json
import warnings
from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from investo._internal.event_rendering import (
    COLLECTION_LIMITED_EVENTS,
    EVENTS_MARKER,
    NO_SELECTED_EVENTS,
    NO_SURVIVING_EVENTS,
    REACTION_UNAVAILABLE,
    EventNarrativeValidationError,
    event_summary_lines,
    first_event_sentence,
    render_event_blocks,
    validate_event_payload,
)
from investo.briefing.event_evidence import build_event_candidates, make_evidence_document
from investo.briefing.event_narrative import assemble_event_synthesis, parse_event_synthesis
from investo.briefing.event_selection import select_events
from investo.briefing.prompts import STAGE2_SECTION_HEADERS
from investo.models.event_narratives import (
    EventGenerationPayload,
    EventMeaning,
    EventNarrative,
    EventReaction,
    Stage2OutputV2,
    Stage2Sections,
)
from investo.models.events import EventCandidateDraft, EventFactDraft, EventKind, EventSelectionPlan
from tests.unit.briefing.test_event_evidence import NOW, item, ref

_CASES = {
    "monetary_policy": (
        "연준",
        "금리 인하",
        "",
        "decision",
        "기준금리 0.25%p 인하",
        "연준은 기준금리를 0.25%p 인하했습니다.",
        "actual",
    ),
    "earnings_result": (
        "Acme",
        "실적 발표",
        "",
        "result",
        "실제 매출 10억 달러",
        "Acme는 매출 10억 달러를 기록했습니다.",
        "actual",
    ),
    "product_service": (
        "Acme",
        "제품 출시",
        "Product A",
        "launch",
        "Product A가 정식 출시됐습니다.",
        "Acme는 Product A를 정식 출시했습니다.",
        "actual",
    ),
    "public_statement": (
        "위원장",
        "정책 발언",
        "",
        "statement",
        "물가 안정이 우선이라고 발언했습니다.",
        "위원장은 물가 안정이 우선이라고 밝혔습니다.",
        "quoted_opinion",
    ),
}


def payload_for(
    kind: EventKind = "product_service",
    *,
    reaction: bool = False,
    quiet: bool = False,
    actor_override: str | None = None,
    object_override: str | None = None,
) -> EventGenerationPayload:
    actor, action, obj, predicate, fact_text, what, status = _CASES[kind]
    if actor_override is not None:
        what = what.replace(actor, actor_override)
        actor = actor_override
    if object_override is not None and obj:
        what = what.replace(obj, object_override)
        fact_text = fact_text.replace(obj, object_override)
        obj = object_override
    doc = make_evidence_document(
        source_name="official",
        title=f"{actor} {action} {obj}".strip(),
        summary=f"{fact_text} 2026년 2분기. 다음 분기 예상 매출 12억 달러.",
        detail_excerpt="시장 반응은 없었습니다." if quiet else "주가가 2% 상승했습니다.",
        url=f"https://example.invalid/{kind}",
        published_at=NOW - timedelta(hours=1),
        received_at=NOW,
        event_time=NOW.date(),
        event_time_basis="source_date",
        source_tier="official",
    )
    fact = EventFactDraft.model_validate(
        {
            "predicate": predicate,
            "evidence_ref": ref(doc, fact_text, "summary"),
            "status": status,
            "period": "2026년 2분기" if kind == "earnings_result" else None,
            "unit": "달러" if kind == "earnings_result" else None,
        }
    )
    facts = [fact]
    if kind == "earnings_result":
        facts.append(
            EventFactDraft(
                predicate="guidance",
                status="forecast",
                evidence_ref=ref(doc, "다음 분기 예상 매출 12억 달러.", "summary"),
                unit="달러",
            )
        )
    proposal = EventCandidateDraft(
        item_ids=(1,),
        event_kind=kind,
        actor_refs=(ref(doc, actor),),
        action_refs=(ref(doc, action),),
        object_refs=(ref(doc, obj),) if obj else (),
        relation_refs=(ref(doc, fact_text, "summary"),),
        impact_refs=(ref(doc, doc.detail_excerpt, "detail_excerpt"),),
        facts=tuple(facts),
        timing="announced",
        relation="direct",
        impact="company",
    )
    candidates = build_event_candidates([proposal], [item(doc)], [doc], observed_at=NOW)
    plan = select_events(
        candidates,
        [doc],
        segment="us-equity",
        window_start=NOW - timedelta(days=1),
        window_end=NOW,
    )
    candidate = plan.selected[0]
    narrative = EventNarrative(
        event_id=candidate.event_id,
        headline=f"{actor} {action}",
        what_happened=what,
        fact_ids=tuple(fact.fact_id for fact in candidate.change_facts),
        source_refs=candidate.evidence_refs,
        meaning=EventMeaning(
            text="수요가 늘어나는 경우 기업 활동에 영향을 줄 수 있습니다.",
            mode="conditional",
            evidence_refs=(ref(doc, fact_text, "summary"),),
        ),
        reaction=EventReaction(
            text=doc.detail_excerpt if reaction else None,
            status=("source_reported_no_reaction" if quiet else "observed")
            if reaction
            else "unavailable",
            evidence_refs=(ref(doc, doc.detail_excerpt, "detail_excerpt"),) if reaction else (),
        ),
    )
    return EventGenerationPayload(plan=plan, narratives=(narrative,))


def output_for(payload: EventGenerationPayload) -> Stage2OutputV2:
    return Stage2OutputV2(
        schema_version=2,
        sections=Stage2Sections(
            market_summary="- 수집된 발표를 확인했습니다.",
            sector_flow="확인된 섹터 자료가 제한적입니다.",
            indicators_events="추가 일정은 확인하지 못했습니다.",
            notable_tickers="개별 종목의 추가 자료는 제한적입니다.",
            today_watch="후속 공식 발표를 확인할 필요가 있습니다.",
        ),
        events=payload.narratives,
    )


@pytest.mark.parametrize("kind", list(_CASES))
def test_annotated_event_cases_preserve_facts_status_time_and_source(kind: EventKind) -> None:
    payload = payload_for(kind)
    output = parse_event_synthesis(output_for(payload).model_dump_json(), payload.plan)
    markdown = assemble_event_synthesis(output, payload.plan)
    assert all(markdown.count(header) == 1 for header in STAGE2_SECTION_HEADERS)
    assert EVENTS_MARKER in markdown
    candidate, narrative = payload.plan.selected[0], payload.narratives[0]
    assert f"<!-- investo:block event:{candidate.event_id} -->" in markdown
    assert f"<!-- /investo:block event:{candidate.event_id} -->" in markdown
    for fact in candidate.change_facts:
        assert fact.value_text in markdown
    for label in (
        "시점:",
        "주체:",
        "무슨 일이 있었나:",
        "결정/실적/발표 내용:",
        "의미:",
        "시장 반응:",
        "출처:",
    ):
        assert label in markdown
    assert "2026-09-21 (출처 날짜)" in markdown
    assert f"[official](https://example.invalid/{kind})" in markdown
    assert REACTION_UNAVAILABLE in markdown
    assert first_event_sentence(narrative) == narrative.what_happened
    assert event_summary_lines(payload)[0] == narrative.what_happened
    if kind == "earnings_result":
        assert "[실제, 기간 2026년 2분기, 단위 달러]" in markdown
        assert "[예상, 단위 달러]" in markdown
    if kind == "public_statement":
        assert "[인용 발언]" in markdown


@pytest.mark.parametrize("mutation", ["missing", "duplicate", "unknown", "wrong_order"])
def test_event_set_and_order_must_exactly_match_selected_plan(mutation: str) -> None:
    left, right = payload_for(), payload_for("earnings_result")
    plan = select_events(
        [*left.plan.selected, *right.plan.selected],
        [*left.plan.evidence_documents, *right.plan.evidence_documents],
        segment="us-equity",
        window_start=NOW - timedelta(days=1),
        window_end=NOW,
    )
    by_id = {n.event_id: n for n in (*left.narratives, *right.narratives)}
    ordered = tuple(by_id[event.event_id] for event in plan.selected)
    changed = {
        "missing": ordered[:1],
        "duplicate": (ordered[0], ordered[0]),
        "unknown": (ordered[0], ordered[1].model_copy(update={"event_id": "0" * 24})),
        "wrong_order": tuple(reversed(ordered)),
    }[mutation]
    output = output_for(left).model_copy(update={"events": changed})
    with pytest.raises(EventNarrativeValidationError, match=r"event\.selection_mismatch"):
        parse_event_synthesis(output.model_dump_json(), plan)


@pytest.mark.parametrize(
    "change,code",
    [
        ({"fact_ids": ()}, "event.fact_unsupported"),
        ({"what_happened": "Beta는 Product A를 정식 출시했습니다."}, "event.entity_unsupported"),
        (
            {"what_happened": "AcmeCorp는 Product A를 정식 출시했습니다."},
            "event.entity_unsupported",
        ),
        ({"what_happened": "Acme는 Product B를 정식 출시했습니다."}, "event.entity_unsupported"),
        ({"what_happened": "Acme는 Product A를 999개 출시했습니다."}, "event.fact_unsupported"),
        ({"what_happened": "Acme의 Product A는 중요한 이슈입니다."}, "event.narrative_invalid"),
        ({"what_happened": "Acme는 Product A를 출시했습니다. 미완성"}, "event.narrative_invalid"),
        (
            {
                "what_happened": "Acme Product A "
                + "시장에 중요한 영향을 주는 " * 5
                + "출시 소식입니다."
            },
            "event.narrative_invalid",
        ),
        (
            {"what_happened": "Acme Product A https://untrusted.invalid 출시입니다."},
            "event.narrative_invalid",
        ),
    ],
)
def test_structural_fact_entity_and_prose_negatives(change: dict[str, object], code: str) -> None:
    payload = payload_for()
    bad = payload.narratives[0].model_copy(update=change)
    with pytest.raises(EventNarrativeValidationError, match=code):
        validate_event_payload(payload.model_copy(update={"narratives": (bad,)}))


def test_field_local_references_do_not_borrow_another_claims_number() -> None:
    payload = payload_for(reaction=True)
    narrative = payload.narratives[0]
    # The number exists in the event's reaction source, but not in the cited
    # launch fact. Field-local validation must not search the entire event.
    wrong = narrative.meaning.model_copy(
        update={"text": "수요가 늘어나는 경우 매출이 2% 늘어날 수 있습니다."}
    )
    bad = narrative.model_copy(update={"meaning": wrong})
    with pytest.raises(EventNarrativeValidationError, match=r"event\.fact_unsupported"):
        validate_event_payload(payload.model_copy(update={"narratives": (bad,)}))


def test_actor_reference_is_not_evidence_of_a_market_reaction() -> None:
    payload = payload_for(reaction=True)
    narrative = payload.narratives[0]
    wrong = narrative.reaction.model_copy(
        update={
            "text": "주가가 상승했습니다.",
            "evidence_refs": payload.plan.selected[0].actor_refs,
        }
    )
    with pytest.raises(EventNarrativeValidationError, match=r"event\.evidence_invalid"):
        validate_event_payload(
            payload.model_copy(
                update={
                    "narratives": (narrative.model_copy(update={"reaction": wrong}),),
                }
            )
        )


def test_conditional_mode_requires_explicit_conditional_language() -> None:
    payload = payload_for()
    narrative = payload.narratives[0]
    wrong = narrative.meaning.model_copy(update={"text": "기업 활동이 확대됩니다."})
    with pytest.raises(EventNarrativeValidationError, match=r"event\.narrative_invalid"):
        validate_event_payload(
            payload.model_copy(
                update={
                    "narratives": (narrative.model_copy(update={"meaning": wrong}),),
                }
            )
        )


def test_forecast_value_cannot_be_presented_as_an_actual_without_forecast_role() -> None:
    payload = payload_for("earnings_result")
    narrative = payload.narratives[0].model_copy(
        update={"what_happened": "Acme는 실제 매출 12억 달러를 기록했습니다."}
    )
    with pytest.raises(EventNarrativeValidationError, match=r"event\.fact_unsupported"):
        validate_event_payload(payload.model_copy(update={"narratives": (narrative,)}))


def test_actual_and_forecast_roles_cannot_swap_known_values() -> None:
    payload = payload_for("earnings_result")
    narrative = payload.narratives[0].model_copy(
        update={"what_happened": "Acme는 실제 매출 12억 달러, 예상 매출 10억 달러를 발표했습니다."}
    )
    with pytest.raises(EventNarrativeValidationError, match=r"event\.fact_unsupported"):
        validate_event_payload(payload.model_copy(update={"narratives": (narrative,)}))


def test_unknown_revision_and_forged_source_value_are_rejected() -> None:
    payload = payload_for()
    narrative = payload.narratives[0]
    bad_ref = narrative.source_refs[0].model_copy(update={"revision_id": "f" * 64})
    with pytest.raises(EventNarrativeValidationError, match=r"event\.evidence_invalid"):
        validate_event_payload(
            payload.model_copy(
                update={
                    "narratives": (narrative.model_copy(update={"source_refs": (bad_ref,)}),),
                }
            )
        )
    candidate = payload.plan.selected[0]
    forged = candidate.change_facts[0].model_copy(update={"value_text": "Fabricated source fact"})
    candidate = candidate.model_copy(update={"change_facts": (forged,)})
    with pytest.raises(EventNarrativeValidationError, match=r"event\.fact_unsupported"):
        validate_event_payload(
            payload.model_copy(
                update={
                    "plan": payload.plan.model_copy(update={"selected": (candidate,)}),
                }
            )
        )


def test_schema_errors_are_bounded_and_never_echo_model_prose() -> None:
    payload = payload_for()
    valid = output_for(payload).model_dump(mode="json")
    for bad in (
        "```json\n" + json.dumps(valid) + "\n```",
        json.dumps({**valid, "schema_version": 1}),
        json.dumps({**valid, "schema_version": 2.0}),
        json.dumps(valid).replace(
            '"schema_version": 2', '"schema_version": 2, "schema_version": 2'
        ),
        json.dumps({key: value for key, value in valid.items() if key != "events"}),
        json.dumps({**valid, "private_prose": "DO_NOT_ECHO_THIS_SOURCE"}),
    ):
        with pytest.raises(ValueError) as error:
            parse_event_synthesis(bad, payload.plan)
        assert str(error.value) == "event_synthesis_unavailable: invalid_schema"
        assert "DO_NOT_ECHO" not in str(error.value)


def test_model_cannot_supply_urls_or_a_second_key_issues_body() -> None:
    payload = payload_for()
    valid = output_for(payload).model_dump(mode="json")
    valid["events"][0]["url"] = "https://invented.invalid"
    with pytest.raises(ValueError, match="invalid_schema"):
        parse_event_synthesis(json.dumps(valid), payload.plan)
    valid = output_for(payload).model_dump(mode="json")
    valid["sections"]["key_issues"] = "Independent competing prose"
    with pytest.raises(ValueError, match="invalid_schema"):
        parse_event_synthesis(json.dumps(valid), payload.plan)


@pytest.mark.parametrize(
    "body", ["## ② 전일 핵심 이슈\nInjected body", "<!-- investo:block event:x -->"]
)
def test_sections_cannot_inject_owned_headings_or_markers(body: str) -> None:
    payload = payload_for()
    valid = output_for(payload).model_dump(mode="json")
    valid["sections"]["market_summary"] = body
    with pytest.raises(EventNarrativeValidationError, match=r"event\.narrative_invalid"):
        parse_event_synthesis(json.dumps(valid), payload.plan)


def test_zero_events_collection_limits_and_all_removed_have_distinct_messages() -> None:
    empty = EventGenerationPayload(plan=EventSelectionPlan(), narratives=())
    output = parse_event_synthesis(output_for(empty).model_dump_json(), empty.plan)
    assert NO_SELECTED_EVENTS in assemble_event_synthesis(output, empty.plan)
    assert COLLECTION_LIMITED_EVENTS in assemble_event_synthesis(
        output, empty.plan, collection_limited=True
    )
    payload = payload_for()
    removed = render_event_blocks(payload, surviving_event_ids=())
    assert EVENTS_MARKER in removed and NO_SURVIVING_EVENTS in removed
    assert payload.narratives[0].event_id not in removed
    assert event_summary_lines(payload, surviving_event_ids=())[0] == NO_SURVIVING_EVENTS


def test_survivor_filter_is_ordered_and_summary_uses_complete_first_sentence() -> None:
    payload = payload_for(reaction=True)
    narrative = payload.narratives[0]
    expanded = narrative.model_copy(
        update={
            "what_happened": narrative.what_happened + " 공식 발표에서 출시 내용을 확인했습니다."
        }
    )
    payload = payload.model_copy(update={"narratives": (expanded,)})
    assert first_event_sentence(expanded) == narrative.what_happened
    assert event_summary_lines(payload)[:2] == (narrative.what_happened, "주가가 2% 상승했습니다.")
    for bad_ids in ((narrative.event_id, narrative.event_id), ("0" * 24,)):
        with pytest.raises(EventNarrativeValidationError, match=r"event\.selection_mismatch"):
            render_event_blocks(payload, surviving_event_ids=bad_ids)


def test_narrative_is_frozen_and_unavailable_reaction_is_not_no_reaction() -> None:
    payload = payload_for()
    with pytest.raises(ValidationError):
        payload.narratives[0].headline = "Changed"  # type: ignore[misc]
    with pytest.raises(ValidationError):
        EventReaction(text="시장 반응이 없었습니다.", status="unavailable")
    assert REACTION_UNAVAILABLE in render_event_blocks(payload)
    assert "시장 반응이 없었습니다" not in render_event_blocks(payload)


def test_reported_no_reaction_requires_explicit_source_evidence() -> None:
    quiet = payload_for(reaction=True, quiet=True)
    assert "- 시장 반응: 시장 반응은 없었습니다." in render_event_blocks(quiet)
    active = payload_for(reaction=True)
    narrative = active.narratives[0]
    wrong = narrative.reaction.model_copy(
        update={"status": "source_reported_no_reaction", "text": "시장 반응은 없었습니다."}
    )
    with pytest.raises(EventNarrativeValidationError, match=r"event\.evidence_invalid"):
        validate_event_payload(
            active.model_copy(
                update={"narratives": (narrative.model_copy(update={"reaction": wrong}),)}
            )
        )


def test_meaning_source_reported_keeps_its_own_references() -> None:
    payload = payload_for()
    narrative = payload.narratives[0]
    fact = payload.plan.selected[0].change_facts[0]
    reported = EventMeaning(
        text=fact.value_text, mode="source_reported", evidence_refs=(fact.evidence_ref,)
    )
    payload = payload.model_copy(
        update={"narratives": (narrative.model_copy(update={"meaning": reported}),)}
    )
    assert f"- 의미: {fact.value_text}" in render_event_blocks(payload)


def test_body_subheadings_remain_available_in_the_five_legacy_sections() -> None:
    payload = payload_for()
    valid = output_for(payload).model_dump(mode="json")
    valid["sections"]["sector_flow"] = "### 섹터 흐름\n추가 자료는 제한적입니다."
    output = parse_event_synthesis(json.dumps(valid), payload.plan)
    assert "### 섹터 흐름" in assemble_event_synthesis(output, payload.plan)


@pytest.mark.parametrize("field", ["headline", "meaning", "reaction"])
@pytest.mark.parametrize("reversed_values", [False, True])
def test_actual_and_forecast_roles_are_checked_in_every_public_slot(
    field: str, reversed_values: bool
) -> None:
    payload = payload_for("earnings_result", reaction=True)
    narrative = payload.narratives[0]
    actual, forecast = (12, 10) if reversed_values else (10, 12)
    text = f"Acme 실제 매출 {actual}억 달러, 예상 매출 {forecast}억 달러."
    if field == "headline":
        update: dict[str, object] = {field: text}
    elif field == "meaning":
        update = {
            field: EventMeaning(
                text=text, mode="source_reported", evidence_refs=narrative.source_refs
            )
        }
    else:
        update = {
            field: EventReaction(
                text="주가 반응: " + text,
                status="observed",
                evidence_refs=narrative.source_refs,
            )
        }
    changed = payload.model_copy(update={"narratives": (narrative.model_copy(update=update),)})
    if reversed_values:
        with pytest.raises(EventNarrativeValidationError, match=r"event\.fact_unsupported"):
            validate_event_payload(changed)
    else:
        validate_event_payload(changed)


@pytest.mark.parametrize("mutation", ["noncanonical_time", "dict_document"])
def test_unvalidated_model_copies_fail_closed_without_serialization_warnings(mutation: str) -> None:
    payload = payload_for()
    doc = payload.plan.evidence_documents[0]
    changed_doc = (
        doc.model_copy(
            update={
                "event_time": datetime(2026, 9, 21, 12, tzinfo=timezone(timedelta(hours=9))),
                "event_time_basis": "source_exact",
            }
        )
        if mutation == "noncanonical_time"
        else doc.model_dump()
    )
    changed = payload.model_copy(
        update={"plan": payload.plan.model_copy(update={"evidence_documents": (changed_doc,)})}
    )
    with (
        warnings.catch_warnings(record=True) as captured,
        pytest.raises(EventNarrativeValidationError, match=r"event\.narrative_invalid"),
    ):
        render_event_blocks(changed)
    assert captured == []

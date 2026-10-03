"""Synthetic source-fact watchpoints, including terminal tamper controls."""

from __future__ import annotations

from datetime import UTC, date, datetime
from hashlib import sha256

import pytest
from pydantic import TypeAdapter, ValidationError

from investo._internal.event_rendering import EventNarrativeValidationError
from investo.models.event_narratives import EventGenerationPayload, EventMeaning
from investo.models.events import (
    CompanionOutcome,
    EventFact,
    EventKind,
    EventWatchpoint,
    EventWatchpointNextCheck,
    EvidenceRef,
    NumericWatchpoint,
    Watchpoint,
)
from investo.publisher.event_watchpoints import (
    EventWatchpointBuildResult,
    build_event_watchpoints,
    event_watchpoint_ids,
    event_watchpoint_issue_codes,
    render_event_watchpoint,
)
from investo.publisher.reader_format.emphasis import wrap_numbers_bold
from tests.unit.briefing.test_event_narrative import payload_for
from tests.unit.publisher.test_event_blocks import combined_payload


def _build(payload: EventGenerationPayload) -> EventWatchpointBuildResult:
    return build_event_watchpoints(
        payload, surviving_event_ids=tuple(event.event_id for event in payload.plan.selected)
    )


def _markdown(payload: EventGenerationPayload) -> str:
    return (
        "## ⑥ 오늘의 관전 포인트\n\n"
        + "\n\n".join(render_event_watchpoint(card) for card in _build(payload).watchpoints)
        + "\n"
    )


def _scheduled_payload() -> EventGenerationPayload:
    payload = payload_for()
    doc, event, narrative = (
        payload.plan.evidence_documents[0],
        payload.plan.selected[0],
        payload.narratives[0],
    )
    text = "Product A의 다음 지역 서비스는 내달 제공할 예정입니다."
    start = len(doc.summary) + 1
    doc = doc.model_copy(update={"summary": f"{doc.summary} {text}"})
    ref = EvidenceRef(
        document_id=doc.document_id,
        revision_id=doc.revision_id,
        field="summary",
        start=start,
        end=start + len(text),
    )
    fact = EventFact(
        fact_id=sha256(text.encode()).hexdigest(),
        predicate="launch",
        evidence_ref=ref,
        value_text=text,
        status="scheduled",
    )
    event = event.model_copy(
        update={
            "change_facts": (*event.change_facts, fact),
            "evidence_refs": (*event.evidence_refs, ref),
        }
    )
    narrative = narrative.model_copy(
        update={
            "fact_ids": (*narrative.fact_ids, fact.fact_id),
            "source_refs": (*narrative.source_refs, ref),
        }
    )
    return payload.model_copy(
        update={
            "plan": payload.plan.model_copy(
                update={"selected": (event,), "evidence_documents": (doc,)}
            ),
            "narratives": (narrative,),
        }
    )


@pytest.mark.parametrize(
    "kind", ["product_service", "public_statement", "monetary_policy", "earnings_result"]
)
def test_source_fact_and_validated_meaning_own_current(kind: EventKind) -> None:
    payload = payload_for(kind)
    built = _build(payload)
    (card,) = built.watchpoints
    facts = payload.plan.selected[0].change_facts
    fact = next((fact for fact in facts if fact.status == "actual"), facts[0])
    assert built.attempted_count == 1 and built.exclusions == ()
    assert card.kind == "event" and card.fact_id == fact.fact_id
    assert card.observed_state == fact.value_text and card.fact_status == fact.status
    assert card.implication == payload.narratives[0].meaning.text
    assert card.next_check.kind == "observation_template"
    assert "상방" not in render_event_watchpoint(card)
    assert "하방" not in render_event_watchpoint(card)
    assert event_watchpoint_issue_codes(_markdown(payload), payload) == ()


@pytest.mark.parametrize("kind", ["geopolitical", "regulation"])
def test_qualitative_agreement_and_regulation_need_no_numeric_observation(kind: EventKind) -> None:
    payload = payload_for("public_statement")
    event = payload.plan.selected[0].model_copy(update={"event_kind": kind})
    payload = payload.model_copy(
        update={"plan": payload.plan.model_copy(update={"selected": (event,)})}
    )
    (card,) = _build(payload).watchpoints
    assert not any(char.isdigit() for char in card.observed_state)
    assert "공식 결정" in card.next_check.text
    assert "인용 발언" in render_event_watchpoint(card)


def test_same_event_scheduled_fact_is_next_check_never_copied_as_current() -> None:
    payload = _scheduled_payload()
    (card,) = _build(payload).watchpoints
    actual, scheduled = payload.plan.selected[0].change_facts
    assert card.observed_state == actual.value_text
    assert card.next_check.kind == "scheduled_fact"
    assert card.next_check.fact_id == scheduled.fact_id
    assert card.next_check.source_refs == (scheduled.evidence_ref,)
    assert card.next_check.text == scheduled.value_text
    assert f"- 다음 확인: [예정] {scheduled.value_text}" in render_event_watchpoint(card)


def test_announced_multifact_scheduled_state_stays_explicitly_scheduled() -> None:
    payload = _scheduled_payload()
    event = payload.plan.selected[0]
    event = event.model_copy(
        update={
            "change_facts": tuple(
                fact.model_copy(update={"status": "scheduled"}) for fact in event.change_facts
            )
        }
    )
    payload = payload.model_copy(
        update={"plan": payload.plan.model_copy(update={"selected": (event,)})}
    )
    (card,) = _build(payload).watchpoints
    assert card.fact_status == "scheduled"
    assert "- 현재 상태: [예정]" in render_event_watchpoint(card)


@pytest.mark.parametrize("timing", ["scheduled", "background", "unknown"])
def test_standalone_schedule_background_unknown_are_excluded(timing: str) -> None:
    payload = payload_for()
    event = payload.plan.selected[0].model_copy(update={"timing": timing})
    payload = payload.model_copy(
        update={"plan": payload.plan.model_copy(update={"selected": (event,)})}
    )
    built = _build(payload)
    assert built.watchpoints == ()
    assert built.exclusions == ((event.event_id, "unsupported_timing"),)


@pytest.mark.parametrize("status", ["forecast", "scheduled"])
def test_single_future_fact_is_not_a_current(status: str) -> None:
    payload = payload_for()
    event = payload.plan.selected[0]
    event = event.model_copy(
        update={"change_facts": (event.change_facts[0].model_copy(update={"status": status}),)}
    )
    payload = payload.model_copy(
        update={"plan": payload.plan.model_copy(update={"selected": (event,)})}
    )
    assert _build(payload).exclusions == ((event.event_id, "observed_state_unavailable"),)


@pytest.mark.parametrize(
    "changes",
    [
        {"url": None},
        {"source_tier": "unknown"},
        {"source_status": "failed"},
        {"source_status": "unavailable"},
        {"source_name": "미상"},
    ],
)
def test_unavailable_or_unknown_source_does_not_acquire_event_card(
    changes: dict[str, object],
) -> None:
    payload = payload_for()
    doc = payload.plan.evidence_documents[0].model_copy(update=changes)
    payload = payload.model_copy(
        update={"plan": payload.plan.model_copy(update={"evidence_documents": (doc,)})}
    )
    built = _build(payload)
    assert built.watchpoints == ()
    assert built.exclusions[0][1] == "source_unavailable"


def test_unavailable_meaning_excludes_without_inventing_implication() -> None:
    payload = payload_for()
    narrative = payload.narratives[0].model_copy(
        update={"meaning": EventMeaning(text=None, mode="unavailable")}
    )
    payload = payload.model_copy(update={"narratives": (narrative,)})
    assert _build(payload).exclusions == ((narrative.event_id, "meaning_unavailable"),)


@pytest.mark.parametrize("mutation", ["fact", "url", "meaning"])
def test_invalid_payload_hard_finding_is_not_swallowed_as_card_exclusion(mutation: str) -> None:
    payload = payload_for()
    if mutation == "fact":
        event = payload.plan.selected[0]
        fact = event.change_facts[0].model_copy(
            update={"value_text": "Another는 999개 출시했습니다."}
        )
        event = event.model_copy(update={"change_facts": (fact,)})
        payload = payload.model_copy(
            update={"plan": payload.plan.model_copy(update={"selected": (event,)})}
        )
    elif mutation == "url":
        doc = payload.plan.evidence_documents[0].model_copy(update={"url": "javascript:forged"})
        payload = payload.model_copy(
            update={"plan": payload.plan.model_copy(update={"evidence_documents": (doc,)})}
        )
    else:
        narrative = payload.narratives[0]
        narrative = narrative.model_copy(
            update={
                "meaning": narrative.meaning.model_copy(
                    update={"text": "가격이 999% 늘어날 수 있습니다."}
                )
            }
        )
        payload = payload.model_copy(update={"narratives": (narrative,)})
    with pytest.raises(EventNarrativeValidationError):
        _build(payload)
    assert event_watchpoint_issue_codes("## ⑥ 관전 포인트\n", payload)


@pytest.mark.parametrize(
    ("changes", "basis", "text"),
    [
        (
            {
                "event_time": datetime(2026, 9, 20, 12, 30, tzinfo=UTC),
                "event_time_basis": "source_exact",
            },
            "source_exact",
            "사건 기준 2026-09-20 12:30 UTC (출처 시각)",
        ),
        (
            {"event_time": date(2026, 9, 20), "event_time_basis": "source_date"},
            "source_date",
            "사건 기준 2026-09-20 (출처 날짜)",
        ),
        (
            {
                "event_time": None,
                "event_time_basis": "unknown",
                "published_date": date(2026, 9, 19),
            },
            "publication_date",
            "보도 기준 2026-09-19 (출처 날짜); 사건 시점 미확인",
        ),
        (
            {
                "event_time": None,
                "event_time_basis": "unknown",
                "published_date": None,
                "published_at": datetime(2026, 9, 19, 9, 45, tzinfo=UTC),
            },
            "publication_exact",
            "보도 기준 2026-09-19 09:45 UTC (출처 시각); 사건 시점 미확인",
        ),
    ],
)
def test_time_basis_comes_from_fact_document_without_fabricated_precision(
    changes: dict[str, object], basis: str, text: str
) -> None:
    payload = payload_for()
    doc = payload.plan.evidence_documents[0].model_copy(update=changes)
    payload = payload.model_copy(
        update={"plan": payload.plan.model_copy(update={"evidence_documents": (doc,)})}
    )
    (card,) = _build(payload).watchpoints
    assert card.time_basis == basis
    assert text in render_event_watchpoint(card)


def test_removed_survivor_is_excluded_in_original_selection_order() -> None:
    payload = combined_payload("product_service", "public_statement")
    ids = tuple(event.event_id for event in payload.plan.selected)
    built = build_event_watchpoints(payload, surviving_event_ids=ids[1:])
    assert built.attempted_count == 2
    assert tuple(card.event_id for card in built.watchpoints) == ids[1:]
    assert built.exclusions == ((ids[0], "finalization_removed"),)
    assert event_watchpoint_issue_codes(
        _markdown(payload), payload, surviving_event_ids=ids[1:]
    ) == ("event.evidence_invalid",)
    with pytest.raises(EventNarrativeValidationError, match="selection_mismatch"):
        build_event_watchpoints(payload, surviving_event_ids=tuple(reversed(ids)))


@pytest.mark.parametrize(
    ("old", "new", "code"),
    [
        (
            "Product A가 정식 출시됐습니다.",
            "Product A가 999개 출시됐습니다.",
            "event.fact_unsupported",
        ),
        ("#### 관찰 신호: Acme", "#### 관찰 신호: Another", "event.entity_unsupported"),
        ("[official]", "[Reuters]", "event.evidence_invalid"),
        ("https://example.invalid", "https://untrusted.invalid", "event.evidence_invalid"),
        ("2026-09-21 (출처 날짜)", "2026-09-22 (출처 날짜)", "event.evidence_invalid"),
        (
            "공식 서비스 제공 상태와 후속 공지를 확인합니다.",
            "즉시 매수합니다.",
            "event.evidence_invalid",
        ),
        ("수요가 늘어나는 경우", "매출이 999% 늘어나는 경우", "event.evidence_invalid"),
    ],
)
def test_canonical_card_mutations_are_hard_findings(old: str, new: str, code: str) -> None:
    payload = payload_for()
    markdown = _markdown(payload)
    assert old in markdown
    assert code in event_watchpoint_issue_codes(markdown.replace(old, new), payload)


@pytest.mark.parametrize(
    "mutation", ["duplicate", "malformed", "outside", "extra_field", "missing_field", "unknown_id"]
)
def test_marker_and_card_shape_are_validated(mutation: str) -> None:
    payload = payload_for()
    markdown = _markdown(payload)
    card = render_event_watchpoint(_build(payload).watchpoints[0])
    if mutation == "duplicate":
        markdown += "\n" + card
    elif mutation == "malformed":
        markdown = markdown.replace("<!-- /investo:watch", "<!-- investo:watch")
    elif mutation == "outside":
        markdown = markdown.replace("## ⑥", "## ②")
    elif mutation == "extra_field":
        markdown = markdown.replace("- 현재 상태:", "- 임의 주장: 상승 확정\n- 현재 상태:")
    elif mutation == "missing_field":
        markdown = markdown.replace("- 출처:", "- 누락:")
    else:
        markdown = markdown.replace(payload.narratives[0].event_id, "f" * 24)
    assert "event.evidence_invalid" in event_watchpoint_issue_codes(markdown, payload)


def test_numeric_facts_remain_exact_and_emphasis_is_byte_idempotent() -> None:
    payload = payload_for("monetary_policy")
    markdown = _markdown(payload)
    assert "0.25%p" in markdown.replace("**", "")
    assert wrap_numbers_bold(markdown) == markdown
    assert event_watchpoint_issue_codes(markdown, payload) == ()
    assert event_watchpoint_ids(markdown) == (payload.narratives[0].event_id,)
    assert event_watchpoint_issue_codes(markdown.replace("0.25", "9.99"), payload)


@pytest.mark.parametrize("fence", ["```", "~~~"])
def test_card_inside_literal_fence_cannot_claim_visible_survival(fence: str) -> None:
    payload = payload_for()
    card = render_event_watchpoint(_build(payload).watchpoints[0])
    markdown = f"## ⑥ 오늘의 관전 포인트\n\n{fence}\n{card}\n{fence}\n"
    assert event_watchpoint_issue_codes(markdown, payload) == ("event.evidence_invalid",)


def test_inline_marker_cannot_claim_a_separate_owned_card() -> None:
    payload = payload_for()
    markdown = _markdown(payload).replace("<!-- investo:watch", "prefix <!-- investo:watch")
    assert event_watchpoint_issue_codes(markdown, payload) == ("event.evidence_invalid",)


@pytest.mark.parametrize(
    "container",
    [
        "div hidden",
        'script type="text/plain"',
        "pre",
        "template",
        "style",
        "textarea",
        "iframe",
        "details",
        "span hidden",
        "custom-hidden hidden",
    ],
)
def test_card_inside_raw_html_cannot_claim_visible_survival(container: str) -> None:
    payload = payload_for()
    card = render_event_watchpoint(_build(payload).watchpoints[0])
    tag = container.split()[0]
    markdown = f"## ⑥ 오늘의 관전 포인트\n\n<{container}>\n\n{card}\n\n</{tag}>\n"
    assert event_watchpoint_issue_codes(markdown, payload) == ("event.evidence_invalid",)


@pytest.mark.parametrize(
    "sibling",
    [
        "<div hidden>별도 자료</div>",
        '<script type="text/plain">별도 자료</script>',
        "<pre>별도 자료</pre>",
        "<!-- <div hidden> source comment -->",
        "&lt;div hidden&gt; source text",
        "<https://example.invalid/source>",
        '<img src="source.svg" alt="합성 자료">',
        "```html\n<div hidden>\n```",
    ],
)
def test_completed_sibling_html_and_literal_source_text_do_not_hide_a_card(sibling: str) -> None:
    payload = payload_for()
    card = render_event_watchpoint(_build(payload).watchpoints[0])
    markdown = f"## ⑥ 오늘의 관전 포인트\n\n{sibling}\n\n{card}\n"
    assert event_watchpoint_issue_codes(markdown, payload) == ()


def test_source_locator_loss_is_not_recorded_as_event_removal() -> None:
    payload = combined_payload("product_service", "public_statement")
    ids = tuple(event.event_id for event in payload.plan.selected)
    built = build_event_watchpoints(
        payload, surviving_event_ids=ids, source_limited_event_ids=ids[:1]
    )
    assert built.attempted_count == 2
    assert tuple(card.event_id for card in built.watchpoints) == ids[1:]
    assert built.exclusions == ((ids[0], "source_locator_missing"),)


@pytest.mark.parametrize("mutation", ["unknown", "removed", "duplicate"])
def test_source_limited_ids_must_be_distinct_terminal_survivors(mutation: str) -> None:
    payload = combined_payload("product_service", "public_statement")
    ids = tuple(event.event_id for event in payload.plan.selected)
    source_limited = {"unknown": ("f" * 24,), "removed": ids[:1], "duplicate": (ids[1], ids[1])}[
        mutation
    ]
    with pytest.raises(EventNarrativeValidationError, match="selection_mismatch"):
        build_event_watchpoints(
            payload, surviving_event_ids=ids[1:], source_limited_event_ids=source_limited
        )


def test_original_limited_evidence_with_intact_source_still_has_a_card() -> None:
    payload = payload_for()
    event = payload.plan.selected[0].model_copy(update={"evidence_state": "detail_limited"})
    payload = payload.model_copy(
        update={"plan": payload.plan.model_copy(update={"selected": (event,)})}
    )
    built = _build(payload)
    assert tuple(card.event_id for card in built.watchpoints) == (event.event_id,)
    assert built.exclusions == ()


def test_explicit_tagged_union_never_reclassifies_an_unresolved_numeric_row() -> None:
    numeric = NumericWatchpoint(
        signal="ETH",
        source="CoinGecko",
        current="미확인",
        bullish_trigger="상회",
        bearish_trigger="이탈",
        confidence="보통",
        implication="관찰",
    )
    adapter = TypeAdapter(Watchpoint)
    assert isinstance(adapter.validate_python(numeric.model_dump()), NumericWatchpoint)
    with pytest.raises(ValidationError):
        adapter.validate_python({**numeric.model_dump(), "kind": "event"})
    card = _build(payload_for()).watchpoints[0]
    assert isinstance(adapter.validate_python(card.model_dump()), EventWatchpoint)


@pytest.mark.parametrize(
    "values",
    [
        {"numeric_attempted": True},
        {"event_rendered": 1},
        {"numeric_attempted": -1},
        {"event_limitation_reasons": ("",)},
        {"numeric_limitation_reasons": ("same", "same")},
    ],
)
def test_companion_validates_private_accounting(values: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        CompanionOutcome.model_validate(values)


def test_companion_can_record_one_kind_limited_while_another_renders() -> None:
    outcome = CompanionOutcome(
        numeric_attempted=1,
        event_attempted=1,
        event_rendered=1,
        numeric_limitation_reasons=("watchpoint_unavailable",),
    )
    assert outcome.event_rendered == 1 and outcome.numeric_rendered == 0
    with pytest.raises(ValidationError):
        outcome.event_rendered = 0


def test_next_check_template_cannot_claim_fabricated_fact_evidence() -> None:
    with pytest.raises(ValidationError, match="cannot claim"):
        EventWatchpointNextCheck(kind="observation_template", text="확인합니다.", fact_id="a" * 64)


def test_empty_payload_and_result_accounting_are_explicit() -> None:
    payload = EventGenerationPayload(plan={"selected": ()}, narratives=())
    assert _build(payload) == EventWatchpointBuildResult((), 0, ())
    with pytest.raises(ValueError, match="attempts"):
        EventWatchpointBuildResult((), 1, ())

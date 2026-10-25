"""Source assertions and input budgets must retain useful, truthful news."""

import json

import pytest

from investo._internal.event_v3_contract import (
    EventEditionValidationError,
    validate_fact_roles,
    validate_text_actions,
)
from investo._internal.korean_subjects import korean_entity_subjects
from investo.briefing.editorial_plan import build_editorial_plan
from investo.briefing.event_context import (
    ContextEvidenceError,
    build_context_prompt_buffer,
    validate_context_event,
)
from investo.briefing.event_identity import canonical_event_binding
from investo.briefing.event_input import is_event_reference_item
from investo.models.event_context import ContextEventDraft, ContextFactDraft
from investo.models.event_evidence import make_event_context_document, make_evidence_document
from investo.models.items import NormalizedItem
from tests._helpers.event_context_v3 import NOW, document, draft, ref


def text_case(sentence, predicate, action, value, *, status="actual", subject="Acme"):
    doc = make_event_context_document(
        make_evidence_document(
            source_name="official", title=sentence, published_at=NOW, received_at=NOW
        )
    )
    fact = ContextFactDraft(
        predicate=predicate,
        status=status,
        value_kind="text",
        subject_refs=(ref(doc, subject),),
        predicate_refs=(ref(doc, action),),
        value_refs=(ref(doc, value),),
        status_refs=(ref(doc, sentence),),
    )
    event = ContextEventDraft(
        item_ids=(1,),
        event_kind="product_service",
        actor_refs=fact.subject_refs,
        action_refs=fact.predicate_refs,
        object_refs=fact.value_refs,
        relation_refs=fact.value_refs,
        impact_refs=fact.value_refs,
        facts=(fact,),
        timing="announced",
        relation="direct",
        impact="company",
    )
    return doc, event


@pytest.mark.parametrize(
    "sentence,predicate,action,value,subject",
    [
        ("Acme launched Widget", "launch", "launched", "Widget", "Acme"),
        ("Acme signed a supply agreement", "agreement", "signed", "a supply agreement", "Acme"),
        ("Acme approved the merger", "decision", "approved", "the merger", "Acme"),
        ("Acme announced the decision", "statement", "announced", "the decision", "Acme"),
        (
            "Acme today announced Widget\u2019s 2026 agenda.",
            "statement",
            "announced",
            "Widget\u2019s 2026 agenda",
            "Acme",
        ),
        (
            "Acme today announced investors\u2019 2026 agenda.",
            "statement",
            "announced",
            "investors\u2019 2026 agenda",
            "Acme",
        ),
        ("아크메가 신제품을 출시했다", "launch", "출시했다", "신제품", "아크메"),
        ("아크메는 공급계약을 체결했다", "agreement", "체결했다", "공급계약", "아크메"),
        ("아크메가 합병을 승인했다", "decision", "승인했다", "합병", "아크메"),
        ("아크메는 결정을 발표했다", "statement", "발표했다", "결정", "아크메"),
    ],
)
def test_literal_performed_news_keeps_a_canonical_fact(sentence, predicate, action, value, subject):
    doc, event = text_case(sentence, predicate, action, value, subject=subject)
    validate_context_event(event, (doc,), observed_at=NOW)
    binding = canonical_event_binding(event, (doc,), (), observed_at=NOW, baseline_available=False)
    assert len(binding.facts) == 1


@pytest.mark.parametrize(
    "sentence,action",
    [
        ("Acme will launch Widget", "launch"),
        ("Acme never launched Widget", "launched"),
        ("Acme reported that Beta launched Widget", "launched"),
        ("Acme announced it will launch Widget", "launch"),
        ('Acme quoted "Beta launched Widget"', "launched"),
        ("Acme launched Widget if approval comes", "launched"),
    ],
)
def test_nonperformed_or_other_actor_action_cannot_become_actual(sentence, action):
    doc, event = text_case(sentence, "launch", action, "Widget")
    for validate in (
        lambda: validate_context_event(event, (doc,), observed_at=NOW),
        lambda: canonical_event_binding(
            event, (doc,), (), observed_at=NOW, baseline_available=False
        ),
    ):
        with pytest.raises((ContextEvidenceError, ValueError)):
            validate()


def test_news_gets_real_byte_budget_after_mandatory_facts_before_optional_calendar():
    docs = tuple(document(str(i), detail="설명 근거 " * 250) for i in range(30))
    preferred = frozenset({21, 25, 29})
    buffer = build_context_prompt_buffer(
        docs, required_item_ids=frozenset({1, 2}), preferred_item_ids=preferred
    )
    assert buffer.item_ids[:5] == (1, 2, 21, 25, 29)
    assert len(buffer.text.encode()) <= 24 * 1024
    assert buffer.required_prompt_item_ids == frozenset({1, 2})
    assert [r["item_id"] for r in json.loads(buffer.text)["documents"]] == list(
        range(1, len(buffer.documents) + 1)
    )
    with pytest.raises(ContextEvidenceError):
        build_context_prompt_buffer(docs, preferred_item_ids=frozenset({31}))


@pytest.mark.parametrize(
    "text",
    [
        "Widget launched Acme",
        "Acme did not launch Widget",
        "Acme will launch Widget",
        "Acme가 Widget을 출시할 예정입니다",
        "Acme가 Widget을 출시하지 않았습니다",
        "Acme가 Widget을 인수했습니다",
    ],
)
def test_text_fact_final_display_cannot_swap_actor_action_or_modality(text):
    doc, event = text_case("Acme launched Widget", "launch", "launched", "Widget")
    binding = canonical_event_binding(event, (doc,), (), observed_at=NOW, baseline_available=False)
    with pytest.raises(EventEditionValidationError):
        validate_fact_roles(text, binding, event, (doc,), require_assertion=True)


@pytest.mark.parametrize("text", ["Acme launched Widget", "Acme가 Widget을 출시했습니다"])
def test_text_fact_final_display_can_translate_only_the_bound_predicate(text):
    doc, event = text_case("Acme launched Widget", "launch", "launched", "Widget")
    binding = canonical_event_binding(event, (doc,), (), observed_at=NOW, baseline_available=False)
    validate_fact_roles(text, binding, event, (doc,), require_assertion=True)


@pytest.mark.parametrize(
    "sentence,subject,action,value",
    [
        ("Acme Reported Beta launched Widget", "Acme Reported Beta", "launched", "Widget"),
        ("Acme Said Beta launched Widget", "Acme Said Beta", "launched", "Widget"),
        ("Acme launched 1200", "Acme", "launched", "1200"),
        ("Acme announced 2026 USD of revenue", "Acme", "announced", "2026 USD of revenue"),
        ("Acme announced 2026", "Acme", "announced", "2026"),
        ("Acme announced 2026 shares", "Acme", "announced", "2026 shares"),
        ("Acme announced 2026 JPY", "Acme", "announced", "2026 JPY"),
        ("Acme announced EPS 2026", "Acme", "announced", "EPS 2026"),
        ("Acme announced 2026 KWD", "Acme", "announced", "2026 KWD"),
        (
            "Acme announced 2026 conference attendees",
            "Acme",
            "announced",
            "2026 conference attendees",
        ),
        ("Acme announced 2026 forum users", "Acme", "announced", "2026 forum users"),
    ],
)
def test_reporting_subject_absorption_and_numeric_as_text_are_rejected(
    sentence, subject, action, value
):
    predicate = "statement" if action == "announced" else "launch"
    doc, event = text_case(sentence, predicate, action, value, subject=subject)
    with pytest.raises(ContextEvidenceError):
        validate_context_event(event, (doc,), observed_at=NOW)


@pytest.mark.parametrize("sentence", ["Acme reported Widget", "Acme actual Widget"])
def test_status_marker_alone_cannot_invent_a_launch_predicate(sentence):
    doc, event = text_case(sentence, "launch", sentence.split()[1], "Widget")
    event = event.model_copy(
        update={"facts": (event.facts[0].model_copy(update={"predicate_refs": ()}),)}
    )
    with pytest.raises(ContextEvidenceError):
        validate_context_event(event, (doc,), observed_at=NOW)


@pytest.mark.parametrize(
    "predicate,source_action,wrong_action",
    [
        ("status_change", "cancelled", "completed"),
        ("status_change", "completed", "resumed"),
        ("result", "increased", "decreased"),
        ("launch", "unveiled", "launched"),
    ],
)
def test_same_predicate_does_not_license_an_opposite_or_different_action(
    predicate, source_action, wrong_action
):
    doc, event = text_case(f"Acme {source_action} Widget", predicate, source_action, "Widget")
    binding = canonical_event_binding(event, (doc,), (), observed_at=NOW, baseline_available=False)
    with pytest.raises(EventEditionValidationError):
        validate_fact_roles(
            f"Acme {wrong_action} Widget", binding, event, (doc,), require_assertion=True
        )


def test_optional_text_surface_cannot_invent_a_known_action():
    doc, event = text_case("Acme launched Widget", "launch", "launched", "Widget")
    with pytest.raises(EventEditionValidationError):
        validate_text_actions("Acme가 Widget을 취소했습니다", event, (doc,))


def test_opposite_text_actions_change_fact_identity_in_the_same_slot():
    from investo._internal.event_text_proof import canonical_text_action

    facts = []
    for action in ("cancelled", "completed"):
        doc, event = text_case(f"Acme {action} Widget", "status_change", action, "Widget")
        binding = canonical_event_binding(
            event, (doc,), (), observed_at=NOW, baseline_available=False
        )
        facts.append(binding.facts[0])
        assert canonical_text_action(facts[-1].canonical.value) == action
        assert facts[-1].original_value == "Widget"
    assert facts[0].canonical.slot_key_hash == facts[1].canonical.slot_key_hash
    assert facts[0].fact_id != facts[1].fact_id


@pytest.mark.parametrize("action", ["completed", "completes", "완료했다", "완료했습니다"])
def test_story_action_decoder_normalizes_closed_equivalent_source_values(action):
    from investo._internal.event_text_proof import canonical_text_action

    assert canonical_text_action(action) == "completed"


def test_numeric_result_does_not_prove_a_directional_change():
    from tests._helpers.event_document_v3 import native_case

    _, edition = native_case()
    with pytest.raises(EventEditionValidationError):
        validate_fact_roles(
            "Acme의 Widget FY2026 실제 revenue 1200 USD가 감소했습니다.",
            edition.bindings[0],
            edition.editorial_plan.events[0].source_event,
            edition.documents,
            require_assertion=True,
        )


def test_korean_topic_and_modifier_grammar_does_not_license_new_company_names():
    assert not tuple(
        korean_entity_subjects(
            "데이터는 정보를 제공하는 자료입니다. 계약은 제품을 설명하는 근거입니다."
        )
    )
    assert tuple(korean_entity_subjects("미확인회사는 출시했다")) == ("미확인회사",)
    assert tuple(korean_entity_subjects("정보테크는 발표했다")) == ("정보테크",)


def test_observed_series_is_not_a_source_confirmed_new_release():
    item = NormalizedItem(
        source_name="fred-macro",
        category="macro",
        title="Old output",
        published_at=NOW,
        raw_metadata={"series_id": "OLD", "release_date": "2026-08-01"},
    )
    assert is_event_reference_item(item)
    assert not is_event_reference_item(
        item.model_copy(
            update={
                "raw_metadata": {
                    "macro_event_key": "output:2026-10",
                    "macro_event_status": "actual",
                    "macro_priority": "P0",
                }
            }
        )
    )


def test_required_recurring_observation_stays_visible_in_reference_panel():
    doc = document()
    event = draft(doc)
    binding = canonical_event_binding(event, (doc,), (), observed_at=NOW, baseline_available=False)
    plan, selected, _ = build_editorial_plan(
        (event,),
        (binding,),
        (doc,),
        required_item_ids=frozenset({1}),
        reference_item_ids=frozenset({1}),
        observed_at=NOW,
    )
    assert plan.events[0].placement == "reference"
    assert selected[0].facts == binding.facts

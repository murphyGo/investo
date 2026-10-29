"""Permission receipts retain their purpose without proving its execution."""

import pytest

from investo._internal.event_context import (
    ContextEvidenceError,
    text_fact_frame,
    validate_context_fact,
)
from investo._internal.event_text_proof import assertion_span_hints, display_matches_frame
from investo.models.event_context import ContextFactDraft, ContextRef
from investo.models.event_evidence import make_event_context_document, make_evidence_document
from tests._helpers.event_context_v3 import NOW


def source_fact(text, *, selected_assertion=None):
    document = make_event_context_document(
        make_evidence_document(
            source_name="synthetic-official",
            title="Approval notice",
            summary=text,
            published_at=NOW,
            received_at=NOW,
        )
    )
    chunk = next(c for c in document.chunks if c.role == "fact")
    selected = selected_assertion or chunk.text
    hint = assertion_span_hints(selected)[0]
    offset = chunk.text.index(selected)

    def reference(key):
        start, end = hint[key]
        return ContextRef(
            document_id=document.document_id,
            revision_id=document.revision_id,
            chunk_id=chunk.chunk_id,
            start=start + offset,
            end=end + offset,
        )

    fact = ContextFactDraft(
        predicate=hint["predicate"],
        status=hint["status"],
        value_kind="text",
        subject_refs=(reference("subject"),),
        predicate_refs=(reference("action"),),
        value_refs=(reference("value"),),
        status_refs=(reference("assertion"),),
    )
    lookup = {(document.document_id, document.revision_id): document}
    validate_context_fact(fact, lookup)
    return fact, lookup


def test_source_domain_name_survives_hint_and_runtime_clause_boundaries():
    fact, lookup = source_fact("Acme.com launches Widget.")
    frame = text_fact_frame(fact, lookup)
    assert frame.subject == "Acme.com"
    assert frame.value == "Widget"
    assert frame.status == "actual"


@pytest.mark.parametrize("verb", ["gained", "gains", "received", "receives"])
def test_approval_receipt_is_actual_but_future_services_are_not_performed(verb):
    text = (
        f"Acme.com {verb} final ABC approval to launch Widget "
        "and bring Token under federal oversight."
    )
    fact, lookup = source_fact(text)
    frame = text_fact_frame(fact, lookup)
    assert frame.predicate == "status_change" and frame.status == "actual"
    assert (
        frame.value == "final ABC approval to launch Widget and bring Token under federal oversight"
    )
    assert display_matches_frame(text, frame)
    assert not display_matches_frame("Acme.com launched Widget.", frame)
    # Selecting a subordinate launch cannot turn permission into execution.
    chunk = next(iter(lookup.values())).chunks[1]
    start = chunk.text.index("launch")
    changed = fact.model_copy(
        update={
            "predicate": "launch",
            "predicate_refs": (
                fact.predicate_refs[0].model_copy(update={"start": start, "end": start + 6}),
            ),
        }
    )
    with pytest.raises(ContextEvidenceError, match="status_unbound"):
        validate_context_fact(changed, lookup)


@pytest.mark.parametrize("modal", ["will", "plans to", "expects to"])
def test_forecast_receipt_cannot_be_promoted_to_actual(modal):
    fact, lookup = source_fact(f"Acme.com {modal} receive final ABC approval to launch Widget.")
    assert fact.status == "forecast"
    with pytest.raises(ContextEvidenceError):
        validate_context_fact(fact.model_copy(update={"status": "actual"}), lookup)


@pytest.mark.parametrize(
    "text",
    [
        "Acme.com did not receive final ABC approval to launch Widget.",
        "Acme.com gains pending ABC approval to launch Widget.",
        "Acme.com receives approval to launch Widget and Beta launches Other.",
        "Acme.com receives approval to launch Widget and released Other.",
        "Acme.com receives approval to launch Widget and defraud customers.",
        "Acme.com received 1200 USD in revenue.",
        "Acme.com receives approval to launch Widget?",
        'Acme.com said "Beta gains approval to launch Widget".',
    ],
)
def test_unproved_conditions_nested_actions_and_numeric_facts_are_not_receipts(text):
    assert not assertion_span_hints(text)


@pytest.mark.parametrize(
    "prefix",
    [
        "According to unverified rumors;\n",
        "Beta said:\n",
        "If approval is granted under the regulator procedure described in this briefing "
        "and the remaining operational requirements discussed by the parties "
        "have been satisfied;\n",
        "It is false that\n",
    ],
)
def test_receipt_cannot_drop_qualifiers_across_lines_or_semicolons(prefix):
    assertion = "Acme receives approval to launch Widget."
    text = prefix + assertion
    assert not assertion_span_hints(text)
    # A model can select an exact inner span without relying on our hints.
    # Runtime validation must still inspect the complete enclosing sentence.
    with pytest.raises(ContextEvidenceError):
        source_fact(text, selected_assertion=assertion)

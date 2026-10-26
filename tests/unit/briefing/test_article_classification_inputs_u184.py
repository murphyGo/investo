"""Real classification failure modes: clipped clauses and observed-series news."""

import json

import pytest

from investo._internal.event_context import (
    ContextEvidenceError,
    build_context_prompt_buffer,
    validate_context_fact,
)
from investo._internal.event_text_proof import assertion_span_hints
from investo.briefing.event_input import is_article_reference_item, is_event_reference_item
from investo.models import NormalizedItem
from investo.models.event_context import ContextFactDraft, ContextRef
from investo.models.event_evidence import make_event_context_document, make_evidence_document
from tests._helpers.event_context_v3 import NOW


def test_hint_proves_complete_unicode_source_clause_and_clipped_value_still_fails():
    summary = "안내. The Acme Commission today announced Widget\u2019s 2027 examination priorities."
    doc = make_event_context_document(
        make_evidence_document(
            source_name="official",
            title="Notice",
            summary=summary,
            published_at=NOW,
            received_at=NOW,
        ),
        article_passages=True,
    )
    chunk = next(c for c in doc.chunks if c.role == "fact")
    hint = assertion_span_hints(chunk.text)[0]

    def reference(field):
        start, end = hint[field]
        return ContextRef(
            document_id=doc.document_id,
            revision_id=doc.revision_id,
            chunk_id=chunk.chunk_id,
            start=start,
            end=end,
        )

    assert chunk.text[reference("value").start : reference("value").end].endswith("priorities")
    assert reference("assertion").start == len("안내. ")
    fact = ContextFactDraft(
        predicate=hint["predicate"],
        status=hint["status"],
        value_kind="text",
        subject_refs=(reference("subject"),),
        predicate_refs=(reference("action"),),
        value_refs=(reference("value"),),
        status_refs=(reference("assertion"),),
    )
    validate_context_fact(fact, {(doc.document_id, doc.revision_id): doc})
    value = reference("value")
    broken = fact.model_copy(
        update={"value_refs": (value.model_copy(update={"end": value.end - 1}),)}
    )
    with pytest.raises(ContextEvidenceError, match="status_unbound"):
        validate_context_fact(broken, {(doc.document_id, doc.revision_id): doc})


@pytest.mark.parametrize(
    "text",
    [
        "Acme did not announce Widget.",
        "Acme announced that OtherCo launched Widget.",
        "Acme announced revenue of 1200 USD.",
        "Acme proposed to launch Widget.",
        "Acme launched Widget?",
        "Acme announced Widget\uff1f",
    ],
)
def test_hints_do_not_license_unsupported_status_grammar_or_financial_text(text):
    assert not assertion_span_hints(text)


@pytest.mark.parametrize(
    "text",
    [
        "가람전자가 새서비스를 출시했다.",
        "Acme가 Widget을 출시했습니다.",
        "가람위원회가 새규정을 발표했다.",
        "가람전자 이사회가 새규정을 발표했다.",
    ],
)
def test_korean_actual_frames_retain_exact_subject_action_and_value_coordinates(text):
    hint = assertion_span_hints(text)[0]
    from investo._internal.event_text_proof import prove_text_assertion

    def literal(key):
        return text[slice(*hint[key])]

    assert (
        prove_text_assertion(
            predicate=hint["predicate"],
            status=hint["status"],
            subject=literal("subject"),
            action=literal("action"),
            value=literal("value"),
            assertion=literal("assertion"),
            object_label="",
            status_proofs=(literal("assertion"),),
        )
        is not None
    )


@pytest.mark.parametrize(
    "text",
    [
        "가람전자가 새서비스를 출시할 예정이다.",
        "가람전자가 새서비스를 출시하지 않았다.",
        "가람위원회가 1200 USD 매출을 발표했다.",
    ],
)
def test_korean_future_negation_and_financial_text_get_no_actual_hint(text):
    assert not assertion_span_hints(text)


@pytest.mark.parametrize(
    "text",
    [
        "가람페이 증권이 새앱을 출시했다.",
        "하이 증권이 새상품을 공개했다.",
    ],
)
def test_ambiguous_multiword_korean_actor_never_gets_a_truncated_hint(text):
    assert not assertion_span_hints(text)


@pytest.mark.parametrize("modal", ["will", "plans to", "expects to"])
def test_supported_future_frame_retains_forecast_instead_of_an_actual_hint(modal):
    text = f"Acme {modal} announce Widget."
    hints = assertion_span_hints(text)
    assert hints and all(hint["status"] == "forecast" for hint in hints)


def test_hint_bytes_are_accounted_and_legacy_buffer_shape_is_unchanged():
    doc = make_event_context_document(
        make_evidence_document(
            source_name="official",
            title="Acme announced Widget",
            published_at=NOW,
            received_at=NOW,
        )
    )
    old = build_context_prompt_buffer((doc,))
    assert "assertion_hints" not in json.loads(old.text)["documents"][0]
    new = build_context_prompt_buffer((doc,), assertion_hints=True)
    assert json.loads(new.text)["documents"][0]["assertion_hints"]
    assert len(new.text.encode()) > len(old.text.encode())
    with pytest.raises(ContextEvidenceError, match="budget_exhausted"):
        build_context_prompt_buffer(
            (doc,),
            assertion_hints=True,
            max_bytes=len(old.text.encode()),
            required_item_ids=frozenset({1}),
        )


@pytest.mark.parametrize("source", ["bls-macro-actuals", "bea-macro-actuals"])
def test_observed_actual_is_reference_but_required_and_source_dated_actual_are_protected(source):
    item = NormalizedItem(
        source_name=source,
        category="macro",
        title="Observed series",
        published_at=NOW,
        raw_metadata={
            "macro_event_key": "series:2026-09",
            "macro_event_status": "actual",
            "macro_priority": "P1",
            "observed_at": NOW.isoformat(),
        },
    )
    assert not is_event_reference_item(item)  # role_v1 compatibility
    assert is_article_reference_item(item)
    required = item.model_copy(
        update={"raw_metadata": {**item.raw_metadata, "macro_priority": "P0"}}
    )
    assert not is_article_reference_item(required)
    dated = item.model_copy(
        update={
            "raw_metadata": {
                **item.raw_metadata,
                "published_at_precision": "date",
                "published_date": "2026-10-10",
                "event_time_basis": "source_date",
                "event_date": "2026-10-10",
            }
        }
    )
    assert not is_article_reference_item(dated)


def test_saturated_candidates_reserve_real_news_and_required_actual_before_observations():
    from datetime import timedelta

    from investo.briefing.event_input import select_event_input_items

    items = [
        NormalizedItem(
            source_name=source,
            category="macro",
            title=f"Observed series {index}",
            published_at=NOW,
            url=f"https://example.com/{source}/{index}",
            raw_metadata={
                "macro_event_key": f"series:{index}",
                "macro_event_status": "actual",
                "macro_priority": "P1",
                "observed_at": NOW.isoformat(),
            },
        )
        for source in ("bea-macro-actuals", "bls-macro-actuals")
        for index in range(12)
    ]
    items.extend(
        NormalizedItem(
            source_name=source,
            category="news",
            title=f"Acme announced Widget {index}",
            published_at=NOW,
            url=f"https://example.com/{source}/{index}",
        )
        for source in ("a-news", "b-news", "c-news")
        for index in range(24)
    )
    official = NormalizedItem(
        source_name="fomc-rss",
        category="calendar",
        title="Federal Reserve issues statement",
        published_at=NOW - timedelta(days=1),
        url="https://example.com/monetary-policy",
    )
    required = NormalizedItem(
        source_name="required-release",
        category="macro",
        title="Required actual",
        published_at=NOW,
        raw_metadata={
            "macro_event_key": "required:actual",
            "macro_event_status": "actual",
            "macro_priority": "P0",
        },
    )
    items.extend((official, required))
    assert official not in select_event_input_items(items, target_date=NOW.date())
    selected = select_event_input_items(items, target_date=NOW.date(), article_v2=True)
    assert len(selected) <= 96
    assert official in selected and required in selected
    assert {"a-news", "b-news", "c-news", "fomc-rss"} <= {i.source_name for i in selected}

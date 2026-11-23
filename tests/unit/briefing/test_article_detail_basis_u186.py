"""Core-only source facts remain briefs even if a verifier calls them detailed."""

import json

import pytest
from pydantic import ValidationError

from investo._internal.event_article_packet import build_article_packets
from investo.briefing.editorial_plan import build_editorial_plan
from investo.briefing.event_identity import canonical_event_binding
from investo.models.event_article import EventEvidencePacket
from investo.models.event_context import ContextEventDraft, ContextFactDraft
from investo.models.event_evidence import make_event_context_document, make_evidence_document
from tests._helpers.event_context_v3 import NOW, ref


def packet_case(*, context="", body="", bind_context=False, impact="company"):
    core = "Acme launched Widget."
    doc = make_event_context_document(
        make_evidence_document(
            source_name="official",
            title=core,
            summary=core + context,
            detail_excerpt=body,
            published_at=NOW,
            received_at=NOW,
        ),
        article_passages=True,
    )
    event = ContextEventDraft(
        item_ids=(1,),
        event_kind="product_service",
        actor_refs=(ref(doc, "Acme"),),
        action_refs=(ref(doc, "launched"),),
        object_refs=(ref(doc, "Widget"),),
        facts=(
            ContextFactDraft(
                predicate="launch",
                status="actual",
                value_kind="text",
                subject_refs=(ref(doc, "Acme"),),
                predicate_refs=(ref(doc, "launched"),),
                value_refs=(ref(doc, "Widget"),),
                status_refs=(ref(doc, core),),
            ),
        ),
        meaning_refs=(ref(doc, context.strip()),) if bind_context else (),
        timing="announced",
        relation="direct",
        impact=impact,
    )
    binding = canonical_event_binding(event, (doc,), (), observed_at=NOW, baseline_available=False)
    plan, bindings, _ = build_editorial_plan((event,), (binding,), (doc,), observed_at=NOW)
    return build_article_packets(plan, bindings, (doc,))[0]


def test_single_text_action_cannot_be_a_detailed_positive():
    packet = packet_case()
    assert packet.detail_basis == "core_only"
    assert not packet.expected_detail
    assert not next(q for q in packet.questions if q.question_id == "why").required
    assert packet.required_fact_ids and packet.passages


def test_repeating_the_core_as_body_does_not_supply_explanation():
    packet = packet_case(body="Acme launched Widget.")
    assert packet.detail_basis == "core_only" and not packet.expected_detail


def test_longer_summary_without_allocated_explanation_does_not_promote():
    packet = packet_case(context=" Widget is named in the announcement." * 10)
    assert packet.detail_basis == "core_only" and not packet.expected_detail


def test_summary_with_bound_scope_keeps_detail_eligibility():
    packet = packet_case(context=" Widget serves existing subscribers.", bind_context=True)
    assert packet.detail_basis == "source_context" and packet.expected_detail
    assert all(p.source_locator.startswith("summary:") for p in packet.passages)


def test_distinct_source_body_keeps_detail_eligibility():
    packet = packet_case(body="Widget serves existing subscribers.")
    assert packet.detail_basis == "source_context" and packet.expected_detail


def test_context_impact_is_still_only_a_brief():
    from tests._helpers.event_article_v2 import article_case

    _, draft, _, _ = article_case(impact="context")
    packet = draft.article_readiness[0].packet
    assert packet.detail_basis == "context_only" and not packet.expected_detail


def test_explicit_brief_basis_cannot_claim_expected_detail():
    packet = packet_case()
    with pytest.raises(ValidationError, match="detail_basis_mismatch"):
        EventEvidencePacket.model_validate({**packet.model_dump(), "expected_detail": True})


def test_legacy_packet_serialization_and_hash_stay_readable():
    packet = packet_case()
    old = {k: v for k, v in packet.model_dump(mode="json").items() if k != "detail_basis"}
    decoded = EventEvidencePacket.model_validate(old)
    assert decoded.detail_basis == "legacy_impact"
    assert json.loads(decoded.model_dump_json()) == old


def test_legacy_basis_cannot_override_reconstructed_terminal_packet():
    from investo._internal.event_article import validate_terminal_articles
    from investo.models.event_article import ArticleReadiness
    from tests._helpers.event_article_v2 import article_case

    _, draft, _, _ = article_case()
    ready = draft.article_readiness[0]
    packet = ready.packet.model_copy(update={"detail_basis": "legacy_impact"})
    composition = ready.composition.model_copy(update={"packet_hash": packet.packet_hash})
    review = ready.review.model_copy(
        update={
            "packet_hash": packet.packet_hash,
            "draft_hash": composition.draft_hash,
        }
    )
    forged = ArticleReadiness(
        composition=composition,
        packet=packet,
        review=review,
        policy_hash=ready.policy_hash,
        state=ready.state,
    )
    with pytest.raises(ValueError, match="packet_mismatch"):
        validate_terminal_articles(
            draft.model_copy(update={"article_readiness": (forged,)}),
            observed_at=NOW,
        )

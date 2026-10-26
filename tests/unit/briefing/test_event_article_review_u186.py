"""Semantic verdicts cannot weaken original hard numeric or ownership checks."""

from datetime import timedelta

import pytest

from investo._internal.event_article import review_gaps, validate_composition
from investo.models.event_article import SentenceClaim
from investo.models.event_context import ReactionContext
from tests._helpers.event_article_v2 import article_case
from tests._helpers.event_context_v3 import NOW


@pytest.mark.parametrize("kind", ["fact", "attributed_explanation", "conditional_analysis"])
def test_numeric_actual_cannot_be_laundered_through_claim_kind(kind):
    _, draft, composition, _ = article_case()
    claim = composition.claims[0]
    updates = {"kind": kind}
    if kind == "attributed_explanation":
        updates["attributed_actor_ref"] = claim.source_refs[0]
    if kind == "conditional_analysis":
        updates.update(mechanism_refs=claim.source_refs[:1], assumption_refs=claim.source_refs[:1])
    claim = SentenceClaim.model_validate({**claim.model_dump(), **updates})
    lead = composition.narrative.sentences[0].model_copy(
        update={"text": "Acme는 Widget의 FY2026 예상 revenue 1200 USD라고 설명했습니다."}
    )
    blocks = (
        composition.narrative.blocks[0].model_copy(update={"sentences": (lead,)}),
        *composition.narrative.blocks[1:],
    )
    altered = composition.model_copy(
        update={
            "claims": (claim, *composition.claims[1:]),
            "narrative": composition.narrative.model_copy(update={"blocks": blocks}),
        }
    )
    with pytest.raises(ValueError, match="fact_unsupported"):
        validate_composition(altered, draft.article_readiness[0].packet, draft, observed_at=NOW)


def test_fact_refs_are_required_even_for_source_explanation():
    _, draft, composition, _ = article_case()
    claim = composition.claims[0].model_copy(
        update={
            "kind": "attributed_explanation",
            "source_refs": composition.claims[0].source_refs[:1],
            "attributed_actor_ref": composition.claims[0].source_refs[0],
        }
    )
    altered = composition.model_copy(update={"claims": (claim, *composition.claims[1:])})
    with pytest.raises(ValueError, match="fact_proof_missing"):
        validate_composition(altered, draft.article_readiness[0].packet, draft, observed_at=NOW)


@pytest.mark.parametrize("organization", [None, "물가테크", "인플레이션은행"])
def test_translated_financial_concepts_are_not_new_organization_aliases(organization):
    _, draft, composition, _ = article_case(
        detail=(
            "Acme explained that inflation remains elevated, productivity is strong "
            "and the unemployment rate has changed little."
        )
    )
    text = (
        "Acme는 인플레이션이 여전히 높고 생산성은 강하며 "
        "실업률에는 변화가 거의 없다고 설명했습니다."
    )
    if organization:
        text = f"Acme는 {organization}가 Widget을 출시했다고 설명했습니다."
    sentence = composition.narrative.sentences[1].model_copy(update={"text": text})
    changed = composition.model_copy(
        update={
            "narrative": composition.narrative.model_copy(
                update={
                    "blocks": (
                        composition.narrative.blocks[0],
                        composition.narrative.blocks[1].model_copy(
                            update={"sentences": (sentence,)}
                        ),
                    ),
                }
            )
        }
    )
    if organization:
        with pytest.raises(ValueError, match="entity_unsupported"):
            validate_composition(changed, draft.article_readiness[0].packet, draft, observed_at=NOW)
    else:
        validate_composition(changed, draft.article_readiness[0].packet, draft, observed_at=NOW)


def test_invented_observation_asset_time_and_values_are_not_source_proof():
    _, draft, composition, _ = article_case()
    claim = composition.claims[0]
    reference = claim.source_refs[0]
    text = "Acme가 관측됐으며 인과관계는 확인되지 않았습니다."
    observation = ReactionContext(
        status="observed",
        attribution="coincidence_only",
        asset_id="InventedAsset",
        window_start=NOW + timedelta(days=1),
        window_end=NOW + timedelta(days=1),
        observed_at=NOW + timedelta(days=1),
        baseline_ref=reference,
        value_ref=reference,
        text=text,
        refs=(reference,),
    )
    altered_claim = claim.model_copy(update={"kind": "observation", "observation": observation})
    altered = composition.model_copy(update={"claims": (altered_claim, *composition.claims[1:])})
    # Even with a future received clock, the fixed observation clock is authority.
    docs = tuple(
        doc.model_copy(
            update={
                "time": doc.time.model_copy(
                    update={
                        "received_at": doc.time.received_at.model_copy(
                            update={"value": NOW + timedelta(days=2)}
                        )
                    }
                )
            }
        )
        for doc in draft.documents
    )
    draft = draft.model_copy(update={"documents": docs})
    with pytest.raises(ValueError, match="observation_unbound"):
        validate_composition(altered, draft.article_readiness[0].packet, draft, observed_at=NOW)


@pytest.mark.parametrize("mutation", ["hash", "missing_claim", "foreign_ref", "missing_question"])
def test_review_must_cover_exact_hash_ids_and_evidence(mutation):
    _, draft, composition, review = article_case()
    if mutation == "hash":
        review = review.model_copy(update={"draft_hash": "0" * 64})
    elif mutation == "missing_claim":
        review = review.model_copy(update={"claims": review.claims[:1]})
    elif mutation == "missing_question":
        review = review.model_copy(update={"questions": review.questions[:1]})
    else:
        foreign = review.claims[0].source_refs[0].model_copy(update={"document_id": "0" * 64})
        review = review.model_copy(
            update={
                "claims": (
                    review.claims[0].model_copy(update={"source_refs": (foreign,)}),
                    *review.claims[1:],
                )
            }
        )
    with pytest.raises(ValueError):
        review_gaps(composition, draft.article_readiness[0].packet, review)


def test_valid_observation_is_bound_to_exact_source_values_and_fixed_clock():
    from investo.models.event_context import ContextRef

    detail = (
        "Acme explained that Widget revenue reflects expanded service access.\n"
        "BTC 100 USD at 2026-10-10T10:00:00Z; BTC 120 USD at 2026-10-10T11:00:00Z. "
        "Observed 2026-10-10T11:01:00Z."
    )
    _, draft, composition, _ = article_case(detail=detail)
    doc = draft.documents[0]
    chunk = next(c for c in doc.chunks if "BTC 100" in c.text)

    def number_ref(value):
        start = chunk.text.index(value + " USD")
        return ContextRef(
            document_id=doc.document_id,
            revision_id=doc.revision_id,
            chunk_id=chunk.chunk_id,
            start=start,
            end=start + len(value),
        )

    baseline = number_ref("100")
    value = number_ref("120")
    packet = draft.article_readiness[0].packet
    refs = tuple(r for r in packet.allowed_refs if r.chunk_id == chunk.chunk_id)
    text = "BTC는 100 USD에서 120 USD로 관측됐으며 인과관계는 확인되지 않았습니다."
    from datetime import datetime

    observation = ReactionContext(
        status="observed",
        attribution="coincidence_only",
        asset_id="BTC",
        window_start=datetime.fromisoformat("2026-10-10T10:00:00+00:00"),
        window_end=datetime.fromisoformat("2026-10-10T11:00:00+00:00"),
        observed_at=datetime.fromisoformat("2026-10-10T11:01:00+00:00"),
        baseline_ref=baseline,
        value_ref=value,
        text=text,
        refs=refs,
    )
    observed = SentenceClaim(
        claim_id="observed", kind="observation", source_refs=refs, observation=observation
    )
    from investo.models.event_article import NarrativeBlock, NarrativeSentence

    sentence = NarrativeSentence(sentence_id="price", text=text, claim_ids=("observed",))
    changed = composition.model_copy(
        update={
            "claims": (*composition.claims, observed),
            "narrative": composition.narrative.model_copy(
                update={
                    "blocks": (*composition.narrative.blocks, NarrativeBlock(sentences=(sentence,)))
                }
            ),
        }
    )
    validate_composition(changed, packet, draft, observed_at=NOW)
    truncated = value.model_copy(update={"end": value.end - 1})
    bad_observation = observation.model_copy(
        update={"value_ref": truncated, "refs": (*refs, truncated)}
    )
    bad = changed.model_copy(
        update={
            "claims": (
                *composition.claims,
                observed.model_copy(
                    update={"source_refs": (*refs, truncated), "observation": bad_observation}
                ),
            )
        }
    )
    with pytest.raises(ValueError):
        validate_composition(bad, packet, draft, observed_at=NOW)


def test_article_activation_does_not_inherit_role_profile_acceptance(monkeypatch):
    from investo.models.event_config import EventExecutionConfig

    monkeypatch.setattr("investo.models.event_config.EVENT_V3_ACTIVE_READY", True)
    with pytest.raises(ValueError, match="profile acceptance"):
        EventExecutionConfig(
            mode="active", document_schema=3, active_segments=("us-equity",), profile="article_v2"
        ).validate_capabilities()

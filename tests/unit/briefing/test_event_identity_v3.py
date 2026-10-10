"""Canonical fact/occurrence behavior with independently authored source examples."""

import pytest

from investo.briefing.event_identity import (
    EventIdentityError,
    canonical_event_binding,
    compare_event_facts,
    normalize_entity_bindings,
    normalize_fact_bindings,
    resolve_event_identity,
)
from investo.models.event_context import ContextEventDraft, ContextFactDraft
from investo.models.event_evidence import make_event_context_document, make_evidence_document
from investo.models.event_identity import (
    CanonicalEventReceipt,
    EntityAliasProposal,
    FactSlotReceipt,
    OccurrenceAlias,
)
from tests._helpers.event_context_v3 import NOW, ref


def source(
    *,
    path: str = "one",
    value: str = "1200",
    metric: str = "revenue",
    unit: str = "USD",
    period: str = "FY2026",
    status: str = "actual",
    metadata: dict[str, object] | None = None,
):
    evidence = make_evidence_document(
        source_name="official",
        title="Acme announced Widget",
        summary=f"Acme {metric} {status} {value} {unit} {period}",
        detail_excerpt="The service expands access. Prices rose 2% during the observed hour.",
        url=f"https://example.com/{path}",
        published_at=NOW,
        received_at=NOW,
    )
    doc = make_event_context_document(
        evidence, metadata={"reference_period": period, **(metadata or {})}
    )
    fact = ContextFactDraft(
        predicate="result",
        status=status,
        value_kind="numeric",
        subject_refs=(ref(doc, "Acme"),),
        metric_refs=(ref(doc, metric),),
        value_refs=(ref(doc, value),),
        unit_refs=(ref(doc, unit),),
        period_refs=(ref(doc, period),),
        status_refs=(ref(doc, status),),
    )
    proposed = ContextEventDraft(
        item_ids=(1,),
        event_kind="earnings_result",
        actor_refs=(ref(doc, "Acme"),),
        action_refs=(ref(doc, "announced"),),
        object_refs=(ref(doc, "Widget"),),
        facts=(fact,),
        timing="announced",
        relation="direct",
        impact="company",
    )
    return doc, proposed


def receipt(binding, *, clock=NOW):
    identity = binding.identity
    return CanonicalEventReceipt(
        event_id=identity.event_id,
        event_key_hash=identity.event_key_hash,
        occurrence_key_hash=identity.occurrence_key_hash,
        canonical_tuple_hash=identity.canonical_tuple_hash,
        occurrence_aliases=(
            OccurrenceAlias(
                key_hash=identity.occurrence_key_hash,
                basis=identity.occurrence_basis,
                stage=identity.occurrence_stage,
            ),
        ),
        entity_ids=identity.actor_ids,
        event_kind=identity.event_kind,
        document_aliases=identity.document_aliases,
        revision_hashes=(),
        cumulative_fact_hashes=tuple(f.fact_id for f in binding.facts),
        fact_slots=tuple(
            FactSlotReceipt(
                slot_key_hash=f.canonical.slot_key_hash,
                fact_hash=f.fact_id,
                status=f.canonical.status,
            )
            for f in binding.facts
        ),
        first_published_at=clock,
        last_evidence_at=clock,
    )


def binding(doc, proposed, baseline=()):
    return canonical_event_binding(
        proposed, (doc,), baseline, observed_at=NOW, baseline_available=True
    )


def test_thousands_separator_is_the_only_numeric_spelling_merge() -> None:
    a, pa = source(value="1,200")
    b, pb = source(value="1200")
    left, right = binding(a, pa), binding(b, pb)
    assert left.facts[0].fact_id == right.facts[0].fact_id
    assert left.facts[0].original_value == "1,200" and left.facts[0].canonical.value == "1200"
    a, pa = source(value="1.20")
    b, pb = source(value="1.2")
    assert binding(a, pa).facts[0].fact_id != binding(b, pb).facts[0].fact_id


@pytest.mark.parametrize(
    "change", [{"metric": "net_income"}, {"unit": "KRW"}, {"period": "Q4"}, {"status": "forecast"}]
)
def test_metric_unit_period_and_status_do_not_merge(change) -> None:
    a, pa = source()
    b, pb = source(**change)
    assert binding(a, pa).facts[0].fact_id != binding(b, pb).facts[0].fact_id


def test_entity_case_suffix_role_and_unapproved_translation_remain_distinct() -> None:
    doc = make_event_context_document(
        make_evidence_document(
            source_name="official",
            title="Apple Apple Bank apple Fed chair Jerome Powell 애플",
            published_at=NOW,
            received_at=NOW,
        )
    )
    labels = ("Apple", "Apple Bank", "apple", "Fed chair", "Jerome Powell", "애플")
    entities = normalize_entity_bindings((doc,), [(ref(doc, label),) for label in labels])
    assert len({e.entity.entity_id for e in entities}) == 6
    registry = {"Apple": "company:apple", "애플": "company:apple"}
    entities = normalize_entity_bindings(
        (doc,), [(ref(doc, label),) for label in ("Apple", "애플")], approved_registry=registry
    )
    assert entities[0].entity.entity_id == entities[1].entity.entity_id
    assert entities[1].entity.source_labels == ("애플",)


def test_source_alias_requires_an_explicit_relation_in_the_same_document() -> None:
    text = "Acme is also known as 에크미."
    doc = make_event_context_document(
        make_evidence_document(
            source_name="official", title=text, published_at=NOW, received_at=NOW
        )
    )
    alias = EntityAliasProposal(
        label_refs=(ref(doc, "Acme"),),
        alias_refs=(ref(doc, "에크미"),),
        relation_refs=(ref(doc, text),),
    )
    entities = normalize_entity_bindings(
        (doc,), [(ref(doc, label),) for label in ("Acme", "에크미")], alias_proposals=(alias,)
    )
    assert entities[0].entity.entity_id == entities[1].entity.entity_id
    bad = alias.model_copy(update={"relation_refs": (ref(doc, "Acme"),)})
    with pytest.raises(EventIdentityError, match="alias_unbound"):
        normalize_entity_bindings((doc,), [(ref(doc, "Acme"),)], alias_proposals=(bad,))


def test_raw_documents_are_uncertain_duplicates_not_automatic_merges() -> None:
    a, pa = source(path="one")
    b, pb = source(path="two")
    first = binding(a, pa)
    next_run = binding(b, pb, (receipt(first),))
    assert next_run.identity.event_id != first.identity.event_id
    assert next_run.match_outcome == "uncertain_duplicate"


def test_official_occurrence_matches_and_conflicting_tuple_does_not() -> None:
    a, pa = source(path="one", metadata={"official_release_id": "release-2026-001"})
    b, pb = source(path="two", metadata={"official_release_id": "release-2026-001"})
    first = binding(a, pa)
    later = binding(b, pb, (receipt(first),))
    assert later.identity.event_id == first.identity.event_id and later.novelty == "repeat"
    changed = pb.model_copy(update={"object_refs": (ref(b, "Acme"),)})
    result = resolve_event_identity(changed, (b,), (receipt(first),), observed_at=NOW)
    assert result.outcome == "conflict"


def test_late_official_alias_keeps_the_remote_raw_id() -> None:
    a, pa = source()
    first = binding(a, pa)
    b, pb = source(metadata={"official_release_id": "release-2026-001"})
    later = binding(b, pb, (receipt(first),))
    assert later.identity.event_id == first.identity.event_id
    assert later.identity.occurrence_basis == "official_key" and later.novelty == "repeat"


def test_fact_omission_does_not_delete_cumulative_history() -> None:
    a, pa = source()
    first = binding(a, pa)
    old = receipt(first)
    b, pb = source(metric="net_income")
    second = normalize_fact_bindings((b,), pb.facts)[0]
    cumulative = old.model_copy(
        update={
            "cumulative_fact_hashes": (*old.cumulative_fact_hashes, second.fact_id),
            "fact_slots": (
                *old.fact_slots,
                FactSlotReceipt(
                    slot_key_hash=second.canonical.slot_key_hash,
                    fact_hash=second.fact_id,
                    status=second.canonical.status,
                ),
            ),
        }
    )
    delta = compare_event_facts(first.identity, first.facts, (cumulative,))
    assert not delta.added_fact_ids and not delta.superseded_fact_ids
    again = compare_event_facts(first.identity, (*first.facts, second), (cumulative,))
    assert not again.added_fact_ids and len(again.unchanged_fact_ids) == 2


def test_unavailable_history_is_unknown_and_not_repeat() -> None:
    doc, proposed = source()
    result = canonical_event_binding(
        proposed, (doc,), (), observed_at=NOW, baseline_available=False
    )
    assert result.novelty == "unknown"


def test_same_slot_conflicting_actual_values_are_explicit() -> None:
    a, pa = source(value="1200")
    b, pb = source(value="1300", path="two")
    first = binding(a, pa)
    facts = (*first.facts, *normalize_fact_bindings((b,), pb.facts))
    delta = compare_event_facts(first.identity, facts, ())
    assert len(delta.unresolved_conflict_ids) == 2


def test_same_company_document_but_different_reporting_period_is_a_distinct_occurrence() -> None:
    one, first = source(period="FY2026")
    two, second = source(period="Q4")
    assert one.document_id == two.document_id
    prior = binding(one, first)
    later = binding(two, second, (receipt(prior),))
    assert later.identity.event_id != prior.identity.event_id


def test_duplicate_doc_arrival_order_does_not_change_official_identity() -> None:
    a, pa = source(path="one", metadata={"official_release_id": "release-2026-001"})
    b, _pb = source(path="two", metadata={"official_release_id": "release-2026-001"})
    merged = pa.model_copy(update={"item_ids": (1, 2)})
    forward = resolve_event_identity(merged, (a, b), (), observed_at=NOW)
    # Refs still bind the same document independently of its dense same-run ID.
    reverse = resolve_event_identity(merged, (b, a), (), observed_at=NOW)
    assert forward.identity == reverse.identity


def test_negated_alias_is_rejected() -> None:
    text = "Acme is not also known as Beta."
    doc = make_event_context_document(
        make_evidence_document(
            source_name="official", title=text, published_at=NOW, received_at=NOW
        )
    )
    proposal = EntityAliasProposal(
        label_refs=(ref(doc, "Acme"),),
        alias_refs=(ref(doc, "Beta"),),
        relation_refs=(ref(doc, text),),
    )
    with pytest.raises(EventIdentityError, match="alias_unbound"):
        normalize_entity_bindings(
            (doc,), [(ref(doc, "Acme"),), (ref(doc, "Beta"),)], alias_proposals=(proposal,)
        )


def test_different_actual_in_a_known_remote_slot_is_a_conflict() -> None:
    one, first = source(value="1200")
    two, second = source(value="1300")
    prior = binding(one, first)
    current = binding(two, second, (receipt(prior),))
    assert current.identity.event_id == prior.identity.event_id
    assert current.novelty == "unknown"
    assert set(current.delta.unresolved_conflict_ids) == {
        prior.facts[0].fact_id,
        current.facts[0].fact_id,
    }


def test_additional_fact_period_does_not_reidentify_a_fixed_source_occurrence() -> None:
    _doc, proposed = source()
    # The same transmitted document owns both historical quarter and full-year
    # facts; its source-owned reporting period fixes the occurrence discriminator.
    combined = make_event_context_document(
        make_evidence_document(
            source_name="official",
            title="Acme announced Widget",
            summary="Acme revenue actual 1200 USD FY2026. Acme net_income actual 1200 USD Q4.",
            url="https://example.com/one",
            published_at=NOW,
            received_at=NOW,
        ),
        metadata={"reference_period": "FY2026"},
    )
    primary = proposed.facts[0].model_copy(
        update={
            "subject_refs": (ref(combined, "Acme"),),
            "metric_refs": (ref(combined, "revenue"),),
            "value_refs": (ref(combined, "1200"),),
            "unit_refs": (ref(combined, "USD"),),
            "period_refs": (ref(combined, "FY2026"),),
            "status_refs": (ref(combined, "actual"),),
        }
    )
    additional = primary.model_copy(
        update={
            "metric_refs": (ref(combined, "net_income"),),
            "period_refs": (ref(combined, "Q4"),),
        }
    )
    base = proposed.model_copy(
        update={
            "actor_refs": (ref(combined, "Acme"),),
            "action_refs": (ref(combined, "announced"),),
            "object_refs": (ref(combined, "Widget"),),
            "facts": (primary,),
        }
    )
    first = binding(combined, base)
    later = binding(
        combined, base.model_copy(update={"facts": (primary, additional)}), (receipt(first),)
    )
    assert later.identity.event_id == first.identity.event_id and later.novelty == "material_update"


def test_correction_requires_event_owned_before_after_bindings() -> None:
    from investo.models.event_identity import FactCorrection

    doc, initial = source(value="1200")
    prior = binding(doc, initial)
    current_doc, changed = source(value="1300")
    current = binding(current_doc, changed, (receipt(prior),))
    unrelated = make_event_context_document(
        make_evidence_document(
            source_name="other",
            title="Other corrected from 1200 to 1300.",
            published_at=NOW,
            received_at=NOW,
        )
    )
    correction = FactCorrection(
        old_fact_id=prior.facts[0].fact_id,
        new_fact_id=current.facts[0].fact_id,
        source_refs=(ref(unrelated, "Other corrected from 1200 to 1300."),),
    )
    with pytest.raises(EventIdentityError, match="correction_unbound"):
        compare_event_facts(
            current.identity,
            current.facts,
            (receipt(prior),),
            corrections=(correction,),
            documents=(doc, current_doc, unrelated),
            prior_fact_bindings=prior.facts,
        )


@pytest.mark.parametrize(
    "claim,metric,allowed",
    [
        ("Acme revenue corrected from 1200 to 1300.", "revenue", True),
        ("Acme revenue was not corrected from 1200 to 1300.", "revenue", False),
        ("Acme net_income corrected from 1200 to 1300.", "net_income", False),
    ],
)
def test_explicit_source_correction_preserves_the_old_new_pair(
    claim: str, metric: str, allowed: bool
) -> None:
    from investo.models.event_identity import FactCorrection

    old_doc, old_draft = source()
    prior = binding(old_doc, old_draft)
    new_doc = make_event_context_document(
        make_evidence_document(
            source_name="official",
            title="Acme announced Widget",
            summary=f"Acme {metric} actual 1300 USD FY2026. " + claim,
            url="https://example.com/one",
            published_at=NOW,
            received_at=NOW,
        ),
        metadata={"reference_period": "FY2026"},
    )
    fact = old_draft.facts[0].model_copy(
        update={
            "subject_refs": (ref(new_doc, "Acme"),),
            "metric_refs": (ref(new_doc, metric),),
            "value_refs": (ref(new_doc, "1300"),),
            "unit_refs": (ref(new_doc, "USD"),),
            "period_refs": (ref(new_doc, "FY2026"),),
            "status_refs": (ref(new_doc, "actual"),),
        }
    )
    new_proposal = old_draft.model_copy(
        update={
            "actor_refs": (ref(new_doc, "Acme"),),
            "action_refs": (ref(new_doc, "announced"),),
            "object_refs": (ref(new_doc, "Widget"),),
            "facts": (fact,),
        }
    )
    current = binding(new_doc, new_proposal, (receipt(prior),))
    old_bound = normalize_fact_bindings(
        (new_doc,), (fact.model_copy(update={"value_refs": (ref(new_doc, "1200"),)}),)
    )
    correction = FactCorrection(
        old_fact_id=prior.facts[0].fact_id,
        new_fact_id=current.facts[0].fact_id,
        source_refs=(ref(new_doc, claim),),
    )
    if not allowed:
        with pytest.raises(EventIdentityError, match="correction_unbound"):
            compare_event_facts(
                current.identity,
                current.facts,
                (receipt(prior),),
                corrections=(correction,),
                documents=(old_doc, new_doc),
                prior_fact_bindings=prior.facts,
            )
        return
    delta = compare_event_facts(
        current.identity,
        current.facts,
        (receipt(prior),),
        corrections=(correction,),
        documents=(new_doc,),
        prior_fact_bindings=old_bound,
    )
    assert delta.correction_pairs == ((prior.facts[0].fact_id, current.facts[0].fact_id),)
    assert not delta.unresolved_conflict_ids


def test_multi_actor_binding_preserves_each_entity_and_merges_duplicate_refs() -> None:
    doc = make_event_context_document(
        make_evidence_document(
            source_name="official",
            title="Acme and Beta announced Widget. Acme confirmed agreement.",
            published_at=NOW,
            received_at=NOW,
        )
    )
    proposed = ContextEventDraft(
        item_ids=(1,),
        event_kind="corporate_action",
        actor_refs=(ref(doc, "Acme"), ref(doc, "Beta")),
        action_refs=(ref(doc, "announced"),),
        object_refs=(ref(doc, "Widget"),),
        timing="announced",
        relation="direct",
        impact="company",
    )
    current = binding(doc, proposed)
    assert len(current.identity.actor_ids) == 2
    assert {entity.entity.display_label for entity in current.entities} == {
        "Acme",
        "Beta",
        "Widget",
    }
    additional = ref(doc, "Acme").model_copy(
        update={
            "start": doc.chunks[0].text.rindex("Acme"),
            "end": doc.chunks[0].text.rindex("Acme") + 4,
        }
    )
    duplicate = binding(
        doc, proposed.model_copy(update={"actor_refs": (*proposed.actor_refs, additional)})
    )
    assert duplicate.identity == current.identity
    acme = next(entity for entity in duplicate.entities if entity.entity.display_label == "Acme")
    assert len(acme.identity_refs) == 2

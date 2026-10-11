"""Source-backed optional domestic context is contained before the native seal."""

from dataclasses import replace
from datetime import timedelta

import pytest

from investo._internal.event_asset_impact import match_event_assets
from investo.briefing.editorial_plan import build_editorial_plan
from investo.briefing.event_context import (
    event_context_refs,
    prepare_context_documents,
    support_vector,
)
from investo.briefing.event_identity import canonical_event_binding
from investo.models.event_context import MeaningContext, ReactionContext
from investo.models.event_document import (
    EditionAvailability,
    EventArticle,
    EventDigest,
    EventEditionDraft,
)
from investo.models.event_evidence import make_evidence_document
from investo.models.items import NormalizedItem
from investo.publisher.anchor_assertion_gate import scan_anchor_assertions
from investo.publisher.public_document import (
    PublicDocumentFinalizationError,
    finalize_public_bundle,
)
from tests._helpers.event_context_v3 import FACT, NOW, TITLE, ref
from tests._helpers.event_context_v3 import draft as source_draft
from tests._helpers.event_document_v3 import TARGET, native_context


def build(segment, detail, *, text=None, mechanism=None, assumptions=(), refs=None):
    evidence = make_evidence_document(
        source_name="official",
        title=TITLE,
        summary=FACT,
        detail_excerpt=detail,
        url="https://example.com/one",
        published_at=NOW,
        received_at=NOW,
        source_tier="official",
    )
    item = NormalizedItem(
        source_name="official",
        category="news",
        title=TITLE,
        summary=FACT,
        url="https://example.com/one",
        published_at=NOW,
        event_evidence=evidence,
        raw_metadata={"official_source": "true"},
    )
    docs = prepare_context_documents((item,), received_at=NOW)
    mrefs = tuple(ref(docs[0], v) for v in (refs or (detail,)))
    source = source_draft(docs[0]).model_copy(update={"meaning_refs": mrefs})
    binding = canonical_event_binding(source, docs, (), observed_at=NOW, baseline_available=True)
    plan, bindings, _ = build_editorial_plan((source,), (binding,), docs, observed_at=NOW)
    article = EventArticle(
        event_id=binding.identity.event_id,
        headline="Acme Widget 실적 발표",
        what_changed="Acme가 Widget의 FY2026 실제 revenue 1200 USD를 발표했습니다.",
        fact_ids=tuple(f.fact_id for f in binding.facts),
        source_refs=event_context_refs(source, optional=False),
        meaning=MeaningContext(
            mode="conditional" if mechanism else "source_reported",
            text=text or detail,
            mechanism=mechanism,
            assumptions=assumptions,
            refs=mrefs,
        ),
    )
    draft = EventEditionDraft(
        segment=segment,
        target_date=TARGET,
        availability=EditionAvailability(status="normal"),
        editorial_plan=plan,
        bindings=bindings,
        documents=docs,
        articles=(article,),
        support=(support_vector(source, docs, baseline_available=True),),
    )
    draft = draft.model_copy(update={"asset_impacts": match_event_assets(draft, ("Beta",))})
    context = replace(
        native_context((item, draft)), event_asset_terms_by_segment={segment: ("Beta",)}
    )
    return item, draft, context


@pytest.mark.parametrize("placement", ["mechanism", "assumption"])
def test_domestic_conditional_context_keeps_required_facts(placement):
    claim = "코스피 1.8% 상승."
    _, draft, ctx = build(
        "domestic-equity",
        "코스피 상승이 나타날 수 있습니다. 코스피 1.8% 상승. 수요가 유지됩니다.",
        text="코스피 상승이 나타날 수 있습니다.",
        mechanism=claim if placement == "mechanism" else "수요가 유지됩니다.",
        assumptions=("수요가 유지됩니다." if placement == "mechanism" else claim,),
    )
    sealed = finalize_public_bundle({draft.segment: draft}, context=ctx).documents[0]
    assert sealed.edition_view.edition.events[0].meaning.mode == "unavailable"
    assert sealed.edition_view.edition.events[0].facts[0].value == "1200"
    assert len(sealed.numeric_containment_outcomes) == 1
    assert not scan_anchor_assertions(
        sealed.rendered_markdown, segment=draft.segment, available_symbols=()
    )


def test_related_asset_cannot_survive_its_contained_meaning():
    _, draft, ctx = build(
        "domestic-equity",
        "Acme affects Beta demand. 코스피 1.8% 상승.",
        refs=("Acme affects Beta demand.", "코스피 1.8% 상승."),
    )
    assert len(draft.asset_impacts) == 1
    sealed = finalize_public_bundle({draft.segment: draft}, context=ctx).documents[0]
    assert not sealed.edition_view.edition.asset_impacts
    assert sealed.edition_view.edition.events[0].facts[0].value == "1200"


def test_original_digest_numeric_finding_is_never_hidden():
    _, draft, ctx = build("domestic-equity", "코스피 1.8% 상승.")
    article = draft.articles[0].model_copy(
        update={"source_refs": (*draft.articles[0].source_refs, *draft.articles[0].meaning.refs)}
    )
    draft = draft.model_copy(
        update={
            "articles": (article,),
            "digests": (
                EventDigest(
                    event_id=article.event_id,
                    fact_ids=article.fact_ids,
                    text="코스피 1.8% 상승.",
                    source_refs=article.meaning.refs,
                ),
            ),
        }
    )
    with pytest.raises(PublicDocumentFinalizationError, match=r"numeric\.anchor_assertion"):
        finalize_public_bundle({draft.segment: draft}, context=ctx)


def test_observed_reaction_warning_is_owned_before_containment():
    start = NOW - timedelta(hours=2)
    end = NOW - timedelta(hours=1)
    detail = (
        "코스피 1.8% 상승 baseline 2700 USD value 2750 USD "
        f"{start.isoformat()} {end.isoformat()} {NOW.isoformat()}"
    )
    _, d, c = build("domestic-equity", detail)
    refs = tuple(ref(d.documents[0], v) for v in (detail, "2700", "2750"))
    source = d.editorial_plan.events[0].source_event.model_copy(
        update={"meaning_refs": (), "reaction_refs": refs}
    )
    binding = canonical_event_binding(
        source, d.documents, (), observed_at=NOW, baseline_available=True
    )
    plan, bindings, _ = build_editorial_plan((source,), (binding,), d.documents, observed_at=NOW)
    reaction = ReactionContext(
        status="observed",
        attribution="coincidence_only",
        asset_id="코스피",
        window_start=start,
        window_end=end,
        observed_at=NOW,
        baseline_ref=refs[1],
        value_ref=refs[2],
        text="코스피 1.8% 상승",
        refs=refs,
    )
    a = d.articles[0].model_copy(
        update={
            "meaning": MeaningContext(mode="unavailable"),
            "reaction": reaction,
            "source_refs": event_context_refs(source, optional=False),
        }
    )
    d = d.model_copy(
        update={
            "articles": (a,),
            "editorial_plan": plan,
            "bindings": bindings,
            "support": (support_vector(source, d.documents, baseline_available=True),),
        }
    )
    sealed = finalize_public_bundle({d.segment: d}, context=c).documents[0]
    assert sealed.edition_view.edition.events[0].reaction.status == "unavailable"
    assert len(sealed.numeric_containment_outcomes) == 1
    assert sealed.edition_view.edition.events[0].facts[0].value == "1200"

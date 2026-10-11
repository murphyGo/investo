"""Independent synthetic probes; run from the u169 worktree. No filesystem writes."""

import asyncio
from dataclasses import replace

from investo.briefing.editorial_plan import build_editorial_plan
from investo.briefing.event_context import (
    event_context_refs,
    prepare_context_documents,
    support_vector,
)
from investo.briefing.event_document import generate_event_document
from investo.briefing.event_identity import canonical_event_binding
from investo.briefing.event_story import attach_story_follow_ups
from investo.briefing.generation_contract import GenerationInput
from investo.briefing.pipeline import GenerationPolicy
from investo.briefing.watchlist import WatchlistConfig
from investo.models.event_context import (
    ContextClassificationResult,
    ContextEventDraft,
    ContextFactDraft,
)
from investo.models.event_document import (
    EditionAvailability,
    EventArticle,
    EventEditionContent,
    EventEditionDraft,
)
from investo.models.event_evidence import make_evidence_document
from investo.models.items import NormalizedItem
from investo.publisher.public_document import (
    PublicDocumentFinalizationError,
    finalize_public_bundle,
)
from tests._helpers.event_context_v3 import NOW, ref
from tests._helpers.event_context_v3 import draft as source_draft
from tests._helpers.event_document_v3 import native_case, native_context
from tests.integration.test_event_generation import _ReplayRunner


def test_multi_actor_prose_binds_each_subject_status():
    item = NormalizedItem(
        source_name="official",
        category="news",
        title="Acme and Beta announced Widget",
        summary="Acme revenue actual 1200 USD FY2026; Beta revenue forecast 1200 USD FY2026.",
        url="https://example.com/one",
        published_at=NOW,
    )
    docs = prepare_context_documents((item,), received_at=NOW)
    doc = docs[0]
    first = ContextFactDraft(
        predicate="result",
        status="actual",
        value_kind="numeric",
        subject_refs=(ref(doc, "Acme"),),
        metric_refs=(ref(doc, "revenue"),),
        value_refs=(ref(doc, "1200"),),
        unit_refs=(ref(doc, "USD"),),
        period_refs=(ref(doc, "FY2026"),),
        status_refs=(ref(doc, "actual"),),
    )
    second = first.model_copy(
        update={
            "subject_refs": (ref(doc, "Beta"),),
            "value_refs": (
                ref(doc, "1200").model_copy(
                    update={
                        "start": doc.chunks[1].text.rindex("1200"),
                        "end": doc.chunks[1].text.rindex("1200") + 4,
                    }
                ),
            ),
            "status": "forecast",
            "status_refs": (ref(doc, "forecast"),),
        }
    )
    event = ContextEventDraft(
        item_ids=(1,),
        event_kind="earnings_result",
        actor_refs=(ref(doc, "Acme"), ref(doc, "Beta")),
        action_refs=(ref(doc, "announced"),),
        object_refs=(ref(doc, "Widget"),),
        facts=(first, second),
        timing="announced",
        relation="direct",
        impact="company",
    )
    binding = canonical_event_binding(event, docs, (), observed_at=NOW, baseline_available=True)
    plan, bindings, _ = build_editorial_plan((event,), (binding,), docs, observed_at=NOW)
    article = EventArticle(
        event_id=binding.identity.event_id,
        headline="Acme와 Beta의 Widget 발표",
        what_changed=(
            "Acme와 Beta가 Widget를 발표했습니다. Acme FY2026 revenue actual 1200 USD; "
            "Beta FY2026 revenue forecast 1200 USD."
        ),
        fact_ids=tuple(f.fact_id for f in binding.facts),
        source_refs=event_context_refs(event),
    )
    base = EventEditionDraft(
        segment="us-equity",
        target_date=NOW.date(),
        availability=EditionAvailability(status="normal"),
        editorial_plan=plan,
        bindings=bindings,
        documents=docs,
        articles=(article,),
        support=(support_vector(event, docs, baseline_available=True),),
    )
    for swapped in (False, True):
        prose = (
            article.what_changed
            if not swapped
            else (
                "Acme와 Beta가 Widget를 발표했습니다. Acme FY2026 revenue forecast 1200 USD; "
                "Beta FY2026 revenue actual 1200 USD."
            )
        )
        changed = base.model_copy(
            update={"articles": (article.model_copy(update={"what_changed": prose}),)}
        )
        try:
            document = finalize_public_bundle(
                {"us-equity": changed}, context=native_context((item, changed))
            ).documents[0]
            assert not swapped, "unsafe subject/status swap was sealed"
            assert len(document.edition_view.edition.events[0].actor_labels) == 2
        except PublicDocumentFinalizationError:
            assert swapped, "valid multi-actor prose was rejected"


def history_revision_inputs():
    item, initial = native_case()
    initial = attach_story_follow_ups(initial, (), observed_at=NOW)
    first = finalize_public_bundle(
        {initial.segment: initial}, context=native_context((item, initial))
    ).documents[0]
    prior = first.story_publication_deltas[0].next_record
    baseline = first.canonical_event_receipts
    summary = "Acme revenue actual 1200 USD FY2026; Acme net_income actual 1300 USD FY2026."
    evidence = make_evidence_document(
        source_name="official",
        title=item.title,
        summary=summary,
        detail_excerpt=item.event_evidence.detail_excerpt,
        url=str(item.url),
        published_at=NOW,
        received_at=NOW,
        source_tier="official",
    )
    current_item = item.model_copy(update={"summary": summary, "event_evidence": evidence})
    docs = prepare_context_documents((current_item,), received_at=NOW)
    event = source_draft(docs[0])
    second = event.facts[0].model_copy(
        update={
            "metric_refs": (ref(docs[0], "net_income"),),
            "value_refs": (ref(docs[0], "1300"),),
        }
    )
    event = event.model_copy(update={"facts": (event.facts[0], second)})
    binding = canonical_event_binding(
        event, docs, baseline, observed_at=NOW, baseline_available=True
    )
    assert binding.novelty == "material_update"
    plan, bindings, _ = build_editorial_plan((event,), (binding,), docs, observed_at=NOW)
    article = EventArticle(
        event_id=binding.identity.event_id,
        headline="Acme Widget 실적 발표",
        what_changed=(
            "Acme가 Widget의 FY2026 실제 revenue 1200 USD 및 "
            "실제 net_income 1300 USD를 발표했습니다."
        ),
        fact_ids=tuple(f.fact_id for f in binding.facts),
        source_refs=event_context_refs(event, optional=False),
    )
    current = EventEditionDraft(
        segment="us-equity",
        target_date=NOW.date(),
        availability=EditionAvailability(status="normal"),
        editorial_plan=plan,
        bindings=bindings,
        documents=docs,
        articles=(article,),
        support=(support_vector(event, docs, baseline_available=True),),
    )
    return current_item, current, prior, baseline, event


def test_history_revision_preserves_prior_sealed_receipts():
    item, current, prior, baseline, _ = history_revision_inputs()
    current = attach_story_follow_ups(current, (prior,), observed_at=NOW)
    context = replace(
        native_context((item, current)),
        story_baselines={"us-equity": (prior,)},
        canonical_event_baselines={"us-equity": baseline},
        canonical_baseline_available={"us-equity": True},
    )
    sealed = finalize_public_bundle({"us-equity": current}, context=context).documents[0]
    assert len(sealed.story_publication_deltas) == 1
    assert set(prior.source_refs) <= set(sealed.story_publication_deltas[0].next_record.source_refs)
    assert r"net\_income" in sealed.rendered_markdown


def test_generation_accepts_supplied_story_history():
    item, current, prior, baseline, event = history_revision_inputs()
    runner = _ReplayRunner(
        [
            ContextClassificationResult(schema_version=3, events=(event,)).model_dump_json(),
            EventEditionContent(articles=current.articles).model_dump_json(),
        ]
    )
    request = GenerationInput(
        target_date=NOW.date(),
        segment="us-equity",
        items=(item,),
        runner=runner,
        watchlist_config=WatchlistConfig(),
        event_observed_at=NOW,
        generation_policy=GenerationPolicy(timeout_s=3, max_attempts=1, total_budget_s=30),
        canonical_event_baseline=baseline,
        story_baseline=(prior,),
    )
    generated = asyncio.run(generate_event_document(request))
    assert len(generated.document.story_proposals) == 1
    assert len(runner.prompts) == 2


def test_unbound_reaction_asset_time_and_units_are_rejected():
    from datetime import timedelta

    import pytest

    from investo.models.event_context import ReactionContext

    item, draft = native_case()
    doc = draft.documents[0]
    source = draft.editorial_plan.events[0].source_event
    refs = (ref(doc, "1200"), ref(doc, "2%"), ref(doc, "Prices rose 2% during the observed hour."))
    source = source.model_copy(update={"reaction_refs": refs})
    binding = canonical_event_binding(
        source, draft.documents, (), observed_at=NOW, baseline_available=True
    )
    plan, bindings, _ = build_editorial_plan(
        (source,), (binding,), draft.documents, observed_at=NOW
    )
    reaction = ReactionContext(
        status="observed",
        attribution="coincidence_only",
        asset_id="UNSUPPORTED_ASSET",
        window_start=NOW - timedelta(days=123),
        window_end=NOW - timedelta(days=122),
        observed_at=NOW,
        baseline_ref=refs[0],
        value_ref=refs[1],
        text="Prices rose 2% during the observed hour.",
        refs=refs,
    )
    changed = draft.model_copy(
        update={
            "editorial_plan": plan,
            "bindings": bindings,
            "articles": (draft.articles[0].model_copy(update={"reaction": reaction}),),
            "support": (support_vector(source, draft.documents, baseline_available=True),),
        }
    )
    with pytest.raises(PublicDocumentFinalizationError, match=r"event\.reaction_unbound"):
        finalize_public_bundle({draft.segment: changed}, context=native_context((item, changed)))

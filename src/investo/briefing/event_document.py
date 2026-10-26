"""Native schema-three orchestration input, typed Stage 2 and parent assembly."""

from __future__ import annotations

import json
import time
from dataclasses import replace
from datetime import UTC, datetime

from pydantic import ValidationError

from investo._internal.event_v3_contract import EventEditionValidationError, validate_event_edition
from investo.briefing.editorial_plan import build_editorial_plan
from investo.briefing.event_context import (
    ContextEvidenceError,
    build_context_prompt_buffer,
    event_context_refs,
    prepare_context_documents,
    support_vector,
)
from investo.briefing.event_identity import canonical_event_binding
from investo.briefing.event_input import (
    is_article_reference_item,
    is_event_reference_item,
    select_event_input_items,
)
from investo.briefing.generation_contract import GenerationInput, NativeEventGenerationResult
from investo.models.event_context import ContextClassificationResult
from investo.models.event_document import (
    EditionAvailability,
    EditionNewsWindow,
    EventEditionContent,
    EventEditionDraft,
    EventReferencePanel,
    MarketReferencePanel,
)
from investo.models.macro import is_required_macro_actual


def parse_event_document(stdout: str) -> EventEditionContent:
    if len(stdout.encode("utf-8")) > 128 * 1024:
        raise EventEditionValidationError("event.schema_invalid")
    try:
        return EventEditionContent.model_validate_json(stdout)
    except ValidationError:
        raise EventEditionValidationError("event.schema_invalid") from None


def render_event_document_prompt(evidence: str) -> str:
    return (
        "Return only schema-three JSON matching this schema. Write Korean news articles. "
        "Use one section per event, with an integrated, coherent news narrative as the default. "
        "Choose the structure for the topic: prose paragraphs normally, a short list or "
        "separate factual table only where it improves understanding. The evidence roles "
        "what_changed/background/meaning/reaction are internal proof slots, not a mandatory "
        "reader outline. Do not write a repetitive questionnaire or fill unavailable roles. "
        "display_blocks may group and order populated roles as paragraph, bullets "
        "or labeled_list blocks; "
        "Use unlabeled bullets for concise points; labeled_list is an explicit opt-in for "
        "topics genuinely clearer as named elements, not the default. "
        "include every populated role exactly once. Omit it for default prose. "
        "Use transitions within the supported texts so grouped paragraphs read naturally. "
        "Use show_facts=true only when a separate verified-fact table helps; facts otherwise "
        "remain available in supporting details. Do not invent headings, causality or content "
        "just to connect events. "
        "Use the exact ordered event IDs and fact IDs in the parent editorial plan. "
        "Every placement=article event needs one complete article "
        "(headline <=120, what_changed <=600). "
        "Do not write articles for placement=reference events. Include actors and objects. "
        "Required facts are rendered as deterministic rows. "
        "Parent events and context.events have the same order. For every included fact, "
        "article.source_refs must include every component reference in the corresponding "
        "context.events row's draft.facts, including subject_refs separate from actor_refs. "
        "Resolve each compact span ID with context.spans[id].ref and copy the complete ref. "
        "If prose repeats a numeric fact, include its literal source metric, value, "
        "unit, period "
        "and actual/forecast role. Source refs must be exact transmitted refs. "
        "For nonnumeric facts whose status_refs include a complete assertion, copy it "
        "verbatim as what_changed and any digest, even when that assertion is English. "
        "If status_refs contain only a verb/status token, use a complete closed "
        "subject-verb-value assertion from the literal component spans, never that token alone. "
        "Preserve its full subject, value, attribution and modality. Do not insert "
        "parenthetical aliases, translations, paraphrases, qualifiers or extra clauses. "
        "Headlines and independently supported explanations remain Korean. "
        "Write no additional tables, sections, prices, dates, identities or facts. "
        "Background, meaning and reaction use their assigned refs independently; "
        "missing support means unavailable, never an invented causal explanation. "
        "Conditional meaning needs a mechanism, assumptions and conditional wording. "
        "A digest is optional, a complete sentence <=140, independently of the article. "
        "No filler events, market-wide thesis, trading recommendation or invented next check.\n"
        + json.dumps(EventEditionContent.model_json_schema(), ensure_ascii=False)
        + "\nProtected evidence and parent plan:\n"
        + evidence
    )


async def generate_event_document(request: GenerationInput) -> NativeEventGenerationResult:
    # Local import keeps the existing provider/budget owner free of a contract cycle.
    from investo.briefing._core.orchestration import (
        GenerationPolicy,
        classify_context,
        synthesize_context_document,
    )
    from investo.briefing.claude_code import RetryBudget

    segment = request.segment
    if segment is None:
        raise ValueError("native event generation requires a market segment")
    article_v2 = bool(
        request.event_generation_policy and request.event_generation_policy.profile == "article_v2"
    )
    reference_item = is_article_reference_item if article_v2 else is_event_reference_item
    started_at = time.monotonic()
    policy = replace(request.generation_policy or GenerationPolicy(), event_mode="preview")
    if article_v2:
        policy = replace(policy, timeout_s=600, max_attempts=1, total_budget_s=3900)
    budget = request.budget or RetryBudget(total_budget_s=policy.total_budget_s)
    observed_at = request.event_observed_at or datetime.now(UTC)
    candidates = select_event_input_items(
        request.items, target_date=request.target_date, article_v2=article_v2
    )
    documents = prepare_context_documents(
        candidates, received_at=observed_at, article_passages=article_v2
    )
    from investo.briefing.event_article import classification_documents

    full_documents = documents
    if article_v2:
        documents = classification_documents(documents)
    if request.event_context_documents and request.event_context_documents != full_documents:
        raise ContextEvidenceError("context.buffer_conflict")
    context_bytes = 24 * 1024
    if article_v2:
        from investo.briefing.event_prompt import render_context_classification_prompt

        # Reserve the real schema/instructions and worst-case required-ID suffix.
        context_bytes = min(
            context_bytes,
            32 * 1024
            - len(
                render_context_classification_prompt(
                    "", segment=segment, assertion_hints=True
                ).encode("utf-8")
            )
            - 512,
        )
    buffer = build_context_prompt_buffer(
        documents,
        required_item_ids=frozenset(
            i
            for i, item in enumerate(candidates, 1)
            if is_required_macro_actual(item) and not reference_item(item)
        ),
        preferred_item_ids=frozenset(
            i for i, item in enumerate(candidates, 1) if not reference_item(item)
        ),
        assertion_hints=article_v2,
        max_bytes=context_bytes,
    )
    article_calls = None
    if article_v2:
        from investo.briefing.event_article_review import ArticleCallBudget

        runner_deadline = getattr(request.runner, "deadline", None)
        article_calls = ArticleCallBudget(
            shared=budget,
            started_at=started_at,
            preparation_elapsed_s=request.event_preparation_elapsed_s,
            deadline=runner_deadline if isinstance(runner_deadline, (int, float)) else None,
            calls=0,
        )
        if buffer.documents:
            article_calls.require(600 + 60)
    classification = (
        await classify_context(
            buffer,
            runner=request.runner,
            budget=budget,
            policy=policy,
            segment=segment,
            observed_at=observed_at,
            observation=article_calls.observe_classification if article_calls is not None else None,
            assertion_hints=article_v2,
        )
        if buffer.documents
        else ContextClassificationResult(schema_version=3, events=())
    )
    if article_v2:
        buffer = replace(buffer, documents=tuple(full_documents[i - 1] for i in buffer.item_ids))
    bindings = tuple(
        canonical_event_binding(
            event,
            buffer.documents,
            request.canonical_event_baseline,
            observed_at=observed_at,
            baseline_available=request.event_baseline_available,
        )
        for event in classification.events
    )
    from investo.briefing.event_article import build_article_packets, packet_payload
    from investo.models.event_article import EventEvidencePacket

    packets: tuple[EventEvidencePacket, ...] = ()
    limit = 5
    while True:
        plan, selected, protected = build_editorial_plan(
            classification.events,
            bindings,
            buffer.documents,
            required_item_ids=buffer.required_prompt_item_ids,
            reference_item_ids=frozenset(
                n
                for n, original in enumerate(buffer.item_ids, 1)
                if reference_item(candidates[original - 1])
            ),
            observed_at=observed_at,
            max_articles=limit,
            max_evidence_bytes=49152 if article_v2 else 16384,
        )
        if not article_v2 or not any(p.placement == "article" for p in plan.events):
            break
        packets = build_article_packets(plan, selected, buffer.documents)
        try:
            evidence = packet_payload(packets, buffer.documents)
        except ValueError as exc:
            if str(exc) != "context.budget_exhausted":
                raise
            last = plan.events[-1]
            if (
                len(plan.events) <= 1
                or set(last.source_event.item_ids) & buffer.required_prompt_item_ids
            ):
                raise ContextEvidenceError("context.budget_exhausted") from None
            limit = len(plan.events) - 1
            continue
        packets_by_id = {p.event_id: p for p in packets}
        plan = plan.model_copy(
            update={
                "events": tuple(
                    p.model_copy(update={"assigned_refs": packets_by_id[p.event_id].allowed_refs})
                    if p.event_id in packets_by_id
                    else p
                    for p in plan.events
                ),
                "evidence_bytes": len(evidence.encode("utf-8")),
            }
        )
        break
    vectors = tuple(
        support_vector(
            p.source_event, buffer.documents, baseline_available=request.event_baseline_available
        )
        for p, b in zip(plan.events, selected, strict=True)
    )
    dates = {anchor.trading_date for anchor in request.market_anchors}
    price_date = next(iter(dates)) if len(dates) == 1 and None not in dates else None
    news_window = None
    if request.news_window_consumptions:
        news_window = EditionNewsWindow(
            start_utc=min(r.requested_start for r in request.news_window_consumptions),
            end_utc=max(r.end_utc for r in request.news_window_consumptions),
        )
    limited = request.data_limited or any(
        o.status in {"failed", "skipped"} for o in request.source_outcomes
    )
    has_articles = any(p.placement == "article" for p in plan.events)
    base = EventEditionDraft(
        content_contract_version=2 if article_v2 else 1,
        segment=segment,
        target_date=request.target_date,
        price_reference_date=price_date,
        price_time_basis="trading_date" if price_date is not None else "unavailable",
        news_window=news_window,
        availability=EditionAvailability(
            status="source_limited" if limited else "normal" if has_articles else "quiet",
            reason_codes=("source_limited",)
            if limited
            else ()
            if has_articles
            else ("no_eligible_events",),
        ),
        editorial_plan=plan,
        bindings=selected,
        documents=buffer.documents,
        support=vectors,
        market_reference=MarketReferencePanel(anchors=request.market_anchors),
        reference_panels=tuple(
            EventReferencePanel(
                event_id=p.event_id,
                fact_ids=p.required_fact_ids,
                source_refs=tuple(
                    dict.fromkeys(event_context_refs(p.source_event, optional=False))
                ),
            )
            for p in plan.events
            if p.placement == "reference"
        ),
    )

    def assemble(stdout: str) -> EventEditionDraft:
        content = parse_event_document(stdout)
        draft = EventEditionDraft.model_validate({**base.model_dump(), **content.model_dump()})
        validate_event_edition(
            draft, observed_at=observed_at, story_baseline=request.story_baseline
        )
        return draft

    if article_v2 and has_articles:
        from investo.briefing.event_article_review import compose_and_review
        from investo.models.event_document import EventArticle

        assert article_calls is not None
        readiness = await compose_and_review(
            packets, base, runner=request.runner, budget=article_calls, observed_at=observed_at
        )
        draft = base.model_copy(
            update={
                "article_readiness": readiness,
                "article_generation_trace": article_calls.trace(),
                "articles": tuple(
                    EventArticle(
                        content_contract_version=2,
                        event_id=r.composition.event_id,
                        headline=r.composition.headline,
                        what_changed=r.composition.narrative.lead,
                        narrative=r.composition.narrative,
                        fact_ids=r.packet.required_fact_ids,
                        source_refs=r.packet.allowed_refs,
                        show_facts=any(
                            b.kind == "fact_table" for b in r.composition.narrative.blocks
                        ),
                    )
                    for r in readiness
                ),
            }
        )
        validate_event_edition(
            draft, observed_at=observed_at, story_baseline=request.story_baseline
        )
    else:
        draft = (
            await synthesize_context_document(
                render_event_document_prompt(protected),
                assemble,
                runner=request.runner,
                budget=budget,
                policy=policy,
                segment=segment,
            )
            if has_articles
            else base
        )
    if request.event_baseline_available:
        from investo.briefing.event_story import attach_story_follow_ups

        draft = attach_story_follow_ups(draft, request.story_baseline, observed_at=observed_at)
        validate_event_edition(
            draft, observed_at=observed_at, story_baseline=request.story_baseline
        )
    from investo.briefing.event_asset_impact import match_event_assets

    config = request.watchlist_config
    asset_terms = (
        tuple(dict.fromkeys((*config.tickers, *config.assets))) if config is not None else ()
    )
    draft = draft.model_copy(update={"asset_impacts": match_event_assets(draft, asset_terms)})
    return NativeEventGenerationResult(
        document=draft,
        asset_selection_terms=asset_terms,
        context_classification=classification,
        event_support_vectors=vectors,
        news_window_consumptions=request.news_window_consumptions,
    )

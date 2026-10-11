"""Native schema-three orchestration input, typed Stage 2 and parent assembly."""

from __future__ import annotations

import json
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
from investo.briefing.event_input import select_event_input_items
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
        "Return only schema-three JSON matching this schema. Write Korean reader prose. "
        "Use the exact ordered event IDs and fact IDs in the parent editorial plan. "
        "Every placement=article event needs one complete article "
        "(headline <=120, what_changed <=600). "
        "Do not write articles for placement=reference events. Include actors and objects. "
        "Required facts are rendered as deterministic rows. "
        "If prose repeats a numeric fact, include its literal source metric, value, "
        "unit, period "
        "and actual/forecast role. Source refs must be exact transmitted refs. "
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
    policy = replace(request.generation_policy or GenerationPolicy(), event_mode="preview")
    budget = request.budget or RetryBudget(total_budget_s=policy.total_budget_s)
    observed_at = request.event_observed_at or datetime.now(UTC)
    candidates = select_event_input_items(request.items, target_date=request.target_date)
    documents = prepare_context_documents(candidates, received_at=observed_at)
    if request.event_context_documents and request.event_context_documents != documents:
        raise ContextEvidenceError("context.buffer_conflict")
    buffer = build_context_prompt_buffer(
        documents,
        required_item_ids=frozenset(
            i for i, item in enumerate(candidates, 1) if is_required_macro_actual(item)
        ),
    )
    classification = (
        await classify_context(
            buffer,
            runner=request.runner,
            budget=budget,
            policy=policy,
            segment=segment,
            observed_at=observed_at,
        )
        if buffer.documents
        else ContextClassificationResult(schema_version=3, events=())
    )
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
    plan, selected, protected = build_editorial_plan(
        classification.events,
        bindings,
        buffer.documents,
        required_item_ids=buffer.required_prompt_item_ids,
        observed_at=observed_at,
    )
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

"""Isolated event preview: supplied inputs in, finalized documents out.

This entrypoint deliberately has no collection, archive, Git, notification or
cursor lifecycle. The supplied runner uses the existing two-stage LLM budget;
replay callers can supply a fixture runner without credentials or network I/O.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from investo.briefing.fact_context import build_verified_fact_bundle, render_fact_context_block
from investo.briefing.generation_contract import GenerationInput, GenerationResult
from investo.briefing.pipeline import GenerationPolicy, generate_briefing_from_input
from investo.briefing.segments import build_segment_coverage, segment_source_outcomes
from investo.models.event_config import EventExecutionConfig
from investo.publisher.public_document import (
    FinalizedPublicBundle,
    PublicDocumentContext,
    finalize_public_bundle,
)


@dataclass(frozen=True, slots=True)
class EventPreviewResult:
    generation: GenerationResult
    finalized: FinalizedPublicBundle


async def preview_event_briefing(request: GenerationInput) -> EventPreviewResult:
    """Generate and seal one preview without invoking any pipeline I/O stages.

    A captured timezone-aware clock is mandatory so source availability,
    novelty and terminal entity checks all see the same instant. History must
    be explicitly supplied on ``GenerationInput``; no local ledger is read.
    """
    EventExecutionConfig(mode="preview").validate_capabilities()
    segment = request.segment
    observed_at = request.event_observed_at
    if segment is None or observed_at is None or observed_at.utcoffset() is None:
        raise ValueError("event preview requires a segment and a timezone-aware observation clock")
    facts = build_verified_fact_bundle(request.items, request.target_date, observed_at)
    policy = replace(request.generation_policy or GenerationPolicy(), event_mode="preview")
    generation = await generate_briefing_from_input(
        replace(
            request,
            generation_policy=policy,
            fact_context_block=render_fact_context_block(facts, observed_at),
        )
    )
    payload = generation.event_payload
    if payload is None:
        raise ValueError("event preview requires a v2 generation payload")
    context = PublicDocumentContext(
        target_date=request.target_date,
        expected_segments=(segment,),
        input_absences={},
        anchors_by_segment={segment: request.market_anchors},
        items_by_segment={segment: request.items},
        coverage_by_segment={
            segment: build_segment_coverage(
                segment,
                request.items,
                source_outcomes=segment_source_outcomes(segment, request.source_outcomes),
            )
        },
        source_outcomes=request.source_outcomes,
        bundle_context=request.bundle_context,
        fact_bundle=facts,
        entity_observed_at_utc=observed_at,
        event_payloads_by_segment={segment: payload},
    )
    finalized = finalize_public_bundle({segment: generation.briefing}, context=context)
    return EventPreviewResult(generation=generation, finalized=finalized)

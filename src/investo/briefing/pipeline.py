"""Two-stage briefing pipeline — thin orchestrator + public re-exports.

References:
    Functional Design L1 (`u2-briefing/functional-design/business-logic-model.md`)
        — end-to-end 11-step flow
    Functional Design L2 — Stage 1 classification algorithm
    Functional Design L3 — Stage 2 synthesis algorithm
    Functional Design R1 (`business-rules.md`) — two-stage LLM pipeline
    Functional Design R3 — retry policy + total budget
    Functional Design R5 — disclaimer auto-insert
    Functional Design R6 — PII / secret leak guard
    Functional Design R7 — NormalizedItem JSON serialization
    Functional Design R10 — LLM-decided section assignment (category as hint)
    Functional Design R12 — atomic generate_briefing (no partial commits)
    Functional Design E2 (`domain-entities.md`) — ClassificationResult
    Functional Design E3 — SectionPlan
    NFR Requirements AC-1.1 / 1.2 / 1.5 — RetryBudget shared across stages
    NFR Requirements AC-3.1 / 3.5 — failure contract (Briefing-or-BGE,
        no Optional / no partial)
    NFR Requirements AC-6.2 — serialize round-trip PBT
    NFR Requirements AC-6.3 — parse_six_sections round-trip PBT

u83 decomposition (Wave 14)
---------------------------
The former 1918-line god-module is split into cohesive sub-packages:

* :mod:`investo.briefing._core` — classification, section planning, the
  Stage 1/2 LLM orchestration retry loops + ``GenerationPolicy``.
* :mod:`investo.briefing._assembly` — text normalization, summary
  extraction, Stage 2 evidence rendering, prompt-field shaping.
* :mod:`investo.briefing._reader_enhance` — coverage badge, context
  blocks, reader-experience enhancement, macro-lineage signals.

This module retains only :func:`generate_briefing` (a thin orchestrator
that wires the stages in their existing order) plus the public
re-exports below, so every external import path is preserved. Generated
briefing markdown is byte-identical to the pre-refactor pipeline.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date
from pathlib import Path

from investo.briefing import trace_footer
from investo.briefing._assembly.markdown_render import (
    _grouped_stage2_rendered_items as _grouped_stage2_rendered_items,
)
from investo.briefing._assembly.markdown_render import (
    _render_grouped_sections as _render_grouped_sections,
)
from investo.briefing._assembly.markdown_render import (
    _render_required_macro_actuals as _render_required_macro_actuals,
)
from investo.briefing._assembly.markdown_render import (
    _render_unassigned as _render_unassigned,
)
from investo.briefing._assembly.markdown_render import (
    _stage2_retry_feedback as _stage2_retry_feedback,
)
from investo.briefing._assembly.prompt_fields import (
    _render_prompt_url as _render_prompt_url,
)
from investo.briefing._assembly.prompt_fields import (
    _truncate_prompt_field as _truncate_prompt_field,
)
from investo.briefing._assembly.summary_extraction import (
    SummaryHeader as SummaryHeader,
)
from investo.briefing._assembly.summary_extraction import (
    _build_summary_header as _build_summary_header,
)
from investo.briefing._assembly.summary_extraction import (
    _is_unsafe_summary_candidate as _is_unsafe_summary_candidate,
)
from investo.briefing._assembly.summary_extraction import (
    _summary_sentence as _summary_sentence,
)
from investo.briefing._assembly.text_normalize import (
    _clean_summary_line as _clean_summary_line,
)
from investo.briefing._assembly.text_normalize import (
    _split_into_sentences as _split_into_sentences,
)
from investo.briefing._assembly.text_normalize import (
    parse_six_sections,
)
from investo.briefing._core.classification import (
    ClassificationResult,
)
from investo.briefing._core.classification import (
    _extract_braced_object as _extract_braced_object,
)
from investo.briefing._core.classification import (
    _load_classification_payload as _load_classification_payload,
)
from investo.briefing._core.classification import (
    _maybe_flip_inverted_assignments as _maybe_flip_inverted_assignments,
)
from investo.briefing._core.classification import (
    _parse_classification as _parse_classification,
)
from investo.briefing._core.orchestration import (
    MAX_ATTEMPTS,
    serialize_items_for_prompt,
)
from investo.briefing._core.orchestration import (
    GenerationPolicy as GenerationPolicy,
)
from investo.briefing._core.orchestration import (
    _classify as _classify,
)
from investo.briefing._core.orchestration import (
    _is_official_crypto_policy_item as _is_official_crypto_policy_item,
)
from investo.briefing._core.orchestration import (
    _select_llm_candidate_items as _select_llm_candidate_items,
)
from investo.briefing._core.orchestration import (
    _synthesize as _synthesize,
)
from investo.briefing._core.orchestration import (
    _validate_required_macro_mentions as _validate_required_macro_mentions,
)
from investo.briefing._core.section_planning import (
    SectionPlan,
    StoryMetadata,
    StoryTier,
    assign_story_metadata,
    build_section_plan,
    story_identity,
)
from investo.briefing._core.section_planning import (
    _required_macro_item_ids as _required_macro_item_ids,
)
from investo.briefing._reader_enhance.context_render import (
    _render_bundle_context_block as _render_bundle_context_block,
)
from investo.briefing._reader_enhance.context_render import (
    _render_carryover_context_block as _render_carryover_context_block,
)
from investo.briefing._reader_enhance.context_render import (
    _render_carryover_prompt_row as _render_carryover_prompt_row,
)
from investo.briefing._reader_enhance.context_render import (
    _render_lookahead_context_block as _render_lookahead_context_block,
)
from investo.briefing._reader_enhance.context_render import (
    _render_recent_context_block as _render_recent_context_block,
)
from investo.briefing._reader_enhance.context_render import (
    _render_recent_entry as _render_recent_entry,
)
from investo.briefing._reader_enhance.context_render import (
    _render_segment_context as _render_segment_context,
)
from investo.briefing._reader_enhance.coverage_badge import (
    _classify_failure_reason as _classify_failure_reason,
)
from investo.briefing._reader_enhance.coverage_badge import (
    _render_coverage_badge as _render_coverage_badge,
)
from investo.briefing._reader_enhance.coverage_badge import (
    _render_source_outcome_line as _render_source_outcome_line,
)
from investo.briefing._reader_enhance.enhancement import (
    _build_data_limited_body as _build_data_limited_body,
)
from investo.briefing._reader_enhance.enhancement import (
    _enhance_reader_experience as _enhance_reader_experience,
)
from investo.briefing._reader_enhance.enhancement import (
    _render_timestamp_watermark as _render_timestamp_watermark,
)
from investo.briefing._reader_enhance.enhancement import (
    _render_watchlist_callout as _render_watchlist_callout,
)
from investo.briefing._reader_enhance.enhancement import (
    _segment_nav as _segment_nav,
)
from investo.briefing._reader_enhance.lineage import (
    _lineage_body_has_source_link as _lineage_body_has_source_link,
)
from investo.briefing._reader_enhance.lineage import (
    _lineage_body_mentions as _lineage_body_mentions,
)
from investo.briefing._reader_enhance.lineage import (
    _lineage_contains_item as _lineage_contains_item,
)
from investo.briefing._reader_enhance.lineage import (
    _lineage_item_id as _lineage_item_id,
)
from investo.briefing._reader_enhance.lineage import (
    _lineage_routed_segment as _lineage_routed_segment,
)
from investo.briefing._reader_enhance.lineage import (
    _macro_lineage_signals_for_segment as _macro_lineage_signals_for_segment,
)
from investo.briefing.claude_code import (
    ClaudeRunner,
    RetryBudget,
)
from investo.briefing.claude_code import (
    call_claude_code as call_claude_code,
)
from investo.briefing.context import RecentBriefingsContext
from investo.briefing.crypto_indicators import render_crypto_indicator_block
from investo.briefing.disclaimer import DISCLAIMER, DISCLAIMER_CRYPTO, append_disclaimer
from investo.briefing.errors import BriefingGenerationError
from investo.briefing.lineage import (
    MacroLineageTrace,
    build_macro_lineage_traces,
)
from investo.briefing.market_anchor import MarketAnchor
from investo.briefing.prompts import format_crypto_indicator_context
from investo.briefing.segments import (
    MarketSegment,
    SegmentCoverage,
    build_segment_coverage,
    segment_source_outcomes,
)
from investo.briefing.validators import build_post_validation_registry
from investo.briefing.watchlist import (
    WatchlistConfig,
    WatchlistImpact,
    load_watchlist,
    match_watchlist_items,
    render_watchlist_prompt_context,
)
from investo.briefing.watchlist_impact import build_impact_center, public_impact
from investo.models import (
    Briefing,
    BriefingCarryover,
    NormalizedItem,
    SourceOutcome,
)
from investo.models.bundle_context import BundleContext


def _assemble_prompt_context(
    *,
    segment: MarketSegment | None,
    effective_data_limited: bool,
    watchlist_impact: WatchlistImpact,
    items: Sequence[NormalizedItem],
) -> str:
    """Build the shared Stage 1/2 segment-context prompt block.

    Composes the segment-scope instructions, the watchlist prompt
    context (when present), and — crypto only — the deterministic
    indicator grounding table. Returns one string fed to both stages so
    classification and synthesis observe the same scope.
    """
    segment_context = _render_segment_context(segment, data_limited=effective_data_limited)
    watchlist_context = render_watchlist_prompt_context(watchlist_impact)
    if watchlist_context:
        segment_context = f"{segment_context}\n\n{watchlist_context}"
    # u66 — crypto-only deterministic indicator grounding context. The
    # same ``## ⓪-A`` table the publisher renders is injected so Stage 2
    # observes the indicator values (and explicit unavailable rows)
    # without re-deriving or inventing them. Crypto segment only.
    if segment == "crypto":
        crypto_indicator_context = format_crypto_indicator_context(
            render_crypto_indicator_block(items)
        )
        if crypto_indicator_context:
            segment_context = f"{segment_context}\n\n{crypto_indicator_context}"
    return segment_context


def _append_traceability_footer(
    enhanced_markdown: str,
    *,
    llm_items: Sequence[NormalizedItem],
    classification: ClassificationResult,
    body_markdown: str,
) -> str:
    """Append the u32 traceability + signature footer before the disclaimer.

    The footer is ``<details>``-collapsed so it does not crowd the first
    viewport but stays one click away for readers who want to verify the
    signature chain.
    """
    return (
        enhanced_markdown
        + "\n"
        + trace_footer.render_traceability_footer(
            llm_items,
            classification.model_dump(),
            body_markdown,
        )
    )


def _finalize_briefing(
    sections: tuple[str, str, str, str, str, str],
    *,
    full_markdown: str,
    segment: MarketSegment | None,
    target_date: date,
) -> Briefing:
    """Run the leak guard then construct the validated ``Briefing``.

    Single home for the post-validation gate + the ``Briefing(...)``
    construction shared by both the data-limited shortcut and the main
    synthesis path (DRY — previously duplicated verbatim). Raises
    ``BriefingGenerationError(stage="post_validation")`` if the leak
    guard matches (no retry per R6).
    """
    registry = build_post_validation_registry(full_markdown)
    for result in registry.run():
        if result.is_block:
            raise BriefingGenerationError(
                stage="post_validation",
                attempt_count=1,
                last_stderr=None,
                cause=ValueError(result.message),
            )
    return Briefing(
        target_date=target_date,
        market_summary=sections[0],
        key_issues=sections[1],
        sector_flow=sections[2],
        indicators_events=sections[3],
        notable_tickers=sections[4],
        today_watch=sections[5],
        disclaimer=DISCLAIMER_CRYPTO if segment == "crypto" else DISCLAIMER,
        rendered_markdown=full_markdown,
    )


async def generate_briefing(
    target_date: date,
    items: Sequence[NormalizedItem],
    *,
    runner: ClaudeRunner | None = None,
    budget: RetryBudget | None = None,
    segment: MarketSegment | None = None,
    data_limited: bool = False,
    watchlist_config: WatchlistConfig | None = None,
    source_outcomes: Sequence[SourceOutcome] = (),
    recent_context: RecentBriefingsContext | None = None,
    carryover: BriefingCarryover | None = None,
    market_anchors: Sequence[MarketAnchor] = (),
    generation_policy: GenerationPolicy | None = None,
    bundle_context: BundleContext | None = None,
    fact_context_block: str = "",
    archive_root: Path | None = None,
    macro_lineage_all_items: Sequence[NormalizedItem] | None = None,
    macro_lineage_out: list[MacroLineageTrace] | None = None,
) -> Briefing:
    """Atomic two-stage briefing generation (FD L1 + R12).

    Returns a fully-validated ``Briefing`` on success. Raises
    ``BriefingGenerationError`` on LLM-traceable failure (stage = one
    of ``classification`` / ``synthesis`` / ``post_validation`` /
    ``budget``). Programmer errors (``KeyError``, ``ValidationError``
    constructing ``Briefing``, ...) propagate as-is per the failure
    contract — they are NOT wrapped.

    ``runner`` is the ``ClaudeRunner`` test seam (``None`` →
    ``call_claude_code`` uses its default real-subprocess runner).
    ``budget`` is the shared retry budget; constructed fresh if not
    provided.
    """
    policy = generation_policy if generation_policy is not None else GenerationPolicy()
    if budget is None:
        budget = RetryBudget(total_budget_s=policy.total_budget_s)

    coverage = _build_coverage(segment, items, source_outcomes)
    watchlist = load_watchlist() if watchlist_config is None else watchlist_config
    watchlist_impact = _resolve_watchlist_impact(items, watchlist, coverage)
    effective_data_limited = data_limited or (coverage is not None and coverage.status != "normal")

    if segment is not None and effective_data_limited and not items:
        return _generate_data_limited(
            target_date,
            segment=segment,
            items=items,
            coverage=coverage,
            watchlist_impact=watchlist_impact,
            market_anchors=market_anchors,
            archive_root=archive_root,
        )

    segment_context = _assemble_prompt_context(
        segment=segment,
        effective_data_limited=effective_data_limited,
        watchlist_impact=watchlist_impact,
        items=items,
    )
    recent_context_block = _render_recent_context_block(segment, recent_context)
    carryover_context_block = _render_carryover_context_block(carryover)
    bundle_context_block = _render_bundle_context_block(bundle_context, segment=segment)
    llm_items = _select_llm_candidate_items(items, target_date=target_date)
    lookahead_context_block = _render_lookahead_context_block(llm_items)
    classification = await _classify(
        llm_items,
        runner=runner,
        budget=budget,
        policy=policy,
        segment_context=segment_context,
        segment=segment,
    )
    plan = build_section_plan(llm_items, classification, target_date)
    body_markdown = await _synthesize(
        plan,
        runner=runner,
        budget=budget,
        policy=policy,
        segment_context=segment_context,
        recent_context_block=recent_context_block,
        lookahead_context_block=lookahead_context_block,
        carryover_context_block=carryover_context_block,
        fact_context_block=fact_context_block,
        bundle_context_block=bundle_context_block,
        segment=segment,
    )

    # Body markdown is verified to have all 6 sections (by _synthesize's
    # internal parse_six_sections check). Re-parse here to extract the
    # section bodies for the Briefing fields.
    sections = parse_six_sections(body_markdown)
    enhanced_markdown = _enhance_reader_experience(
        body_markdown,
        target_date=target_date,
        segment=segment,
        sections=sections,
        coverage=coverage,
        watchlist_impact=watchlist_impact,
        data_limited=effective_data_limited,
        candidates=llm_items,
        market_anchors=market_anchors,
        archive_root=archive_root,
    )
    _record_macro_lineage(
        macro_lineage_out,
        macro_lineage_all_items=macro_lineage_all_items,
        items=items,
        llm_items=llm_items,
        classification=classification,
        plan=plan,
        segment=segment,
        final_markdown=enhanced_markdown,
    )
    enhanced_markdown = _append_traceability_footer(
        enhanced_markdown,
        llm_items=llm_items,
        classification=classification,
        body_markdown=body_markdown,
    )
    full_markdown = append_disclaimer(enhanced_markdown, segment)
    return _finalize_briefing(
        sections,
        full_markdown=full_markdown,
        segment=segment,
        target_date=target_date,
    )


def _build_coverage(
    segment: MarketSegment | None,
    items: Sequence[NormalizedItem],
    source_outcomes: Sequence[SourceOutcome],
) -> SegmentCoverage | None:
    """Build the per-segment coverage card, or ``None`` (unsegmented)."""
    if segment is None:
        return None
    # source_outcomes coming from the orchestrator span every
    # registered adapter; the reader-facing coverage card only cares
    # about adapters mapped to *this* segment.
    relevant_outcomes = segment_source_outcomes(segment, source_outcomes)
    return build_segment_coverage(segment, items, source_outcomes=relevant_outcomes)


def _resolve_watchlist_impact(
    items: Sequence[NormalizedItem],
    watchlist: WatchlistConfig,
    coverage: SegmentCoverage | None,
) -> WatchlistImpact:
    """Match items against the watchlist and reduce to the public impact.

    u73 — the briefing/Telegram first impression surfaces only
    public-eligible (Direct/Related) impacts. Uncertain/Rejected groups
    stay on the watchlist diagnostics block and never reach this body.
    """
    raw_watchlist_impact = match_watchlist_items(
        items,
        watchlist,
        coverage_status=coverage.status if coverage is not None else None,
    )
    watchlist_center = build_impact_center(raw_watchlist_impact, items=items, config=watchlist)
    return public_impact(watchlist_center)


def _generate_data_limited(
    target_date: date,
    *,
    segment: MarketSegment,
    items: Sequence[NormalizedItem],
    coverage: SegmentCoverage | None,
    watchlist_impact: WatchlistImpact,
    market_anchors: Sequence[MarketAnchor],
    archive_root: Path | None,
) -> Briefing:
    """Build the zero-input data-limited briefing (no LLM call)."""
    body_markdown = _build_data_limited_body(target_date, segment)
    sections = parse_six_sections(body_markdown)
    enhanced_markdown = _enhance_reader_experience(
        body_markdown,
        target_date=target_date,
        segment=segment,
        sections=sections,
        coverage=coverage,
        watchlist_impact=watchlist_impact,
        data_limited=True,
        candidates=items,
        market_anchors=market_anchors,
        archive_root=archive_root,
    )
    full_markdown = append_disclaimer(enhanced_markdown, segment)
    return _finalize_briefing(
        sections,
        full_markdown=full_markdown,
        segment=segment,
        target_date=target_date,
    )


def _record_macro_lineage(
    macro_lineage_out: list[MacroLineageTrace] | None,
    *,
    macro_lineage_all_items: Sequence[NormalizedItem] | None,
    items: Sequence[NormalizedItem],
    llm_items: Sequence[NormalizedItem],
    classification: ClassificationResult,
    plan: SectionPlan,
    segment: MarketSegment | None,
    final_markdown: str,
) -> None:
    """Append macro-lineage traces to ``macro_lineage_out`` when wired."""
    if segment is None or macro_lineage_out is None:
        return
    all_lineage_items = macro_lineage_all_items if macro_lineage_all_items is not None else items
    macro_lineage_out.extend(
        build_macro_lineage_traces(
            _macro_lineage_signals_for_segment(
                all_items=all_lineage_items,
                llm_items=llm_items,
                classification=classification,
                plan=plan,
                segment=segment,
                final_markdown=final_markdown,
            ),
            target_segment=segment,
        )
    )


__all__ = [
    "MAX_ATTEMPTS",
    "ClassificationResult",
    "SectionPlan",
    "StoryMetadata",
    "StoryTier",
    "assign_story_metadata",
    "build_section_plan",
    "generate_briefing",
    "parse_six_sections",
    "serialize_items_for_prompt",
    "story_identity",
]

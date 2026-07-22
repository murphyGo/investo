"""Segment-level reader-format chain (u84 — relocated from orchestrator).

``apply_reader_format_to_segments`` was historically defined inside
``orchestrator/pipeline.py`` as ``_apply_reader_format_to_segments``,
even though every step it performs is a publisher concern: anchor-table
swap, anchor-assertion gate, the u51 reader-format chain, shared-macro
injection, cross-segment lint, crypto-indicator + channel-anchor blocks,
the cross-market cause-map line, the u56 compliance-language gate + first-
viewport short disclaimer, the u72 watchpoint matrix, and the u71 first-
viewport reflow. It calls publisher APIs end-to-end and never reads any
orchestrator/pipeline state.

u84 originally exposed it directly to the orchestrator. u144 now treats the
module as an internal phase-1 collaborator beneath ``publisher.public_document``;
the public function name remains only as a compatibility surface for existing
tests and non-production callers. Its signature speaks publisher/models
vocabulary only and never accepts a ``PipelineContext``.

The collaborator owns text-producing reader transforms and surface repair. It
does not own terminal surface validation; the public-document boundary retains
the fail-close compatibility check until the sealed lifecycle lands.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Final

from investo._internal.surface_quality import repair_surface_artifacts
from investo.models import Briefing, NormalizedItem
from investo.models.bundle_context import BundleContext
from investo.models.market_anchor import MarketAnchor
from investo.models.segments import MarketSegment
from investo.publisher.anchor_assertion_gate import (
    NumericAnchorReconciliationError,
    gate_body_assertions,
)
from investo.publisher.anchor_table import render_anchor_table
from investo.publisher.channel_anchor_block import (
    inject_channel_anchor_block,
    render_channel_anchor_block,
)
from investo.publisher.compliance_language import (
    repair_compliance_language,
    scan_compliance,
)
from investo.publisher.cross_market_cause_map import (
    CauseMapDecision,
    evaluate_cause_map,
    inject_cause_map_line,
)
from investo.publisher.cross_segment_lint import run_all_cross_segment_lints
from investo.publisher.crypto_indicators import (
    inject_crypto_indicator_block,
    render_crypto_indicator_block,
)
from investo.publisher.daily_thesis import (
    assert_distinct_daily_thesis_lines,
    inject_rendered_daily_thesis_line,
    render_daily_thesis_line,
)
from investo.publisher.reader_format import (
    apply_reader_format,
    check_filler_phrase_density,
    check_sentence_ending_diversity,
    emit_first_viewport_disclaimer,
    reflow_first_viewport,
)
from investo.publisher.shared_macro import inject_shared_macro_block
from investo.publisher.watchpoint_matrix import (
    WatchpointRenderResult,
    render_watchpoint_matrix_result,
)

_logger = logging.getLogger("investo.publisher.segment_reader_format")

# Disclaimer enforcement: the chain does NOT touch the disclaimer string
# (regexes anchor on header / sub-heading / number patterns that never
# coincide with ``briefing.disclaimer.DISCLAIMER``). Pinned by
# ``tests/integration/test_briefing_reader_format.py`` and
# ``tests/unit/publisher/test_reader_format.py::test_apply_reader_format_preserves_disclaimer``.
_ANCHOR_LINE_RE: Final = re.compile(r"^>\s*\*\*시장 anchor\*\*:.*?\n", re.MULTILINE)
_SurfaceRepairObserver = Callable[[MarketSegment, str, str], None]
_WatchpointResultObserver = Callable[[MarketSegment, WatchpointRenderResult], None]


@dataclass(frozen=True, slots=True)
class SegmentReaderProducerPlan:
    """One active-pass source for producer payloads and region eligibility."""

    segment: MarketSegment
    anchors: tuple[MarketAnchor, ...]
    anchor_table: str
    shared_macro_block: str | None
    crypto_indicator_block: str
    channel_anchor_block: str
    cause_map: CauseMapDecision
    daily_thesis_line: str


def build_segment_reader_producer_plan(
    segment: MarketSegment,
    *,
    anchors: Sequence[MarketAnchor],
    bundle_context: BundleContext | None,
    items: Sequence[NormalizedItem],
) -> SegmentReaderProducerPlan:
    """Evaluate each conditional phase-one producer exactly once."""

    canonical_anchors = tuple(anchors)
    canonical_items = tuple(items)
    return SegmentReaderProducerPlan(
        segment=segment,
        anchors=canonical_anchors,
        anchor_table=render_anchor_table(canonical_anchors, segment=segment),
        shared_macro_block=(
            bundle_context.shared_macro_block if bundle_context is not None else None
        ),
        crypto_indicator_block=(
            render_crypto_indicator_block(canonical_items)
            if segment == "crypto" and canonical_items
            else ""
        ),
        channel_anchor_block=render_channel_anchor_block(
            segment,
            anchors=canonical_anchors,
            crypto_items=canonical_items if segment == "crypto" else (),
            source_items=canonical_items,
        ),
        cause_map=evaluate_cause_map(bundle_context),
        daily_thesis_line=(
            render_daily_thesis_line(
                bundle_context.daily_thesis_decision,
                segment=segment,
            )
            if bundle_context is not None
            else ""
        ),
    )


def apply_reader_format_to_segments(
    segment_briefings: dict[MarketSegment, Briefing],
    *,
    anchors_by_segment: Mapping[MarketSegment, Sequence[MarketAnchor]],
    bundle_context: BundleContext | None = None,
    items_by_segment: Mapping[MarketSegment, Sequence[NormalizedItem]] | None = None,
    _surface_repair_observer: _SurfaceRepairObserver | None = None,
    _watchpoint_result_observer: _WatchpointResultObserver | None = None,
    _watchpoint_preserved_fragments_by_segment: Mapping[MarketSegment, Sequence[str]] | None = None,
    _apply_surface_repairs: bool = True,
    _producer_plans_by_segment: Mapping[MarketSegment, SegmentReaderProducerPlan] | None = None,
) -> dict[MarketSegment, Briefing]:
    """Replace the u49 anchor line with a table + apply the u51 format chain.

    Returns a fresh dict where every segment's :class:`Briefing` has the
    rewritten ``rendered_markdown``. Empty input → input returned as-is.

    u57 additions (when ``bundle_context`` is non-null):
      * ``## ⓪ 오늘의 매크로`` injection (idempotent) via
        :func:`inject_shared_macro_block`.
      * Cross-segment lint chain — violations are logged at WARN /
        REJECT; the orchestrator does not (yet) auto-demote
        paragraphs (config flag ``INVESTO_LINT_STRICT`` default
        ``demote`` — but the demote rewrite itself is left for a
        follow-up; logging is the audit surface for now per u57
        open-question default).
    """
    if not segment_briefings:
        return segment_briefings
    producer_plans = (
        {
            segment: build_segment_reader_producer_plan(
                segment,
                anchors=anchors_by_segment.get(segment, ()),
                bundle_context=bundle_context,
                items=(items_by_segment or {}).get(segment, ()),
            )
            for segment in segment_briefings
        }
        if _producer_plans_by_segment is None
        else dict(_producer_plans_by_segment)
    )
    if set(producer_plans) != set(segment_briefings) or any(
        plan.segment != segment for segment, plan in producer_plans.items()
    ):
        raise ValueError("producer plans must exactly match segment briefings")
    assert_distinct_daily_thesis_lines(
        {segment: producer_plans[segment].daily_thesis_line for segment in segment_briefings}
    )
    rewritten: dict[MarketSegment, Briefing] = {}
    for segment, briefing in segment_briefings.items():
        producer_plan = producer_plans[segment]
        markdown = briefing.rendered_markdown
        # Step 2 — anchor table swap. Only fires when the segment has at
        # least one anchor; otherwise the deprecated line (or its absence)
        # is left untouched and reader_format handles the rest.
        anchors = producer_plan.anchors
        table = producer_plan.anchor_table
        if table:
            # Idempotent: if the briefing already contains the table
            # (same-day re-run), skip the swap so we don't duplicate.
            # u66 — crypto uses a UTC 24h snapshot header, so check
            # both the legacy equity header and the crypto header.
            if (
                "| 종목 | 종가 | 변동 | 비고 |" in markdown
                or "| 종목 | 스냅샷(UTC 24h) | 구간 변동 | 비고 |" in markdown
            ):
                pass
            else:
                new_markdown, count = _ANCHOR_LINE_RE.subn(f"\n{table}\n", markdown, count=1)
                if count > 0:
                    markdown = new_markdown
                else:
                    # Anchor line is missing from the markdown (e.g.
                    # data-limited segment with no header line). Inject
                    # the table immediately before ``## ① 요약`` so the
                    # reader still gets the quantitative grid.
                    marker = "## ①"
                    idx = markdown.find(marker)
                    if idx != -1:
                        markdown = markdown[:idx] + f"{table}\n" + markdown[idx:]
        # u70 — gate precise body claims on canonical anchor availability.
        # ``anchors`` is the reconciled single-payload set for this segment;
        # its tickers are the only core symbols the body may assert a precise
        # move about. A missing/stale core anchor with an isolated offending
        # sentence is rewritten to a data-limited callout; an un-rewritable
        # contradiction raises ``NumericAnchorReconciliationError`` (caught by
        # the publish-stage handler below alongside the other reader gates).
        anchor_gate = gate_body_assertions(
            markdown,
            segment=segment,
            available_symbols=tuple(a.ticker for a in anchors),
        )
        if anchor_gate.has_blocking_finding:
            blocking = next(finding for finding in anchor_gate.findings if not finding.isolated)
            raise NumericAnchorReconciliationError(
                f"{segment}: precise move claim for {blocking.label} "
                f"({blocking.symbol}) without a canonical anchor: {blocking.sentence!r}"
            )
        markdown = anchor_gate.markdown
        # Step 3 — pure str → str post-format chain.
        markdown = apply_reader_format(markdown, segment=segment)
        # u57 — inject shared macro block + run cross-segment lint.
        if producer_plan.shared_macro_block:
            markdown = inject_shared_macro_block(
                markdown,
                producer_plan.shared_macro_block,
                segment=segment,
            )
        if bundle_context is not None:
            violations = run_all_cross_segment_lints(
                markdown,
                segment=segment,
                ctx=bundle_context,
            )
            for v in violations:
                log_level = logging.WARNING if v.severity == "WARN" else logging.ERROR
                _logger.log(
                    log_level,
                    "%s segment=%s severity=%s",
                    v.kind,
                    segment,
                    v.severity,
                    extra={
                        "segment": segment,
                        "kind": v.kind,
                        "severity": v.severity,
                        "evidence_len": len(v.evidence),
                        "paragraph_len": len(v.paragraph),
                    },
                )
        # u66 — crypto-native indicator block (Fear & Greed, dominance,
        # funding/OI, DeFi, scope-out rows). Crypto segment only; placed
        # after the shared-macro block and before §①. Idempotent.
        markdown = inject_crypto_indicator_block(
            markdown,
            producer_plan.crypto_indicator_block,
        )
        # u74 — channel-depth v2 native-anchor block. Standardises every
        # segment's reader-facing anchor block so missing native anchors
        # render explicit reason rows instead of silent omissions. Consumes
        # the same reconciled ``anchors`` (u49/u55/u67) the table swap used
        # and, for crypto, the u66 indicator raw_metadata contract. Does NOT
        # re-collect or re-rank either — pure presentation. Idempotent.
        markdown = inject_channel_anchor_block(
            markdown,
            producer_plan.channel_anchor_block,
        )
        # u74 Step 4 — cross-market cause-map line, gated by the u57
        # BundleContext shared-macro evidence + cross_market_core_allowed
        # allow-list. Forbidden linkages are omitted (logged), never demoted
        # into prose. Observational wording only.
        for suppressed in producer_plan.cause_map.suppressed:
            _logger.info(
                "cross_market_cause_map.suppressed",
                extra={"segment": segment, "cause_type": suppressed},
            )
        markdown = inject_cause_map_line(markdown, producer_plan.cause_map)
        markdown = inject_rendered_daily_thesis_line(
            markdown,
            producer_plan.daily_thesis_line,
        )
        # u56 — compliance-language gate + first-viewport short disclaimer
        # + retail tone caps. Order: scan first (cheap reject of P0 hits
        # before any post-format I/O), then prepend the short disclaimer
        # so it lands above ``## 한눈에 보기``, then non-blocking tone
        # diagnostics.
        repaired_markdown = repair_compliance_language(markdown, segment)
        if repaired_markdown != markdown:
            _logger.warning(
                "[publish] repaired compliance language segment=%s",
                segment,
            )
            markdown = repaired_markdown
        scan_compliance(markdown, segment)
        # u72 — convert §⑥ bullets into the observational watchpoint matrix.
        # Runs AFTER scan_compliance so the raw bullets are scanned as prose
        # (a table-cell mask would otherwise hide advice wording from the
        # P0 gate); the resulting matrix is observational only and rescanned
        # by the second scan_compliance below.
        watchpoint_result = render_watchpoint_matrix_result(
            markdown,
            segment=segment,
            preserved_fragments=(_watchpoint_preserved_fragments_by_segment or {}).get(segment, ()),
        )
        if _watchpoint_result_observer is not None:
            _watchpoint_result_observer(segment, watchpoint_result)
        markdown = watchpoint_result.markdown
        scan_compliance(markdown, segment)
        markdown = emit_first_viewport_disclaimer(markdown, segment)
        # u71 — reader-first viewport reflow. Runs last in the header
        # chain (after the short disclaimer is positioned) so it sees the
        # final first-viewport shape: it bounds the caution snippet, then
        # moves the compact status chip and raw coverage-badge diagnostics
        # into a <details> block behind the main sections. Pure str -> str,
        # idempotent, disclaimer-preserving.
        markdown = reflow_first_viewport(markdown, segment=segment)
        if _apply_surface_repairs:
            surface_before = markdown
            repaired_surface = repair_surface_artifacts(surface_before)
            if repaired_surface != markdown:
                _logger.warning(
                    "surface_quality.repaired segment=%s",
                    segment,
                    extra={"segment": segment},
                )
                markdown = repaired_surface
            if _surface_repair_observer is not None:
                _surface_repair_observer(segment, surface_before, markdown)
        elif _surface_repair_observer is not None:
            raise ValueError("surface repair observer requires surface repairs")
        check_sentence_ending_diversity(markdown, segment=segment)
        check_filler_phrase_density(markdown, segment=segment)
        if markdown == briefing.rendered_markdown:
            rewritten[segment] = briefing
        else:
            rewritten[segment] = briefing.model_copy(update={"rendered_markdown": markdown})
    return rewritten


__all__ = [
    "SegmentReaderProducerPlan",
    "apply_reader_format_to_segments",
    "build_segment_reader_producer_plan",
]

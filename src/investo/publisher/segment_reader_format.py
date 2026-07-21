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
from typing import Final

from investo._internal.surface_quality import repair_surface_artifacts
from investo.models import Briefing, NormalizedItem
from investo.models.bundle_context import BundleContext
from investo.models.market_anchor import MarketAnchor
from investo.models.segments import MarketSegment
from investo.publisher.anchor_assertion_gate import enforce_anchor_assertions
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
    inject_daily_thesis_line,
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
from investo.publisher.watchpoint_matrix import render_watchpoint_matrix

_logger = logging.getLogger("investo.publisher.segment_reader_format")

# Disclaimer enforcement: the chain does NOT touch the disclaimer string
# (regexes anchor on header / sub-heading / number patterns that never
# coincide with ``briefing.disclaimer.DISCLAIMER``). Pinned by
# ``tests/integration/test_briefing_reader_format.py`` and
# ``tests/unit/publisher/test_reader_format.py::test_apply_reader_format_preserves_disclaimer``.
_ANCHOR_LINE_RE: Final = re.compile(r"^>\s*\*\*시장 anchor\*\*:.*?\n", re.MULTILINE)
_SurfaceRepairObserver = Callable[[MarketSegment, str, str], None]


def apply_reader_format_to_segments(
    segment_briefings: dict[MarketSegment, Briefing],
    *,
    anchors_by_segment: Mapping[MarketSegment, Sequence[MarketAnchor]],
    bundle_context: BundleContext | None = None,
    items_by_segment: Mapping[MarketSegment, Sequence[NormalizedItem]] | None = None,
    _surface_repair_observer: _SurfaceRepairObserver | None = None,
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
    if bundle_context is not None:
        assert_distinct_daily_thesis_lines(
            {
                segment: render_daily_thesis_line(
                    bundle_context.daily_thesis_decision,
                    segment=segment,
                )
                for segment in segment_briefings
            }
        )
    rewritten: dict[MarketSegment, Briefing] = {}
    for segment, briefing in segment_briefings.items():
        markdown = briefing.rendered_markdown
        # Step 2 — anchor table swap. Only fires when the segment has at
        # least one anchor; otherwise the deprecated line (or its absence)
        # is left untouched and reader_format handles the rest.
        anchors = anchors_by_segment.get(segment, ())
        if anchors:
            table = render_anchor_table(anchors, segment=segment)
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
        markdown = enforce_anchor_assertions(
            markdown,
            segment=segment,
            available_symbols=tuple(a.ticker for a in anchors),
        )
        # Step 3 — pure str → str post-format chain.
        markdown = apply_reader_format(markdown, segment=segment)
        # u57 — inject shared macro block + run cross-segment lint.
        if bundle_context is not None:
            markdown = inject_shared_macro_block(
                markdown,
                bundle_context.shared_macro_block,
                segment=segment,
            )
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
        if segment == "crypto" and items_by_segment is not None:
            crypto_items = items_by_segment.get("crypto", ())
            if crypto_items:
                markdown = inject_crypto_indicator_block(
                    markdown,
                    render_crypto_indicator_block(crypto_items),
                )
        # u74 — channel-depth v2 native-anchor block. Standardises every
        # segment's reader-facing anchor block so missing native anchors
        # render explicit reason rows instead of silent omissions. Consumes
        # the same reconciled ``anchors`` (u49/u55/u67) the table swap used
        # and, for crypto, the u66 indicator raw_metadata contract. Does NOT
        # re-collect or re-rank either — pure presentation. Idempotent.
        crypto_block_items = (
            items_by_segment.get("crypto", ())
            if (segment == "crypto" and items_by_segment is not None)
            else ()
        )
        segment_source_items = (
            items_by_segment.get(segment, ()) if items_by_segment is not None else ()
        )
        channel_block = render_channel_anchor_block(
            segment,
            anchors=anchors,
            crypto_items=crypto_block_items,
            source_items=segment_source_items,
        )
        markdown = inject_channel_anchor_block(markdown, channel_block)
        # u74 Step 4 — cross-market cause-map line, gated by the u57
        # BundleContext shared-macro evidence + cross_market_core_allowed
        # allow-list. Forbidden linkages are omitted (logged), never demoted
        # into prose. Observational wording only.
        if bundle_context is not None:
            cause_map = evaluate_cause_map(bundle_context)
            for suppressed in cause_map.suppressed:
                _logger.info(
                    "cross_market_cause_map.suppressed",
                    extra={"segment": segment, "cause_type": suppressed},
                )
            markdown = inject_cause_map_line(markdown, cause_map)
            markdown = inject_daily_thesis_line(
                markdown,
                bundle_context.daily_thesis_decision,
                segment=segment,
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
        markdown = render_watchpoint_matrix(markdown, segment=segment)
        scan_compliance(markdown, segment)
        markdown = emit_first_viewport_disclaimer(markdown, segment)
        # u71 — reader-first viewport reflow. Runs last in the header
        # chain (after the short disclaimer is positioned) so it sees the
        # final first-viewport shape: it bounds the caution snippet, then
        # moves the compact status chip and raw coverage-badge diagnostics
        # into a <details> block behind the main sections. Pure str -> str,
        # idempotent, disclaimer-preserving.
        markdown = reflow_first_viewport(markdown, segment=segment)
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
        scan_compliance(markdown, segment)
        check_sentence_ending_diversity(markdown, segment=segment)
        check_filler_phrase_density(markdown, segment=segment)
        if markdown == briefing.rendered_markdown:
            rewritten[segment] = briefing
        else:
            rewritten[segment] = briefing.model_copy(update={"rendered_markdown": markdown})
    return rewritten


__all__ = ["apply_reader_format_to_segments"]

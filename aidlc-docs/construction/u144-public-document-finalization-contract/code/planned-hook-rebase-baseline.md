# Planned Hook Rebase Baseline

**Unit**: u144 public-document-finalization-contract
**Frozen**: 2026-07-21
**Scope**: planned u130/u131/u133/u134/u135 integration points only

## Boundary rule

Every issue-specific producer remains owned by its planned unit, but any public
Markdown it changes must run in u144 assembly phase 1. Phase 2 public
projection, phase 3 deterministic containment, phase 4 read-only validation,
and the validated SHA-256 seal are terminal. No planned unit may append a
second projection, producer, renderer, or `Briefing.model_copy` mutation after
the seal.

The exact rebases required if a planned unit lands while u144 is active are:

| Unit | Planned owner and current hook | Required u144 rebase | Shared/conflict surface |
|---|---|---|---|
| u130 domestic anchor quarantine v2 | Extend `publisher.anchor_assertion_gate.enforce_anchor_assertions()` with level-claim detection and a consistency sweep; extend `orchestrator.domestic_anchor_quarantine.classify_domestic_anchor_candidate()` and existing pipeline quality metadata with `discontinuous`. | Keep anchor classification/history lookup before `PublicDocumentContext` is built. Run the extended assertion gate exactly once in phase 1, immediately after anchor-table replacement and before reader structure/projection. Pass only the reconciled surviving anchors into the producer plan. Numeric scanning in phase 4 stays read-only; do not add a late gate rewrite. | `anchor_assertion_gate.py`; `domestic_anchor_quarantine.py`; orchestrator context/quality assembly; numeric-gate tests. |
| u131 bounded sentence truncation | Add `_internal.text.bound_at_sentence()`; use it in `reader_format.meaning`, `reader_format.reflow.bound_summary_snippet()` / `reflow_first_viewport()`, and the watchpoint title renderer; extend `_internal.surface_quality` truncation coverage. | All three call sites remain producer algorithms in phase 1: meaning structure before downstream augmentations, watchpoint title bounding inside watchpoint rendering, and first-viewport reflow before projection. The extended surface detector runs only in phase 4. Any new issue code must update `SURFACE_ISSUE_CODES` and the exhaustive disposition table in the same commit. | `_internal/text.py`; `reader_format/meaning.py`; `reader_format/reflow.py`; `watchpoint_matrix.py`; `_internal/surface_quality.py`; policy exhaustiveness test. |
| u133 registry-source impact suppression | Add `SourceSpec.reference_registry`; route registry matches in `briefing.watchlist_impact.build_impact_center()` before `public_impact()`; align prompt and site/Telegram/visual/watchlist-page counts. | Perform registry routing, prompt shaping, and generated callout composition before finalizer entry; only public-eligible impact rows/counts may enter the generated draft. The finalizer seals that reader-visible callout after projection. Telegram consumes the terminal DTO's sealed `watchlist` value rather than re-counting raw matches; no consumer may rewrite sealed Markdown. | `_internal/source_specs.py`; `briefing/watchlist_impact.py`; `briefing/watchlist.py`; `briefing/prompts.py`; `notifier/summary.py`; visual/watchlist-page consumers and tests. |
| u134 callout/diagnostic composition | Repair `_assembly.summary_extraction._build_summary_header()` driver composition, the low-coverage conclusion append site, `reader_format.reflow` source-count composition, and Decimal formatting in `channel_anchor_block` plus the crypto-indicator renderer. | Driver and conclusion text must be complete before the generated draft enters phase 1. Diagnostics, first-viewport, channel-anchor, and crypto-indicator composition all execute in phase 1 before the single projection. Evidence/body-used accounting consumes the composed phase-1 document before seal; no diagnostics cleanup is allowed afterward. | briefing assembly; low-coverage producer; `reader_format/reflow.py`; `channel_anchor_block.py`; crypto-indicator renderer; evidence/quality parser tests. |
| u135 watchpoint current value/fallback | Extend `publisher.watchpoint_matrix`, add `publisher.watchpoint_fallback`, pass reconciled payloads from the orchestrator, synthesize deterministic cards, re-run compliance, and stamp `watchpoint_synthesized`. | Rebase onto u144's typed `render_watchpoint_matrix_result(...) -> WatchpointRenderResult`. Put the plain-data resolution payload in `PublicDocumentContext`/the producer plan, render and compliance-scan cards in phase 1, and merge typed limitation reasons before projection. Because E6 `SegmentFinalizationOutcome` has no diagnostics-metadata field, coordinate an explicit non-public typed producer result if the synthesized count must reach the quality snapshot; do not overload E6 or recover the count from sealed Markdown. | Direct collision in `watchpoint_matrix.py`, orchestrator pipeline/context wiring, typed producer-result ownership, compliance tests, and notification/layout derivation. Explicit coordination is mandatory. |

## Ordering and coordination

1. u130 quarantine decisions and u133 routing are upstream context inputs.
2. u134 generated callout composition precedes u144 assembly.
3. u130 assertion repair, u131 meaning/reflow algorithms, u134 diagnostics and
   table composition, and u135 watchpoint synthesis execute inside phase 1.
4. u144 performs the only public projection, containment, terminal validation,
   E5 notification derivation, and seal.
5. u131 must land before u135's card-title fixtures, as already required by the
   u135 plan. u135 cannot land concurrently with u144 without rebasing onto the
   typed result/context contract above.

This is a documentation baseline; none of the five planned units is implemented
or switched by this checklist item.

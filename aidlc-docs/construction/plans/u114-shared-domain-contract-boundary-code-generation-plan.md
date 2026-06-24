# Code Generation Plan: `u114 shared-domain-contract-boundary`

**Date**: 2026-06-24
**Unit**: u114 shared-domain-contract-boundary
**Stage**: Code Generation
**Status**: Complete
**Source**: 2026-06-24 clean-code architecture review: `models` imports `briefing.time_state`, and sibling units import `briefing` modules as shared vocabulary.
**Estimated Effort**: ~6-8 h
**Dependencies**:
- u83 briefing-pipeline decomposition is complete.
- u84 orchestrator-stage-abstraction is complete; do not add or alter stage abstractions.
- u85 unified-validator-gate-protocol is complete; do not expand validator registry in this unit.
- Existing `models` public API is guarded by model tests.

---

## Problem Statement

The documented dependency direction says `models` is the inner shared layer, `orchestrator` is the composition root, and sibling working units should not import each other. Current code has drifted:

- `models/bundle_context.py` imports `briefing.time_state.TimeState`.
- `publisher`, `notifier`, `visuals`, and `sources` import `briefing.segments`, `briefing.market_anchor`, `briefing.watchlist`, `briefing.watchlist_impact`, or `briefing.extract` for pure shared vocabulary.

That makes `briefing` a de facto shared domain package and weakens the clean-architecture boundary.

## Goal

Promote pure shared contracts to `models` or `_internal`, keep behavior owners in their current packages, preserve compatibility re-exports, and add boundary tests so the same import drift cannot recur.

## Existing Coverage / Deduplication

- `models.segments` already owns `MarketSegment`; extend it rather than adding another segment literal.
- `models.core_fact` already owns `CoreFact`; move only core-fact metadata key formatting there, not source ticker mapping.
- `briefing` keeps behavior-heavy logic such as routing, anchor computation, watchlist matching, and summary validation.
- Legacy `briefing.*` imports must remain valid in this unit.

## Scope Boundary

In scope:
- Promote `TimeState` to `models`.
- Promote segment constants, labels, coverage status/reason/value DTOs to `models`.
- Promote `MarketAnchor`, `OHLCRow`, `AnchorLabel`, and anchor-label lookup to `models`.
- Promote `CORE_FACT_METADATA_PREFIX` and `core_fact_metadata_key()` to `models.core_fact`; keep `core_fact_for_ticker()` source-local.
- Promote watchlist DTOs consumed outside `briefing` to `models`.
- Promote first-viewport extraction marker/helper utilities and canonical summary prefix literals to `_internal`.
- Update cross-unit imports in `publisher`, `notifier`, `visuals`, `sources`, and `models`.
- Add AST boundary regression tests.

Out of scope:
- No segment-routing behavior change.
- No market-anchor computation/rendering behavior change.
- No watchlist matching/grouping behavior change.
- No validator/gate abstraction change.
- No compatibility re-export removal.
- No archive backfill.

## Stage Decision

Functional Design: skip. This is a behavior-preserving architecture-boundary refactor over existing documented contracts.

NFR Requirements: skip. No new dependency, source, secret, network call, runtime budget, or deploy surface.

## Fixed Contracts

| Contract | New canonical owner | Compatibility owner |
|----------|---------------------|---------------------|
| `TimeState` | `models/time_state.py` | `briefing.time_state` re-export |
| `MarketSegment`, segment constants, labels | `models/segments.py` | `briefing.segments` re-export |
| coverage status/reason DTOs | `models/segments.py` or `models/segment_coverage.py` | `briefing.segments` re-export |
| `MarketAnchor`, `OHLCRow`, `AnchorLabel`, `anchor_label()` | `models/market_anchor.py` | `briefing.market_anchor` re-export |
| `CORE_FACT_METADATA_PREFIX`, `core_fact_metadata_key()` | `models.core_fact` | `sources._core_fact_map` re-export |
| watchlist DTOs used outside briefing | `models/watchlist.py` | `briefing.watchlist` / `briefing.watchlist_impact` re-export |
| first-viewport summary prefix literals | `_internal/briefing_extract.py` | `briefing.summary_quality` re-export/import |
| first-viewport extraction helpers | `_internal/briefing_extract.py` | `briefing.extract` re-export |

Behavior ownership stays where it is:

- `briefing.segments` keeps routing, coverage building, and severity policy.
- `briefing.market_anchor` keeps anchor computation/rendering.
- `briefing.time_state` keeps detection logic and regex catalogue.
- `briefing.watchlist` keeps config loading and matching.
- `briefing.watchlist_impact` keeps grouping logic.
- `_internal.briefing_extract` must be pure: no I/O, no clock, no import from working units.
- The first-viewport prefix literals (`CONCLUSION_PREFIX`, `DRIVER_PREFIX`, `CAUTION_PREFIX`, `WATERMARK_PREFIX`, and the summary prefix tuple/fallback map they feed) move with the extraction helpers so `_internal` never imports `briefing.summary_quality`.
- `briefing.summary_quality` keeps validation/repair behavior but imports or re-exports the canonical prefix literals from `_internal.briefing_extract`; do not duplicate the literal strings in both modules.

## Implementation Steps

- [x] Add failing AST boundary tests proving `models -> briefing` and sibling-unit `-> briefing` shared-vocabulary imports are currently present.
- [x] Add `models/time_state.py`; update `models/bundle_context.py`; keep `briefing.time_state` compatibility.
- [x] Promote segment labels and coverage DTOs into `models`; keep `briefing.segments` behavior and compatibility re-exports.
- [x] Add `models/market_anchor.py`; update type/value imports in sources, publisher, notifier, visuals, and orchestrator where appropriate.
- [x] Move core-fact metadata key formatting into `models.core_fact`; keep source-local ticker mapping in `sources._core_fact_map`.
- [x] Add `models/watchlist.py` for DTOs only; keep loading/matching/grouping behavior in `briefing`.
- [x] Add `_internal/briefing_extract.py` for pure extraction markers/helpers and canonical prefix literals; keep `briefing.extract` and `briefing.summary_quality` compatibility.
- [x] Update `models/__init__.py` only for names intended as stable public API.
- [x] Add compatibility tests proving old imports resolve to the same classes/functions.
- [x] Run targeted and full validation.
- [x] Write `aidlc-docs/construction/u114-shared-domain-contract-boundary/code/summary.md`.

## Acceptance Criteria

1. `models/bundle_context.py` no longer imports `investo.briefing`.
2. `publisher`, `notifier`, `visuals`, and `sources` no longer import shared vocabulary from `briefing`.
3. Legacy imports from the affected `briefing.*` modules still work.
4. Segment constants/labels, coverage DTOs, anchors, `TimeState`, core-fact metadata key formatting, watchlist DTOs, first-viewport prefix literals, and first-viewport extraction helpers each have one canonical implementation.
5. `core_fact_for_ticker()` remains source-local.
6. Segment routing, coverage severity, anchor computation, watchlist matching, and summary extraction output remain compatible for existing fixtures.
7. u84 stage abstraction and u85 validation registry are untouched except for import path updates.
8. `mypy src` is clean after import moves.

## Tests / Validation

```bash
uv run --extra dev pytest tests/unit/models tests/unit/briefing/test_segments.py tests/unit/briefing/test_segments_severity.py tests/unit/briefing/test_anchor_label.py tests/unit/briefing/test_numeric_verify.py tests/unit/briefing/test_watchlist.py tests/unit/briefing/test_extract.py tests/unit/briefing/test_summary_quality.py tests/unit/publisher tests/unit/notifier tests/unit/visuals tests/unit/sources/test_stooq_price.py tests/unit/sources/test_yfinance.py
uv run --extra dev ruff check src/investo tests/unit/models tests/unit/briefing tests/unit/publisher tests/unit/notifier tests/unit/visuals tests/unit/sources
uv run --extra dev mypy src
```

## Non-Goals

- No stage abstraction rewrite.
- No validator/gate protocol rewrite.
- No source adapter addition.
- No public reader output change.
- No removal of compatibility re-exports.

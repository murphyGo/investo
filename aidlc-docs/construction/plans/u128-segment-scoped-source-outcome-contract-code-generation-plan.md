# Code Generation Plan: `u128 segment-scoped-source-outcome-contract`

**Date**: 2026-06-29
**Unit**: u128 segment-scoped-source-outcome-contract
**Stage**: Code Generation
**Status**: Complete
**Source**: Clean Code & Software Architecture guide re-audit, 2026-06-29. Focus: explicit contracts, value-level boundaries, and preventing cross-segment data leaks. Converts existing `DEBT-038` into a bounded AIDLC unit.
**Estimated Effort**: ~1.5 h
**Dependencies**:
- u22 source-coverage-transparency is complete; `SegmentCoverage` and source outcomes are public reader-trust inputs.
- u45/u57/u74/u107 routing semantics are complete; do not change item routing.
- u115 source-spec-registry-unification is complete; use existing segment/outcome source registries instead of inventing a new source map.
- u117 model-contract-invariants-and-typed-metadata is complete; keep model invariants explicit.

---

## Problem Statement

`src/investo/briefing/segments.py::build_segment_coverage(...)` accepts `source_outcomes: Sequence[SourceOutcome]`. Its docstring says callers must pre-filter outcomes to the requested segment, but the type shape is identical to a global outcome list. A future refactor can pass all outcomes by mistake, causing another segment's source status to leak into a segment's data-confidence card or markdown reason callout.

The current orchestrator filters correctly, so this is not a live defect. It is a contract visibility issue: the boundary depends on convention rather than type/runtime enforcement.

## Goal

Introduce an explicit segment-scoped source-outcome contract so `build_segment_coverage` cannot silently consume global outcomes.

## Existing Coverage / Deduplication

- u22 owns `SegmentCoverage` and reader-visible source-status transparency.
- u115 owns canonical source specs and source-to-segment metadata. Reuse that registry or existing `segment_source_outcomes` logic.
- u117 owns model invariant hardening; this unit extends the same principle to a cross-function boundary, not to `SourceOutcome` construction itself.
- Do not duplicate u102 source registry completeness tests.

## Scope Boundary

In scope:
- Add an explicit `SegmentScopedOutcomes` contract in `briefing/segments.py` or a leaf model module if the implementation needs wider reuse.
- Provide a builder such as `segment_source_outcomes(report_or_outcomes, segment) -> SegmentScopedOutcomes` or `scope_source_outcomes(source_outcomes, segment) -> SegmentScopedOutcomes`.
- Make the builder validate that each outcome belongs to the target segment using existing canonical routing/spec metadata.
- Change `build_segment_coverage(..., source_outcomes=...)` to accept the scoped contract or to validate and fail loudly when a plain/global sequence is supplied.
- Update orchestrator call sites to construct the scoped object at the boundary where the segment is known.
- Add tests for correct scoping, rejected cross-segment outcomes, shared sources, and CFTC contract-group outcome visibility.

Out of scope:
- No item routing changes.
- No source registry redesign.
- No reader copy changes.
- No `SourceOutcome` model field changes unless strictly required by the scoped builder.
- No change to coverage severity rules.

## Stage Decision

Functional Design: skip. This is a behavior-preserving contract hardening slice over existing source coverage semantics.

NFR Requirements: skip. No new dependency, external source, secret, network call, workflow, runtime budget, or deploy surface.

## Fixed Contracts

### Scoped Outcomes Contract

Preferred shape:

```python
SegmentScopedOutcomes = NewType("SegmentScopedOutcomes", tuple[SourceOutcome, ...])

def scope_source_outcomes(
    source_outcomes: Sequence[SourceOutcome],
    segment: MarketSegment,
) -> SegmentScopedOutcomes:
    ...
```

Rules:
- `scope_source_outcomes` is the only place that converts a global sequence to scoped outcomes.
- It raises `ValueError` on any outcome whose source is not allowed to contribute operational status to the target segment.
- Shared sources remain valid for every configured shared segment.
- CFTC positioning outcome visibility preserves current u107 behavior: source outcome can be visible to the segment(s) where registered, while individual rows still route by `contract_group`.
- Existing no-outcome callers can pass an empty scoped tuple or use a default empty contract.

### Coverage Contract

- `build_segment_coverage` consumes segment-scoped outcomes only.
- If compatibility requires accepting `Sequence[SourceOutcome]` temporarily, it must immediately validate/scope internally and tests must pin rejection of global cross-segment input.
- Error messages should include the target segment and at least the offending source name.

## Implementation Steps

- [x] Add `SegmentScopedOutcomes` and `scope_source_outcomes` using existing source-spec/segment metadata.
- [x] Update `build_segment_coverage` signature and internals to consume the scoped contract.
- [x] Update all call sites, especially orchestrator generation/coverage paths, to scope outcomes explicitly.
- [x] Add unit tests in `tests/unit/briefing/test_segments.py` or a focused new file for happy path, cross-segment rejection, shared-source acceptance, and CFTC visibility.
- [x] Update any tests that currently pass global outcome lists directly to use the builder unless the test intentionally checks rejection.
- [x] Write `aidlc-docs/construction/u128-segment-scoped-source-outcome-contract/code/summary.md`.

## Acceptance Criteria

1. A global mixed-segment source-outcome list cannot silently reach `build_segment_coverage`.
2. Existing correct orchestrator output is unchanged for normal, partial, limited, and failed coverage cases.
3. Shared-source and CFTC outcome semantics remain consistent with u74/u107.
4. The contract is visible in type hints or enforced by a loud runtime guard.
5. No new sibling imports violate the component DAG.

## Tests / Validation

```bash
uv run --extra dev pytest tests/unit/briefing/test_segments.py tests/unit/briefing/test_segments_severity.py tests/unit/orchestrator/test_stage_generate.py tests/unit/orchestrator/test_run_pipeline.py
uv run --extra dev ruff check src/investo/briefing/segments.py src/investo/orchestrator tests/unit/briefing/test_segments.py tests/unit/briefing/test_segments_severity.py tests/unit/orchestrator/test_stage_generate.py tests/unit/orchestrator/test_run_pipeline.py
uv run --extra dev ruff format --check src/investo/briefing/segments.py src/investo/orchestrator tests/unit/briefing/test_segments.py tests/unit/briefing/test_segments_severity.py tests/unit/orchestrator/test_stage_generate.py tests/unit/orchestrator/test_run_pipeline.py
uv run --extra dev mypy src
```

## Non-Goals

- No source-adapter work.
- No source-spec registry redesign.
- No coverage label or severity wording change.
- No archive backfill.

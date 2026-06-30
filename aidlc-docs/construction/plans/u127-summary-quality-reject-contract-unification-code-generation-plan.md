# Code Generation Plan: `u127 summary-quality-reject-contract-unification`

**Date**: 2026-06-29
**Unit**: u127 summary-quality-reject-contract-unification
**Stage**: Code Generation
**Status**: Complete
**Source**: Clean Code & Software Architecture guide re-audit, 2026-06-29. Focus: DRY as knowledge, single authoritative representation, and producer/gate contract consistency. Converts existing `DEBT-047` into a bounded AIDLC unit.
**Estimated Effort**: ~1 h
**Dependencies**:
- u83 briefing-pipeline-decomposition is complete; summary extraction lives in `briefing/_assembly/summary_extraction.py`.
- u119 adapter-contract-ports-cleanup is complete; shared pure contracts may live in `_internal`.
- u108/u112 surface-quality gates are complete; reuse their existing blocking issue contract.

---

## Problem Statement

The first-viewport summary producer and publish gate encode the same reject knowledge in two places:

- `src/investo/briefing/_assembly/summary_extraction.py::_is_unsafe_summary_candidate`
- `src/investo/_internal/summary_quality.py::_validate_summary_value`

Both check marker-only values, meaningful text, unbalanced markdown, surface-quality blockers, heading residue, broken numeric bold, generator residue, dangling truncation, and English/Korean conjunction tails. The docstring says the producer mirrors the gate, but the actual reject list is duplicated. Per the guide, this is duplicated knowledge, not harmless text duplication: a future widening in only one side either makes the producer emit strings the gate rejects or forces unnecessary fallbacks.

## Goal

Single-home the summary reject predicate in the inward pure summary-quality contract, then make the producer and publish gate consume that same predicate.

## Existing Coverage / Deduplication

- u21/u30/u61/u108/u112 already own first-viewport summary repair and surface-quality policy. Do not add a new summary gate.
- `briefing/summary_quality.py` is a compatibility export over `_internal.summary_quality`; keep that import path stable.
- `tests/unit/briefing/test_summary_fidelity.py`, `test_summary_quality.py`, and `test_summary_extraction_surface_quality.py` already cover the current reject shapes. Extend them rather than creating a broad new suite.
- This does not duplicate u100/u112: those own public surface issue detection; this unit only centralizes summary candidate rejection.

## Scope Boundary

In scope:
- Add `is_unsafe_summary_value(value: str) -> bool` to `src/investo/_internal/summary_quality.py`.
- Export the helper through `src/investo/briefing/summary_quality.py` for compatibility.
- Replace `briefing/_assembly/summary_extraction.py::_is_unsafe_summary_candidate` internals with a thin call to the canonical helper while keeping the private function importable for existing tests.
- Refactor `_validate_summary_value` so its reject decisions reuse the same helper or a shared lower-level reason helper.
- Add regression tests proving the producer predicate and publish gate reject the same current shapes.
- Remove dead duplicate regex constants from `summary_extraction.py` when no longer used there.

Out of scope:
- No new summary rules.
- No public markdown output change.
- No prompt change.
- No surface-quality issue-code change.
- No removal of `briefing.summary_quality` compatibility exports.

## Stage Decision

Functional Design: skip. This is a behavior-preserving internal contract cleanup over already implemented summary-quality behavior.

NFR Requirements: skip. No new dependency, external source, secret, workflow, runtime budget, or deploy surface.

## Fixed Contracts

### Canonical Predicate

```python
def is_unsafe_summary_value(value: str) -> bool:
    """Return True when a first-viewport summary value must not be emitted or published."""
```

Rules:
- The helper lives in `_internal.summary_quality`.
- It is pure: no I/O, no env reads, no logging, no mutation.
- It accepts the raw value without the summary prefix.
- It returns `True` for every value that `_validate_summary_value(prefix, value)` would reject due to value shape.
- It returns `False` for clean values currently accepted by `validate_first_viewport_summary`.

### Compatibility Contract

- `briefing.summary_quality.is_unsafe_summary_value` re-exports the helper.
- `briefing._assembly.summary_extraction._is_unsafe_summary_candidate` remains importable and delegates to the helper.
- `SummaryQualityError` messages may remain prefix-specific; do not collapse them into a generic message if existing tests assert detail.

## Implementation Steps

- [x] Add canonical `is_unsafe_summary_value` in `_internal.summary_quality`.
- [x] Rework `_validate_summary_value` to use the canonical predicate without losing existing error specificity where tests cover it.
- [x] Export `is_unsafe_summary_value` from `briefing.summary_quality`.
- [x] Replace duplicated producer reject logic in `_assembly/summary_extraction.py` with the canonical helper.
- [x] Add/extend tests so marker-only, meaningless, unbalanced bold/link, surface blocker, heading residue, broken numeric bold, generator residue, dangling truncation, English conjunction tail, and Korean particle tail are rejected by both paths.
- [x] Write `aidlc-docs/construction/u127-summary-quality-reject-contract-unification/code/summary.md`.

## Acceptance Criteria

1. There is exactly one authoritative summary reject predicate for producer/gate value-shape decisions.
2. `_is_unsafe_summary_candidate` and `validate_first_viewport_summary` stay behavior-compatible for all existing reject and accept fixtures.
3. `briefing.summary_quality` keeps backward-compatible exports.
4. No new dependency direction violates the component DAG.
5. The implementation removes duplicate regex ownership from `summary_extraction.py` unless a regex is still uniquely producer-specific.

## Tests / Validation

```bash
uv run --extra dev pytest tests/unit/briefing/test_summary_fidelity.py tests/unit/briefing/test_summary_quality.py tests/unit/briefing/test_summary_extraction_surface_quality.py
uv run --extra dev ruff check src/investo/_internal/summary_quality.py src/investo/briefing/summary_quality.py src/investo/briefing/_assembly/summary_extraction.py tests/unit/briefing/test_summary_fidelity.py tests/unit/briefing/test_summary_quality.py tests/unit/briefing/test_summary_extraction_surface_quality.py
uv run --extra dev ruff format --check src/investo/_internal/summary_quality.py src/investo/briefing/summary_quality.py src/investo/briefing/_assembly/summary_extraction.py tests/unit/briefing/test_summary_fidelity.py tests/unit/briefing/test_summary_quality.py tests/unit/briefing/test_summary_extraction_surface_quality.py
uv run --extra dev mypy src
```

## Non-Goals

- No LLM prompt edits.
- No new summary fallback language.
- No broader surface-quality refactor.
- No first-viewport layout change.

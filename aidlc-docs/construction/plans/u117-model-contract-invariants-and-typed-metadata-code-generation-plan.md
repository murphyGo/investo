# Code Generation Plan: `u117 model-contract-invariants-and-typed-metadata`

**Date**: 2026-06-24
**Unit**: u117 model-contract-invariants-and-typed-metadata
**Stage**: Code Generation
**Status**: Complete
**Source**: 2026-06-24 model-contract audit: `SourceOutcome` direct construction can bypass documented invariants, and macro decisions parse `raw_metadata` ad hoc.
**Estimated Effort**: ~4-6 h
**Dependencies**:
- u22 source coverage transparency is complete.
- u32 source tier propagation is complete.
- u57 bundle context is complete.
- u59 macro actual priority and lineage is complete.
- u92 source elapsed timing is complete.
- u114 owns shared-domain contract movement; avoid duplicating segment/time-state promotion here.

---

## Problem Statement

Some foundation model contracts are looser than their factories and consumers assume:

- `SourceOutcome.__post_init__` only rejects negative `elapsed_s`, while factories/documentation imply cross-field invariants between `status`, `item_count`, `failure_reason`, and `transient`.
- Macro decision helpers repeatedly parse flat `NormalizedItem.raw_metadata` keys and can silently ignore malformed enum/date/section values.

The flat primitive metadata boundary is correct and should stay. The issue is the missing typed view and validation boundary over metadata that already drives macro behavior.

## Goal

Harden model contracts without changing adapter output shapes:

- enforce `SourceOutcome` cross-field invariants for direct construction and factories
- add a typed macro metadata view over the existing flat `raw_metadata` bag
- route macro helper functions through that typed view
- keep valid prompt payloads and adapter outputs compatible

## Existing Coverage / Deduplication

- `NormalizedItem.raw_metadata` already rejects nested/list/bool metadata.
- `SourceOutcome.ok`, `.zero`, and `.from_failure` already construct valid states.
- `models.macro` already centralizes macro decision helpers.
- This unit deliberately does not narrow broader `BundleContext.segment`, `BundleContext.tz`, or `BundleContext.segments` types. If that model-shape work is desired, it should be a separate unit because it is not required for the `SourceOutcome` and macro metadata gaps here.

## Scope Boundary

In scope:
- Runtime cross-field validation in `SourceOutcome`.
- Tests for invalid direct `SourceOutcome` construction.
- Typed macro metadata parse/view object over existing flat metadata.
- Boundary issue codes for malformed macro enum/date/section metadata.
- Refactor `models.macro` helpers to consume the typed view.

Out of scope:
- No adapter metadata format change.
- No nested `raw_metadata`.
- No new macro source fields unless already emitted.
- No source registry/tier/routing work.
- No public rendering change.
- No historical migration.

## Stage Decision

Functional Design: skip. This is bounded foundation contract hardening; fixed contracts are pinned here.

NFR Requirements: skip. No new dependency, source, secret, network call, workflow change, or runtime cost.

## Fixed Contracts

### SourceOutcome Invariants

`SourceOutcome` must reject impossible states whether created through factories or direct dataclass construction:

| Status | Required | Forbidden / constrained |
|--------|----------|-------------------------|
| `ok` | `item_count > 0` | `failure_reason is None`; `transient is None` |
| `zero` | `item_count == 0` | `failure_reason is None`; `transient is None` |
| `failed` | `item_count == 0`; non-empty `failure_reason`; `transient` is bool | positive item count |

Additional rules:

- `item_count >= 0`
- `elapsed_s is None` or finite and `>= 0`
- `latest_item_at is None` or timezone-aware
- tier/category/status remain closed values
- factories keep current signatures and failure-message sanitization

### Macro Metadata View Contract

Keep `NormalizedItem.raw_metadata` as the adapter boundary. Add a typed view, for example:

```python
@dataclass(frozen=True, slots=True)
class MacroMetadataView:
    event_key: str | None
    status: MacroEventStatus | None
    priority: MacroImportance | None
    label: str | None
    actual: str | None
    prior: str | None
    forecast: str | None
    release_period: str | None
    event_date: date | None
    required_sections: tuple[int, ...]
    issues: tuple[MacroMetadataIssue, ...]
```

Rules:

- Invalid enum values do not silently promote priority/status.
- Invalid dates fall back to existing behavior but emit a bounded issue.
- `required_sections` accepts only existing section ids and reports invalid tokens.
- Macro helpers consume one parsed view instead of re-reading the raw dict independently.
- The view is pure and side-effect-free.

Issue contract:

```python
MacroMetadataIssueCode = Literal[
    "invalid_macro_event_status",
    "invalid_macro_priority",
    "invalid_macro_event_date",
    "invalid_required_section",
]

@dataclass(frozen=True, slots=True)
class MacroMetadataIssue:
    code: MacroMetadataIssueCode
    key: str
    value: str
```

Export `MacroMetadataIssue`, `MacroMetadataIssueCode`, and `MacroMetadataView` from the same module that owns the parser. Existing helper return types stay compatible; callers that need diagnostics use the typed view explicitly.

## Implementation Steps

- [x] Add failing tests for invalid direct `SourceOutcome` construction and valid factory construction.
- [x] Enforce `SourceOutcome` invariants in `models/coverage.py` while keeping frozen/slotted dataclass behavior.
- [x] Add macro metadata view tests for valid explicit metadata, inferred FRED/FOMC metadata, invalid enum values, malformed dates, invalid `required_sections`, and numeric primitive conversion.
- [x] Implement the macro metadata view in `models/macro.py` or a small `models/macro_metadata.py`.
- [x] Implement the fixed `MacroMetadataIssue` dataclass and `MacroMetadataIssueCode` literal list; do not invent a second diagnostics shape.
- [x] Refactor `macro_event_key`, `macro_event_status`, `macro_priority`, `is_required_macro_actual`, `macro_required_sections`, `macro_event_date`, and prompt payload helpers to consume the view.
- [x] Add regression tests for BLS/BEA/FRED/FOMC source fixtures if behavior changes.
- [x] Fix invalid test fixtures rather than loosening the new contract.
- [x] Confirm no adapter needs to emit nested metadata or typed metadata objects.
- [x] Write `aidlc-docs/construction/u117-model-contract-invariants-and-typed-metadata/code/summary.md`.

## Acceptance Criteria

1. Direct `SourceOutcome(...)` construction cannot create invalid `ok`, `zero`, or `failed` states.
2. Existing `SourceOutcome` factories remain compatible for valid call sites.
3. Invalid negative counts, non-finite elapsed seconds, naive latest timestamps, and invalid status/category/tier values are rejected.
4. Macro metadata parsing has one typed view and one issue surface.
5. Valid macro prompt payloads remain semantically identical for existing tests.
6. Invalid macro enum/date/section metadata is surfaced through bounded issues and cannot silently promote required macro actuals.
7. Existing adapters do not need to emit typed metadata objects.

## Tests / Validation

```bash
uv run --extra dev pytest tests/unit/models tests/unit/orchestrator/test_bundle_context.py tests/unit/briefing/test_macro_lineage.py tests/unit/briefing/test_macro_carryover.py tests/unit/sources/test_bls_macro_actuals.py tests/unit/sources/test_bea_macro_actuals.py tests/unit/sources/test_fred_economic_calendar.py
uv run --extra dev ruff check src/investo/models src/investo/briefing tests/unit/models tests/unit/briefing tests/unit/sources
uv run --extra dev mypy src
```

## Non-Goals

- No adapter rewrites.
- No source registry/tier/routing expansion.
- No nested `raw_metadata`.
- No public rendering redesign.
- No historical migration.

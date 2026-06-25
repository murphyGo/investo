# Code Generation Plan: `u119 adapter-contract-ports-cleanup`

**Date**: 2026-06-25
**Unit**: u119 adapter-contract-ports-cleanup
**Stage**: Code Generation
**Status**: Complete (2026-06-25)
**Source**: Clean Code & Software Architecture guide review, 2026-06-25. Focus: dependency direction, information hiding, DIP, and duplicated cross-adapter knowledge.
**Estimated Effort**: ~4-6 h
**Dependencies**:
- u78 module-boundary guard is complete.
- u114 shared-domain-contract-boundary is complete; do not repeat its shared vocabulary moves.
- u116 repo-quality-guardrails-ci is complete; extend its AST guard instead of adding an unrelated scanner.

---

## Problem Statement

The repo now has an explicit adapter boundary test, but it still preserves several sibling adapter imports by allowlist:

- `publisher/briefing_replay.py` imports `investo.briefing.summary_quality`.
- `publisher/crypto_indicators.py` imports `investo.briefing.crypto_indicators`.
- `publisher/verifier.py` and `publisher/weekly_digest.py` import `investo.briefing.disclaimer`.
- `visuals/quality_sparkline.py` imports `investo.briefing.quality_eval`.
- `briefing/numeric_verify.py::aggregate_source_facts` lazily imports `investo.sources._core_fact_map.CORE_FACT_METADATA_PREFIX`.

The allowlist records why those edges exist, but it is not a clean architecture port. The guide's rule is that stable contracts should be owned by an inner/shared module, while adapters depend inward. Today, `briefing` and `sources` still act as contract owners for some publisher/visual/briefing call sites.

## Goal

Promote the remaining cross-adapter contract pieces to `models` or `_internal`, keep behavior owners compatible, and shrink the adapter allowlist so new sibling imports are exceptional rather than normal.

## Existing Coverage / Deduplication

- u114 already moved segment labels, anchors, watchlist DTOs, extraction prefixes, and core-fact key formatting. This unit must not move those again.
- u85 owns the publish-boundary validator registry. This unit may change import ownership of validators, but must not redesign the registry.
- u108 owns reader-facing quality language. This unit must not change public quality wording.
- u116 owns the CI guard location. Extend `tests/unit/_internal/test_module_boundary.py`.

## Scope Boundary

In scope:
- Move pure first-viewport summary validation/repair contracts out of `briefing` into `_internal` while preserving `briefing.summary_quality` compatibility exports.
- Move canonical disclaimer text and pure disclaimer predicates to `_internal.disclaimer`, while preserving existing `briefing.disclaimer` imports.
- Move pure crypto indicator rendering helpers used by both briefing/publisher to `_internal.crypto_indicators` or another inward pure module; keep old briefing imports compatible.
- Move `QualityHistoryRow`/quality-history row parsing shape consumed by visuals/publisher to `models.quality` or `models.quality_history`; keep `briefing.quality_eval` compatibility exports.
- Change `briefing.numeric_verify.aggregate_source_facts` to import `CORE_FACT_METADATA_PREFIX` from `models.core_fact`, not `sources._core_fact_map`.
- Update boundary tests so adapter modules no longer import these contracts from sibling adapters.

Out of scope:
- No rendered markdown change.
- No quality KPI formula change.
- No source adapter behavior change.
- No validator order change.
- No compatibility export removal.
- No broad package rename.

## Stage Decision

Functional Design: skip. This is a behavior-preserving architecture-boundary refactor over existing contracts.

NFR Requirements: skip. No new dependency, source, secret, network call, workflow, runtime budget, or deploy surface.

## Fixed Contracts

| Contract | New canonical owner | Compatibility owner |
|----------|---------------------|---------------------|
| `SummaryQualityError`, `validate_first_viewport_summary`, `repair_first_viewport_summary` | `_internal.summary_quality` | `briefing.summary_quality` |
| `DISCLAIMER`, pure disclaimer predicates/text helpers | `_internal.disclaimer` | `briefing.disclaimer`, `publisher.verifier` |
| pure crypto indicator rendering/parsing helpers shared by briefing/publisher | `_internal.crypto_indicators` | `briefing.crypto_indicators`, `publisher.crypto_indicators` |
| `QualityHistoryRow` and read-only quality-history row DTO | `models.quality_history` | `briefing.quality_eval` |
| `CORE_FACT_METADATA_PREFIX` for numeric verification | `models.core_fact` | `sources._core_fact_map` re-export only |

Rules:
- New canonical modules must not import from `sources`, `briefing`, `publisher`, `notifier`, or `visuals`.
- Compatibility modules may import inward and re-export.
- The AST guard must fail on new module-level sibling imports unless a future plan explicitly documents a behavior call that cannot be inverted.

## Implementation Steps

- [x] Add failing import-boundary assertions for the current remaining adapter-to-briefing and briefing-to-sources contract leaks.
- [x] Add or extend inward modules for summary quality, disclaimer, crypto indicator rendering, and quality-history DTOs.
- [x] Update publisher, visuals, and briefing consumers to import the canonical inward owners.
- [x] Keep compatibility exports in `briefing.summary_quality`, `briefing.disclaimer`, `briefing.crypto_indicators`, and `briefing.quality_eval`.
- [x] Update tests that assert import paths or monkeypatch old owners so compatibility remains explicit.
- [x] Extend `tests/unit/_internal/test_module_boundary.py` to assert that shared-contract sibling edges are gone.
- [x] Run targeted boundary, briefing, publisher, visuals, and model tests.
- [x] Write `aidlc-docs/construction/u119-adapter-contract-ports-cleanup/code/summary.md`.

## Acceptance Criteria

1. `tests/unit/_internal/test_module_boundary.py` no longer needs allowlist entries for pure shared contracts moved by this unit.
2. `publisher` and `visuals` no longer import `briefing` for summary quality, disclaimer, crypto indicator, or quality-history row DTOs.
3. `briefing.numeric_verify` no longer imports from `sources`.
4. Legacy import paths still resolve and return the same objects/functions for compatibility.
5. Public markdown, quality pages, replay findings, and visual sparkline output remain unchanged for existing fixtures.
6. The new inward modules have no I/O, clock, network, subprocess, or adapter-package imports.

## Tests / Validation

```bash
uv run --extra dev pytest tests/unit/_internal/test_module_boundary.py tests/unit/briefing/test_summary_quality.py tests/unit/briefing/test_disclaimer.py tests/unit/briefing/test_numeric_verify.py tests/unit/publisher/test_briefing_replay.py tests/unit/publisher/test_verifier.py tests/unit/publisher/test_crypto_indicators.py tests/unit/visuals/test_quality_sparkline.py tests/unit/models
uv run --extra dev ruff check src/investo tests/unit/_internal tests/unit/briefing tests/unit/publisher tests/unit/visuals tests/unit/models
uv run --extra dev mypy src
```

## Non-Goals

- No prompt rewrite.
- No quality KPI redesign.
- No source registry change.
- No removal of legacy briefing imports.
- No broad module-boundary policy rewrite beyond the moved contracts.

# u60 Shared Macro Evidence Hardening — Code Generation Summary

**Date**: 2026-05-23
**Unit**: u60 shared-macro-evidence-hardening
**Status**: Complete

## Scope

u60 closes the deterministic false positive where the shared macro block rendered:

```markdown
- **미 국채 수익률** — Immunefi to absorb Code4rena bug bounty customers after shutdown decision
```

The bug was not an LLM hallucination. `bundle_context.py` matched bare `UST` inside `customers`, chose that first title as representative evidence, and the publisher injected the already-wrong shared macro block into all segments.

## Delivered

- Replaced bare shared-macro regex scanning with key-specific matcher predicates in `src/investo/orchestrator/bundle_context.py`.
- Added UST context rules:
  - `UST` must be an ASCII token and near rate/yield/curve/tenor context.
  - FRED `DGS10`/`DGS2`/`DGS30`/`DGS3MO` rate series match directly.
  - Korean matching accepts U.S. Treasury wording, not generic Korean treasury wording.
  - `customers`, `trust`, `custody`, `dust`, `UST stablecoin`, and `UST depeg` false positives are rejected.
- Added deterministic candidate ranking by `(source_rank, category_rank, title_rank, source_name, title, segment)`.
- Added UST canonical-source gate: `ust_yield` renders only when valid candidates appear in at least two routed segments and at least one candidate is `treasury-rates` or `fred-macro`.
- Preserved existing routing:
  - `treasury-rates` fan-out remains valid shared evidence.
  - `fred-macro` remains US-only evidence and does not create crypto fan-out.
  - `src/investo/briefing/segments.py` was not changed.
- Added R13-safe diagnostics:
  - `shared_macro.candidate_accepted`
  - `shared_macro.candidate_rejected`
  - `shared_macro.key_suppressed`
  - `shared_macro.representative_selected`
- Kept reader-facing behavior unchanged except corrected evidence. Suppressed keys are silent in markdown.

## Tests

Added/updated tests in:

- `tests/unit/orchestrator/test_bundle_context.py`
- `tests/integration/test_bundle_reconciliation.py`
- existing `tests/unit/publisher/test_shared_macro_block.py` remains green.

Verified behaviors:

- False positives are rejected.
- Real `treasury-rates` / `fred-macro` evidence matches.
- Canonical evidence wins over earlier generic news.
- Non-canonical-only UST candidates are suppressed.
- `fred-macro` alone does not create a shared macro block.
- Oil/FOMC happy paths remain green and boundary false positives are rejected.
- The integration path exercises `NormalizedItem -> compute_bundle_context() -> _apply_reader_format_to_segments()`.
- Shared macro injection remains idempotent.

## Known Affected Archives

Automatic archive backfill was not performed. The known affected generated archives are:

- `archive/domestic-equity/2026/05/2026-05-13.md`
- `archive/us-equity/2026/05/2026-05-13.md`
- `archive/crypto/2026/05/2026-05-13.md`

Backfill should be a separate explicit operation if desired.

## Verification

| Gate | Result |
|------|--------|
| `uv run pytest tests/unit/orchestrator/test_bundle_context.py tests/integration/test_bundle_reconciliation.py tests/unit/publisher/test_shared_macro_block.py -q` | 48 passed |
| `uv run ruff check src/investo/orchestrator/bundle_context.py tests/unit/orchestrator/test_bundle_context.py tests/integration/test_bundle_reconciliation.py` | passed |
| `uv run mypy --strict src/investo/orchestrator/bundle_context.py` | passed |
| `uv run mkdocs build --strict` | passed |

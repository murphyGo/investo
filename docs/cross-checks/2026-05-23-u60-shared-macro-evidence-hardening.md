# Cross-Check: u60 Shared Macro Evidence Hardening

**Date**: 2026-05-23
**Scope**: u60 shared-macro-evidence-hardening
**Overall Compliance**: Complete for the targeted shared macro evidence regression.

## Requirements Trace

| Requirement | Status | Evidence |
|-------------|--------|----------|
| FR-015 UST false-positive rejection | Pass | `customers`, `trust`, `custody`, `dust`, `UST stablecoin`, `UST depeg`, and `UST custody product` regressions are covered in `tests/unit/orchestrator/test_bundle_context.py`. |
| FR-015 real UST evidence preserved | Pass | `UST curve`, `DGS10`, `10Y Treasury yield`, and `미 국채 10년물 수익률` cases remain accepted with canonical evidence. |
| FR-015 canonical source gate | Pass | `ust_yield` requires at least two routed valid segments and at least one `treasury-rates` or `fred-macro` candidate. |
| FR-015 no `fred-macro` fan-out | Pass | `fred-macro` alone does not produce a shared macro block; `segments.py` was not changed. |
| FR-015 representative evidence ranking | Pass | Canonical `treasury-rates` evidence wins over earlier generic news and the Immunefi false-positive title. |
| FR-015 injection idempotency | Pass | Integration test covers computed context through `_apply_reader_format_to_segments()` and a second reader-format pass. |
| R13 secret hygiene | Pass | Candidate diagnostics use bounded/redacted `title_preview`, `title_hash`, and do not log `raw_metadata`. |

## Known Affected Archives

Automatic archive backfill was not performed. The known affected generated archives are:

- `archive/domestic-equity/2026/05/2026-05-13.md`
- `archive/us-equity/2026/05/2026-05-13.md`
- `archive/crypto/2026/05/2026-05-13.md`

This cross-check validates future generation behavior only. Backfill remains a separate explicit operation.

## Verification

| Command | Result |
|---------|--------|
| `uv run pytest tests/unit/orchestrator/test_bundle_context.py tests/integration/test_bundle_reconciliation.py tests/unit/publisher/test_shared_macro_block.py -q` | 48 passed |
| `uv run ruff check src/investo/orchestrator/bundle_context.py tests/unit/orchestrator/test_bundle_context.py tests/integration/test_bundle_reconciliation.py` | passed |
| `uv run mypy --strict src/investo/orchestrator/bundle_context.py` | passed |
| `uv run mkdocs build --strict` | passed |

## Residual Risk

- The public 2026-05-13 archive markdown still contains the already-generated bad line until an explicit backfill is requested.
- u60 intentionally does not add macro actual lineage artifacts; that remains in u59.

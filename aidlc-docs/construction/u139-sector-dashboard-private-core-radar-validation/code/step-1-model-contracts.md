# u139 Code Generation Step 1 — Typed Sector Contracts

**Date**: 2026-07-18
**Status**: Complete
**Plan**: `aidlc-docs/construction/plans/u139-sector-dashboard-private-core-radar-validation-code-generation-plan.md`

## Delivered Surface

- `src/investo/models/sector.py` defines the fixed eleven-sector universe plus SPY
  and the typed E1-E21-aligned manifest, NAV, failure, coverage, diagnostic, bundle,
  metric, regime, rank, record, snapshot, and artifact contracts.
- `src/investo/models/__init__.py` exposes the new public model surface without
  changing the pre-existing briefing `CoverageStatus` contract.
- `src/investo/sector_dashboard/__init__.py` establishes the isolated component
  namespace without importing sources, briefing, publisher, notifier, or any network
  client.
- `tests/unit/models/test_sector.py` pins exact identities, immutable mappings,
  validation failures, JSON round-trip, stable ordering, suppression behavior, and
  decimal quantization with deterministic examples and Hypothesis properties.

## Fixed Invariants

1. Symbol identity and order are closed to `XLC, XLY, XLP, XLE, XLF, XLV, XLI,
   XLB, XLRE, XLK, XLU, SPY`; manifest paths are exact, absolute, unique `.xlsx`
   paths.
2. NAV observations are finite and positive; dates accept only date objects or exact
   `YYYY-MM-DD` strings; series dates are strictly ascending and unique.
3. Parsed results partition all twelve identities, mappings are deeply immutable,
   and bundle coverage counts/as-of state agree with the canonical series.
4. Metrics are either ten-decimal half-even values or an explicit closed missing
   reason. Negative zero is canonicalized.
5. Regime labels must match their two axis states; the 10-bps sensitivity value must
   equal the primary regime; rank inputs and display order are deterministic.
6. Missing sectors, warming-up snapshots, and insufficient snapshots cannot carry
   unsupported metric, regime, sensitivity, or rank claims.
7. Diagnostic metric identifiers are closed tokens, and snapshot fingerprints and
   projection `snapshot_id` values use the `sha256:<64 lowercase hex>` shape.

## Review and Verification

The required independent fresh-eyes review found two High and three Medium contract
issues. All five were fixed, regression-tested, and the re-review returned
`APPROVED` with no remaining Critical, High, or Medium finding.

Local validation at Step 1 closeout:

- `uv run --extra dev pytest tests/unit/models/test_sector.py -q` — 27 passed
- `uv run --extra dev pytest tests/unit/models -q` — 237 passed
- scoped Ruff format/check — passed
- scoped mypy — passed

Step 2 owns the explicit local XLSX adapter, dependency addition, ZIP/XML preflight,
path/privacy boundary, and synthetic workbook tests. No parser, renderer, public
artifact, workflow, source adapter, Pages, or Telegram behavior is introduced here.

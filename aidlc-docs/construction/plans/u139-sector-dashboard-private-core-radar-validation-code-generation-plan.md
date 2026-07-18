# Code Generation Plan: `u139 sector-dashboard-private-core-radar-validation`

**Date**: 2026-07-18
**Unit**: u139 sector-dashboard-private-core-radar-validation
**Stage**: Code Generation
**Status**: In Progress — Step 4 complete
**Source**: FR-022, NFR-008, US-010, and the approved S0-P Application Design
**Estimated Effort**: ~12-18 h after design approval
**Dependencies**: none; u140 is intentionally not a dependency

---

## Stage Decision

- Functional Design: **COMPLETE — approved 2026-07-18**. Binding artifacts are under
  `aidlc-docs/construction/u139-sector-dashboard-private-core-radar-validation/functional-design/`.
- NFR Requirements: **COMPLETE — approved 2026-07-18**. The binding artifacts are under
  `aidlc-docs/construction/u139-sector-dashboard-private-core-radar-validation/nfr-requirements/`.
- Code Generation: **IN PROGRESS**. Steps 1-4 are complete; Step 5 is the next bounded slice.

## Scope Boundary

In scope:

- A fixed universe of `XLC, XLY, XLP, XLE, XLF, XLV, XLI, XLB, XLRE, XLK, XLU`
  plus benchmark `SPY`.
- Local parsing of operator-provided State Street NAV History workbooks.
- Canonical dated NAV series validation and deterministic metric/regime computation.
- Private table/quadrant output to an explicit operator-selected directory outside
  repository public roots.
- Synthetic schema-equivalent fixtures and property-based tests.

Out of scope:

- Network requests, source-adapter registration, provider login automation, and raw
  provider fixture recording.
- `archive/`, `site_docs/`, GitHub Pages, GitHub Actions, publisher, and Telegram
  integration.
- Exchange volume, dollar volume, actual ETF flow, earnings actual, and public-source
  claims.
- Clearing the public OHLCV source gate owned by u140.

## Fixed Application Contracts

1. `sector_dashboard` imports shared `models` but does not import `sources`,
   `briefing`, `publisher`, or `notifier`.
2. Every input bundle declares `input_kind="nav"`, source label, as-of date, and the
   fixed symbol identities; SPY is mandatory.
3. Metric code computes 1D/5D/21D/63D NAV returns, same-window SPY excess returns,
   5D acceleration, 20D realized NAV volatility, and 20D max drawdown from one
   canonical bundle.
4. Regime output is exactly `leading`, `weakening`, `recovering`, `lagging`, or
   `insufficient`; neutral-band parameters live in one versioned policy object.
5. Private rendering labels every value as NAV-based and never presents unsupported
   volume, dollar-volume, flow, or earnings fields.
6. The entrypoint requires explicit input and output paths. It rejects `archive/`,
   `site_docs/`, tracked fixture paths, the repository root, and implicit default
   output.
7. Logs contain only symbol, row count, date range, coverage state, metric-policy
   version, and redacted error class. Workbook paths, cells, and raw rows are absent.

## Planned File Surfaces

- `src/investo/models/sector.py`
- `src/investo/sector_dashboard/__init__.py`
- `src/investo/sector_dashboard/private_input.py`
- `src/investo/sector_dashboard/metrics.py`
- `src/investo/sector_dashboard/regime.py`
- `src/investo/sector_dashboard/private_render.py`
- `scripts/validate_sector_dashboard_private.py`
- focused unit, property, privacy-boundary, and CLI tests under `tests/`

## Implementation Steps

### Step 0 — Fix Functional Design and NFR Contracts

- [x] Define workbook identification, sheet/column matching, Excel date/numeric
  coercion, duplicate resolution, sort order, and cross-symbol as-of rules.
- [x] Define metric formulas, minimum observations, neutral bands, discontinuity
  diagnostics, coverage states, and serialization schema.
- [x] Define private path, log-redaction, fixture, retention, and failure contracts.
- [x] Map each requirement to deterministic unit/PBT/privacy tests.

Contract definition and its NFR review gate were explicitly approved on 2026-07-18.

### Step 1 — Typed sector contracts and universe

- [x] Add fixed symbol and benchmark identities plus NAV series/value constraints.
- [x] Add metric, regime, coverage, provenance, and snapshot models.
- [x] Pin JSON round-trip and stable ordering with property-based tests.

### Step 2 — Local private input adapter

- [x] Parse only explicit local workbook paths without network access.
- [x] Validate schema, ticker identity, dates, NAV domain, duplicates, ordering, and
  as-of alignment.
- [x] Produce redacted, typed failures and synthetic workbook tests.

### Step 3 — Metric and regime engine

- [x] Implement the fixed return, excess, acceleration, volatility, and drawdown
  formulas as pure functions.
- [x] Implement the versioned regime policy and insufficient-data behavior.
- [x] Cover equal series, sparse series, discontinuities, neutral bands, and
  deterministic repeat execution.

### Step 4 — Private renderer and manual runner

- [x] Render a compact summary, quadrant/table, coverage, and diagnostics with
  mandatory NAV/private labels.
- [x] Reject public/tracked output paths before reading source bytes.
- [x] Verify output contains no raw row, provider payload, exchange-volume, flow, or
  public-source claim.

### Step 5 — Quality gates and handoff evidence

- [ ] Run focused tests, full pytest, ruff, format check, mypy strict, no-paid guard,
  and `mkdocs build --strict`.
- [ ] Confirm existing briefing/public artifacts remain unchanged, including an
  explicit `git diff` sentinel scan over `archive/`, `site_docs/`, `mkdocs.yml`, and
  `.github/workflows/` after the synthetic/manual run.
- [ ] Record a synthetic-input run and an operator-local smoke result without
  committing the input or private output.

## Acceptance Evidence

- Requirement-to-test matrix for every u139 Definition of Done item.
- Deterministic snapshot JSON hash from repeated synthetic runs.
- Negative path tests for every forbidden repository/public output location.
- Explicit statement that a successful u139 run does not authorize public Pages
  output and does not change u140 status.

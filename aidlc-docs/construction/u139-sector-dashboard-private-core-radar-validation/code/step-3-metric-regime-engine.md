# u139 Code Generation Step 3 — Metric and Regime Engine

**Date**: 2026-07-18
**Status**: Complete
**Plan**: `aidlc-docs/construction/plans/u139-sector-dashboard-private-core-radar-validation-code-generation-plan.md`

## Delivered Surface

- `src/investo/sector_dashboard/metrics.py` implements Decimal-first NAV returns,
  SPY excess returns, adjacent non-overlapping 5D acceleration, 20D annualized NAV
  log-return volatility, 20D NAV max drawdown, descending tied midranks,
  weight-renormalized relative rank, and immutable snapshot assembly.
- `src/investo/sector_dashboard/regime.py` implements the primary 10-bps policy,
  0/5/15/20-bps sensitivity policies, closed-band two-axis hysteresis, and the
  five-value regime result contract.
- `src/investo/sector_dashboard/__init__.py` exports the pure computation surface
  without importing sources, briefing, publisher, notifier, orchestrator, network,
  filesystem, or rendering code.
- `tests/unit/sector_dashboard/test_metrics.py` and `test_regime.py` cover the fixed
  vectors, failure states, integration paths, and Hypothesis properties.

## Fixed Numeric and Availability Contracts

1. Simple ratios, excess, drawdown, midranks, weight renormalization, and rank use a
   local Decimal context with precision 34 and half-even rounding. Snapshot model
   values remain quantized to ten decimal places.
2. Binary float is confined to daily `log`, sample standard deviation, and
   `sqrt(252)` for realized volatility; the finite result returns through
   `Decimal(repr(value))`. A fixed golden vector pins that boundary.
3. Return/excess horizons require every sector observation on the corresponding
   `h+1` SPY-grid dates. Volatility and drawdown require all 21 dates. Missing points
   return `sector_date_missing`; short benchmark history returns
   `insufficient_history`; nothing is interpolated or forward-filled.
4. Five-day acceleration uses only exact SPY-grid offsets 0, 5, and 10 and subtracts
   the immediately preceding non-overlapping 5D excess window from the current one.
5. `warming_up` exposes only available 1D/5D return and excess values. Missing
   sectors and `insufficient` coverage suppress every metric, regime, and rank claim.

## Regime and Rank Contracts

- Historical regime observations require a complete 22-point 21D strength window
  plus the exact three acceleration endpoints. The two axis signs carry through the
  closed neutral band; the first eligible zero initializes negative.
- The primary policy is `sector-regime-v1` at 10 bps. The sensitivity matrix reruns
  the same history at 0/5/10/15/20 bps and keeps the 10-bps result identical to the
  primary result.
- `relative_rank_v1` uses 5D/21D/63D excess-return percentiles with
  0.20/0.50/0.30 weights, requires at least two eligible horizons and eight scored
  sectors, and renormalizes missing horizon weights.
- Rank ordering consumes unquantized excess values so ten-decimal snapshot storage
  cannot create an artificial tie. Tied percentiles share their occupied midrank;
  display ties remain fixed-universe deterministic.

## Review and Verification

The required independent review found one blocking full-window discontinuity issue
in the current and historical strength paths and two missing AC-4.8 property-test
proofs. The calculation paths and regressions were fixed, acceleration and tied
midrank PBTs were added, and final re-review returned `APPROVED` with no remaining
Critical, High, or Medium finding.

Local validation:

- focused Step 3 metric/regime tests — 29 passed
- combined Step 1-3 model/adapter/engine tests — 92 passed
- scoped Ruff check and format check — passed
- scoped strict mypy — passed
- `git diff --check` — passed

Step 4 owns private JSON/Markdown rendering, path rejection, transaction/recovery,
and the manual runner. This step adds no workbook read, repository/public output,
source adapter, scheduled pipeline, Pages, Telegram, or u140 public-source behavior.

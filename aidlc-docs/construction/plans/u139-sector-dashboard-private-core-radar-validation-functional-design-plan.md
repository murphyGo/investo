# Functional Design Plan: `u139 sector-dashboard-private-core-radar-validation`

**Date**: 2026-07-18
**Stage**: Functional Design
**Status**: Complete — approved 2026-07-18
**Parent code plan**: `aidlc-docs/construction/plans/u139-sector-dashboard-private-core-radar-validation-code-generation-plan.md`
**Requirements**: FR-022, NFR-002, NFR-003, NFR-006, NFR-008, US-010

## Context Loaded

- Product and S0 decisions for the US sector dashboard
- C6 `sector_dashboard` Application Design and service/dependency contracts
- u139 unit definition, story map, dependency map, and code-generation plan
- Current project module boundaries and private/public artifact policy
- State Street NAV History spike facts: 12/12 workbooks, columns `Date | NAV |
  Shares Outstanding | Total Net Assets`, at least 2,030 rows per symbol

## Decisions Already Fixed

The following decisions are binding and are not reopened by this plan:

- Universe is exactly 11 Select Sector SPDR ETFs plus benchmark SPY.
- Input is operator-provided local XLSX; u139 performs no network request.
- Only NAV-derived return, excess return, acceleration, realized volatility, and
  drawdown are supported.
- Exchange volume, dollar volume, actual flow, earnings actual, and public-source
  claims are absent.
- Raw workbooks and daily derived rows never enter git, fixtures, logs, `archive/`,
  `site_docs/`, GitHub Actions, Pages, or Telegram.
- Rendering is private-only and labels every applicable value as NAV-based and
  `실제 시장 OHLCV 아님`.
- u139 completion does not clear the u140 public price-data gate.

## Plan Steps

- [x] Load requirements, stories, Application Design, unit contracts, source spike,
  project rules, and prior trust-boundary design patterns.
- [x] Separate already-approved decisions from implementation-affecting Functional
  Design ambiguities.
- [x] Create bounded questions covering input identity, as-of alignment, acceleration,
  regime sensitivity, coverage, and private artifacts.
- [x] Collect and validate every `[Answer]:` response.
- [x] Resolve contradictions or create a dedicated clarification file.
- [x] Author `functional-design/business-logic-model.md`.
- [x] Author `functional-design/business-rules.md`.
- [x] Author `functional-design/domain-entities.md`.
- [x] Author `functional-design/frontend-components.md` for the private report
  information hierarchy and state behavior.
- [x] Validate markdown, fixed identifiers, formulas, state transitions, public/private
  boundaries, and contextless implementation readiness.
- [x] Record completion in `aidlc-state.md` and `audit.md`, then present the required
  two-option stage closeout.

## Functional Design Questions

Please fill every `[Answer]:` tag with one letter. The first option is the recommended
contract where applicable.

### Question 1 — Workbook identity contract

How should the operator bind the 12 local workbooks to canonical tickers?

A) Require one explicit, untracked JSON manifest mapping every ticker to an absolute
workbook path; reject missing, duplicate, unknown, and relative-path entries.
B) Require twelve repeated CLI arguments in the form `--input TICKER=PATH`; reject
missing, duplicate, and unknown tickers.
C) Scan one explicit directory for the exact State Street filename convention and
infer tickers from filenames.
D) Other (please describe after the `[Answer]:` tag below).

[Answer]: A

### Question 2 — Cross-symbol as-of alignment

When the newest NAV date is not identical across all 12 workbooks, what should the
canonical bundle do?

A) Fail the calculation and render only a redacted alignment diagnostic; no regime or
rank is produced until all 12 newest dates match.
B) Truncate every series to the newest date shared by all 12 symbols when the latest
date drift is at most three calendar days; fail beyond that limit.
C) Allow mixed as-of dates and attach per-symbol freshness badges.
D) Other (please describe after the `[Answer]:` tag below).

[Answer]: A

### Question 3 — Five-day acceleration formula

Which deterministic definition should `nav_relative_acceleration_5d` use?

A) Current 5-trading-day SPY excess return minus the immediately preceding,
non-overlapping 5-trading-day SPY excess return.
B) Current 5-trading-day SPY excess return minus current 21-trading-day SPY excess
return.
C) Least-squares slope of daily SPY-relative NAV returns over the latest five trading
days.
D) Other (please describe after the `[Answer]:` tag below).

[Answer]: A

### Question 4 — Regime neutral-band validation

How should the private prototype handle the product plan's provisional `±0.10%p`
neutral band?

A) Use 10 basis points as the primary v1 classification and include a private
sensitivity comparison for 0/5/10/15/20 basis points so the policy can be reviewed
before any public implementation.
B) Fix 10 basis points immediately and omit the sensitivity comparison.
C) Use a zero band so only the signs of 21D excess return and 5D acceleration matter.
D) Other (please describe after the `[Answer]:` tag below).

[Answer]: A

### Question 5 — Coverage and warming-up behavior

How closely should private validation mimic the future public coverage behavior?

A) Exercise the full state machine: `normal` for 11 sectors + SPY with at least 22
common observations, `partial` for 8-10 sectors + SPY with at least 22, `warming_up`
for at least 8 sectors + SPY with 6-21, and `insufficient` otherwise; unavailable 63D
metrics remain explicit nulls until 64 observations exist.
B) Require all 12 symbols and at least 64 common observations for every run; any gap
is a terminal validation error.
C) Require SPY plus any available sectors and calculate every metric independently
without a bundle-level coverage state.
D) Other (please describe after the `[Answer]:` tag below).

[Answer]: A

### Question 6 — Private artifact set

Which outputs should one successful private validation run create?

A) Deterministic `snapshot.json` plus reader-facing `report.md`; the report contains a
summary, sector table, textual quadrant, coverage, sensitivity, and diagnostics, with
no standalone HTML/SVG asset.
B) Deterministic `snapshot.json` only; inspect it with external tools.
C) `snapshot.json`, `report.md`, and a generated SVG quadrant card.
D) Other (please describe after the `[Answer]:` tag below).

[Answer]: A

## Answer Validation

**Recorded from user**: "전부 권장안으로" on 2026-07-18.

- Q1-Q6 are all resolved as option A.
- No clarification file is required.
- Q1, Q2, and Q5 are compatible under the following fixed interpretation: the
  manifest must name all 12 symbols; per-file parse failures can reduce available
  coverage, but every successfully parsed series must share one latest NAV date.
  An as-of mismatch among successful series blocks all metric/regime/rank output.
- Functional Design artifacts are ready for review. NFR Requirements remains the
  next required stage after explicit approval.

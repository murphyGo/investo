# Session Log: 2026-07-22 - u140 - Source Qualification Step 0 MIAX Pearl Equities Historical Data

## Overview

- **Unit**: u140 sector-dashboard-public-ohlcv-source-qualification
- **Stage**: Source qualification before Construction
- **Iteration**: Step 0 candidate fact sheet — MIAX Pearl Equities Historical Market Data
- **Result**: Reject under current published cost, delivery, and rights terms; u140 remains blocked

## Work Summary

Committed and pushed the preceding direct IEX HIST Step 0 slice as `2a146f0`.
The isolated commit was rebased onto two concurrent generated-briefing commits before
push, preserving exactly seven u140 documentation files while leaving the original
dirty worktree and unrelated generated/settings/worktree artifacts untouched.

Twelve Data was initially considered as the next candidate, then rejected as a new
iteration during local deduplication because the S0 decision, product plan, story map,
and unit-of-work already explicitly classify its individual/free plans as unsuitable
for public redistribution/display. No duplicate Twelve Data artifact was created.

Reviewed MIAX Pearl Equities' official historical-data product, ToM/DoM field page,
market-data and vendor-agreement page, current fees page, and May 1, 2026 fee schedule.
The feeds include venue quotes, last sales or executions, cancellations, and status
messages and offer up to the most recent six months, which is technically deep enough
for 63 trading days.

The binding cost and delivery gates fail. Historical data costs USD 500 for each
MIAX-provided eight-terabyte USB device and is not a public API or automated download.
Direct receipt requires an Exchange Data Agreement and request schedule; external
distribution has separate requirements and fees. Aggregated daily values would still
be MIAX-only, require binary decoding and cancellation handling, and lack a native
split/dividend-adjusted series.

No request form or agreement was submitted. No purchase, device, payload, exact-symbol,
decoder, continuity, freshness, adjustment, local-runner, or GitHub Actions probe was
performed, and no provider data was retained.

## Decision

| Question | Answer |
| --- | --- |
| Free 63+ history | Fail: six months is sufficient in depth, but access costs USD 500 per physical device |
| Automated daily OHLCV / bounded request shape | Fail: proprietary ToM/DoM feed on up to an 8TB USB device, requiring binary decoding and aggregation |
| Exact 12-symbol/freshness evidence | Unproven; paid physical access blocks exact trade-continuity and usable T+1 timing probes |
| Explicit free public derived-display rights | Fail; exchange agreement and separate external-distribution requirements/fees apply |
| Truthful price/volume semantics | Fail for the current contract; resulting bars are MIAX-only, not consolidated |
| Existing source overlap | None; no MIAX feed, agreement, device ingest, decoder, adapter, fixture, dependency, or workflow exists |
| Disposition | `reject under current published cost, delivery, and rights terms` |

## Files Changed

- Added the dated MIAX Pearl Equities source fact sheet.
- Updated the u140 plan and state/audit records.
- Added the candidate to the product-plan disposition matrix and primary references.
- Updated the story map with the paid physical-delivery and venue-only boundary.

## Next Boundary

u140 stays blocked after Step 0 iterations 1-20. MIAX Pearl Equities Historical Market
Data may be reconsidered only if a permanently free automated daily-bar surface and
explicit free public derived-display rights become available. Otherwise the next
bounded action is Step 0 for one non-duplicate candidate; local and five-run GitHub
Actions probes remain gated.

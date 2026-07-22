# Session Log: 2026-07-22 - u140 - Source Qualification Step 0 MEMX MEMOIR Historical Data

## Overview

- **Unit**: u140 sector-dashboard-public-ohlcv-source-qualification
- **Stage**: Source qualification before Construction
- **Iteration**: Step 0 candidate fact sheet — MEMX MEMOIR Historical Data
- **Result**: Reject for current public MVP cost/rights certainty and metric fitness; u140 remains blocked

## Work Summary

Committed and pushed the preceding Cboe DataShop Equity EOD Summary Step 0 slice as
`3667395`, preserving exactly seven u140 documentation files while leaving the
original dirty worktree and unrelated generated/settings/worktree artifacts untouched.

Reviewed MEMX's official equities FAQ, current Rulebook and fee schedule, user manual,
market-data document library, Market Data Agreement boundary, and Market Data
Policies. MEMOIR Historical Data provides historical/prior-day versions of MEMX
Depth, Top, and Last Sale through cloud APIs. The underlying products contain venue
orders, quotes, executions, cancellations, corrections, and administrative messages;
they are not ticker-filtered daily OHLCV.

The binding evidence and metric gates fail. A market-data-only subscriber must execute
an agreement and request connectivity. Derived-data distribution must be declared in
an Exchange Data Order Form/System Description and approved; the policy's statement
that derived use is generally non-fee-liable remains subject to feed-specific
exceptions. The current schedule separately charges USD 2,000/month for external or
Digital Media Enterprise distribution of Top or Last Sale, and publishes no anonymous
permanent-free historical entitlement.

Even if MEMX approved a fee-free derived configuration, aggregated values would be
MEMX-only rather than consolidated ETF activity and would require protocol decoding,
execution correction handling, and a separate corporate-action source. Exact retained
history, the 12-symbol trade continuity, posting SLA, endpoint/auth/quota, and payload
size were therefore not probed. No agreement, order form, connectivity request,
account, credential, provider data, fixture, local probe, or GitHub Actions probe was
created or retained.

## Decision

| Question | Answer |
| --- | --- |
| Free 63+ history | Fail as published evidence: historical cloud delivery exists, but no anonymous permanent-free entitlement or retained range is stated |
| Structured daily OHLCV | Fail: prior-day raw Depth/Top/Last Sale messages require decoding, correction handling, and daily aggregation |
| Exact 12-symbol/freshness evidence | Unproven; broad NMS coverage and prior-day products do not prove daily trades or an at-most-36-hour posting SLA |
| Explicit free public derived-display rights | Fail; agreement, approved Order Form/System Description, and feed-specific fee review are required |
| Truthful price/volume semantics | Fail for the current radar contract; resulting bars are MEMX-only, not consolidated |
| Existing source overlap | None exact; direct IEX and MIAX are separate venue-feed candidates |
| Disposition | `reject for current public MVP cost/rights certainty and metric fitness` |

## Files Changed

- Added the dated MEMX MEMOIR Historical Data source fact sheet.
- Updated the u140 plan and state/audit records.
- Added the candidate to the product-plan disposition matrix and primary references.
- Updated the story map with the agreement/approval, fee, and venue-only boundary.

## Next Boundary

u140 stays blocked after Step 0 iterations 1-22. MEMX may be reconsidered only with a
published permanent-free historical entitlement, explicit public derived-display
approval, and an accepted MEMX-only metric label. Otherwise the next bounded action is
Step 0 for one non-duplicate candidate; local and five-run GitHub Actions probes remain
gated.

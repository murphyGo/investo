# Session Log: 2026-07-22 - u140 - Source Qualification Step 0 NYSE Daily TAQ

## Overview

- **Unit**: u140 sector-dashboard-public-ohlcv-source-qualification
- **Stage**: Source qualification before Construction
- **Iteration**: Step 0 candidate fact sheet — NYSE Daily TAQ
- **Result**: Reject under current published pricing, licensing, and operational budget; u140 remains blocked

## Work Summary

Committed and pushed the preceding MEMX MEMOIR Historical Data Step 0 slice as
`bf4e910`, preserving exactly seven u140 documentation files while leaving the
original dirty worktree and unrelated generated/settings/worktree artifacts untouched.

Reviewed NYSE's official Daily TAQ product catalog, historical-data overview, current
pricing schedule, two client specifications, complete market-data policy package, and
contract/policy hub. Daily TAQ is a technically exact consolidated source: it contains
CTA/UTP all-trades, all-quotes, and NBBO files for U.S.-listed securities, delivers
previous-day data, and retains history from 1993.

The binding free/public-rights gates nevertheless fail. The commercial ongoing
subscription costs USD 3,800/month and requires a 12-month minimum; older history is
separately charged. Client access requires an agreement, purchase order, approval,
and credentials. External redistribution of historical data requires a specific NYSE
license and relevant fee, so no permanent-free public derived-display entitlement is
published.

The delivery shape also fails the bounded runner contract. This is not a 12-symbol
daily-bar API: representative whole-market daily files are approximately 649 MB for
Trades, 17 GB for Quotes, and 2.2 GB for NBBO. Reconstructing OHLCV would also require
sale-condition and cancel/correction handling plus separate corporate actions. No
agreement, order, account, credential, sample, provider payload, fixture, local probe,
or GitHub Actions probe was created or retained.

## Decision

| Question | Answer |
| --- | --- |
| Free 63+ history | Fail: the range is deep but subscription and back history are paid |
| Structured daily OHLCV | Fail for direct use: consolidated raw tick files require aggregation and normalization |
| Exact 12-symbol/freshness evidence | Product scope strongly indicates coverage and T+1 freshness, but no purchased payload or measured run exists |
| Explicit free public derived-display rights | Fail: external historical redistribution requires a specific license and fee |
| Truthful price/volume semantics | Provisional technical pass from consolidated trades if corrections/sale conditions are handled |
| Bounded GHA operation | Fail: whole-market daily files are hundreds of MB to tens of GB |
| Existing source overlap | None exact; prior exchange and EOD reviews cover different products |
| Disposition | `reject under current published pricing, licensing, and operational budget` |

## Files Changed

- Added the dated NYSE Daily TAQ source fact sheet.
- Updated the u140 plan and state/audit records.
- Added the candidate to the product-plan disposition matrix and primary references.
- Updated the story map with the cost, licensing, consolidated-data, and file-scale boundary.

## Next Boundary

u140 stays blocked after Step 0 iterations 1-23. NYSE Daily TAQ may be reconsidered
only with a permanent-free entitlement, explicit public derived-display rights, and a
bounded ticker-filtered delivery surface. Otherwise the next bounded action is Step 0
for one non-duplicate candidate; local and five-run GitHub Actions probes remain gated.

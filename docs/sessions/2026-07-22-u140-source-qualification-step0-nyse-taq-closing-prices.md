# Session Log: 2026-07-22 - u140 - Source Qualification Step 0 NYSE TAQ Closing Prices

## Overview

- **Unit**: u140 sector-dashboard-public-ohlcv-source-qualification
- **Stage**: Source qualification before Construction
- **Iteration**: Step 0 candidate fact sheet — NYSE TAQ Closing Prices
- **Result**: Reject under current published cost, public-rights, and volume-semantics terms; u140 remains blocked

## Work Summary

Committed and pushed the preceding NYSE Daily TAQ Step 0 slice as `16e833d`,
preserving exactly seven u140 documentation files while leaving the original dirty
worktree and unrelated generated/settings/worktree artifacts untouched.

Reviewed NYSE's official TAQ Closing Prices catalog, current client specification,
historical pricing schedule, complete policy package, and contract/policy hub. The
product provides pre-aggregated daily Open/High/Low/Last, Total Volume, closing
bid/ask, and symbol fields for each NYSE group exchange. NYSE Arca history begins in
December 2008 and current files are typically available around 10 p.m. Eastern.

This avoids Daily TAQ's raw-tick file scale, but the binding gates still fail. Access
costs USD 500/month under a 12-month minimum, older history is separately charged,
and external historical redistribution requires a specific NYSE license and relevant
fee. The field contract also defines Total Volume as volume on that exchange, so the
required ETF values would represent NYSE Arca venue activity rather than consolidated
U.S. OHLCV.

No dashboard registration, purchase, agreement, entitlement, credential, sample,
provider payload, fixture, local probe, or GitHub Actions probe was created or
retained. Exact ticker rows, adjustment behavior, file size, and measured freshness
remain unprobed because cost, rights, and metric fitness fail first.

## Decision

| Question | Answer |
| --- | --- |
| Free 63+ history | Fail: NYSE Arca history is deep, but access is USD 500/month with a 12-month minimum |
| Structured daily OHLCV | Technical pass as a pre-aggregated exchange summary |
| Exact 12-symbol/freshness evidence | Strongly indicated and documented daily, but no entitled/sample payload or measured run exists |
| Explicit free public derived-display rights | Fail: external historical distribution needs a specific license and fee |
| Truthful price/volume semantics | Fail for the current contract: fields are NYSE Arca venue-local, not consolidated |
| Bounded GHA operation | Promising but unprobed; no raw-tick decoding is needed |
| Existing source overlap | None exact; NYSE Daily TAQ is a separate raw consolidated product |
| Disposition | `reject under current published cost, public-rights, and volume-semantics terms` |

## Files Changed

- Added the dated NYSE TAQ Closing Prices source fact sheet.
- Updated the u140 plan and state/audit records.
- Added the candidate to the product-plan disposition matrix and primary references.
- Updated the story map with the cost, licensing, and venue-local metric boundary.

## Next Boundary

u140 stays blocked after Step 0 iterations 1-24. TAQ Closing Prices may be
reconsidered only with a permanent-free entitlement, explicit public derived-display
rights, and acceptance of clearly labeled NYSE Arca-only metrics. Otherwise the next
bounded action is Step 0 for one non-duplicate candidate; local and five-run GitHub
Actions probes remain gated.

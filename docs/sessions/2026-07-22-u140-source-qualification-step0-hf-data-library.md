# Session Log: 2026-07-22 - u140 - Source Qualification Step 0 HF Data Library

## Overview

- **Unit**: u140 sector-dashboard-public-ohlcv-source-qualification
- **Stage**: Source qualification before Construction
- **Iteration**: Step 0 candidate fact sheet — HF Data Library daily OHLCV
- **Result**: Defer pending exact-universe and volume-fitness repair; u140 remains blocked

## Work Summary

Reviewed HF Data Library's API reference, license, terms, known-issues disclosure,
status/update metadata, public GitHub repository, upstream IEX Historical Data Terms,
and UCA operator identity. The candidate was deduplicated against Investo's runtime,
configuration, dependencies, tests, workflows, requirements, and planning surfaces.

This is the first u140 candidate in the current sequence with a plausible no-cost,
publicly reusable history path. It publishes a free API at 100 downloads/minute,
daily OHLCV aggregation, 23+ years of history, CC BY sharing/adaptation, and an IEX
upstream distribution right with mandatory attribution. Public update metadata was
operational and current through 2026-07-20 when checked.

The exact universe fails before account/API probing. Public catalog metadata contains
SPY plus XLB, XLC, XLE, XLF, XLI, XLK, XLP, XLU, XLV, and XLY, but not `XLRE`, so
coverage is 11/12. The recent data segment is also IEX-only, approximately 2–3% of
consolidated volume, and the provider warns about no-trade days and OHLC differences
from the full tape. That volume cannot be presented as total ETF trading activity.
The free API key additionally expires every 30 days, so unattended GHA rotation needs
a contract before acceptance.

No account, API key, provider data payload, fixture, local/API probe, GitHub Actions
probe, adapter, or public artifact was created. Only public catalog metadata and legal
documentation were read.

## Decision

| Question | Answer |
| --- | --- |
| Free 63+ daily OHLCV | Preliminary pass for cataloged tickers; free daily aggregation and 23+ years are documented |
| Exact 12-symbol/freshness evidence | Fail on coverage: 11/12 with `XLRE` absent; freshness metadata is promising but payload remains unprobed |
| Explicit free public derived-display rights | Provisional pass with HF Data Library and IEX attribution |
| Truthful volume semantics | Fail for total-volume claims; post-2022 data is IEX-only at roughly 2–3% of consolidated volume |
| Existing source overlap | None; no HF Data Library/IEX HIST runtime, key, fixture, dependency, or workflow exists |
| Disposition | `defer pending exact-universe and volume-fitness repair` |

## Files Changed

- Added the dated HF Data Library source fact sheet.
- Updated the u140 plan and state/audit records.
- Added HF Data Library to the product-plan disposition matrix and primary references.
- Updated the story map with the 11/12 coverage and IEX-only-volume boundary.

## Next Boundary

u140 stays blocked after Step 0 iterations 1-16. HF Data Library can be reconsidered
if `XLRE` is added and venue-limited metric/auth semantics are explicitly resolved.
Otherwise the next bounded action is Step 0 for another non-duplicate candidate;
local and five-run GitHub Actions probes remain gated.

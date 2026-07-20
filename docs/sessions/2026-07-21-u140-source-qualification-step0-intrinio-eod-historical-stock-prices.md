# Session Log: 2026-07-21 - u140 - Source Qualification Step 0 Intrinio EOD Historical Stock Prices

## Overview

- **Unit**: u140 sector-dashboard-public-ohlcv-source-qualification
- **Stage**: Source qualification before Construction
- **Iteration**: Step 0 candidate fact sheet — Intrinio EOD Historical Stock Prices
- **Result**: Reject under current published pricing and terms; u140 remains blocked

## Work Summary

Reviewed Intrinio using its official Stock Prices by Security endpoint contract, Web
API access guide, API-call accounting guide, pricing page, and effective 2026-06-03
Terms of Service. The candidate was then deduplicated against Investo's adapters,
source registry, routing, tests, fixtures, secrets, dependencies, workflows, plans,
and requirements.

Intrinio is technically suitable for a daily radar. It advertises more than 50 years
of daily full-volume US EOD history and returns raw and split/dividend-adjusted OHLCV
plus factor, split, and dividend fields. A historical page can carry up to 100 daily
rows, so the required 63-day window would preliminarily fit in one call per ticker.

It cannot advance because there is no permanent free production tier. Individual
access is USD 150/month and expressly excludes redistribution or external display.
Startup, which begins at USD 333/month, is the first published plan with Display &
Commercial Use. The terms independently make external website/dashboard/report use
and externally visible derived output subject to an executed Order Form. No
attribution-only or free derived-display exception was found.

No account or free trial was opened. No credential, paid-plan inquiry, API payload,
fixture, GitHub Actions probe, adapter, or public artifact was created.

## Decision

| Question | Answer |
| --- | --- |
| Free 63+ daily OHLCV | Fail; the history is technically deep enough, but only a trial is free and production starts at USD 150/month |
| Exact 12-symbol/freshness evidence | Not run after binding cost and rights failures |
| Explicit free public derived-display rights | Fail; external display requires paid Startup/Enterprise rights in an executed Order Form |
| Existing source overlap | None; no Intrinio runtime, credential, fixture, dependency, or planning surface exists |
| Disposition | `reject under current published pricing and terms` |

## Files Changed

- Added the dated Intrinio EOD Historical Stock Prices source fact sheet.
- Updated the u140 plan and state/audit records.
- Added Intrinio to the product-plan rejection matrix and primary references.
- Updated the story map with the paid-display and executed-Order-Form boundary.

## Next Boundary

u140 stays blocked after Step 0 iterations 1-13. The next bounded action is another
Step 0 iteration for a non-duplicate candidate. Local and five-run GitHub Actions
probes remain unavailable until a candidate first clears explicit free public
derived-display rights and the 63-trading-day history requirement.

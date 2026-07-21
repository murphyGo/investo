# Session Log: 2026-07-21 - u140 - Source Qualification Step 0 SimFin Daily Share Prices

## Overview

- **Unit**: u140 sector-dashboard-public-ohlcv-source-qualification
- **Stage**: Source qualification before Construction
- **Iteration**: Step 0 candidate fact sheet — SimFin Daily Share Prices
- **Result**: Reject under the current FREE/BASIC data license; u140 remains blocked

## Work Summary

Reviewed SimFin using its current pricing/features page, Data License Agreement,
data-download FAQ, official Python repository, and API v3/bulk technical-update page.
The candidate was then deduplicated against Investo's adapters, source registry,
routing, tests, fixtures, secrets, dependencies, workflows, plans, and requirements.

SimFin is the first candidate in this sequence whose published Free tier clearly looks
large enough for the calculation: USD 0 with no billing, five years of history, daily
OHLC, adjusted close, volume, API/bulk access, and a free account API-key path. The
reviewed pages do not, however, confirm the 12 required ETFs or define the Free bulk
`delayed` period.

The binding failure is licensing. FREE/BASIC data is limited to personal research and
own use and cannot be shared. Reprocessed data remains under the same disclosure and
transfer restrictions. SimFin separately says Enterprise is the only subscription
that permits redistribution. The license excludes `interpretations` from its data
restrictions, but does not define public quantitative returns, ranks, volume scores,
volatility, or regimes as interpretations instead of restricted reprocessed data.
Investo does not infer public rights from that ambiguity.

No SimFin account or API key was created. No API/bulk payload, fixture, GitHub Actions
probe, adapter, or public artifact was created.

## Decision

| Question | Answer |
| --- | --- |
| Free 63+ daily OHLCV | Preliminary pass; Free advertises five years, daily OHLC/adjusted close/volume, and API/bulk access |
| Exact 12-symbol/freshness evidence | Unproven; ETF coverage and the Free `delayed` interval were not probed after the rights failure |
| Explicit free public derived-display rights | Fail; FREE/BASIC forbids sharing and applies the same restrictions to reprocessed data |
| Existing source overlap | None; no SimFin runtime, key, fixture, dependency, or planning surface exists |
| Disposition | `reject under the current FREE/BASIC data license` |

## Files Changed

- Added the dated SimFin Daily Share Prices source fact sheet.
- Updated the u140 plan and state/audit records.
- Added SimFin to the product-plan rejection matrix and primary references.
- Updated the story map with the personal-research, reprocessing, and redistribution boundary.

## Next Boundary

u140 stays blocked after Step 0 iterations 1-14. The next bounded action is another
Step 0 iteration for a non-duplicate candidate. Local and five-run GitHub Actions
probes remain unavailable until a candidate first clears explicit free public
derived-display rights and the 63-trading-day history requirement.

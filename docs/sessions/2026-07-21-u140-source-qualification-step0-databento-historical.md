# Session Log: 2026-07-21 - u140 - Source Qualification Step 0 Databento Historical

## Overview

- **Unit**: u140 sector-dashboard-public-ohlcv-source-qualification
- **Stage**: Source qualification before Construction
- **Iteration**: Step 0 candidate fact sheet — Databento Historical API / `EQUS.SUMMARY`
- **Result**: Reject under current published cost and rights evidence; u140 remains blocked

## Work Summary

Reviewed Databento using its official US Equities Summary dataset specification,
Historical API contract, consolidated closing-price example, pricing and credit FAQ,
quickstart, portal licensing guide, and OHLCV schema reference. The candidate was
then deduplicated against Investo's adapters, source registry, routing, tests,
fixtures, secrets, dependencies, workflows, plans, and requirements.

`EQUS.SUMMARY` is technically strong: Nasdaq NLS+ supplies consolidated US-equities
end-of-day OHLCV, the official example queries multiple symbols over one year, and the
Historical API supports structured daily output with ample rate limits. It cannot
advance because historical data is billed by bytes. The only free funding is one
$125 grant per team, and it expires after six months.

Public display is not accepted by inference. Databento states that redistribution
rights depend on the exact dataset and publisher and are selected through its Data
Catalog or License Manager. The reviewed public pages do not expressly grant
`EQUS.SUMMARY` a free public derived-display right. No account or API key was
requested. No cost-estimate request, credentialed payload, fixture, GitHub Actions
probe, adapter, or public artifact was created.

## Decision

| Question | Answer |
| --- | --- |
| Free 63+ daily OHLCV | Fail; one year is technically available, but all historical bytes are metered after a one-time six-month credit |
| Exact 12-symbol/freshness evidence | Not run after the permanent-free failure |
| Explicit free public derived-display rights | Unproven for `EQUS.SUMMARY`; Databento requires dataset/use-case-specific licensing confirmation |
| Existing source overlap | None; no Databento runtime, key, fixture, dependency, or planning surface exists |
| Disposition | `reject under current published cost and rights evidence` |

## Files Changed

- Added the dated Databento Historical source fact sheet.
- Updated the u140 plan and state/audit records.
- Added Databento to the product-plan rejection matrix and primary references.
- Updated the story map with the metered-data and dataset-specific-rights boundary.

## Next Boundary

u140 stays blocked. The next bounded action is another Step 0 iteration for a
non-duplicate candidate. Local and five-run GitHub Actions probes remain unavailable
until a candidate first clears explicit free public derived-display rights and the
63-trading-day history requirement.

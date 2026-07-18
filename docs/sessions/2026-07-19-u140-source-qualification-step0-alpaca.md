# Session Log: 2026-07-19 - u140 - Source Qualification Step 0 Alpaca

## Overview

- **Unit**: u140 sector-dashboard-public-ohlcv-source-qualification
- **Stage**: Source qualification before Construction
- **Iteration**: Step 0 candidate fact sheet — Alpaca historical stock bars
- **Result**: Reject under current written terms; u140 remains blocked

## Work Summary

Reviewed Alpaca using current official plan, API, support, and customer-agreement
surfaces, then deduplicated the candidate against Investo's source registry, specs,
routing, tests, fixtures, secrets, dependencies, and workflows.

Alpaca Basic is technically suitable for a bounded test: it is free, covers US
stocks/ETFs since 2016, supports multi-symbol daily bars and corporate-action
adjustments, and allows 200 historical requests/minute. It cannot advance because
Alpaca's official support prohibits API-data redistribution and the current customer
agreement requires written consent for reproduction/distribution.

No account or key was requested. No credentialed request, local raw payload, fixture,
GitHub Actions probe, adapter, or public artifact was created.

## Decision

| Question | Answer |
| --- | --- |
| Free 63+ daily OHLCV | Preliminary pass; Basic history begins in 2016 |
| Exact 12-symbol/freshness evidence | Not run after binding rights failure |
| Explicit public derived-display rights | No; redistribution is disallowed and written consent is absent |
| Existing source overlap | No Alpaca surface exists; Yahoo/u138 remains separate |
| Disposition | `reject under current written terms` |

## Files Changed

- Added the dated Alpaca source fact sheet.
- Updated the u140 plan and state/audit records.
- Added Alpaca to the product-plan rejection matrix and primary references.
- Updated the story map so a free structured API is not mistaken for a public-use
  grant.

## Next Boundary

u140 stays blocked. The next bounded action is another Step 0 iteration for a
non-duplicate candidate. Local and five-run GitHub Actions probes remain unavailable
until a candidate first clears explicit public derived-display rights.

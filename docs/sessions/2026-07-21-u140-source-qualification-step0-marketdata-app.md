# Session Log: 2026-07-21 - u140 - Source Qualification Step 0 MarketData.app

## Overview

- **Unit**: u140 sector-dashboard-public-ohlcv-source-qualification
- **Stage**: Source qualification before Construction
- **Iteration**: Step 0 candidate fact sheet — MarketData.app Historical Candles API
- **Result**: Reject under current written terms; u140 remains blocked

## Work Summary

Reviewed MarketData.app using its current official candle endpoint, authentication,
rate-limit, free-account, pricing, terms, redistribution policy, and Commercial Use
Addendum. The candidate was then deduplicated against Investo's source registry,
specs, routing, tests, fixtures, secrets, dependencies, and workflows.

The candidate clears the preliminary technical gate. Free Forever provides one year
of split-adjusted daily OHLCV, 100 credits/day, and a historical-candle cost of one
credit per 1,000 candles. Twelve 63-candle requests therefore fit within the free
budget. Free data is delayed by at least 24 hours.

It cannot advance because every self-service plan is licensed for Internal Use. The
redistribution policy prohibits embedding live or recent data in a product accessible
to others, while end-user display and redistribution require a custom annual
Commercial plan and applicable exchange licenses. No account or API token was
requested. No credentialed request, local raw payload, fixture, GitHub Actions probe,
adapter, or public artifact was created.

## Decision

| Question | Answer |
| --- | --- |
| Free 63+ daily OHLCV | Preliminary pass; one year of history and 100 credits/day cover the bounded workload |
| Exact 12-symbol/freshness evidence | Not run after the binding rights failure; the documented free delay is at least 24 hours |
| Explicit free public derived-display rights | No; self-service is Internal Use and public/end-user display requires Commercial Services and exchange licensing |
| Existing source overlap | No MarketData.app surface exists; Yahoo/u138 remains separate |
| Disposition | `reject under current written terms` |

## Files Changed

- Added the dated MarketData.app source fact sheet.
- Updated the u140 plan and state/audit records.
- Added MarketData.app to the product-plan rejection matrix and primary references.
- Updated the story map with the Internal Use and Commercial-plan boundary.

## Next Boundary

u140 stays blocked. The next bounded action is another Step 0 iteration for a
non-duplicate candidate. Local and five-run GitHub Actions probes remain unavailable
until a candidate first clears explicit free public derived-display rights and the
63-trading-day history requirement.

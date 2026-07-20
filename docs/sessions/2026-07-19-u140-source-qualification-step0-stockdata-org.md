# Session Log: 2026-07-19 - u140 - Source Qualification Step 0 StockData.org

## Overview

- **Unit**: u140 sector-dashboard-public-ohlcv-source-qualification
- **Stage**: Source qualification before Construction
- **Iteration**: Step 0 candidate fact sheet — StockData.org EOD API
- **Result**: Reject under current written terms; u140 remains blocked

## Work Summary

Reviewed StockData.org using its current official EOD documentation, pricing, and
terms. The candidate was then deduplicated against Investo's source registry, specs,
routing, tests, fixtures, secrets, dependencies, and workflows.

The EOD endpoint is structured and exposes split-adjusted daily OHLCV. Its Free tier
allows 100 requests/day, enough for 12 symbol-specific requests, but includes only
one month of EOD history and therefore cannot provide 63 trading days. One year of
history begins with the paid Basic tier at USD 29/month, or USD 24/month billed
annually. The terms independently restrict the general license to personal,
non-commercial use and provide no public derived-display authorization.

No account or API token was requested. No credentialed request, local raw payload,
fixture, GitHub Actions probe, adapter, or public artifact was created.

## Decision

| Question | Answer |
| --- | --- |
| Free 63+ daily OHLCV | No; Free is limited to one month and one year requires paid Basic |
| Exact 12-symbol/freshness evidence | Not run after binding history and rights failures; daily completion and dividend adjustment semantics also remain incomplete |
| Explicit free public derived-display rights | No; current terms specify personal, non-commercial use and require approval for commercial endeavors |
| Existing source overlap | No StockData.org surface exists; Yahoo/u138 remains separate |
| Disposition | `reject under current written terms` |

## Files Changed

- Added the dated StockData.org source fact sheet.
- Updated the u140 plan and state/audit records.
- Added StockData.org to the product-plan rejection matrix and primary references.
- Updated the story map with the independent free-history and public-rights failures.

## Next Boundary

u140 stays blocked. The next bounded action is another Step 0 iteration for a
non-duplicate candidate. Local and five-run GitHub Actions probes remain unavailable
until a candidate first clears explicit free public derived-display rights and the
63-trading-day history requirement.

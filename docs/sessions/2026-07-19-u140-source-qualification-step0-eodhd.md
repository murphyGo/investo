# Session Log: 2026-07-19 - u140 - Source Qualification Step 0 EODHD

## Overview

- **Unit**: u140 sector-dashboard-public-ohlcv-source-qualification
- **Stage**: Source qualification before Construction
- **Iteration**: Step 0 candidate fact sheet — EODHD End-Of-Day Historical API
- **Result**: Reject under current written terms; u140 remains blocked

## Work Summary

Reviewed EODHD using its current official EOD endpoint contract, personal pricing,
terms, and data-source disclosure, then deduplicated the candidate against Investo's
source registry, specs, routing, tests, fixtures, secrets, dependencies, and
workflows.

EODHD Free Starter is technically suitable for the bounded daily workload: its
single-symbol API provides one year of OHLCV plus split- and dividend-adjusted close,
20 calls/day cover 12 sector/SPY requests, and the documented major-US-exchange
update time is within 15 minutes after close. It cannot advance because free access
is Personal use and the terms prohibit non-professional users from displaying or
redistributing original or repackaged Information. Professional display requires
prior written approval, which Investo does not have.

No account or API token was requested. No credentialed request, local raw payload,
fixture, GitHub Actions probe, adapter, or public artifact was created.

## Decision

| Question | Answer |
| --- | --- |
| Free 63+ daily OHLCV | Preliminary pass; one free year and 20 calls/day cover the 12 one-symbol requests |
| Exact 12-symbol/freshness evidence | Not run after binding rights failure |
| Explicit free public derived-display rights | No; free use is private/personal and display/redistribution requires approval |
| Existing source overlap | No EODHD surface exists; Yahoo/u138 remains separate |
| Disposition | `reject under current written terms` |

## Files Changed

- Added the dated EODHD source fact sheet.
- Updated the u140 plan and state/audit records.
- Added EODHD to the product-plan rejection matrix and primary references.
- Updated the story map so documented technical sufficiency is not mistaken for a
  public-use grant.

## Next Boundary

u140 stays blocked. The next bounded action is another Step 0 iteration for a
non-duplicate candidate. Local and five-run GitHub Actions probes remain unavailable
until a candidate first clears explicit free public derived-display rights.

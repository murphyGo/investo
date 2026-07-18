# Session Log: 2026-07-19 - u140 - Source Qualification Step 0 Tiingo

## Overview

- **Unit**: u140 sector-dashboard-public-ohlcv-source-qualification
- **Stage**: Source qualification before Construction
- **Iteration**: Step 0 candidate fact sheet — Tiingo EOD API
- **Result**: Reject; u140 remains blocked

## Work Summary

Reviewed Tiingo using its current official EOD documentation, pricing, product, and
terms surfaces, then deduplicated the candidate against Investo's source registry,
specs, routing, tests, fixtures, secrets, dependencies, and workflows.

Tiingo Starter is technically suitable for a bounded test: it is free, covers broad
US equity/ETF EOD history, exposes raw and adjusted OHLCV plus corporate actions, and
allows 50 requests/hour and 1,000/day. It cannot advance because all standard tiers
are Internal Use Only, current terms prohibit public analysis/display, and the
explicit display-redistribution plan starts at USD 250/month.

No account or token was requested. No credentialed request, local raw payload,
fixture, GitHub Actions probe, adapter, or public artifact was created.

## Decision

| Question | Answer |
| --- | --- |
| Free 63+ daily OHLCV | Preliminary pass; Starter provides broad EOD history |
| Exact 12-symbol/freshness evidence | Not run after binding rights/no-paid failures |
| Explicit free public derived-display rights | No; standard access is Internal Use Only |
| Existing source overlap | No Tiingo surface exists; Yahoo/u138 remains separate |
| Disposition | `reject` |

## Files Changed

- Added the dated Tiingo source fact sheet.
- Updated the u140 plan and state/audit records.
- Added Tiingo to the product-plan rejection matrix and primary references.
- Updated the story map so ample free internal-use quotas are not mistaken for a
  public redistribution grant.

## Next Boundary

u140 stays blocked. The next bounded action is another Step 0 iteration for a
non-duplicate candidate. Local and five-run GitHub Actions probes remain unavailable
until a candidate first clears explicit free public derived-display rights.

# Session Log: 2026-07-19 - u140 - Source Qualification Step 0

## Overview

- **Unit**: u140 sector-dashboard-public-ohlcv-source-qualification
- **Stage**: Source qualification before Construction
- **Iteration**: Step 0 candidate fact sheet — Finnhub stock candles
- **Result**: Reject; u140 remains blocked

## Work Summary

Reviewed Finnhub using current official API, pricing, and registration surfaces,
then deduplicated the candidate against Investo's source registry, specs, routing,
tests, fixtures, secrets, and workflows. Historical stock OHLCV is Premium-only and
the listed market-data licenses are Personal Use, so the candidate fails before
reachability testing.

No API key was requested. No credentialed request, local raw payload, fixture,
GitHub Actions probe, adapter, or public artifact was created.

## Decision

| Question | Answer |
| --- | --- |
| Free 63+ daily OHLCV | No; stock candles are Premium-only |
| Explicit public derived-display rights | No; Personal Use is listed and written commercial/professional approval is absent |
| Existing source overlap | No Finnhub surface exists; Yahoo/u138 remains a separate operational path without u140 rights clearance |
| Local/GHA probe justified | No; the binding cost and rights gates already fail |
| Disposition | `reject` |

## Files Changed

- Added the dated Finnhub source fact sheet.
- Updated the u140 plan and state/audit records.
- Added Finnhub to the product-plan rejection matrix and official references.
- Removed the stale `Finnhub free` public-candidate wording from requirements and
  split Finnhub out of the u138 defer note.

## Next Boundary

u140 stays blocked. The next bounded action is another Step 0 iteration for a
non-duplicate candidate. Local and five-run GitHub Actions probes remain unavailable
until a candidate first passes the free-access and public-rights review.

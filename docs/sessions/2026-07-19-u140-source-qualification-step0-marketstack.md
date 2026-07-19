# Session Log: 2026-07-19 - u140 - Source Qualification Step 0 Marketstack

## Overview

- **Unit**: u140 sector-dashboard-public-ohlcv-source-qualification
- **Stage**: Source qualification before Construction
- **Iteration**: Step 0 candidate fact sheet — Marketstack v2 EOD API
- **Result**: Reject under current written terms; u140 remains blocked

## Work Summary

Reviewed Marketstack using its current official v2 OpenAPI specification, pricing,
service agreement, and APILayer legal surface, then deduplicated the candidate
against Investo's source registry, specs, routing, tests, fixtures, secrets,
dependencies, and workflows.

Marketstack Free is technically suitable for a bounded test: one `/eod` request can
contain the complete 12-symbol universe, one year exceeds 63 bars, and the 100-call
monthly allowance covers once-daily collection. It cannot advance because Commercial
Use begins on a paid plan and the current linked APILayer Freeware agreement limits
free access to testing/evaluation without granting public display or redistribution.

No account or access key was requested. No credentialed request, local raw payload,
fixture, GitHub Actions probe, adapter, or public artifact was created.

## Decision

| Question | Answer |
| --- | --- |
| Free 63+ daily OHLCV | Preliminary pass; one-year multi-symbol EOD fits the request budget |
| Exact 12-symbol/freshness evidence | Not run after binding rights failure |
| Explicit free public derived-display rights | No; current free license is testing/evaluation only |
| Existing source overlap | No Marketstack/APILayer surface exists; Yahoo/u138 remains separate |
| Disposition | `reject under current written terms` |

## Files Changed

- Added the dated Marketstack source fact sheet.
- Updated the u140 plan and state/audit records.
- Added Marketstack to the product-plan rejection matrix and primary references.
- Updated the story map so a viable free batch quota is not mistaken for a public-use
  grant.

## Next Boundary

u140 stays blocked. The next bounded action is another Step 0 iteration for a
non-duplicate candidate. Local and five-run GitHub Actions probes remain unavailable
until a candidate first clears explicit free public derived-display rights.

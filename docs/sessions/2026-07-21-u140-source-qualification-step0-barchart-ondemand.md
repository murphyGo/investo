# Session Log: 2026-07-21 - u140 - Source Qualification Step 0 Barchart OnDemand

## Overview

- **Unit**: u140 sector-dashboard-public-ohlcv-source-qualification
- **Stage**: Source qualification before Construction
- **Iteration**: Step 0 candidate fact sheet — Barchart OnDemand `getHistory` API
- **Result**: Reject under current published terms; u140 remains blocked

## Work Summary

Reviewed Barchart OnDemand using its current official `getHistory` contract, data
coverage, OnDemand product/pricing pages, FAQ, Terms of Service, and exchange-fee
guidance. The candidate was then deduplicated against Investo's source registry,
specs, routing, tests, fixtures, secrets, dependencies, and workflows.

The endpoint is technically plausible: it documents stock/ETF historical daily
OHLCV, date bounds, deterministic ordering, JSON/XML/CSV output, and explicit split
and dividend adjustment controls. It cannot advance because Barchart publishes only
a limited-request free trial before plan commitment; production pricing is based on
usage and tailored through sales. No permanent free production tier or request quota
is published.

The general terms independently limit ordinary content use to personal,
non-commercial use and require prior express written consent before publication or
distribution. The narrow attributed-screenshot permission does not authorize an API-
derived public radar. No account or API key was requested. No credentialed request,
local raw payload, fixture, GitHub Actions probe, adapter, or public artifact was
created.

## Decision

| Question | Answer |
| --- | --- |
| Free 63+ daily OHLCV | Fail; the endpoint supports the shape and depth in principle, but only a limited evaluation trial is free and production is usage-priced |
| Exact 12-symbol/freshness evidence | Not run after the binding cost/rights failures |
| Explicit free public derived-display rights | No; publication/distribution needs prior written consent and the website/app route is sales-led |
| Existing source overlap | No OnDemand integration exists; `Barchart` appears only as article-creator metadata in news fixtures |
| Disposition | `reject under current published terms` |

## Files Changed

- Added the dated Barchart OnDemand source fact sheet.
- Updated the u140 plan and state/audit records.
- Added Barchart OnDemand to the product-plan rejection matrix and primary references.
- Updated the story map with the trial, paid-production, and written-consent boundary.

## Next Boundary

u140 stays blocked. The next bounded action is another Step 0 iteration for a
non-duplicate candidate. Local and five-run GitHub Actions probes remain unavailable
until a candidate first clears explicit free public derived-display rights and the
63-trading-day history requirement.

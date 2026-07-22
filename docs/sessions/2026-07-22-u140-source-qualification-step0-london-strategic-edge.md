# Session Log: 2026-07-22 - u140 - Source Qualification Step 0 London Strategic Edge

## Overview

- **Unit**: u140 sector-dashboard-public-ohlcv-source-qualification
- **Stage**: Source qualification before Construction
- **Iteration**: Step 0 candidate fact sheet — London Strategic Edge Free Market Data API
- **Result**: Reject under current published terms; u140 remains blocked

## Work Summary

Committed and pushed the preceding BusinessQuant Step 0 slice as `c547701`, with
only its seven u140 documentation files staged. Unrelated generated, settings, and
worktree artifacts remained untouched.

Reviewed London Strategic Edge's official free API, REST overview, databank, and
binding Terms, then deduplicated the candidate against Investo runtime, configuration,
tests, workflows, dependencies, requirements, and plans.

The technical offer is promising. It advertises one free key, JSON/CSV OHLCV from
one-minute through daily resolution, up to 5,000 rows per request, long-instrument
daily history back to 2003, and 25 index/sector ETFs. The databank separately
advertises ten free downloads per hour at up to one million rows.

The rights gate fails first. The Terms prohibit redistributing, reselling, or
commercially exploiting data and prohibit copying, modifying, distributing, or
creating derivative works without express written consent. The reviewed pages also
do not identify the upstream ETF feed, consolidated-volume meaning, adjustment
semantics, exact fixed universe, or a binding daily finalization deadline.

No account or API key was created. The API and databank were not called; no
exact-symbol, payload, freshness, adjustment, volume, continuity, local runner, or
GitHub Actions probe was performed, and no provider data was retained.

## Decision

| Question | Answer |
| --- | --- |
| Free 63+ daily OHLCV | Preliminary technical pass: free daily API and history back to 2003 are advertised for long-listed instruments |
| Exact 12-symbol/freshness evidence | Unproven; only aggregate 25-ETF coverage is published on the reviewed static page |
| Explicit free public derived-display rights | Fail; redistribution and derivative works require express written consent |
| Truthful price/volume semantics | Unproven; adjustment and upstream/consolidated-volume provenance are not stated |
| Existing source overlap | None; no London Strategic Edge runtime, key, client, fixture, dependency, or workflow exists |
| Disposition | `reject under current published terms` |

## Files Changed

- Added the dated London Strategic Edge source fact sheet.
- Updated the u140 plan and state/audit records.
- Added the candidate to the product-plan disposition matrix and primary references.
- Updated the story map with the written-consent and provenance boundary.

## Next Boundary

u140 stays blocked after Step 0 iterations 1-18. London Strategic Edge may be
reconsidered only with written public derived-display/retention permission and clear
upstream ETF provenance. Otherwise the next bounded action is Step 0 for one
non-duplicate candidate; local and five-run GitHub Actions probes remain gated.

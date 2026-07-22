# Session Log: 2026-07-22 - u140 - Source Qualification Step 0 Direct IEX HIST

## Overview

- **Unit**: u140 sector-dashboard-public-ohlcv-source-qualification
- **Stage**: Source qualification before Construction
- **Iteration**: Step 0 candidate fact sheet — Direct IEX Exchange HIST / TOPS
- **Result**: Reject for current public MVP operational and metric fitness; u140 remains blocked

## Work Summary

Committed and pushed the preceding London Strategic Edge Step 0 slice as `3b4a1ed`.
Because concurrent generated-output and u144 commits had advanced `origin/main` while
the original worktree contained unrelated dirty artifacts, the seven u140 documents
were transferred byte-for-byte to an isolated worktree, rebased on the new remote
head, and pushed without overwriting or staging the original worktree's other changes.

Reviewed IEX's official market-data product page, HIST Terms, per-date download
catalog, feed specifications/resources, and eligible-symbol surface. Direct HIST is a
distinct delivery candidate even though the IEX rights and venue semantics were
previously assessed through HF Data Library.

The cost and rights evidence is unusually favorable: IEX provides free T+1 files for
the most recent 12 months, and the Terms permit use and distribution with mandatory
attribution. The delivery and metric contracts fail the current MVP. The smallest
relevant feed is a whole-market gzip PCAP, not a ticker-filtered OHLCV API. Current
official catalog examples put one TOPS day at roughly 9–21 GB, so 63 trading days
would require hundreds of gigabytes before filtering, IEX-TP decoding, and daily-bar
aggregation.

The result would also be IEX-only OHLCV. It excludes other exchanges and routed
executions, can have no-trade dates for otherwise eligible ETFs, and cannot be labeled
as consolidated ETF volume or full-tape OHLC. Raw exchange messages have no built-in
split/dividend-adjusted daily series.

No HIST/PCAP file or provider payload was downloaded. No exact-symbol, decoder,
continuity, freshness, adjustment, local-runner, or GitHub Actions probe was performed,
and no raw provider data was retained.

## Decision

| Question | Answer |
| --- | --- |
| Free 63+ history and public rights | Pass preliminarily: free 12-month T+1 history; distribution allowed with required attribution |
| Ready daily OHLCV / bounded request shape | Fail: whole-market binary PCAP, roughly 9–21 GB per day, requiring decode and aggregation |
| Exact 12-symbol/freshness evidence | Unproven; eligible-symbol publishing does not establish daily trade continuity or exact posting time |
| Truthful price/volume semantics | Fail for the current contract; resulting bars are IEX-only, not consolidated |
| Existing source overlap | Rights/venue facts overlap HF Data Library; no direct downloader, decoder, adapter, fixture, dependency, or workflow exists |
| Disposition | `reject for current public MVP operational and metric fitness` |

## Files Changed

- Added the dated direct IEX HIST source fact sheet.
- Updated the u140 plan and state/audit records.
- Added the candidate to the product-plan disposition matrix and primary references.
- Updated the story map with the whole-feed and IEX-only metric boundary.

## Next Boundary

u140 stays blocked after Step 0 iterations 1-19. Direct IEX HIST may be reconsidered
only with a ticker-filtered daily-bar surface or a separately funded preprocessing
architecture plus an explicit IEX-only product contract. Otherwise the next bounded
action is Step 0 for one non-duplicate candidate; local and five-run GitHub Actions
probes remain gated.

# Cross-Check: u138 Price Source Endpoint Lifecycle Repair

**Scope**: u138 Functional Design R1-R13, interfaces I1-I5, NFR
AC-1.1 through AC-6.4, and code-plan acceptance criteria
**Date**: 2026-07-26
**Result**: PASS - 26/26 NFR acceptance criteria complete

## Summary

| Status | Count | Percentage |
| --- | ---: | ---: |
| Complete | 26 | 100% |
| Partial | 0 | 0% |
| Gap | 0 | 0% |
| Deferred | 0 | 0% |
| **Total** | **26** | **100%** |

## Compliance Matrix

| ID | Status | Evidence |
| --- | --- | --- |
| AC-1.1 | Complete | Static lifecycle checks and run `30200378661` contain no Stooq/query1 request. |
| AC-1.2 | Complete | Critical query2 fixtures pass; production replay returned `yfinance-price=27`. |
| AC-1.3 | Complete | `test_yfinance.py` pins HTTP/chart/malformed per-ticker isolation. |
| AC-1.4 | Complete | Critical-first/enrichment-failure tests preserve critical items. |
| AC-1.5 | Complete | Direct+history outage tests emit no synthetic price and keep unrelated stages alive. |
| AC-2.1 | Complete | `test_direct_snapshot_wins_and_prevents_duplicate_ticker`. |
| AC-2.2 | Complete | Fallback age 0-4 accepted; future/5+ rejected; direct rows are target-date bounded. |
| AC-2.3 | Complete | Non-finite/non-positive OHLC and negative/NaN volume tests pass. |
| AC-2.4 | Complete | Reconciliation unit and integrated pipeline tests pin one matching outcome before all consumers. |
| AC-2.5 | Complete | Yonhap/FRED adapter tests pin truthful provenance, direction, and timestamps. RSS `pubDate` exact-date clarification is recorded in FD/NFR. |
| AC-3.1 | Complete | Yahoo default concurrency remains 2 with bounded env parsing. |
| AC-3.2 | Complete | Request-order tests pin critical completion before enrichment and skip enrichment on zero critical output. |
| AC-3.3 | Complete | Replay emitted the fixed 27 direct Yahoo requests, zero Stooq, and one FRED FX item. |
| AC-3.4 | Complete | Source collection completed inside the existing budget; entire replay completed in 953.005 s. |
| AC-4.1 | Complete | Central redaction paths and missing-key tests expose no secret value. |
| AC-4.2 | Complete | `check_no_paid_apis.py` passes; no dependency, secret, or paid path added. |
| AC-4.3 | Complete | Static scans find no Cboe/Nasdaq quote adapter or restricted FRED index fallback. |
| AC-4.4 | Complete | FRED DEXKOUS and Yahoo quote URLs are pinned in adapter tests. |
| AC-5.1 | Complete | Snapshot/history delegate to `sources/_yahoo_chart.py`; duplicate parser removed. |
| AC-5.2 | Complete | Plugin, SourceSpec, tier, window, and segment tests cover both replacements. |
| AC-5.3 | Complete | Runtime imports/specs/routes/core sets contain no retired Stooq identity. |
| AC-5.4 | Complete | Source parsing remains under `sources`; reconciliation remains under `orchestrator`; mypy passes. |
| AC-6.1 | Complete | R10 fixtures cover query2, fallback, Yonhap timestamp integrity, and FRED valid/error paths. |
| AC-6.2 | Complete | Source/plugin/spec/segment regression suites pass. |
| AC-6.3 | Complete | Exact run `30200378661`: query2 200, yfinance 27, no Stooq/query1, 3/3 finalized, pipeline success. |
| AC-6.4 | Complete | Ruff/format, mypy, 4099 tests, guards, strict MkDocs, and diff check pass. |

## Production Closeout

- Implementation commit: `5ae473b`.
- Generated content commit: `ce6ab25`.
- Daily run:
  <https://github.com/murphyGo/investo/actions/runs/30200378661>.
- Pages run:
  <https://github.com/murphyGo/investo/actions/runs/30200904739>.
- Live domestic, US, and crypto pages returned HTTP 200.
- Telegram briefing dispatch succeeded with message id `80`.

## Gaps and Actions

No u138 requirement gap remains. Five auxiliary sources are still degraded for
independent credential/access/feed reasons; the new dedicated source-health
notice reports them without changing the successful pipeline result.

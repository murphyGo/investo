# NFR Requirements: `u138 price-source-endpoint-lifecycle-repair`

**Date**: 2026-07-18
**Status**: Complete for implementation handoff
**Parent plan**: `aidlc-docs/construction/plans/u138-price-source-endpoint-lifecycle-repair-code-generation-plan.md`

## 1. Reliability and Availability

### AC-1.1 Retired endpoints

A runtime source-collection test records zero requests to Stooq `q/l` and Yahoo `query1`.

### AC-1.2 Query2 success

Recorded query2 fixtures for every critical ticker produce non-empty items with the existing public metadata contract.

### AC-1.3 Per-ticker isolation

One 404/429/5xx/chart-error/malformed ticker does not remove successful sibling tickers.

### AC-1.4 Critical isolation from enrichment

Complete enrichment failure preserves every successful critical item and its outcome count.

### AC-1.5 Total outage behavior

When direct snapshot and same-run history both fail, the pipeline emits no synthetic price and source coverage remains visibly degraded without failing unrelated segments.

## 2. Correctness and Provenance

### AC-2.1 Direct-wins rule

For the same ticker, direct query2 snapshot data always wins over history fallback.

### AC-2.2 Freshness

Fallback accepts age 0-4 calendar days, rejects future rows, and rejects age 5+ days.

### AC-2.3 Numeric validity

Fallback rejects non-finite/non-positive OHLC and negative volume. Output numeric strings use canonical `format_float`/`format_int` helpers.

### AC-2.4 Outcome consistency

Every final `yfinance-price` item set has exactly one matching outcome; its status/count/latest timestamp agree with the items used by coverage, public markdown, visuals, and quality history.

### AC-2.5 Korean semantics

- Yonhap output labels provenance as `yonhap-rss` and never claims Stooq.
- DEXKOUS is emitted as KRW per one USD without inversion and labeled `fred-h10`.
- FRED observation time is New York noon; Yonhap index time remains KRX close semantics from u67.

## 3. Performance and Runtime Budget

### AC-3.1 Concurrency

Yahoo concurrency defaults to 2 and remains operator-configurable through the existing bounded env parser.

### AC-3.2 Request ordering

Critical requests complete before enrichment begins. Enrichment is skipped when critical output is empty.

### AC-3.3 Request ceiling

With default baskets, direct Yahoo snapshot requests are capped at 27 per run: 13 critical plus 14 enrichment. Stooq request count is zero. FRED FX adds exactly one request.

### AC-3.4 Pipeline budget

The focused all-success replay completes within the existing source-stage budget. An all-429 replay remains failure-isolated and does not exceed the existing per-adapter timeout contract.

## 4. Security, Cost, and Compliance

### AC-4.1 Secret hygiene

`FRED_API_KEY` is read at fetch time and never appears in logs, exceptions, fixtures, metadata, rendered markdown, or provenance URLs.

### AC-4.2 No new paid path

`scripts/check_no_paid_apis.py` passes. No new package, billable API, trial credential, or secret name is added.

### AC-4.3 Terms boundary

Production code and fixtures contain no Cboe delayed-quote JSON endpoint, Nasdaq quote-page JSON endpoint, or restricted FRED index-series adapter.

### AC-4.4 Source attribution

FRED FX public URLs point to the DEXKOUS series page and preserve citation-requested provenance. Yahoo items point to the corresponding Yahoo quote page and do not claim official exchange provenance.

## 5. Architecture and Maintainability

### AC-5.1 Single Yahoo parser

Snapshot and history modules delegate network parsing to one shared `_yahoo_chart.py` implementation; duplicate chart-shape parsers are absent.

### AC-5.2 SourceSpec completeness

Every registered replacement source has explicit tier, market window, item segment, outcome segment, adapter import, and plugin-contract coverage.

### AC-5.3 Retired identity absence

`stooq-price` and `stooq-kr-market` are absent from runtime imports/specs/routes/core sets. Historical documents and retired evidence are exempt.

### AC-5.4 Module boundary

Shared source parsing remains under `sources`; fallback orchestration remains under `orchestrator`; cross-unit data continues through `models`. No new sources-to-briefing or briefing-to-sources import is introduced.

## 6. Testing and Operations

### AC-6.1 R10 fixtures

Byte-preserved fixtures cover:

- query2 success for the critical basket
- HTTP 429 and terminal chart error
- malformed/misaligned arrays
- direct partial basket
- fallback accepted/stale/future/invalid/direct-wins
- Yonhap two-index/one-index/no-index/malformed XML
- DEXKOUS valid/placeholder/stale/missing-key/malformed JSON

### AC-6.2 Registry regression

Plugin/source-spec/tier/window/segment tests fail if a retired Stooq source reappears or a replacement surface is missing.

### AC-6.3 GHA closeout evidence

Implementation closeout requires one exact-date GitHub Actions run showing:

- non-zero `yfinance-price` final outcome;
- zero Stooq HTTP requests;
- zero Yahoo query1 requests;
- query2 request evidence;
- no source-outcome/coverage consistency failure.

### AC-6.4 Documentation gate

`git diff --check`, unresolved-placeholder scan, no-paid guard, full tests, mypy, ruff, and `mkdocs build --strict` pass before completion.

## Technology Decisions

### TS-1 HTTP and parsing

Reuse injected `httpx.AsyncClient`, `retry_get`, stdlib/typed JSON parsing, and existing `OHLCRow`. No new dependency.

### TS-2 FRED access

Use the documented FRED observations API and the already-enrolled `FRED_API_KEY`, not the graph CSV endpoint. The graph CSV was used only for no-secret reachability corroboration during planning.

### TS-3 No browser automation

Do not bypass Stooq's JavaScript challenge or automate Cboe/Nasdaq quote pages. Their rejection is a binding design decision.

### TS-4 No persisted stale-price cache in u138

Fallback is same-run only. A cross-run archive cache remains out of scope because it adds a persisted source-of-truth and stale-value policy. Promote it only if query2 itself becomes persistently empty after this repair.

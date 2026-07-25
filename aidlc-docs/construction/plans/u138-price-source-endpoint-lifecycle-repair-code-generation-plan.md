# Code Generation Plan: `u138 price-source-endpoint-lifecycle-repair`

**Date**: 2026-07-18
**Unit**: u138 price-source-endpoint-lifecycle-repair
**Stage**: Code Generation
**Status**: In Progress (3/6 steps complete; FD/NFR complete)
**Source**: Direct 2026-07-18 reachability probes plus GitHub Actions runs `29541149434` and `29457241746`
**Estimated Effort**: ~8-12 h
**Dependencies**:
- u46 `stooq-price-primary`
- u49 `deterministic-market-anchor` and `sources/yfinance_history.py`
- u54 source-status severity/core-source policy
- u67 domestic channel depth and Yonhap index fallback
- u70/u109 domestic anchor reconciliation/quarantine
- u102/u115 source registry completeness and unified `SourceSpec`
- u128 segment-scoped source outcomes

---

## Problem Statement

The current two-source US price contract no longer provides redundancy:

- Stooq's unauthenticated `https://stooq.com/q/l/` endpoint returns HTTP 404 for every tested US, crypto, Korean-index, and FX symbol.
- Yahoo `query1.finance.yahoo.com/v8/finance/chart` is rate-limited from the GitHub Actions shared runner. On run `29541149434`, every configured `query1` request returned 429 and `yfinance-price` emitted zero items.
- The same run successfully fetched every configured `query2.finance.yahoo.com/v8/finance/chart/{ticker}?interval=1d&range=1y` history request. The process therefore already has usable same-provider OHLC rows later in the run while the snapshot source outcome remains zero.
- `stooq-kr-market` still emits KOSPI/KOSDAQ through its Yonhap fallback, but it wastes two 404 calls and reports a misleading Stooq source identity. Its KRW/USD leg is empty.

This is an endpoint-lifecycle failure, not a parser edge case. The repair must remove retired endpoints from runtime, promote the proven Yahoo request shape, reconcile same-run history fallback with source outcomes, and preserve the Korean legs under truthful source identities.

## Live Evidence

### Local probes — 2026-07-18 KST

| Probe | Result | Disposition |
| --- | --- | --- |
| Stooq `q/l` AAPL | HTTP 404, Stooq moved/not-found HTML | retire |
| Stooq `q/l` `^spx` | HTTP 404, same HTML | retire |
| Stooq `q/d/l` AAPL | HTTP 200 JavaScript proof-of-work page, not CSV | reject as adapter path |
| Yahoo `query1` AAPL, 5d | HTTP 429 | reject as primary host |
| Yahoo `query1` `^GSPC`, 5d | HTTP 200 | confirms unstable mixed behavior |
| Yahoo `query2` after local throttling | HTTP 429 | preserve graceful degradation; local IP is not proof of GHA reachability |
| FRED graph CSV `DEXKOUS` | HTTP 200 with daily values | source availability corroboration |

### GitHub Actions evidence

Run `29541149434`, target window 2026-07-16:

- `stooq-price`: `item_count=0`
- `yfinance-price`: `item_count=0`
- all logged Stooq `q/l` calls: HTTP 404
- all logged Yahoo `query1` calls: HTTP 429
- all 12 configured Yahoo `query2 range=1y` history calls: HTTP 200
- `stooq-kr-market`: `item_count=2`, supplied by the existing Yonhap RSS fallback after the Stooq failures

Run `29457241746`, target window 2026-07-15:

- `stooq-price`: `item_count=0`
- `yfinance-price`: `item_count=1`
- pipeline completed partial, demonstrating that a green workflow does not mean the price-source redundancy is healthy

## Candidate Evaluation and Disposition

| Candidate | Provenance / structure | Auth / cost | Current evidence | Terms / license | Decision |
| --- | --- | --- | --- | --- | --- |
| Yahoo `query2` chart | Existing Yahoo JSON source already used by u49 | none; no new paid path | 12/12 HTTP 200 on the affected GHA run | Existing-source repair only; undocumented rate limit, no tier promotion | **ship-now** |
| Same-run Yahoo history fallback | Derived from the exact `query2` response already fetched by Investo | no extra provider | healthy on affected run | no new external terms | **ship-now** |
| Yonhap market RSS numeric close | Existing RSS/XML source and parser from u67 | none | still emitted two index items after Stooq failure | existing repo-approved source; best-effort prose parse | **ship-now / retain** |
| FRED `DEXKOUS` | Federal Reserve Board H.10 via FRED JSON; daily KRW per USD | existing `FRED_API_KEY`; one request/run | live official data present | public domain, citation requested | **ship-now** |
| Stooq `q/d/l` | JavaScript challenge instead of structured data | no key presented | not machine-readable | anti-automation challenge | **reject** |
| Cboe delayed quote JSON | Cboe JSON | no key | AAPL and `_SPX` returned 200 | Cboe delayed-quote page explicitly prohibits automated extraction | **reject** |
| Nasdaq quote-page JSON | Nasdaq website JSON | no key | AAPL and COMP returned 200 | Nasdaq site agreement prohibits automated data capture | **reject** |
| FRED SP500/DJIA/NASDAQCOM | FRED structured series | existing key | daily values available | series notes impose copyright/reproduction restrictions; S&P/Dow require prior permission | **reject for public fallback** |
| Alpha Vantage / Twelve Data / Finnhub | structured vendor APIs | new free-tier key and metering | not configured in repo | key acquisition and quota contract absent | **defer** |

Primary evidence URLs:

- Yahoo existing path: `https://query2.finance.yahoo.com/v8/finance/chart/{ticker}`
- FRED API: `https://api.stlouisfed.org/fred/series/observations`
- FRED DEXKOUS facts/license: `https://fred.stlouisfed.org/series/DEXKOUS`
- Cboe delayed quote restriction: `https://www.cboe.com/delayed_quotes/api/`
- Nasdaq site agreement: `https://www.nasdaq.com/legal`

## Source Facts

### Yahoo chart — existing source repair

| Field | Value |
| --- | --- |
| Source owner | Yahoo |
| Data family | US index/equity/ETF/futures daily OHLCV |
| Endpoint | `https://query2.finance.yahoo.com/v8/finance/chart/{ticker}?interval=1d&range=1y` |
| Auth | none |
| Cost/no-paid | no API key or paid plan added |
| Rate limit | undocumented; bounded concurrency 2, critical basket first, per-ticker isolation |
| Format | JSON |
| Key fields | `timestamp`, `indicators.quote.open/high/low/close/volume`, `meta.chartPreviousClose` |
| Cadence | daily market bars |
| Reliability | proven 12/12 HTTP 200 on affected GHA run; local/IP 429 remains possible |
| Existing overlap | `yfinance-price` snapshot plus u49 `yfinance_history` |
| Source name | preserve `yfinance-price` |
| Degradation | missing ticker drops; same-run fresh-history fallback; otherwise visible zero/failed outcome |

### FRED H.10 KRW/USD

| Field | Value |
| --- | --- |
| Source owner | Board of Governors of the Federal Reserve System via FRED |
| Data family | daily FX reference rate |
| Endpoint | `https://api.stlouisfed.org/fred/series/observations` with `series_id=DEXKOUS` |
| Auth | existing `FRED_API_KEY` |
| Cost/no-paid | free official API key; already allowed/redacted in repo |
| Request count | one request per run |
| Format | JSON |
| Key fields | observation `date`, `value`; prior observation for comparison |
| Cadence | daily H.10 noon buying rate; holidays/placeholders possible |
| License | public domain; citation requested |
| Existing overlap | `fred-macro` currently requests DEXKOUS as macro context; move the series to the new price adapter to avoid duplicate requests |
| Proposed source name | `fred-fx-close` |
| Proposed adapter | `src/investo/sources/fred_fx_close.py` |
| Degradation | missing key is terminal adapter failure; placeholder/stale >7 calendar days returns zero; siblings unaffected |

## Scope Boundary

In scope:

- Yahoo host/request/parser consolidation.
- Critical-first and enrichment-second price collection.
- Same-run history fallback for missing snapshot tickers.
- Truthful `SourceOutcome` reconciliation before any segment coverage or public rendering.
- Runtime removal of both Stooq source identities and every `q/l` call.
- Truthful replacement identities for the Korean Stooq adapter's surviving legs.
- Registry/tier/window/routing/core-source/test/documentation updates.

Out of scope:

- A new paid or operator-keyed market-data vendor.
- Intraday/realtime quotes.
- Replacing the u49 market-anchor model or adding technical indicators.
- Backfilling old archive pages or renaming historical source references in completed AIDLC documents.
- Treating SPY/QQQ/DIA as exact index closes.
- Publishing restricted FRED index series.
- Qualifying a 12-symbol sector OHLCV source for public GitHub Pages or granting
  derived-display/redistribution rights. That independent gate is owned by u140.

## Fixed Contracts

### Contract 1 — Yahoo chart request

- New shared module: `src/investo/sources/_yahoo_chart.py`.
- `QUERY_HOST = "https://query2.finance.yahoo.com/v8/finance/chart"`.
- `query1.finance.yahoo.com` must not occur in production source code after the unit.
- Request parameters are exactly `interval=1d`, `range=1y` for both snapshot and history paths.
- Browser User-Agent is single-homed in the shared module.
- Parser returns ascending `tuple[OHLCRow, ...]`; explicit chart errors become `SourceFetchError`; malformed rows are skipped.

### Contract 2 — request ordering and basket

- Critical basket, fetched first: `^GSPC,^IXIC,^DJI,^VIX,AAPL,MSFT,GOOGL,AMZN,NVDA,META,TSLA,BZ=F,^RUT`.
- Enrichment basket, fetched only when at least one critical item succeeds: `XLK,XLE,XLF,XLV,XLY,XLI,SMH,IWM,TLT,GLD,USO,UUP,CL=F,GC=F`.
- `INVESTO_YFINANCE_TICKERS` continues to override the critical basket.
- New optional `INVESTO_YFINANCE_ENRICHMENT_TICKERS` overrides the enrichment basket; blank uses the fixed default.
- Concurrency default remains 2. Critical failures never prevent a sibling critical ticker; enrichment failures never remove critical items.

### Contract 3 — same-run fallback

`reconcile_yahoo_history_fallback(...)` is a pure helper with inputs:

- collected `items`
- collected `source_outcomes`
- `market_history_by_ticker`
- target date

For each critical ticker absent from direct `yfinance-price` items:

1. Read only the latest history row.
2. Require `row.trading_date <= target_date` and age `<=4` calendar days.
3. Require finite positive OHLC values and non-negative volume when present.
4. Emit one `NormalizedItem` with `source_name="yfinance-price"`, `category="price"`, the current core-fact metadata contract, and `raw_metadata["provenance"]="query2-history-fallback"`.
5. Never overwrite a direct snapshot item and never emit duplicate tickers.

The helper replaces the one `yfinance-price` outcome only when fallback items are added:

- final status `ok`
- `item_count = direct_count + fallback_count`
- `latest_item_at = max(final item timestamps)`
- preserve direct elapsed time
- emit a structured operator log containing original status and fallback count; no URLs, response bodies, or secrets

The reconciled items and outcomes replace the accumulated pipeline values before segmentation, quality calculation, visual preparation, publish, and notify.

### Contract 4 — Stooq lifecycle retirement

- Remove `stooq_price` and `stooq_kr_market` from `sources/__init__.py` discovery.
- Remove `stooq-price` and `stooq-kr-market` from `SourceSpec`, tier views, market-window views, item/outcome routing, and `SEGMENT_CORE_SOURCES`.
- Delete production modules after their surviving Yonhap logic is migrated.
- Historical AIDLC documents and old fixture metadata may retain the names as immutable evidence.
- Runtime contract tests assert zero registered names containing the retired source identities and zero production URL literals for `stooq.com/q/l/`.

### Contract 5 — Korean replacements

`yonhap-index-close`:

- New module `src/investo/sources/yonhap_index_close.py` reuses the u67 `defusedxml` parser and KOSPI/KOSDAQ patterns.
- One RSS request per run, domestic-only, category `price`, tier B.
- `raw_metadata`: `ticker`, `close`, optional `pct_change`, `provenance=yonhap-rss`, `source_headline`, and core-fact key.
- No KRW/USD item and no Stooq fallback.

`fred-fx-close`:

- New module `src/investo/sources/fred_fx_close.py`, source name `fred-fx-close`, category `price`, tier S, domestic-only.
- Fixed series `DEXKOUS`; remove DEXKOUS from `FredMacroAdapter._DEFAULT_SERIES` to avoid duplicate fetch and mixed routing.
- `published_at` is observation date at 12:00 America/New_York converted to UTC.
- `raw_metadata`: `ticker=KRW=X`, `series_id=DEXKOUS`, `close`, optional `previous_close`, `source_date`, `provenance=fred-h10`, and the `usd_krw` core-fact key.
- Latest valid observation older than 7 calendar days yields zero items.
- Public trace/citation points to `https://fred.stlouisfed.org/series/DEXKOUS`.

### Contract 6 — coverage semantics

- US core source set becomes `{yfinance-price}` with same-run history fallback treated as the same provider/source identity.
- If both direct snapshot and same-run history are empty, US coverage remains limited/failed under u54; no stale archive value is invented.
- Domestic core source set remains `{fsc-krx-index-price}`; the two replacements are fallbacks and do not mask official KRX failure.
- `coingecko-price` remains responsible for crypto price coverage; retired Stooq BTC/ETH rows are not replaced by Yahoo routing.

## Implementation Steps

### Step 1 — Record live evidence and fixtures

- [x] Complete (2026-07-18)

- Add a 2026-07-18 metadata note to the Yahoo/Stooq fixture area with the exact local and GHA results.
- Record/replay `query2 range=1y` fixtures for critical success, 429, chart error, malformed arrays, and partial basket.
- Record/replay FRED `DEXKOUS` valid, placeholder, and stale bodies without an API key value.
- Keep Stooq 404 HTML and JavaScript challenge snippets as test evidence only; production code must not call them.

### Step 2 — Consolidate Yahoo chart handling

- [x] Complete (2026-07-18)

- Add `_yahoo_chart.py` request/parser helper.
- Make `yfinance_history.py` delegate without changing its public functions.
- Make `yfinance.py` use the shared query2/1y contract and preserve the public item shape.
- Add critical-first/enrichment-second sequencing and env parsing.

### Step 3 — Add fallback and outcome reconciliation

- [x] Complete (2026-07-18)

- Add the pure reconciliation helper in `orchestrator/stage_context.py` or a focused sibling module under `orchestrator/`.
- Invoke after `_load_market_anchors_for_run` and before `_stage_generate_segmented`.
- Replace accumulated `items` and `source_outcomes`, not local-only copies.
- Pin direct-wins, freshness, future-row rejection, duplicate suppression, and outcome/public-consistency tests.

### Step 4 — Retire Stooq and preserve Korean legs

- [x] Complete (2026-07-18)

- Migrate the Yonhap parser into `yonhap_index_close.py`.
- Add `fred_fx_close.py` and move DEXKOUS out of `fred-macro` defaults.
- Remove Stooq production modules, imports, source specs, tiers, and routes.
- Update tech-env and CONTRIBUTING source declarations.

### Step 5 — Registry, routing, coverage, and diagnostics

- [x] Complete (2026-07-19)

- Update `src/investo/_internal/source_specs.py` and every derived view.
- Update source plugin count/name tests, market windows, segment item/outcome scopes, and core-source constants.
- Add operator diagnostic `price_fallback_reconciled` with only source name, original status, direct count, fallback count, and final count.
- Confirm no reader-facing status lists a retired source.

### Step 6 — Validation

- [ ] Complete

- Run focused tests listed below.
- Run full source/plugin/segment/orchestrator gates.
- Run no-paid guard and strict docs build.
- Run a GHA exact-date workflow dispatch only during implementation closeout; success requires non-zero `yfinance-price`, zero Stooq requests, and query2 evidence in logs.

## Acceptance Criteria

1. Runtime code contains no Stooq `q/l` request and no Yahoo `query1` request.
2. A replay where direct query2 succeeds emits the same public item contract as current `yfinance-price`.
3. A replay where direct snapshot is empty but history succeeds emits fresh fallback items and a truthful final `ok` outcome.
4. A replay where both paths fail emits no invented items and leaves coverage degraded.
5. Critical items survive complete enrichment failure.
6. `yonhap-index-close` and `fred-fx-close` appear in every required source-spec/routing/test surface; retired Stooq names appear in none of those runtime surfaces.
7. DEXKOUS missing-key, placeholder, stale, and valid paths are deterministic and secret-safe.
8. No Cboe/Nasdaq quote-page endpoint or restricted FRED index series is added.
9. Existing public output shape, numeric core-fact keys, u70 reconciliation, u109 quarantine, u123 evidence accounting, and u128 outcome scoping remain green.

## Tests / Validation

Focused:

```bash
uv run pytest tests/unit/sources/test_yfinance.py tests/unit/sources/test_yfinance_history.py -q
uv run pytest tests/unit/sources/test_fred_fx_close.py tests/unit/sources/test_yonhap_index_close.py -q
uv run pytest tests/unit/sources/test_plugin_contract.py tests/unit/sources/test_source_specs.py tests/unit/sources/test_tiers.py -q
uv run pytest tests/unit/briefing/test_segments.py tests/unit/briefing/test_segments_exclusivity.py -q
uv run pytest tests/unit/orchestrator/test_stage_context_budget.py tests/unit/orchestrator/test_run_pipeline.py -q
```

Repository gates:

```bash
uv run ruff check src tests
uv run ruff format --check src tests
uv run mypy src
uv run pytest -q
uv run python scripts/check_no_paid_apis.py
uv run mkdocs build --strict
git diff --check
```

Static lifecycle checks:

```bash
rg -n 'query1\.finance\.yahoo\.com|stooq\.com/q/l/' src tests/unit/sources/test_plugin_contract.py
rg -n 'stooq-price|stooq-kr-market' src/investo/sources/__init__.py src/investo/_internal/source_specs.py src/investo/briefing/segments.py
rg -n 'yonhap-index-close|fred-fx-close' src/investo/sources/__init__.py src/investo/_internal/source_specs.py src/investo/briefing/segments.py
```

The first two lifecycle searches must return no runtime matches; historical AIDLC and retired fixture evidence are excluded from that assertion.

## Documentation Deliverables

- `aidlc-docs/construction/u138-price-source-endpoint-lifecycle-repair/functional-design/functional-design.md`
- `aidlc-docs/construction/u138-price-source-endpoint-lifecycle-repair/nfr-requirements/nfr-requirements.md`
- `docs/tech-env.md` source/env update during implementation
- `CONTRIBUTING.md` official source declaration update during implementation
- code summary and cross-check report at unit closeout

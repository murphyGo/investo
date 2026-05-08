# Code Generation Plan: `u36 source-expansion-bundles`

**Date**: 2026-05-08
**Unit**: u36 source-expansion-bundles
**Stage**: Code Generation

---

## Goal

Turn the 2026-05-08 five-subagent data-source research into a shippable source expansion unit, covering the top three implementation bundles:

1. **Domestic base layer**: FSC public-data KRX price/index/listing adapters plus Korea policy/financial RSS.
2. **Rates and macro layer**: U.S. Treasury daily rates plus official U.S. macro-calendar feeds.
3. **Crypto market-structure layer**: DeFiLlama market structure plus Binance public crypto market data.

The unit is scoped to free/public data only, existing async `httpx` source-adapter architecture, recorded fixtures, plugin-contract updates, and segment routing/coverage transparency.

---

## Definition of Done

- [x] All new sources are free/public and compatible with NFR-002 monthly `$0` operations. Any source requiring paid access, unofficial Investing.com scraping, CME FedWatch paid API, or unstable browser scraping is explicitly excluded.
- [x] New adapters use the existing `@register` plugin pattern, `SourceAdapter` protocol, shared `retry_get`, `SourceFetchError`, `FetchWindow`, `strip_html`, `defusedxml` for XML/RSS, and recorded fixture tests.
- [x] Domestic-equity gains official price/index coverage:
  - [x] FSC/data.go.kr KRX index daily price adapter.
  - [x] FSC/data.go.kr KRX stock daily price adapter or a bounded watchlist/index proxy if full stock coverage is too broad for the first slice.
  - FSC/data.go.kr listed-issues/reference adapter only if required to map stock codes; otherwise deferred behind the price adapter.
- [x] Domestic-equity gains policy/event RSS coverage from official public feeds (MOEF/FSC/MOTIE/MSS or equivalent `korea.kr` feeds) without using Naver Finance or web-scraped KRX/KIND pages. (Slice 3: official FSC RSS service)
- [x] US-equity and crypto gain daily rates context via U.S. Treasury public data: latest available nominal curve fields plus derived spread metadata (`2y10y`, `3m10y` when available); holiday/date lag is visible in `raw_metadata`.
- [x] US-equity gains official macro-calendar/release context from BLS/BEA/Census public feeds or machine-readable schedules. This is calendar/event context, not forecast generation.
- [x] Crypto gains market-structure context:
  - [x] DeFiLlama public API for TVL / stablecoin supply / DEX or protocol activity.
  - [x] Binance public market endpoints for a small symbol set (`BTCUSDT`, `ETHUSDT`, optionally `SOLUSDT`) covering 24h ticker / daily klines / funding or open-interest if endpoint access is stable.
- [x] Segment routing updates include the new source slugs in `src/investo/briefing/segments.py`, with domestic price coverage resolving the current `domestic-equity` `MISSING_PRICE` gap when data is available.
- [x] `tests/unit/sources/test_plugin_contract.py` adapter count/name imports stay in lockstep with `src/investo/sources/__init__.py`.
- [x] Fixture metadata records endpoint URL, captured timestamp, status, headers relevant to fair access / user-agent policy, and any required API-key placeholder behavior.
- [x] Secret hygiene follows the u27 redaction chokepoint; optional keys such as data.go.kr / ECOS-like keys, if used, are read through shared config and missing-key paths degrade only the relevant adapter. (Slice 1: missing `INVESTO_KRX_SERVICE_KEY` / `INVESTO_DATA_GO_KR_SERVICE_KEY` raises source-local `SourceFetchError` without key leakage)
- [x] Coverage transparency from u22 remains honest: source failure / zero items / missing category reason codes render for all three segments without leaking raw endpoint errors.
- [x] LLM candidate cap from u13 remains effective; high-volume adapters include deterministic per-source caps before Stage 1/2 prompt construction.
- [x] Full quality gate passes: `ruff check`, `ruff format --check`, `mypy --strict src/`, `pytest -q`, `mkdocs build --strict`.

---

## Out of Scope

- CME FedWatch paid API or scraped FedWatch web-tool probabilities.
- Investing.com public-page scraping or third-party paid scrapers.
- Truflation API integration until free-credit/license behavior is explicitly accepted.
- Naver Finance, TradingView, Google News, KRX OTP/KIND scraping, or social APIs.
- Portfolio tracking, trading signals, account linking, or paid vendor data.
- Broad refactors of the source architecture beyond the narrow seams needed for the new adapters.

---

## Steps

### Step 1 — Shared Source-Expansion Scaffolding

- [x] Define new source slugs, module names, categories, and segment ownership for the six planned adapters:
  - `fsc-krx-index-price` (`price`, domestic-equity)
  - `fsc-krx-stock-price` (`price`, domestic-equity; bounded watchlist/index scope)
  - `korea-policy-rss` (`news` or `calendar`, domestic-equity)
  - `treasury-rates` (`macro`, us-equity + crypto cross-market context)
  - `us-economic-calendar` (`calendar` or `macro`, us-equity)
  - `defillama-market-structure` (`macro` or `price`-adjacent metadata, crypto)
  - `binance-crypto-market-structure` (`price`, crypto; optional if rate-limit/geofence fixture is stable)
- [x] Add or extend shared config helpers for optional source keys and symbol lists:
  - [x] `INVESTO_KRX_SERVICE_KEY` or compatible data.go.kr service-key env var.
  - [x] `INVESTO_KRX_STOCK_TICKERS` bounded default/watchlist fallback.
  - `INVESTO_CRYPTO_MARKET_SYMBOLS` defaulting to `BTCUSDT,ETHUSDT,SOLUSDT`.
- [x] Decide whether to ship all seven slugs in one unit or split Step 7's Binance adapter to a follow-up if live fixture access is unstable.

### Step 2 — Domestic Base Layer

- [x] Implement `fsc_krx_index_price.py` using official FSC/data.go.kr JSON/XML endpoint, strict target-date filtering, holiday fallback, numeric-string parsing, and KST-aware timestamps.
- [x] Implement `fsc_krx_stock_price.py` for a bounded stock/watchlist set rather than all listings; normalize OHLCV, market, code, and display name into `raw_metadata`.
- [x] Implement `korea_policy_rss.py` using official RSS feeds only; strip HTML, normalize publication timestamps to KST, dedupe duplicate policy releases, and cap noisy feeds.
- [x] Add fixtures and tests covering successful parse, missing service key (if applicable), holiday/no-row fallback, malformed numeric fields, RSS HTML stripping, and strict source-window behavior. (Domestic base complete: index/stock parse, missing key, holiday fallback, malformed numeric fields, data.go.kr error shape, per-ticker stock isolation, RSS HTML stripping, dedupe, strict window, partial feed failure, and unsupported URL scheme)

### Step 3 — Rates and Macro Layer

- [x] Implement `treasury_rates.py` against U.S. Treasury public daily rates endpoint, no key required; parse latest available row and derive spread metadata.
- [x] Implement `us_economic_calendar.py` from official BLS/BEA/Census machine-readable schedule/RSS feeds; classify scheduled releases without inventing forecasts or expected impact.
- [x] Add fixtures and tests covering no-key happy path, lagged latest date, numeric string conversion, missing rate terms, RSS/calendar date parsing, and source errors.
- [x] Route `treasury-rates` to both `us-equity` and crypto relevance where the existing segment router permits cross-market macro context; otherwise document the routing decision in the adapter test.

### Step 4 — Crypto Market-Structure Layer

- [x] Implement `defillama_market_structure.py` using public JSON endpoints for selected chain/protocol/stablecoin metrics; cap output to a small deterministic set useful for daily briefing.
- [x] Implement `binance_crypto_market.py` using public market endpoints for `BTCUSDT` / `ETHUSDT` / optional `SOLUSDT`; handle 429, unavailable symbols, string decimals, and rolling-24h semantics.
- [x] Add fixtures and tests covering stablecoin/TVL parse, schema drift resilience, symbol filtering, rate-limit/failure degradation, and deterministic ordering.
- [x] Keep raw numeric metrics in `raw_metadata` and produce concise `title`/`summary` text so the Stage 1 candidate cap is not overwhelmed.

### Step 5 — Registration, Routing, and Coverage Transparency

- [x] Import all shipped adapters from `src/investo/sources/__init__.py`.
- [x] Update `tests/unit/sources/test_plugin_contract.py` expected adapter count/names and production re-registration fixture.
- [x] Update `src/investo/briefing/segments.py` source sets so domestic/us/crypto routing reflects the new slugs.
- [x] Confirm domestic-equity `SEGMENT_REQUIRED_CATEGORIES` now has a real official price source; no change to required category thresholds unless tests prove current thresholds are now too low/high.
- [x] Extend coverage/source-outcome tests to prove failures in one new source do not fail the pipeline and are rendered as source-status reasons. (Slice 1 pins `segment_source_outcomes` allowlist for the new domestic source)

### Step 6 — Prompt and Candidate Budget Guard

- [x] Add prompt wording only if needed to teach Stage 1/2 how to read new `raw_metadata` fields:
  - Treasury spread and latest-date lag are factual input, not a forecast.
  - Macro calendars are scheduled facts, not expected outcomes.
  - DeFiLlama/Binance metrics are market-structure context, not investment advice.
- [x] Add deterministic per-source caps for noisy RSS/calendar sources before they reach the u13 total-96 / per-source-24 cap.
- [x] Add prompt regression tests if any prompt text changes; otherwise record that no prompt change was needed.

### Step 7 — Documentation and Source Policy Sync

- [x] Update source adapter documentation / contributing notes with the new official-source preference and rejected-source list.
- [x] Register any deferred findings as TECH-DEBT only when implementation cannot complete a source due to access instability, not as a substitute for tests.
- [x] Add session log and code summary under `docs/sessions/` and `aidlc-docs/construction/u36-source-expansion-bundles/code/summary.md`.

### Step 8 — Verification

- [x] Run adapter-targeted tests after each source slice.
- [x] Run source plugin-contract tests after registration.
- [x] Run segment routing / coverage transparency tests after Step 5.
- [x] Run full quality gate: `ruff check`, `ruff format --check`, `mypy --strict src/`, `pytest -q`, `mkdocs build --strict`.

---

## Source Research Snapshot

This unit comes from the 2026-05-08 user-directed five-subagent research request: "subagent 5개를 병렬로 띄워서 데이터 소스로 추가하면 좋을 곳들을 리서치시키고 취합해봐".

Consolidated implementation bundles selected by the lead:

1. **Domestic base layer**: FSC public-data KRX price/index/listing + official Korea policy RSS.
2. **Rates/macro layer**: U.S. Treasury daily rates + BLS/BEA/Census official macro-calendar/release feeds.
3. **Crypto market-structure layer**: DeFiLlama public market-structure APIs + Binance public market data.

Rejected or deferred by policy: CME FedWatch official API is paid, Investing.com has no public API, Truflation free access/license needs explicit acceptance, and unofficial scraping sources do not match the repo's unattended daily-run and fixture-test discipline.

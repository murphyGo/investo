# Code Summary: u36 source expansion bundles

**Date**: 2026-05-08

## Completed

- Created the u36 source-expansion implementation unit from the 5-subagent source research and shipped all three selected bundles.
- Added `fsc-krx-index-price`, an official FSC/data.go.kr KRX index daily price adapter for domestic-equity price coverage.
- The adapter reads `INVESTO_KRX_SERVICE_KEY` or `INVESTO_DATA_GO_KR_SERVICE_KEY`, raises a source-local `SourceFetchError` when no key is configured, and never includes the key in errors or metadata.
- Added target-date lookup with 7-day holiday fallback, KST 16:00 close timestamps, numeric-string parsing, deterministic index ordering, and concise OHLCV/trading-value summaries.
- Registered the adapter in the plugin surface and updated segment routing so the new domestic, rates/macro, and crypto market-structure sources run under the correct market windows.
- Added `fsc-krx-stock-price`, a bounded official FSC/data.go.kr stock daily price adapter for configured Korean tickers via `INVESTO_KRX_STOCK_TICKERS`.
- The stock adapter isolates ticker-level failures, applies the same missing-key degradation contract, and emits OHLCV, market, ISIN, listed-share, market-cap, and source-date-lag metadata.
- Added `korea-policy-rss`, an official FSC RSS adapter using the Financial Services Commission RSS service. It strips HTML, parses RFC-822/KST timestamps to UTC, dedupes duplicate URLs, caps noisy policy feeds, and isolates per-feed failures.
- Added `treasury-rates`, a no-key U.S. Treasury daily yield-curve adapter routed to both US-equity and crypto for cross-market rates context. It selects the latest row on or before the target date and emits 3M/2Y/10Y/30Y plus 2y10y and 3m10y spread metadata.
- Added `defillama-market-structure`, a no-key DeFiLlama adapter that emits compact crypto market-structure context for chain TVL and stablecoin supply. It isolates endpoint failures so a stablecoin outage can still leave TVL context available, and vice versa.
- Added `binance-crypto-market`, a no-key Binance public 24h ticker adapter for configured symbols (`INVESTO_CRYPTO_MARKET_SYMBOLS`, default BTC/ETH/SOL). It isolates per-symbol failures and emits rolling 24h price, range, VWAP, volume, and trade-count metadata.
- Added `us-economic-calendar`, a no-key official BEA release schedule adapter. It emits upcoming scheduled calendar events without forecasts or expected impact labels.

## Post-Review Hardening

- Added aggregator market-window coverage for `treasury-rates`, `us-economic-calendar`, `defillama-market-structure`, and `binance-crypto-market`.
- Changed Binance item timestamps to use source `closeTime` instead of the fetch window end, while preserving source open/close times in metadata.
- Changed Treasury rate timestamps to use the New York 16:00 market close with DST-aware conversion to UTC.
- Tightened all-child failure behavior so FSC stock and Binance raise `SourceFetchError` when every child request fails, while keeping partial-success isolation.
- Tightened schema-drift behavior for BEA and DeFiLlama so unexpected response shapes fail visibly instead of silently reporting zero items.
- Dropped non-finite DeFiLlama numeric rows before they can enter briefing candidates.

## Files Changed

- `src/investo/sources/fsc_krx_index_price.py` — new FSC/data.go.kr KRX index price adapter.
- `src/investo/sources/fsc_krx_stock_price.py` — new bounded FSC/data.go.kr KRX stock price adapter.
- `src/investo/sources/korea_policy_rss.py` — new official Korean financial-policy RSS adapter.
- `src/investo/sources/treasury_rates.py` — new U.S. Treasury daily yield-curve adapter.
- `src/investo/sources/defillama_market_structure.py` — new DeFiLlama TVL/stablecoin market-structure adapter.
- `src/investo/sources/binance_crypto_market.py` — new Binance public 24h ticker adapter.
- `src/investo/sources/us_economic_calendar.py` — new official BEA release schedule adapter.
- `src/investo/sources/__init__.py` — imports the new adapter for registry discovery.
- `src/investo/sources/aggregator.py` — routes new U.S. and crypto sources through their correct market windows.
- `src/investo/briefing/segments.py` — adds the new source slugs to segment source allowlists.
- `tests/unit/sources/test_fsc_krx_index_price.py` — fixture-based tests for parsing, missing key, holiday fallback, malformed numeric rows, and upstream error shape.
- `tests/unit/sources/test_fsc_krx_stock_price.py` — fixture-based tests for parsing, missing key, holiday fallback, invalid ticker isolation, and upstream error shape.
- `tests/unit/sources/test_korea_policy_rss.py` — fixture-based tests for FSC RSS parsing, HTML stripping, date-window filtering, dedupe/sort, partial feed failure, all-feed failure, and unsupported schemes.
- `tests/unit/sources/test_treasury_rates.py` — fixture-based tests for latest available curve selection, lag metadata, spread computation, empty feed, and malformed rates.
- `tests/unit/sources/test_defillama_market_structure.py` — fixture-based tests for TVL/stablecoin parsing, partial endpoint failure, all-endpoint failure, and malformed payloads.
- `tests/unit/sources/test_binance_crypto_market.py` — fixture-based tests for symbol parsing, per-symbol isolation, and malformed payloads.
- `tests/unit/sources/test_us_economic_calendar.py` — fixture-based tests for BEA schedule parsing and empty schedule handling.
- `tests/unit/sources/fixtures/api/fsc-krx-index-price/` — deterministic JSON fixtures.
- `tests/unit/sources/test_plugin_contract.py` — adapter contract count/name/import updates.
- `tests/unit/briefing/test_segments.py` — domestic routing and source-outcome allowlist coverage.
- `aidlc-docs/aidlc-state.md` and `aidlc-docs/construction/plans/u36-source-expansion-bundles-code-generation-plan.md` — u36 marked complete with corrected adapter count and source scope.

## Verification

- `uv run pytest tests/unit/sources/test_fsc_krx_index_price.py tests/unit/sources/test_plugin_contract.py tests/unit/briefing/test_segments.py -q`
- `uv run pytest tests/unit/sources/test_fsc_krx_stock_price.py tests/unit/sources/test_plugin_contract.py tests/unit/briefing/test_segments.py -q`
- `uv run pytest tests/unit/sources/test_korea_policy_rss.py tests/unit/sources/test_plugin_contract.py tests/unit/briefing/test_segments.py -q`
- `uv run pytest tests/unit/sources/test_treasury_rates.py tests/unit/sources/test_plugin_contract.py tests/unit/briefing/test_segments.py -q`
- `uv run pytest tests/unit/sources/test_defillama_market_structure.py tests/unit/sources/test_plugin_contract.py tests/unit/briefing/test_segments.py -q`
- `uv run pytest tests/unit/sources/test_binance_crypto_market.py tests/unit/sources/test_us_economic_calendar.py tests/unit/sources/test_plugin_contract.py tests/unit/briefing/test_segments.py -q`
- Post-review hardening targeted regression suite: `uv run pytest tests/unit/sources/test_aggregator.py tests/unit/sources/test_binance_crypto_market.py tests/unit/sources/test_treasury_rates.py tests/unit/sources/test_fsc_krx_stock_price.py tests/unit/sources/test_defillama_market_structure.py tests/unit/sources/test_us_economic_calendar.py -q` — 43 passed.
- Full quality gate after hardening: `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy --strict src/`, `uv run pytest -q` (1344 passed), and `uv run mkdocs build --strict`.

## Remaining Scope

- None for u36. Follow-up source candidates should become new units rather than expanding this one.

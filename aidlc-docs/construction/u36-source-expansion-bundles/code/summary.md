# Code Summary: u36 source expansion bundles

**Date**: 2026-05-08

## Completed

- Created the u36 source-expansion implementation unit from the 5-subagent source research and started the first domestic-base slice.
- Added `fsc-krx-index-price`, an official FSC/data.go.kr KRX index daily price adapter for domestic-equity price coverage.
- The adapter reads `INVESTO_KRX_SERVICE_KEY` or `INVESTO_DATA_GO_KR_SERVICE_KEY`, raises a source-local `SourceFetchError` when no key is configured, and never includes the key in errors or metadata.
- Added target-date lookup with 7-day holiday fallback, KST 16:00 close timestamps, numeric-string parsing, deterministic index ordering, and concise OHLCV/trading-value summaries.
- Registered the adapter in the plugin surface and updated domestic segment routing so `domestic-equity` can satisfy its required `price` category when the official index source returns data.
- Added `fsc-krx-stock-price`, a bounded official FSC/data.go.kr stock daily price adapter for configured Korean tickers via `INVESTO_KRX_STOCK_TICKERS`.
- The stock adapter isolates ticker-level failures, applies the same missing-key degradation contract, and emits OHLCV, market, ISIN, listed-share, market-cap, and source-date-lag metadata.
- Added `korea-policy-rss`, an official FSC RSS adapter using the Financial Services Commission RSS service. It strips HTML, parses RFC-822/KST timestamps to UTC, dedupes duplicate URLs, caps noisy policy feeds, and isolates per-feed failures.

## Files Changed

- `src/investo/sources/fsc_krx_index_price.py` — new FSC/data.go.kr KRX index price adapter.
- `src/investo/sources/fsc_krx_stock_price.py` — new bounded FSC/data.go.kr KRX stock price adapter.
- `src/investo/sources/korea_policy_rss.py` — new official Korean financial-policy RSS adapter.
- `src/investo/sources/__init__.py` — imports the new adapter for registry discovery.
- `src/investo/briefing/segments.py` — adds `fsc-krx-index-price` to the domestic-equity source allowlist.
- `tests/unit/sources/test_fsc_krx_index_price.py` — fixture-based tests for parsing, missing key, holiday fallback, malformed numeric rows, and upstream error shape.
- `tests/unit/sources/test_fsc_krx_stock_price.py` — fixture-based tests for parsing, missing key, holiday fallback, invalid ticker isolation, and upstream error shape.
- `tests/unit/sources/test_korea_policy_rss.py` — fixture-based tests for FSC RSS parsing, HTML stripping, date-window filtering, dedupe/sort, partial feed failure, all-feed failure, and unsupported schemes.
- `tests/unit/sources/fixtures/api/fsc-krx-index-price/` — deterministic JSON fixtures.
- `tests/unit/sources/test_plugin_contract.py` — adapter contract count/name/import updates.
- `tests/unit/briefing/test_segments.py` — domestic routing and source-outcome allowlist coverage.
- `aidlc-docs/aidlc-state.md` and `aidlc-docs/construction/plans/u36-source-expansion-bundles-code-generation-plan.md` — u36 moved from planned to in-progress slice 1.

## Verification

- `uv run pytest tests/unit/sources/test_fsc_krx_index_price.py tests/unit/sources/test_plugin_contract.py tests/unit/briefing/test_segments.py -q`
- `uv run pytest tests/unit/sources/test_fsc_krx_stock_price.py tests/unit/sources/test_plugin_contract.py tests/unit/briefing/test_segments.py -q`
- `uv run pytest tests/unit/sources/test_korea_policy_rss.py tests/unit/sources/test_plugin_contract.py tests/unit/briefing/test_segments.py -q`

## Remaining Scope

- U.S. Treasury rates and official macro-calendar adapters.
- DeFiLlama and Binance public market-structure adapters.
- Full quality gate after the next broader slice.

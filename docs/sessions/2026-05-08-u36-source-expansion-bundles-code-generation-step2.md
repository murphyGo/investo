# 2026-05-08 u36 source expansion bundles — step 2

## Context

After landing the official KRX index source, continue the domestic base layer with a bounded stock price source.

## Implementation

- Added `src/investo/sources/fsc_krx_stock_price.py`.
- Registered `fsc-krx-stock-price` in source discovery and plugin-contract tests.
- Added the source to domestic segment routing.
- Added fixture tests for two Korean tickers, missing key handling, holiday fallback, invalid ticker isolation, and upstream data.go.kr error shape.

## Verification

```bash
uv run pytest tests/unit/sources/test_fsc_krx_stock_price.py tests/unit/sources/test_plugin_contract.py tests/unit/briefing/test_segments.py -q
```

Result: 26 passed.

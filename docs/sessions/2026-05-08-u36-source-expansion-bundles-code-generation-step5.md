# 2026-05-08 u36 source expansion bundles — step 5

## Context

Start the crypto market-structure bundle with a no-key public DeFiLlama source.

## Implementation

- Added `src/investo/sources/defillama_market_structure.py`.
- Registered `defillama-market-structure` in source discovery and plugin-contract tests.
- Added the source to crypto segment routing.
- Added fixture tests for TVL/stablecoin parsing, deterministic ordering, partial endpoint failure, all-endpoint failure, and malformed payloads.

## Verification

```bash
uv run pytest tests/unit/sources/test_defillama_market_structure.py tests/unit/sources/test_plugin_contract.py tests/unit/briefing/test_segments.py -q
```

Result: 25 passed.

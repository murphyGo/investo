# 2026-05-08 u36 source expansion bundles — step 4

## Context

Start the rates/macro bundle with a no-key official rates source useful to both US-equity and crypto segments.

## Source

U.S. Treasury daily treasury par yield curve rates XML.

## Implementation

- Added `src/investo/sources/treasury_rates.py`.
- Registered `treasury-rates` in source discovery and plugin-contract tests.
- Routed `treasury-rates` to both US-equity and crypto segment source allowlists.
- Added fixture tests for latest-row selection, lag metadata, spread computation, empty feed, and malformed rates.

## Verification

```bash
uv run pytest tests/unit/sources/test_treasury_rates.py tests/unit/sources/test_plugin_contract.py tests/unit/briefing/test_segments.py -q
```

Result: 24 passed.

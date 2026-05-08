# 2026-05-08 u36 source expansion bundles — step 1

## Context

User requested that the 5-subagent domestic-source research be turned into an AIDLC unit first, then development proceed.

## Decision

Start with `fsc-krx-index-price` because it directly fills the domestic-equity `price` category gap with an official/free FSC/data.go.kr source while preserving the existing adapter and fixture architecture.

## Implementation

- Added `src/investo/sources/fsc_krx_index_price.py`.
- Registered the adapter in `src/investo/sources/__init__.py`.
- Added `fsc-krx-index-price` to domestic segment routing.
- Updated plugin-contract and segment tests.
- Added deterministic recorded-shape JSON fixtures and adapter tests.

## Verification

```bash
uv run pytest tests/unit/sources/test_fsc_krx_index_price.py tests/unit/sources/test_plugin_contract.py tests/unit/briefing/test_segments.py -q
```

Result: 26 passed.

# u115 source-spec-registry-unification - Code Summary

**Date**: 2026-06-24
**Status**: Complete
**Stage**: Code Generation

## Summary

Added a shared-leaf `SourceSpec` descriptor registry so production source tier,
market-window, item-routing, and outcome-segment metadata are single-sourced
outside both `sources` and `briefing`.

## Changes

- Added `src/investo/_internal/source_specs.py`
  - `SourceSpec`
  - `SourceItemRouting`
  - `SOURCE_SPECS`
  - `SOURCE_SPECS_BY_NAME`
  - descriptor view helpers for market window, item segment, outcome segment,
    and routing mode.
- Refactored `src/investo/sources/tiers.py`
  - `ADAPTER_TIERS` is now derived from `SOURCE_SPECS`.
  - Unknown non-production stubs still fall back to `DEFAULT_TIER`.
- Refactored `src/investo/sources/aggregator.py`
  - `_US_MARKET_SOURCES` and `_CRYPTO_MARKET_SOURCES` are now descriptor-derived.
  - Unknown source names still use the domestic window fallback.
- Refactored `src/investo/briefing/segments.py`
  - Single-segment, shared, and outcome source sets are now descriptor-derived.
  - CFTC contract-group routing, `treasury-rates` fan-out, and `stooq-price`
    US-window/crypto-outcome semantics are preserved.
- Updated tests
  - `tests/unit/sources/test_plugin_contract.py` now derives expected adapter
    names/counts from specs and still compares them to production registration.
  - Added `tests/unit/sources/test_source_specs.py` for descriptor uniqueness,
    valid segment membership, special-case semantics, and module-boundary purity.
  - Added a subprocess discoverability guard proving `import investo.sources`
    registers every descriptor-backed production adapter without relying on
    direct test-module adapter imports.
- Code review follow-up:
  - Replaced arbitrary CFTC routing-source selection with a single-source
    assertion helper.

## Validation

```bash
uv run --extra dev pytest tests/unit/sources/test_source_specs.py tests/unit/sources/test_plugin_contract.py tests/unit/sources/test_tiers.py tests/unit/sources/test_aggregator.py tests/unit/briefing/test_segments.py tests/unit/briefing/test_segments_exclusivity.py tests/unit/briefing/test_segments_count_split.py tests/unit/briefing/test_segments_severity.py tests/unit/briefing/test_segments_staleness.py
# 175 passed

uv run --extra dev ruff check src/investo/_internal/source_specs.py src/investo/sources src/investo/briefing/segments.py tests/unit/sources tests/unit/briefing
# All checks passed

uv run --extra dev mypy src
# Success: no issues found in 217 source files
```

## TECH-DEBT

None.

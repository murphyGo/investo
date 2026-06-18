# u102 Code Generation Summary

## Overview

u102 closes the source-adapter registry completeness gap found during the 2026-06-18 data-source expansion review. The unit adds tests that fail loudly when a registered production adapter lacks explicit tier metadata, segment routing, or a market-clock window assignment.

## Files Changed

- Modified: `src/investo/sources/tiers.py`
- Modified: `src/investo/sources/aggregator.py`
- Modified: `tests/unit/sources/test_plugin_contract.py`
- Modified: `tests/unit/sources/test_aggregator.py`
- Modified: `tests/unit/sources/test_tiers.py`

## Implementation

- Added plugin-contract coverage requiring every registered production adapter to have an explicit `ADAPTER_TIERS` entry.
- Added plugin-contract coverage requiring `ADAPTER_TIERS` not to retain stale unregistered production entries.
- Added plugin-contract coverage requiring every registered production adapter to be routed by exactly one segment-only source set or the explicit shared-source map.
- Added plugin-contract coverage tying `_SEGMENT_SOURCES` outcome routing to segment-only, shared, and explicit extra-outcome maps.
- Added aggregator coverage requiring every US-only source to be present in `_US_MARKET_SOURCES` and every crypto-only source to be present in `_CRYPTO_MARKET_SOURCES`.
- Added parametrized window checks for all US and crypto market-window source registrations.
- Added a regression proving unknown non-production stubs still use `DEFAULT_TIER` and emit the diagnostic fallback log.
- Filled explicit tier omissions for `alternative-fng`, `bybit-derivatives`, `coingecko-global-market`, `okx-derivatives`, and `stooq-kr-market`.
- Removed stale `coingecko-events` from production tier metadata.
- Filled market-window omissions for `alternative-fng`, `bybit-derivatives`, `coingecko-global-market`, `okx-derivatives`, `fed-board-leadership`, and `stooq-price`.
- Split the `stooq-price` crypto outcome exception into `_OUTCOME_EXTRA_SOURCES_BY_SEGMENT` so tests can verify the full outcome routing composition without changing item routing.

## Acceptance Criteria

| AC | Result | Evidence |
| --- | --- | --- |
| Registered adapter without an `ADAPTER_TIERS` entry fails tests | Met | `test_registered_adapters_have_explicit_tiers` |
| Registered adapter without segment membership fails tests | Met | `test_registered_adapters_have_explicit_segment_routing` |
| US-only or crypto-only adapter omitted from market-window sets fails tests | Met | `test_all_us_only_sources_have_new_york_market_window_registration`, `test_all_crypto_only_sources_have_utc_market_window_registration` |
| No public source outcome or reader-facing tier changes except explicit registrations | Met | Registry map omissions were filled and one stale unregistered tier entry was removed; no source fetch/parsing or markdown rendering changed |
| Default tier fallback remains for non-production stubs | Met | `test_unknown_adapter_fallback_emits_diagnostic_log` |

## Validation

- `uv run pytest tests/unit/sources/test_plugin_contract.py tests/unit/sources/test_aggregator.py tests/unit/sources/test_tiers.py tests/unit/briefing/test_segments*.py -q` -> 148 passed
- `uv run ruff check tests/unit/sources/test_plugin_contract.py tests/unit/sources/test_aggregator.py tests/unit/sources/test_tiers.py src/investo/sources src/investo/briefing/segments.py` -> clean

## Code Review

Subagent review found no blocking issues. One Medium suggestion to make `_SEGMENT_SOURCES` outcome composition testable and one Low suggestion to reject stale tier entries were both addressed before close.

## Scope Notes

No new adapter, external network call, dependency, secret, paid API, archive backfill, or reader-facing markdown feature was added.

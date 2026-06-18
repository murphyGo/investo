# Code Generation Plan: `u102 source-adapter-registry-completeness`

**Date**: 2026-06-18
**Unit**: u102 source-adapter-registry-completeness
**Stage**: Code Generation
**Status**: Complete (6/6 steps — 2026-06-18)
**Source**: 2026-06-18 ten-agent data-source expansion review.
**Estimated Effort**: ~1-2 h
**Dependencies**:
- u1 source adapter plugin contract
- u8 market-aware source window
- u22 source coverage transparency
- u54 source-status severity

---

## Problem Statement

Investo's source layer registers adapters in several separate places:

- `src/investo/sources/__init__.py` imports adapter modules.
- `tests/unit/sources/test_plugin_contract.py` pins adapter names/count.
- `src/investo/sources/tiers.py` maps adapters to reader-facing source tiers.
- `src/investo/sources/aggregator.py` maps adapter names to market-clock windows.
- `src/investo/briefing/segments.py` maps source outcomes and items to market segments.

The review found that an adapter can be registered while missing tier or market-window registration. That causes reader-facing tier drift, wrong date-window filtering, and silent default behavior. This is a source-quality problem before any new provider is added.

## Goal

Make source registration complete-by-test. A future source adapter must fail tests unless it has explicit tier, segment routing, and market-clock coverage.

## Existing Coverage / Deduplication

- `test_plugin_contract.py` already pins adapter count and adapter names.
- `tiers.adapter_tier()` defaults unknown adapters to `B`; this unit keeps that fallback for tests but prevents production adapters from reaching it.
- `aggregator._window_for_adapter()` already applies US/New York, crypto/UTC, and domestic/KST windows.
- This unit adds no external source and changes no runtime output.

## Scope Boundary

In scope:
- Tests that compare registered adapters to `ADAPTER_TIERS`.
- Tests that compare registered adapters to segment membership maps.
- Tests that assert market-clock assignment for all registered US and crypto adapters.
- Small helper functions only when needed to make tests readable.

Out of scope:
- Adding data sources.
- Changing source severity policy.
- Refactoring the registry into a new abstraction.
- Changing public markdown output.

## Stage Decision

Functional Design: skip. This is a test-contract hardening slice over existing source registry behavior.

NFR Requirements: skip. No new dependency, network call, secret, or cost surface is introduced.

## Implementation Steps

- [x] Add a test in `tests/unit/sources/test_plugin_contract.py` asserting every registered production adapter has an explicit `ADAPTER_TIERS` entry.
- [x] Add a test asserting every registered adapter appears in exactly one segment-only source set or in the explicit shared-source map.
- [x] Add market-clock assignment tests for all production adapters listed in `_US_MARKET_SOURCES` and `_CRYPTO_MARKET_SOURCES`.
- [x] Add a focused regression proving unknown test stubs still receive the default tier path and emit a diagnostic log.
- [x] Update any existing adapter map omissions surfaced by the new tests.
- [x] Run focused tests for source plugin contract, aggregator window routing, and segment routing.

## Acceptance Criteria

1. A newly registered adapter without an `ADAPTER_TIERS` entry fails the unit test suite.
2. A newly registered adapter without segment membership fails the unit test suite.
3. A US-only or crypto-only adapter omitted from aggregator market-window sets fails a focused test.
4. No public source outcome or reader-facing tier changes occur except fixing currently omitted explicit registrations.
5. The default tier fallback remains available for non-production stubs.

## Tests / Validation

- `uv run pytest tests/unit/sources/test_plugin_contract.py -q`
- `uv run pytest tests/unit/sources/test_aggregator.py -q`
- `uv run pytest tests/unit/briefing/test_segments*.py -q`
- `uv run ruff check tests/unit/sources/test_plugin_contract.py tests/unit/sources/test_aggregator.py src/investo/sources src/investo/briefing/segments.py`

## Non-Goals

- No new adapters.
- No external HTTP fixture recording.
- No source-health policy redesign.
- No MkDocs or archive backfill.

# Code Generation Plan: `u115 source-spec-registry-unification`

**Date**: 2026-06-24
**Unit**: u115 source-spec-registry-unification
**Stage**: Code Generation
**Status**: Backlog / Planned
**Source**: 2026-06-24 clean-code architecture review; follow-up to u102 source-adapter-registry-completeness.
**Estimated Effort**: ~3-5 h
**Dependencies**:
- u1 source adapter plugin contract is complete.
- u7 segmented briefing is complete.
- u8 market-aware source window is complete.
- u22 source coverage transparency is complete.
- u32 source tier registry is complete.
- u45 segment routing exclusivity is complete.
- u54 source-status severity is complete.
- u102 source-adapter-registry-completeness is complete.
- u114 shared-domain-contract-boundary is planned immediately before this unit; this unit must preserve the same sibling-boundary direction.

---

## Problem Statement

u102 made incomplete source registration loud, but source metadata is still duplicated across:

- `sources/__init__.py` adapter imports and registry discovery
- `sources/tiers.py` tier table
- `sources/aggregator.py` market-window sets
- `briefing/segments.py` segment/outcome routing tables
- plugin-contract tests with expected names/counts

Adding a source still requires editing several independent source-name truth tables.

## Goal

Create a small explicit `SourceSpec` descriptor registry that centralizes each production adapter's name, tier, market window, item routing mode, and outcome segment membership. Existing consumers derive compatibility views from this registry while preserving current runtime behavior and explicit adapter imports.

The descriptor must live in a shared leaf module, not under `sources`, because both `sources` and `briefing` consume it. This avoids turning `sources` into a sibling dependency for `briefing`.

## Existing Coverage / Deduplication

- u102 already proves every registered adapter has tier, segment routing, and market-window coverage.
- `adapter_tier()` keeps a default fallback for non-production stubs.
- `_window_for_adapter()` keeps a domestic fallback for unknown test stubs.
- Special routing for `treasury-rates`, `cftc-cot-positioning`, and `stooq-price` already exists and must remain behavior-owned by `briefing/segments.py`.

## Scope Boundary

In scope:
- Add a frozen data-only `SourceSpec` module under `_internal`.
- Populate specs for all currently registered production adapters, derived from `list_sources()` during implementation.
- Derive `ADAPTER_TIERS` from specs while keeping the exported constant.
- Derive aggregator market-window sets from specs while keeping private compatibility names.
- Derive normal segment/outcome membership sets from specs while keeping existing private compatibility names.
- Replace duplicated expected adapter lists/counts in tests with descriptor-derived expectations.
- Add descriptor/registry drift tests in both directions.

Out of scope:
- No DI framework.
- No dynamic adapter auto-discovery.
- No source adapter additions/removals.
- No source tier reclassification.
- No severity/core-source/macro-actual/lookahead threshold policy redesign.
- No public markdown, prompt, archive, or notifier output change.

## Stage Decision

Functional Design: skip. This is a bounded internal registry refactor; the descriptor contract is pinned here.

NFR Requirements: skip. No new dependency, source, secret, paid service, workflow, or runtime infrastructure is introduced.

## Fixed Contracts

Add `src/investo/_internal/source_specs.py` with a small immutable descriptor, for example:

```python
@dataclass(frozen=True, slots=True)
class SourceSpec:
    name: str
    tier: SourceTier
    market_window_segment: MarketSegment
    item_routing: SourceItemRouting
    item_segments: frozenset[MarketSegment]
    outcome_segments: frozenset[MarketSegment]
```

Recommended routing literals:

```python
SourceItemRouting = Literal[
    "single-segment",
    "shared-segments",
    "us-with-crypto-signal",
    "cftc-contract-group",
]
```

Rules:

- `name` must match `SourceAdapter.name`.
- The descriptor module must not import `investo.sources`, adapter modules, `investo.briefing`, or mutate the plugin registry.
- `sources`, `briefing`, and `orchestrator` may import the descriptor; the descriptor may import only shared leaf contracts such as `models.SourceTier` and `models.MarketSegment`.
- `tier` replaces the independent `ADAPTER_TIERS` source-name table.
- `market_window_segment` drives aggregator market-window compatibility sets.
- `item_segments` and `outcome_segments` drive normal segment membership compatibility sets.
- Special item-routing logic remains implemented in `briefing/segments.py`; the descriptor names the routing mode and membership.

Compatibility requirements:

- Importing `investo.sources` still registers adapters through explicit imports.
- `adapter_tier("unknown-test-stub")` still returns `DEFAULT_TIER`.
- `_window_for_adapter(target_date, "unknown-test-stub")` still uses the domestic window.
- Existing private constants may remain as derived compatibility views.

## Implementation Steps

- [ ] Add `src/investo/_internal/source_specs.py` with `SourceSpec`, routing literals, `SOURCE_SPECS`, `SOURCE_SPECS_BY_NAME`, and helper functions.
- [ ] Populate `SOURCE_SPECS` for every current production adapter by comparing with `list_sources()`.
- [ ] Refactor `sources/tiers.py` so `ADAPTER_TIERS` is derived from specs.
- [ ] Refactor `sources/aggregator.py` so `_US_MARKET_SOURCES` and `_CRYPTO_MARKET_SOURCES` are derived from specs.
- [ ] Refactor `briefing/segments.py` so normal segment/outcome source sets are derived from specs while preserving special-case routing logic.
- [ ] Update `tests/unit/sources/test_plugin_contract.py` to use descriptor-derived expected names/counts.
- [ ] Add `tests/unit/sources/test_source_specs.py` for uniqueness, stale descriptors, missing specs, tier/window/segment completeness, and special-case semantics.
- [ ] Keep compatibility tests proving private derived sets match descriptor-derived sets.
- [ ] Run focused source and segment validation.
- [ ] Write `aidlc-docs/construction/u115-source-spec-registry-unification/code/summary.md`.

## Acceptance Criteria

1. `set(spec.name for spec in SOURCE_SPECS)` equals the production registered adapter names.
2. A registered production adapter without a `SourceSpec` fails tests.
3. A stale `SourceSpec` without a registered adapter fails tests.
4. `SourceSpec` canonical data lives in `_internal/source_specs.py`; `briefing/segments.py` must not import `investo.sources`.
5. `ADAPTER_TIERS` is descriptor-derived.
6. Aggregator market-window membership is descriptor-derived.
7. Normal segment/outcome membership is descriptor-derived.
8. CFTC item routing remains `contract_group` based.
9. `stooq-price` keeps US-window collection, US default item routing, crypto-signal override, and crypto outcome relevance.
10. `treasury-rates` still fans out to US and crypto.
11. Unknown non-production stubs keep existing tier/window fallback behavior.
12. Public source outcomes and segment coverage stay unchanged for existing fixtures.

## Tests / Validation

```bash
uv run --extra dev pytest tests/unit/sources/test_source_specs.py tests/unit/sources/test_plugin_contract.py tests/unit/sources/test_tiers.py tests/unit/sources/test_aggregator.py
uv run --extra dev pytest tests/unit/briefing/test_segments.py tests/unit/briefing/test_segments_exclusivity.py tests/unit/briefing/test_segments_count_split.py tests/unit/briefing/test_segments_severity.py tests/unit/briefing/test_segments_staleness.py
uv run --extra dev ruff check src/investo/_internal/source_specs.py src/investo/sources src/investo/briefing/segments.py tests/unit/sources tests/unit/briefing
uv run --extra dev mypy src
```

## Non-Goals

- No adapter auto-loading.
- No plugin registry rewrite.
- No DI container.
- No new data source.
- No source tier reclassification.
- No segment severity or core-source policy change.
- No LLM prompt change.

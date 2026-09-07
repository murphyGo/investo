# Code Generation Plan: `u151 shared-macro-positioning-kind-boundary`

**Date**: 2026-09-06
**Unit**: u151 shared-macro-positioning-kind-boundary
**Stage**: Code Generation
**Status**: Backlog — ready for Functional Design; implementation design-gated
**Source**: `briefing-review-20260906.md`; September 1–4 committed briefings at `d553035`
**Estimated Effort**: ~5–8 h
**Dependencies**:
- u57/u60 shared-macro detection and representative ranking — complete.
- u74 cause-map, u107 CFTC metadata/routing, u124 daily thesis — complete.
- DEBT-076 tracks rendered-label coupling; close it only after implementation validation.

## Problem Statement

`archive/us-equity/2026/09/2026-09-04.md:27` presents `CFTC WTI crude oil
managed_money net +94281 contracts` as `국제 유가`; line 36 then presents an
oil/geopolitics connection. Domestic and crypto repeat the same pair. A weekly
contract position is admitted by a title keyword and becomes a shared price
or market-driver premise. `_daily_thesis_signals` independently applies the
same matcher, so changing only the rendered label leaves a second leak.

## Goal

CFTC positions remain available as delayed positioning context in their
existing routed channels, but cannot supply the existing shared oil/yield/FOMC
keys or their deterministic cause-map/thesis signals. Cause-map eligibility
must come from selected structured keys, independent of translated labels.

## Existing Coverage / Deduplication

- u60 owns the matchers, canonical UST prerequisite and deterministic ranking;
  extend those chokepoints rather than adding another detector.
- u107 owns collection, trader category, report/as-of/release dates and channel
  positioning rows; do not alter its adapter or source routing.
- u74 owns allowed cause types and suppress-and-log behavior; keep that gate.
- u124 owns segment-native daily thesis decisions; filter its evidence inputs,
  without inventing another thesis selector.
- DEBT-076's typed-key transport is included. Its debt status remains open
  during planning and closes only with the implementation's rendered tests.

## Scope Boundary

In scope: positioning rejection at shared classification, typed key transport,
cause-map key consumption, matching daily-thesis eligibility, regressions.
Out of scope: CFTC schedule estimation, any new macro key, source qualification,
general natural-language causal inference, arbitrary paragraph rewriting,
new price/positioning scores, historical archive edits.

## Stage Decision

Functional Design: REQUIRED — add a shared model field and freeze the legacy
context compatibility rule before implementation. Fixed Contracts below are
the proposed design baseline; this planning run does not record approval.

NFR Requirements: SKIP — existing NFR-003/005/006 and R13 apply; no new I/O,
dependency, source, secret, LLM invocation, retry or cost.

## Fixed Contracts

1. Define `SharedMacroKey = Literal["fomc", "oil", "ust_yield"]` in
   `src/investo/models/bundle_context.py` and add
   `detected_macro_keys: frozenset[SharedMacroKey] = frozenset()` to
   `BundleContext`. Reject unknown key values through the model. An empty
   field means no proven cause-map keys; never infer keys from the string as a
   legacy fallback.
2. An item whose `source_name == "cftc-cot-positioning"` is ineligible for all
   three existing shared-macro matchers. Source identity takes precedence even
   with missing/malformed metadata or misleading titles. This is a bounded
   exclusion for the existing positioning producer, not a new universal
   financial taxonomy. Other producer eligibility remains under u60's rules.
3. Apply that eligibility predicate through the shared matcher entry path
   used by both `_detect_shared_macros` and `_daily_thesis_signals`.
   Positioning rows do not contribute to the two-distinct-segment threshold,
   representative ranking, or a core daily-thesis signal. Do not remove them
   from the routed item tuple, prompt source list, or channel anchor renderer.
4. Populate `detected_macro_keys` only from the final selected `shared` pairs
   after u60 prerequisites and the two-segment threshold pass. `shared_macro_block`
   continues rendering the same selected pairs. Serialize sets in deterministic
   order wherever a prompt/log/fixture needs a sequence; never depend on set
   iteration order.
5. Cause-map mapping stays `oil -> geopolitical_oil_macro`,
   `fomc/ust_yield -> fed_policy_event`, deduplicated in existing output order.
   `global_systemic_risk` remains dormant. Both a nonempty shared block and a
   mapped typed key are required; `cross_market_core_allowed` remains the
   independent second gate. Renaming a Korean label cannot change eligibility.
6. Existing contexts with a nonempty block and empty keys yield no cause-map
   line; their shared block can still display. Update all in-repo constructor
   fixtures that intend proven evidence to supply keys explicitly.
7. Rejection logging uses the existing bounded candidate log with reason
   `positioning_not_shared_macro`; no raw_metadata, URL, or full payload output.

## Implementation Steps

- [ ] Step 1 — Characterize September 4's CFTC WTI promotion with synthetic
  `NormalizedItem` fixtures and the existing `compute_bundle_context` path.
  Include a mixed case where eligible oil news in one segment plus CFTC in
  another must not meet the two-segment threshold.
- [ ] Step 2 — Add the typed model field and source-kind exclusion in
  `orchestrator/bundle_context.py`; update `_detect_shared_macros`,
  `_daily_thesis_signals` and `compute_bundle_context` as one eligibility path.
- [ ] Step 3 — Replace `_candidate_types(block)` label search in
  `publisher/cross_market_cause_map.py` with typed-key lookup; remove dead label
  mirrors while preserving cause ordering and forbidden-type suppression.
- [ ] Step 4 — Inspect all `BundleContext` construction/copy/serialization sites,
  including `public_document.py::_snapshot_bundle_context` and
  `models/bundle_context.py::with_self_pending`, to preserve the field. Update
  prompt and daily-thesis fixtures without changing their ranking policies.
- [ ] Step 5 — Run finalizer-backed rendered regression: CFTC WTI alone produces
  neither the shared oil line nor oil cause-map/thesis; US/crypto positioning
  channel rows still contain their existing dates and weekly-lag label.
- [ ] Step 6 — Run the local gate; record AC results and close DEBT-076 only
  after relabel-resilience and legacy-empty-key behavior pass.

## Acceptance Criteria

1. AC-151.1: Every CFTC contract group, including energy/rates/crypto and absent
   metadata, is rejected for all existing shared keys regardless of title.
2. AC-151.2: One eligible segment plus any number of CFTC rows is insufficient;
   eligible evidence in two distinct segments still qualifies under u60.
3. AC-151.3: Selected keys, rendered shared block and daily-thesis core inputs
   derive from the same eligible candidates; no CFTC source ID supplies a core
   shared signal.
4. AC-151.4: Cause-map survives a presentation-label change with keys fixed,
   emits nothing for empty keys, and still suppresses forbidden cause types.
5. AC-151.5: Three-segment final Markdown removes the incident's deterministic
   overpromotion while retaining routed positioning rows and delayed labels.
6. AC-151.6: Identical/permuted equivalent input produces the same selected
   evidence and rendered output; no adapter/network/source contract changes.

## Tests / Validation

- Extend `tests/unit/orchestrator/test_bundle_context.py` with source-kind,
  threshold, missing metadata, representative ranking and permutation cases.
- Extend `tests/unit/models/test_bundle_context_allowlist.py` with typed-key
  validation/default/copy checks.
- Extend `tests/unit/publisher/test_cross_market_cause_map.py`,
  `test_shared_macro_block.py`, `test_daily_thesis.py`, and
  `test_daily_thesis_owner_u144.py` with typed and legacy contexts.
- Add `tests/unit/publisher/test_shared_macro_positioning_regression_u151.py`
  using the u144 finalized-document fixture pattern and synthetic official
  item metadata; assert final Markdown and notification summary, not just
  `_matches_oil`'s return value.
- Local gate: `uv run --extra dev pytest tests/unit/orchestrator/test_bundle_context.py tests/unit/models/test_bundle_context_allowlist.py tests/unit/publisher/test_cross_market_cause_map.py tests/unit/publisher/test_shared_macro_block.py tests/unit/publisher/test_daily_thesis.py tests/unit/publisher/test_daily_thesis_owner_u144.py tests/unit/publisher/test_shared_macro_positioning_regression_u151.py -q`;
  scoped Ruff/check+format and `uv run --extra dev mypy src`.

## Non-Goals

No promise to detect every unsupported CFTC causal sentence generated by the
LLM. No new APIs, paid data, public replay dispatch, Telegram send, deployment,
historical backfill, or new KPI family.

# Code Generation Plan: `u148 domestic-price-public-trust-projection`

**Date**: 2026-08-05
**Unit**: u148 domestic-price-public-trust-projection
**Stage**: Code Generation
**Status**: Backlog / Ready for implementation
**Source**: 2026-08-04 daily-briefing incident diagnosis; GitHub Actions run `30958850155` and `origin/main@b06b1bac9b9f`
**Estimated Effort**: ~8-12 h across five bounded steps
**Dependencies**:
- u109 domestic-anchor-sanity-quarantine (Complete) — canonical domestic trust states, plausibility/provenance rules, public-use boundary, and bounded diagnostics.
- u130 domestic-anchor-level-claim-quarantine-v2 (Complete) — level-claim detection and seven-day `discontinuous` classification; no duplicate threshold or archive scanner.
- u138 price-source-endpoint-lifecycle-repair (Complete) — current domestic index source identity/routing, including `yonhap-index-close`.
- u144 public-document-finalization-contract (Complete) — sole generated-to-sealed path. This unit fixes its E1 inputs; it does not change finalizer policy.

---

## Problem Statement

The 2026-08-04 production run generated all three drafts, but the domestic segment was removed during finalization with `numeric.anchor_assertion`. The two structured FSC/KRX price sources failed at collection, and `yonhap-index-close` emitted two domestic index rows that u109 correctly classified as `implausible`. The canonical domestic anchor table therefore withheld both numbers.

The same rejected price items were nevertheless still present in other public semantic inputs:

- `orchestrator.pipeline._stage_generate_segments()` routes the raw collected `items`, uses them for `compute_bundle_context()`, derives `data_limited` from the raw route, builds the verified-fact context from the raw tuple, and passes the raw domestic items to classification/synthesis.
- image, visual, watchlist, carryover, body-evidence, and `PublicDocumentContext.items_by_segment` preparation also fork from raw routed items.
- `trusted_domestic_price_items()` is applied only near the notification call, after the rejected numbers have already had opportunities to influence generated Markdown and other public surfaces.

This is an implementation gap against u109 R1/R6/R9: domestic exact values must cross one trust boundary before *any* public table, prose, visual, chart, fact, or notification fork. It also makes coverage inaccurate: a domestic route can report `data_limited=False` merely because untrusted price rows exist.

The Yonhap fallback increases the chance of this gap becoming visible. Its current parser accepts the first number within forty characters after `코스피` or `코스닥` when that number is at least 100. A move amount such as `483.00p` can therefore be mistaken for the closing level even when a later number is explicitly coupled to `마감` or `장종료`.

## Goal

Compute domestic anchor verdicts once after collection, preserve raw rows only for source-health and quality diagnostics, and route one filtered public item tuple to every public semantic consumer. Tighten the existing Yonhap adapter so it emits only a number explicitly coupled to terminal close wording and fails quietly on ambiguous move/round-level text.

After this unit, an `implausible`, `discontinuous`, `stale`, `provenance_missing`, or otherwise non-trusted domestic registry price cannot reach LLM input, bundle/fact context, coverage, visuals, watchlist/carryover, finalizer E1, public numeric verification, or Telegram.

## Existing Coverage / Deduplication

- **u109 is the policy owner.** Reuse `DomesticAnchorTrust`, `DomesticAnchorVerdict`, `domestic_anchor_verdicts()`, the source/provenance registry, plausibility bands, E5 quarantine-result semantics, and bounded diagnostics. Do not add a parallel trust enum, band, or public-missing mapping.
- **u130 owns continuity and claim detection.** Its `discontinuous` verdict and history lookup remain authoritative. This unit only makes all public consumers respect the verdict.
- **u138 owns the source adapter and routing.** The Yonhap change is a lexical exact-close correction inside the registered adapter, not a new source or precedence redesign.
- **u144 owns document finalization.** This unit supplies trusted E1 inputs and preserves the current `trust_blocked` behavior. Numeric-claim containment is deliberately assigned to dependent unit u149.
- **u55/u70 remain numeric verification owners.** No new numeric truth model or assertion scanner is introduced.

## Scope Boundary

In scope:

- One run-scoped domestic verdict computation and a filtered public item tuple derived from it.
- Explicit raw/public naming and routing through all public semantic consumers.
- Coverage and `data_limited` computation after the domestic projection.
- Raw source-health totals and u109 withheld metadata retained independently from public inputs.
- Yonhap exact-close clause parsing with fail-quiet ambiguity handling.
- Incident-shaped regression fixtures for 2026-08-03 (`discontinuous`) and 2026-08-04 (`implausible`).
- Static architecture coverage proving raw domestic price rows cannot be passed to public consumers after projection.

Out of scope:

- Changing u109 plausibility bands, source/provenance rules, or u130 continuity thresholds.
- New source adapters, paid APIs, scraping, credentials, or source-precedence redesign.
- Local repair of unsupported generated claims or any change to `trust_blocked`; u149 owns that policy.
- Rewriting historical archives or closing the broader structured-source gap tracked by DEBT-068.
- US/crypto trust-registry changes.

## Stage Decision

### Functional Design — SKIP

This unit implements the already-approved u109 E5 and R1/R6/R9 public-use boundary. It adds no new product state or trust decision. The code must reuse the existing `DomesticAnchorVerdict` contract rather than create a generic public-input domain model.

### NFR Requirements — SKIP

The projection is deterministic in-memory filtering with no new I/O, dependency, secret, network request, runtime budget, or public policy. Existing u109 determinism/R13 requirements and u144 E1 safety requirements apply unchanged.

### Code Generation — EXECUTE

The unit is ready. It is independently valuable and must land before u149 so the finalizer never attempts to repair claims derived from already-rejected raw price evidence.

## Fixed Contracts

### C1. One verdict computation, no parallel trust DTO

1. Add the narrow frozen implementation result `orchestrator.domestic_anchor_quarantine.DomesticPublicProjection` with exactly `public_items: tuple[NormalizedItem, ...]` and `item_verdicts: tuple[tuple[int, DomesticAnchorVerdict], ...]`. The integer is the original zero-based `raw_items` ordinal; it is the duplicate-safe join key and is never public metadata.
2. `project_domestic_public_items(raw_items, target_date=..., source_outcomes=..., previous_closes=...) -> DomesticPublicProjection` is the default pipeline entry point and classifies each registry item exactly once after the u130 prior-close context is available. `domestic_anchor_verdicts()` may delegate to the same loop for compatibility, but the default path must not call both APIs.
3. Filtering is performed in that same enumerated pass. Rejoining a verdict by candidate equality, symbol, source, value, object `id()`, or a second classification call is forbidden; duplicate model-equal rows retain distinct ordinals and verdict witnesses.
4. Preserve the u109 trust/candidate/verdict types and canonical reason order. `DomesticPublicProjection` is only an ownership/pairing wrapper, not a new trust decision. No `PublicInputTrust`, second band table, second source registry, or second discontinuity/history scanner is allowed.
5. Non-price items, US/crypto items, and non-registry domestic price items pass through model-equal and in their original order. A u109-registry domestic price item passes only when its own ordinal-paired verdict is `trusted`.

### C2. Raw/public ownership

The pipeline must use explicit names with disjoint responsibilities:

- `raw_items`: source-health, raw collected totals, per-source outcome diagnostics, u109 verdict computation, withheld counts/reasons, and bounded internal quality evidence only.
- `public_items`: every semantic input that can affect reader-visible bytes, public metadata, a sealed notification DTO, or a published asset.

The following consumers must receive only `public_items` (or a segment route derived from it):

1. Stage-1 classification and Stage-2 synthesis / LLM prompts.
2. `compute_bundle_context()` and shared macro/daily-thesis inputs.
3. `build_verified_fact_bundle()` and body-evidence verification.
4. market-anchor reconciliation and `_snapshot_close_by_ticker()`.
5. coverage, missing-category calculation, and `data_limited`.
6. watchlist matching, carryover candidates, image selection, visual/card/chart preparation.
7. `PublicDocumentContext.items_by_segment` and every publisher-side item lookup.
8. public quality numeric verification and Telegram price-summary input.

Ambiguous `items` parameters that serve both diagnostic and public roles must be split at the stage boundary. Quality snapshot builders receive raw counts/verdict metadata and public evidence as separate named inputs.

### C3. Coverage after trust projection

1. A non-trusted domestic registry price row cannot satisfy the domestic `price` category or core-anchor availability for public coverage.
2. If no trusted domestic core price remains, the domestic generation request receives `data_limited=True` even when news/disclosure items remain.
3. The existing zero-public-item path remains no-LLM; a route with other public items may still use the current data-limited prompt path.
4. Raw source success/failure and u109 withheld counts remain observable and must not be rewritten as generation failure.

### C4. Yonhap exact-close parser

For each same-entry title or description clause:

1. Require a `코스피`/`코스닥` alias and a numeric token directly coupled to one of `마감`, `종가`, `장종료`, `거래를 마쳤`, or `장을 마쳤`.
2. Select the numeric token nearest that terminal-close phrase, not the first number following the index label. Exact comma-separated integer or decimal closes are allowed.
3. Reject tokens coupled to `%`, `％`, `p`, `pt`, `포인트`, `선`, or `대`, plus dates/sequence numbers and futures/options table headlines.
4. When two different candidates are equally eligible or the close relationship is ambiguous, emit no item for that index. Do not guess.
5. u109 remains the only plausibility/continuity authority; the parser must not duplicate bands or previous-close logic.

Examples pinned by tests:

- `코스피 2,650.50 마감` -> `2650.50`.
- `코스피가 2,650.50에 거래를 마쳤다` -> `2650.50`.
- `[코스피] 483.00p 내린 7,500.00(장종료)` -> `7500.00`, never `483.00`.
- `코스피 483.00포인트 하락` -> no item.
- `코스피 7,500선 회복` -> no item.

### C5. Diagnostics and compatibility

1. Withheld diagnostics may contain target date, canonical symbol, source name, trust code, and counts. They must not contain the exact rejected value, full raw payload, full URL, environment, or secret.
2. Existing injected test seams may retain a compatibility facade, but the default segmented production path must have one projection and no late notifier-only filtering branch.
3. Normal trusted domestic output and all US/crypto output remain byte-compatible.

## Implementation Steps

- [x] Step 1 — Add the 2026-08-03/04 incident-shaped fixtures and characterize the current leak. Assert that rejected values can currently reach generation/public context while canonical anchors withhold them; keep the test failing until Steps 2-4.
- [x] Step 2 — Replace the first-number Yonhap regex path in `src/investo/sources/yonhap_index_close.py` with the C4 close-coupled extractor. Extend `tests/unit/sources/test_yonhap_index_close.py` with accepted close forms, move-point confusion, round-level wording, futures/options, multiple-number, and ambiguity cases.
- [x] Step 3 — Add the exact C1 `DomesticPublicProjection`/ordinal-paired API in `src/investo/orchestrator/domestic_anchor_quarantine.py` so one enumerated pass drives public filtering and u109 diagnostics. Reuse u130 continuity input; add no new classifier or history read. Pin duplicate model-equal rows and forbid equality/symbol/`id()` rejoin.
- [x] Step 4 — In `src/investo/orchestrator/pipeline.py` and its stage helpers, compute `raw_items`/`public_items` once and route C2 consumers explicitly. Update stage/context/quality function signatures so a raw tuple cannot accidentally satisfy a public parameter. Remove the notifier-only default-path filtering branch or make it an assertion-only compatibility guard.
- [x] Step 5 — Add architecture/composition tests, update `docs/DESIGN.md` and component-method docs with the public E1 projection, write the code summary, then run the full quality gate. Record u148 completion only after all public-fork and byte-compatibility tests pass.

## Acceptance Criteria

1. AC-148.1: Every u109-registry domestic price item is classified exactly once per run, ordinal-paired to its verdict without equality/symbol/`id()` rejoin, and all public consumers share the resulting filtered tuple.
2. AC-148.2: `implausible`, `discontinuous`, `stale`, `provenance_missing`, and unavailable domestic registry values cannot occur in LLM input, bundle/fact context, anchors, coverage evidence, visual/image/chart text, watchlist/carryover, finalizer E1, public quality verification, or Telegram.
3. AC-148.3: Raw source counts/outcomes and bounded u109 withheld reasons remain present in quality/source-health diagnostics without exposing the rejected exact value.
4. AC-148.4: A domestic route with no trusted core price reports missing price/data-limited truthfully even if rejected price rows or unrelated domestic news remain.
5. AC-148.5: The Yonhap parser selects `7,500.00`, not `483.00`, from `[코스피] 483.00p 내린 7,500.00(장종료)` and emits nothing for move-only, round-level, futures/options, or ambiguous shapes.
6. AC-148.6: The existing exact-close fixture still emits one KOSPI and one KOSDAQ row from one request with unchanged provenance/core-fact metadata.
7. AC-148.7: Non-registry domestic items preserve order and model equality; trusted normal domestic output and US/crypto outputs are byte-identical to the pre-u148 baseline.
8. AC-148.8: Applying the projection twice yields equal public items/verdict metadata, but the default pipeline calls the classifier only once.
9. AC-148.9: A static architecture test fails if raw post-projection domestic price items are passed to any C2 public consumer or if the default path reintroduces late-only filtering.
10. AC-148.10: The 2026-08-03 `discontinuous` and 2026-08-04 `implausible` fixtures keep bad values out of every captured public argument while preserving their bounded quality verdicts.
11. AC-148.11: Two model-equal duplicate raw rows retain distinct ordinal witnesses, are each classified once, and cannot be accidentally admitted by symbol/value-based verdict lookup.

## Tests / Validation

Focused tests:

```bash
uv run --extra dev pytest \
  tests/unit/sources/test_yonhap_index_close.py \
  tests/unit/orchestrator/test_domestic_anchor_quarantine.py \
  tests/unit/orchestrator/test_domestic_public_item_projection.py \
  tests/unit/orchestrator/test_run_pipeline.py \
  tests/unit/orchestrator/test_bundle_context.py \
  tests/integration/test_bundle_reconciliation.py
```

Required static checks:

- Add an AST-based production-path test for the C2 ownership rule; do not rely only on `rg` variable names.
- Assert the default segmented call graph calls `project_domestic_public_items()` exactly once and has zero independent `domestic_anchor_verdicts()` / `trusted_domestic_price_items()` trust decisions; compatibility APIs may delegate only outside the default path.

Full gate:

```bash
uv run --extra dev ruff check src tests
uv run --extra dev ruff format --check src tests
uv run --extra dev mypy src
uv run --extra dev pytest
uv run python scripts/check_no_paid_apis.py
uv run --extra docs mkdocs build --strict
git diff --check
```

Production closeout is executed together with dependent u149: exact-date workflow dispatch for 2026-08-03 and 2026-08-04 must show the bad domestic values absent from generation/public inputs while the original source-health/withheld verdict remains visible.

## Non-Goals

- No new numeric truth source or validation registry.
- No public fallback-state or pipeline-exit change.
- No numeric-claim Markdown mutation.
- No retry, LLM repair, or network call in the projection.
- No historical archive backfill.

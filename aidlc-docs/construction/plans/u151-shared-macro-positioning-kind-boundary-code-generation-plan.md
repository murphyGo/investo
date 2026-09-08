# Code Generation Plan: `u151 shared-macro-positioning-kind-boundary`

**Date**: 2026-09-06
**Unit**: u151 shared-macro-positioning-kind-boundary
**Stage**: Code Generation
**Status**: Complete — 6/6 (2026-09-08); independent review Pass; cross-check pending
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
context compatibility rule before implementation. Q1=A and Q2=A were approved
on 2026-09-08. After Step 7's final design presentation, the user responded
`진행시켜` (recorded 2026-09-08T04:17:23Z), approving the completed design
and its next Code Generation step. Step 1 characterization is complete;
Steps 2–6 are not executed by this approval.

After Step 1's handoff, the user responded `진행시켜` (recorded
2026-09-08T07:54:08Z), approving Step 2 only. Step 2 implementation and
independent review are complete; Steps 3–6 require subsequent approval.
Execution record:
[Step 2](../u151-shared-macro-positioning-kind-boundary/code/step-2-eligibility-and-keys.md).

After Step 2's handoff, the user responded `진행시켜` (recorded
2026-09-08T08:21:30Z), approving Step 3 only. Implementation/validation and
independent review are complete; Steps 4–6 remain subsequent approval.
Execution record:
[Step 3](../u151-shared-macro-positioning-kind-boundary/code/step-3-typed-cause-map.md).

After Step 3 and Step 4 handoffs, the user responded `진행시켜` (observed
2026-09-08T08:34:39Z and 2026-09-08T10:23:36Z respectively).
Steps 4 and 5 completed with independent review; this invocation approved
Step 5 only. The stale Step 3 header was reconciled with the completed Step 4
checkbox/state/session. Step 6 remains a subsequent approval.
Execution records:
[Step 4](../u151-shared-macro-positioning-kind-boundary/code/step-4-context-transport-audit.md),
[Step 5](../u151-shared-macro-positioning-kind-boundary/code/step-5-finalized-positioning-regression.md).

After Step 5's handoff, the user responded `진행시켜` (observed
2026-09-08T10:59:52Z), approving Step 6 only. The full local gate and
independent cumulative review passed; six ACs and five DoDs are complete,
and DEBT-076 is resolved locally. Code Generation is complete (6/6).
Cross-check, commit/push/main integration and production acceptance remain
separate and unperformed. Final evidence:
[Step 6](../u151-shared-macro-positioning-kind-boundary/code/step-6-local-gate-and-closeout.md),
[summary](../u151-shared-macro-positioning-kind-boundary/code/summary.md).

Design inputs: [Functional Design plan](u151-shared-macro-positioning-kind-boundary-functional-design-plan.md),
[business logic](../u151-shared-macro-positioning-kind-boundary/functional-design/business-logic-model.md),
[business rules](../u151-shared-macro-positioning-kind-boundary/functional-design/business-rules.md),
[domain entities](../u151-shared-macro-positioning-kind-boundary/functional-design/domain-entities.md),
and [design validation](../u151-shared-macro-positioning-kind-boundary/functional-design/design-validation.md).
Testable Properties in all three artifacts are mandatory inputs for the
implementation test steps below. Final design approval must precede Step 1.

Historical Step 1 execution detail:
[approved bounded plan](../u151-shared-macro-positioning-kind-boundary/code/step-1-characterization.md).
Its baseline assertions deliberately described the then-current defect, not
desired repaired behavior. Step 2 has converted all ten defect cases to
exclusion assertions; no skip/xfail or conditional old/new expectations.

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
8. Q2=A: each eligible routed item per segment emits at most one thesis
   signal, selecting the first matching final selected key in canonical
   `fomc, oil, ust_yield` order. Unselected keys must not shadow selected
   matches. Do not emit all matches, limit earlier all-key candidate
   collection, shrink the shared keys/block or change representative ranking
   and the existing thesis decision algorithm.

## Implementation Steps

- [x] Step 1 — Characterize September 4's CFTC WTI promotion with synthetic
  `NormalizedItem` fixtures and the existing `compute_bundle_context` path.
  Include a mixed case where eligible oil news in one segment plus CFTC in
  another must not meet the two-segment threshold.
  Completed baseline characterization: 15 new cases (13 examples, two seeded
  properties), focused 52 and expanded 103 passed; independent review all five
  categories Pass. The current defect is reproduced, not repaired. Step 2
  converts the defect assertions to the required exclusion behavior.
- [x] Step 2 — Add the typed model field and source-kind exclusion in
  `orchestrator/bundle_context.py`; update `_detect_shared_macros`,
  `_daily_thesis_signals` and `compute_bundle_context` as one eligibility path.
  Implement Q2's ordered first-selected-match emission while retaining every
  qualified shared key and the existing u60 threshold/UST/ranking rules.
  Complete: ten characterization cases converted; 76 cases added. Focused
  134 / expanded 854 passed, four seeded properties and four interpreter
  hash seeds verified. Scoped static checks and mypy 256 source/test files
  pass; independent review five categories Pass. No cause-map consumer
  conversion, finalizer acceptance or DEBT-076 closure in this step.
- [x] Step 3 — Replace `_candidate_types(block)` label search in
  `publisher/cross_market_cause_map.py` with typed-key lookup; remove dead label
  mirrors while preserving cause ordering and forbidden-type suppression.
  Complete: 34 new cases; cause-map 44, expanded publisher/orchestrator/model
  2,197 and reader-format integration 13 passed. Cumulative static checks and
  mypy 257 files pass; independent review five categories Pass, 178 focused
  tests passed. Legacy/relabel/gating verified; no exhaustive copy audit,
  new finalizer suite or DEBT-076 closure in this step.
- [x] Step 4 — Inspect all `BundleContext` construction/copy/serialization sites,
  including `public_document.py::_snapshot_bundle_context` and
  `models/bundle_context.py::with_self_pending`, to preserve the field. Update
  prompt and daily-thesis fixtures without changing their ranking policies.
  Complete: existing three copy owners preserve keys without production
  edits; proven oil/UST fixtures updated, legacy/None/minimal prompt contracts
  retained. Added 78 cases including two seeded properties. Focused 140 and
  expanded related 3,252 passed; cumulative twelve-file Ruff/format and
  source/new-test mypy 257 files pass. Expanded existing-fixture mypy retains
  13 baseline-identical diagnostics, not a clean gate. Independent review
  five categories Pass; no new debt. Finalizer acceptance and closure pending.
- [x] Step 5 — Run finalizer-backed rendered regression: CFTC WTI alone produces
  neither the shared oil line nor oil cause-map/thesis; US/crypto positioning
  channel rows still contain their existing dates and weekly-lag label.
  Complete: 51 new cases (49 examples, two seeded properties) use the real
  finalizer and terminal seal/notification path, with no extra production
  edits. Native rows/date/lag/group/cap, eligible controls, legacy/relabel,
  forbidden cause and fixed-original repeat verified. Focused 51 / expanded
  related 3,303 passed; thirteen-file Ruff/format and cumulative source/test
  mypy 261 files pass. Independent review all five categories Pass, 254
  related tests passed. Existing sealed-input glossary replay limitation
  recorded separately; no universal F(F(x)) claim. Step 6 gate/closure remains.
- [x] Step 6 — Run the local gate; record AC results and close DEBT-076 only
  after relabel-resilience and legacy-empty-key behavior pass.
  Complete: full repository 5,204 passed in 304.88s; locked dev/docs sync,
  full Ruff/check+581-file format, source mypy 254 files, all four policy
  guards, strict MkDocs and Material contracts pass. Supplemental typed
  source/test mypy 261 files pass. Independent cumulative 13-file review
  five categories Pass, 394 focused tests and ten properties/500 generated
  examples pass. All six ACs/five DoDs satisfied; DEBT-076 closed, Low 34→33.
  No Step 6 Python edit, new debt, cross-check, commit or live operation.

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
   Include selected-key subsets, overlap one-signal behavior and hash-seed
   stability. Full rendered-byte comparisons fix drafts, active segments,
   market-state inputs and positioning row order; adding a first CFTC item
   to an empty segment is not a global pipeline-invariance claim.

## Tests / Validation

- Extend `tests/unit/orchestrator/test_bundle_context.py` with source-kind,
  threshold, missing metadata, representative ranking, overlap, selected-key
  subset, permutation and hash-seed cases. Keep original routed inputs.
- Extend `tests/unit/models/test_bundle_context_allowlist.py` with typed-key
  validation/default/copy checks, invalid/null rejection, duplicate valid
  values, canonical JSON key-array order and ordinary context JSON round-trip.
  Do not promise full snapshot MappingProxyType JSON support or globally
  override unchecked model-copy behavior.
- Extend `tests/unit/publisher/test_cross_market_cause_map.py`,
  `test_shared_macro_block.py`, `test_daily_thesis.py`, and
  `test_daily_thesis_owner_u144.py` with typed and legacy contexts.
- Add `tests/unit/publisher/test_shared_macro_positioning_regression_u151.py`
  using the u144 finalized-document fixture pattern and synthetic official
  item metadata; assert final Markdown and notification summary, not just
  `_matches_oil`'s return value.
- PBT (Partial): use structured NormalizedItem/BundleContext strategies,
  including model-valid scalar metadata defects, key subsets and overlap.
  Each new u151 property test uses `@seed(15120260908)` with shrinking enabled.
  The ordinary `uv run pytest` CI job runs these tests with that fixed seed;
  no workflow edit or blanket random-retry suppression is needed. On failure
  capture the seed and shrunk minimal counterexample and retain a regression.
  Complement properties with explicit six-AC examples; do not claim test
  success during Functional Design.
- Local gate: `uv run --extra dev pytest tests/unit/orchestrator/test_bundle_context.py tests/unit/models/test_bundle_context_allowlist.py tests/unit/publisher/test_cross_market_cause_map.py tests/unit/publisher/test_shared_macro_block.py tests/unit/publisher/test_daily_thesis.py tests/unit/publisher/test_daily_thesis_owner_u144.py tests/unit/publisher/test_shared_macro_positioning_regression_u151.py -q`;
  scoped Ruff/check+format and `uv run --extra dev mypy src`.

## Non-Goals

No promise to detect every unsupported CFTC causal sentence generated by the
LLM. No new APIs, paid data, public replay dispatch, Telegram send, deployment,
historical backfill, or new KPI family.

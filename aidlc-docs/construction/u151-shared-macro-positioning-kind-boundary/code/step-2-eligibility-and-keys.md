# u151 Code Generation Step 2 — common eligibility and typed keys

**Status**: Complete — Step 2/6, recorded 2026-09-08T08:10:17Z.

## Approval and bounded execution plan

- User: `진행시켜`, approval recorded 2026-09-08T07:54:08Z, after Step 1's handoff.
- Skill: dev-investo, one implementation step. No Plan-mode tool is available;
  this written research/execution plan precedes implementation.
- Worktree: `.tmp/u151-functional-design-recovery-20260908`, baseline
  `17d859ab19ab693bc04747abe36d1ab4a4e6a874`; preserve prior design/Step 1
  changes and the unrelated original dirty root.
- Inputs: approved Functional Design's business logic, rules, entities and
  validation; Code Generation fixed contracts and Step 2; FR-013/015,
  NFR-003/005/006/007-R13; existing model/orchestrator and Step 1 tests.

## Implementation sequence

1. Convert the ten defect-characterization cases to exclusion regressions,
   retaining positive controls and original routed inputs.
2. Define the closed SharedMacroKey alias, frozen default and sorted JSON
   field serialization. Normal Pydantic validation rejects unknown/null input;
   no label inference, cross-field validator or unchecked-copy override.
3. Use one source-identity eligibility entry for detection and thesis.
   Reject exact CFTC producer for every matcher and log only the existing
   bounded/redacted candidate fields with positioning_not_shared_macro.
4. Derive keys and block from the final selected pairs. Preserve u60 distinct
   segment threshold, UST canonical prerequisite and representative ranking.
   Emit one first-matching selected key per item in fomc/oil/ust_yield order.
5. Validate all selected-key subsets, overlapping titles, contract groups,
   metadata defects, input preservation, serializer round-trip, permutations
   and independent interpreter hash seeds. Structured Hypothesis strategies
   use seed 15120260908, failure notes, shrinking and ordinary pytest discovery.
6. Run focused and related regression suites, Ruff/format and mypy; request
   separate read-only review, resolve findings, then update progress to 2/6.

## Boundaries

Cause-map consumption is Step 3; exhaustive constructor/copy-site audit is
Step 4; finalizer/positioning-row rendered acceptance is Step 5; the full
local gate, final AC/DoD closure and DEBT-076 closure remain Step 6.
Do not change routing, prompt source inputs, close-state computation, channel
rows, thesis decision policy, producer adapters, dependency/workflow files,
archive/site, requirements/DESIGN or debt. No new I/O, cost, LLM call, commit,
push, merge, live generation, deployment or notification.

## Results

Implemented in two existing production owners and two existing test modules.
The ten Step 1 defect cases now assert exclusion, with no skip/xfail or
conditional old/new acceptance. Step 2 adds 76 cases (74 parameterized examples
and two properties) on top of Step 1's 15. There are now four u151 properties.

- SharedMacroKey is closed to fomc/oil/ust_yield; normal model validation
  rejects unknown/null values and collapses duplicate valid values.
  Python projection remains a frozenset; JSON projection is a sorted array.
  Legacy display and caller-provided decision remain unchanged.
- Detection and thesis use the same source-identity entry. Final selected
  pairs produce both keys and display; first-selected-match thesis emission
  never shrinks those pairs. No global or per-segment decision policy changed.
- Tests cover all eight selected-key subsets, seven current CFTC contract
  groups plus unknown/blank/non-string/absent metadata across all five
  NormalizedItem categories, one-news-plus-CFTC thresholds, mixed canonical
  UST exclusion, independent eligible positives, original input/close-state
  preservation, exact producer matching and bounded/redacted rejection logs.
- Ordinary JSON round-trip and local self-pending copy are covered; this is
  not the Step 4 exhaustive constructor/snapshot audit or a full-snapshot
  MappingProxyType JSON guarantee.

| Validation | Result |
|---|---|
| Final focused model/orchestrator gate | 134 passed in 3.97s |
| Four Hypothesis properties | 40 passing examples each; seed 15120260908; zero failing examples |
| Independent interpreter seeds | 1, 2, 42, 20260908: identical selected keys/block/signals/decision |
| Scoped Ruff / format | Pass, four files |
| Mypy | Pass, 254 production files plus two changed test files |
| No-paid / no-Anthropic-SDK guards | Pass |
| Expanded related regression gate | 854 passed in 60.32s |
| Independent review | Five categories Pass; independent focused 134 passed in 5.12s |
| Diff / protected-tree / original-root checks | Pass, task HEAD and unrelated root dirt unchanged |
| Scoped documentation validation | 17 documents/touched registry sections, 40 relative links, 32 tables, balanced fences; code plan 2/6 |

Expanded gate command: `uv run python -m pytest tests/unit/orchestrator tests/unit/models tests/unit/publisher/test_cross_market_cause_map.py tests/unit/publisher/test_shared_macro_block.py tests/unit/publisher/test_daily_thesis.py tests/unit/publisher/test_daily_thesis_owner_u144.py tests/unit/publisher/test_channel_anchor_block.py tests/unit/sources/test_cftc_cot_positioning.py -q`.
This is not the full repository gate or the new Step 5 finalizer acceptance.
Review: [independent report](step-2-code-review.md).
Documentation validation covers complete u151 artifacts and only the changed
u151 sections of shared registries; unrelated historical Markdown examples
and table structures are not globally revalidated or edited.

The focused and expanded counts overlap and are not additive. During initial
test authoring the large Hypothesis seed was also used as an interpreter
hash seed, exceeding Python's uint32 range. The test now uses the four valid
interpreter seeds above; this was a test setup correction, not a runtime
implementation failure. The deliberate frozen-field mutation check uses the
existing model-test convention of a local type: ignore[misc]; all other
type/format checks pass without suppression.

## PBT compliance — current Step 2 scope

| Rule | Status | Evidence / remaining obligation |
|---|---|---|
| PBT-01 | Compliant, advisory | Approved business logic/rules/entities properties reused |
| PBT-02 | Compliant | Generated ordinary context JSON round-trip, sorted typed-key projection |
| PBT-03 | Compliant for scope | Exclusion, original-input preservation, selected subsets, overlap, repeat and permutation invariants |
| PBT-04 | N/A, advisory | No new idempotent transform/service; repeated computation is determinism |
| PBT-05 | N/A, advisory | No optimized replacement or new algorithm requiring an implementation oracle |
| PBT-06 | N/A | No new stateful service |
| PBT-07 | Compliant | Structured bounded routes, signed contract counts, metadata variants and closed key subsets |
| PBT-08 | Compliant | Seed 15120260908 and failure notes on every u151 property; default shrinking; normal pytest CI |
| PBT-09 | Compliant | Existing locked pytest/Hypothesis dependencies, no dependency/workflow changes |
| PBT-10 | Compliant, advisory | Explicit examples complement the four properties |

Hypothesis generation discarded 0/2/12/5 examples respectively in the final
focused run; these are generation rejections, not assertion failures or
malformed fixtures admitted into the production model.

## Handoff boundary

Step 2 implements and tests the model/orchestrator portion of AC-151.1–3
and the selected-evidence determinism portion of AC-151.6. It does not
complete the unit's rendered ACs/DoDs, cause-map label independence or
DEBT-076. Next approval is Step 3 typed-key cause-map consumption only.

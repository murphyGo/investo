# Design Validation — u151 shared-macro-positioning-kind-boundary

**Date**: 2026-09-08
**Baseline**: `17d859ab19ab693bc04747abe36d1ab4a4e6a874`
**Result**: Design validation PASS — ready for final user review; no unresolved design blocker.
**Validation recorded at**: 2026-09-08T01:20:39Z
**Final Functional Design approval**: Approved — `진행시켜`, recorded 2026-09-08T04:17:23Z.
**Implementation at design validation**: 0/6; no runtime, property-test or production pass claimed by this report.
**Skill / scope**: dev-investo Functional Design Step 7 only.

## 1. Inputs and provenance

- [Functional Design plan and approved A/A](../../plans/u151-shared-macro-positioning-kind-boundary-functional-design-plan.md)
- [Business logic model](business-logic-model.md)
- [Business rules](business-rules.md)
- [Domain entities](domain-entities.md)
- [Code Generation plan](../../plans/u151-shared-macro-positioning-kind-boundary-code-generation-plan.md)
- [Recovery and validation session](../../../../docs/sessions/2026-09-08-u151-functional-design-recovery-step7.md)

The old temporary worktree is absent. Documents were reconstructed from the
retained conversation's approved decisions/design and freshly inspected
baseline sources, not restored byte-for-byte. No historical per-step session
or successful interrupted-tool result is fabricated. This is main-agent
design validation, not an independent code review or requirements cross-check.
The user's earlier `gogo` resumed Step 7, not final design approval.
After final presentation, the subsequent `진행시켜` approved the design
and Code Generation Step 1; that later approval is recorded above.

## 2. Approved answers and ambiguity review

| Decision | Approved meaning | Reconciled owners |
|---|---|---|
| Q1=A | Legacy display stays; absent/empty keys imply no cause-map evidence | BLM §6; BR-151-08; entities §2/3/5 |
| Q2=A | One canonical first-matching selected key per eligible occurrence/segment | BLM §4; BR-151-05/06; entities §4 |

No contradiction remains between the one-signal rule and all-key selection:
the former applies only after final key selection. Unselected earlier keys
cannot shadow selected later keys. Display-only legacy compatibility is
not permission to infer keys or reject the whole context.

Intentional boundaries: the broader selected set need not equal the narrower
thesis decision; active-survivor redecision keeps base keys/block; CFTC-only
segments may receive data_limited fallback; minimal numeric contexts remain
None. Fixed-input byte determinism is not an invariance promise for changed
activity, drafts, close-state inputs or positioning order.

## 3. Eight fixed contracts

| Contract | Required result | Design evidence | Planned implementation proof |
|---|---|---|---|
| FC-1 | Closed typed key field, empty default, invalid rejection | BLM §3/9; BR-151-04; entities §2/6 | Steps 2/4: validation, copy, canonical JSON and round-trip |
| FC-2 | Source identity excludes all CFTC shared matches | BLM §3; BR-151-01; entities §4 | Steps 1/2: groups/titles/model-valid metadata defects |
| FC-3 | Common eligibility for detection/thesis, original routing retained | BLM §3/4/5/7; BR-151-01/02/05/10; entities §4/5 | Steps 1/2/5: mixed threshold, zero CFTC core IDs, preserved rows |
| FC-4 | Keys and display derive from final selected pairs | BLM §3; BR-151-03/04; entities §3/4/6 | Steps 2/4: threshold, UST, rank, permutation and projection |
| FC-5 | Typed cause mapping plus independent allowlist | BLM §6; BR-151-07; entities §4 | Step 3: relabel, dedup/order and forbidden suppression |
| FC-6 | Legacy display with empty keys produces no cause-map | BLM §6; BR-151-08; entities §2/3 | Steps 3/4: display-only legacy and explicit proven fixtures |
| FC-7 | Existing bounded/redacted rejection logging | BLM §7; BR-151-11; entities §4 | Steps 2/6: bounded reason and no payload/secret output |
| FC-8 | Q2 canonical first-selected-match, all shared keys retained | BLM §3/4; BR-151-05/06; entities §4/7 | Steps 2/6: overlap/subsets, one signal and hash-seed invariance |

## 4. Six acceptance criteria

| Acceptance | Design coverage | Future implementation acceptance |
|---|---|---|
| AC-151.1 | BLM §3/8; BR-151-01/11; entities §4/7 | All CFTC groups, absent/model-valid malformed metadata and misleading titles rejected |
| AC-151.2 | BLM §3/8; BR-151-02/03; entities §4 | One eligible plus CFTC fails; two eligible segments qualify under unchanged UST/rank rules |
| AC-151.3 | BLM §3/4; BR-151-03/04/05/06; entities §3/4 | Selected keys/block agree; signals use same eligibility, no CFTC core source IDs |
| AC-151.4 | BLM §6; BR-151-04/07/08; entities §2/4 | Label-independent causes; legacy empty keys yield none; forbidden types suppressed |
| AC-151.5 | BLM §5/7/8; BR-151-09/10/12; entities §5 | Real three-segment finalizer fixtures retain valid delayed rows/dates/labels without promotion |
| AC-151.6 | BLM §8/9; BR properties; entities §6/7 | Controlled permutations, overlap/subsets, repeat bytes and hash seeds; no adapter/network changes |

Traceability is u151's contribution to US-002/003/005, FR-002/008/013/015 and
NFR-003/005/006/007-R13, not global recertification of parent requirements.
At design validation all six implementation ACs were unexecuted and all five
unit DoDs unchecked. Follow the Code Generation plan for current progress;
this report does not recertify later runtime results.

## 5. Baseline owner inspection and bounded clarifications

Freshly read source ownership:

- `src/investo/orchestrator/bundle_context.py`: common matcher routes,
  distinct-segment threshold, canonical UST prerequisite, rank tuple,
  selected-pair ordering, set-iteration thesis ambiguity and constructor.
- `src/investo/models/bundle_context.py`: additive field location,
  self-pending copy and unchanged generic thesis models.
- `src/investo/_internal/daily_thesis_decision.py`: existing modes/global
  cause allowlist and survivor filtering of original signals.
- `src/investo/publisher/cross_market_cause_map.py`: label-based baseline
  candidate lookup, empty-block gate, allowlist, emitted/suppressed order.
- `src/investo/publisher/public_document.py`: dictionary snapshots,
  survivor owner, explicit None and minimal semantic-context removal.
- `src/investo/briefing/_reader_enhance/context_render.py`: explicit
  minimal prompt fields and existing is-not-None block-presence test.
- `src/investo/publisher/channel_anchor_block.py` and
  `src/investo/models/items.py`: existing row/string-presence and flat
  strict metadata boundaries.
- `pyproject.toml`, `CLAUDE.md`, `.github/workflows/quality.yml` and
  existing u153 seeded properties: Hypothesis/pytest selection and normal CI.

Two clarifications preserve approved scope:

1. BR-151-10 says missing/blank/non-string required positioning metadata
   omits a row. Nonblank semantically malformed strings are not promised to
   be rejected: the existing _meta helper checks string presence only.
   No new numeric/date validator or source policy is added.
2. The Code Generation plan requires `@seed(15120260908)` on each new u151
   property test, shrinking enabled, seed/minimal counterexample capture
   on failure and ordinary pytest CI inclusion. This follows existing
   per-test seed practice without a workflow or dependency change.

No new business choice, unresolved design blocker or debt was identified.
DEBT-076 remains open until rendered implementation acceptance passes.

## 6. PBT Compliance

Enforcement: **Partial**. PBT-02/03/07/08/09 are enforced when applicable;
the other rules are advisory. Functional Design's applicable rule is PBT-01.

| Rule | Status at this stage | Evidence / implementation obligation |
|---|---|---|
| PBT-01 | Compliant (advisory) | All three artifacts identify categories per component, explicit no-property/lossy boundaries and Code Generation references |
| PBT-02 | N/A — design-only execution | Ordinary context JSON inverse identified; generated round-trip tests mandatory in Code Generation; no lossy prompt/Markdown or full snapshot inverse claim |
| PBT-03 | N/A — design-only execution | Eligibility, threshold/rank, projection, one-signal, cause and copy invariants carried to generated tests |
| PBT-04 | N/A — design-only execution (advisory) | Existing composition repeatability retained; no new idempotent service or delivery policy |
| PBT-05 | N/A — design-only execution (advisory) | Existing rank/decision examples retained as oracle boundary; no new optimized algorithm |
| PBT-06 | N/A | No new mutable/stateful service; snapshots remain existing immutable projections |
| PBT-07 | N/A — generators not implemented | Structured domain strategies planned; valid scalar metadata defects, subsets, overlap, boundary collections and shared reuse |
| PBT-08 | N/A — properties not executed | Per-test fixed seed 15120260908, shrinking, failure evidence and normal pytest CI required; do not suppress flaky failures |
| PBT-09 | Compliant (existing configuration) | Hypothesis/pytest in dev dependencies and CLAUDE stack; existing seeded tests/quality workflow; no new framework |
| PBT-10 | Compliant (design planning, advisory) | Six explicit business scenarios plus distinct property categories; preserve shrunk failures as example regressions |

Blocking PBT design findings: **None**. These are design/planning findings,
not claims that any future invariant has passed runtime tests.

## 7. Content validation and scope checks

Mechanical validation passes for seven scoped documents: 33 relative Markdown
links resolve, 23 tables have consistent columns, fences balance and no trailing
whitespace is present. The plan retains two A answers, seven design steps and
zero of six code steps completed; twelve business rules, eight fixed-contract
rows, six AC rows and ten PBT rows are present. Every design artifact contains
Testable Properties. Step 7 was checked with final stage approval pending
at that checkpoint; approval was subsequently recorded above.

Git whitespace and application/test/archive/site/workflow/dependency/debt/
requirements/architecture diff checks pass. Task HEAD remains the exact baseline;
original-root HEAD and dirty path list remain unchanged. No application or
property tests were executed for this documentation-only validation.

## 8. Final review and next action

The following actions were presented at Step 7. The subsequent user response
`진행시켜` approves Continue to Next Stage (recorded 2026-09-08T04:17:23Z):

- **Request Changes** — identify changes to these design artifacts; revise
  and revalidate before approval.
- **Continue to Next Stage** — explicitly approve this Functional Design;
  the next step is Code Generation Step 1, synthetic incident characterization.

Neither action authorizes commit, push, main integration, deployment, live
pipeline dispatch, source/API calls, Telegram sending or next-unit work.

# Cross-Check: u151 shared-macro-positioning-kind-boundary

**Subsequent integration**: Report commit `aabd83ea` was pushed and verified.
The later September 9 main integration combines this implementation with
`f93def42` without conflicts or Python changes; its full gate passes 5,204
tests in 334.50s and focused gate passes 394 tests in 16.28s. All static,
policy and strict docs/Material gates pass. Production acceptance remains
separate. See the [integration record](../sessions/2026-09-09-u151-main-integration.md).
Earlier cross-check timings, line references and no-delivery statements below
describe the original checkpoint and are preserved.

**Date**: 2026-09-09 KST

**Checked by**: Codex, `cross-check` skill

**Verdict**: APPROVE — all six u151 acceptance criteria complete; no new gap/task/debt.

**Approval**: User replied `진행시켜` after the commit/push handoff proposed
u151 requirements cross-check as the next step. This invocation covers the
report and current u151 state synchronization, not another Git delivery or
main/production action.

**Validated implementation**: `bf9d52b839143f166238dcf30ef32e8bd127d6f8`, branch
`codex/u151-functional-design-recovery-20260908`. Read-only `git ls-remote`
confirmed the same SHA on the remote branch during this check. The isolated
worktree `.tmp/u151-functional-design-recovery-20260908` was clean at entry.
Report/state changes are subsequent, uncommitted documentation only.

## Scope and compliance summary

This checks the approved Q1=A legacy-display and Q2=A canonical-one-signal
contracts, shared evidence eligibility, typed-key transport and final output.
It does not certify current remote main, live source/LLM generation, archive
backfill, Telegram delivery, Pages or production output. No implementation or
test changes were made during this cross-check.

| Status | Count | Percentage |
|---|---:|---:|
| Complete | 6 | 100% |
| Partial | 0 | 0% |
| Gap | 0 | 0% |
| Deferred | 0 | 0% |
| In Progress | 0 | 0% |
| Total u151 acceptance criteria | 6 | 100% |

The denominator is AC-151.1–6, not every AC in the parent FRs/NFRs.
Historical September 4 evidence was rechecked read-only at `d553035`:
`archive/us-equity/2026/09/2026-09-04.md:27` labels a WTI contract position as
international oil; line 36 emits the oil/geopolitics cause. Synthetic tests
exercise this failure without modifying historical archive content.

## Requirements and design traceability

Primary SoT: `docs/requirements.md`; the inception requirements document
points to it. The bounded contribution mapping is:

| Requirement | u151 contribution / preserved contract | Status within scope | Evidence |
|---|---|---|---|
| FR-002 — briefing (`:45`) | Remove deterministic unsupported shared premises while preserving Korean final output and original generation inputs | Complete | AC-151.1/3/5; `BT:25`, `F:224` |
| FR-008 — segments (`:34`) | Keep original routed inputs and native US/crypto delayed rows; no domestic positioning row | Complete | `O:273`, `BT:25`, `F:224`, `F:356` |
| FR-013 — shared context (`:161`) | One existing context owner; preserve self-pending, minimal prompt and independent allowed-type gates | Complete | `P:758`, `M:172`, `BT:38`, `BT:57`, `PT:55` |
| FR-015 — macro matching (`:193`) | Exact producer exclusion before matching; preserve distinct-segment threshold, canonical UST prerequisite and original representative rank | Complete | `O:207`, `O:302`; `OT:129`, `OT:242`, `OT:277`, `OT:688`, `OT:868`, `OT:902` |
| NFR-003 — reliability (`:319`) | Safe legacy/empty/None/minimal behavior, original-signal survivor filtering and stable finalization within approved inputs | Complete | `MT:72`, `CT:163`, `PT:97`, `PT:111`, `F:413`, `F:539` |
| NFR-005 — maintainability (`:328`) | Closed three-key model and existing owners; remove cause-map label coupling | Complete | `M:59`, `M:154`, `C:47`, `C:86`; fresh source and supplemental mypy gates |
| NFR-006 — testing (`:334`) | Unit/transport/finalizer regression, seeded structured properties and interpreter hash-seed checks | Complete | Fresh 5,204-test full gate and ten properties / 500 passing generated examples |
| NFR-007 / R13 — safety (`:339`) | Existing bounded/redacted candidate logging; no new secret, payload or URL sink | Complete | `O:132`, `O:242`, `OT:930`; policy guards pass |

Table path aliases, with line numbers referring to the validated SHA:

- `M`: `src/investo/models/bundle_context.py`; `O`:
  `src/investo/orchestrator/bundle_context.py`; `C`:
  `src/investo/publisher/cross_market_cause_map.py`; `P`:
  `src/investo/orchestrator/pipeline.py`.
- `MT`: `tests/unit/models/test_bundle_context_allowlist.py`; `OT`:
  `tests/unit/orchestrator/test_bundle_context.py`; `CT`:
  `tests/unit/publisher/test_cross_market_cause_map.py`.
- `PT`: `tests/unit/publisher/test_bundle_context_transport_u151.py`; `BT`:
  `tests/unit/briefing/test_bundle_context_transport_u151.py`; `F`:
  `tests/unit/publisher/test_shared_macro_positioning_regression_u151.py`.

US-002/003/005 (`stories.md:42`, `:61`, `:100`) trace through briefing inputs,
publisher finalization and orchestration. C2/C3/C5 ownership remains unchanged
(`components.md:47`, `:66`, `:112`). Paths are under
`aidlc-docs/inception/user-stories/` and `aidlc-docs/inception/application-design/`,
respectively. FR-003 publication, NFR-002 cost and NFR-004 disclaimer contracts
are preserved, not separately recertified end to end. No new paid dependency,
SDK or source was introduced. US-005/NFR-001 live ten-minute timing is not a
unit-test runtime claim; existing DEBT-090 remains open.

Functional Design is approved, 7/7. The three FD artifacts, twelve business
rules and eight fixed contracts align with the implementation. NFR Requirements
is explicitly SKIP: existing NFR-003/005/006 and R13, no new I/O/source/cost.
Code Generation is complete, 6/6. Historical design-time unchecked code steps
and early story/execution-plan previews are not current implementation gaps.
The separate global Build and Test stage is not advanced by this report.

## Acceptance criteria evidence

| Criterion | Status | Implementation and named executable evidence |
|---|---|---|
| AC-151.1 — every CFTC group excluded, regardless of title/metadata | Complete | `O:207` exact source identity gate; `OT:868` `test_u151_all_cftc_groups_cannot_complete_any_threshold_or_supply_core` covers all groups, absent/model-valid malformed metadata and all-key titles; `OT:911` proves exact, not prefix/title-based identity; `F:224` exercises real finalization |
| AC-151.2 — CFTC cannot complete two-segment threshold; eligible controls survive | Complete | `O:330` distinct segments, `O:333` matching canonical UST prerequisite and original `O:113` rank; `OT:649` one news segment plus CFTC, `OT:688` positive control, `OT:708` one-segment multiplicity, original UST tests and `OT:902`; `F:258` final output control |
| AC-151.3 — common eligible selection for keys/display/core evidence | Complete | `O:474` final selected-pair projections and `O:389` first selected canonical match per occurrence; `OT:843` selected subsets/overlap preserve all keys, `OT:666` no CFTC core source IDs; `M:154` closed default-empty frozenset, `M:164` sorted JSON; `PT:55` 64 key/survivor combinations; `F:268` all eight subsets |
| AC-151.4 — relabel resilience, empty-key legacy and forbidden suppression | Complete | `C:86` typed causes and `C:91` nonempty-block/independent allowlist gates; `CT:163` legacy display, `CT:188` keys without block, `CT:199` label invariance, `CT:207` Fed dedup/order, `CT:239` forbidden partition; `F:296` finalized legacy/relabel and `F:433` no forbidden public prose |
| AC-151.5 — final three-segment repair preserves delayed positioning | Complete | Actual producer/finalizer/seal/notification in `F:224`; US six-group coverage `F:356`, native order/cap `F:373`, net/%OI/as-of/release/weekly lag and no domestic row; missing/blank/non-string fields `F:315`; legitimate watchpoint retained `F:394`; existing renderer `channel_anchor_block.py:216` unchanged |
| AC-151.6 — deterministic equivalent inputs, no source/network change | Complete | `OT:745`, `OT:768`, `OT:972` original input/permutation properties; `OT:992` interpreter hash seeds 1/2/42/20260908; `MT:129` ordinary JSON round-trip/sorted keys; `F:413` minimized equal-zero original-draft repeat, `F:500` delayed rows and `F:539` fixed-input bytes/SHA/DTO equivalence; only three production owners changed in the delivered implementation |

The five checked unit DoDs map to AC-151.1/2 (source boundary), AC-151.3/4
(typed/legacy), AC-151.2/3/4 (cause/thesis gates), AC-151.5 (final rows) and
AC-151.3/4/6 (transport/order/forbidden regression and debt closure).
DEBT-076 is already in Resolved Items; 33 active Low items remain, with zero
active Critical/High/Medium. This report does not edit the debt register.

## Fresh validation

All checks below ran on the exact delivered implementation SHA in this turn:

| Check | Result |
|---|---|
| `uv run python -m pytest -q` | 5,204 passed in 329.62s; exit 0 |
| `uv run ruff check src tests scripts` | Pass |
| `uv run ruff format --check src tests scripts` | 581 files already formatted |
| `uv run mypy src` | Pass, 254 source files |
| Supplemental source + seven typed test/helper paths | Pass, 261 files |
| Six-module `-k property --hypothesis-show-statistics -q` | 10 passed, 297 deselected in 4.94s; 500 passing examples, zero failures, 64 internal invalid draws |
| `check_no_anthropic_sdk.py`, `check_no_paid_apis.py` | Pass |
| `check_curated_assets.py` | Pass; 19 filed, zero deferred |
| `check_image_store.py` | Pass; zero binaries/sidecars |
| `uv run mkdocs build --strict -q` | Pass |
| `check_material_theme_contract.py` | Pass; light/dark CSS and exact rendered asset pair |
| Post-report documentation / preservation checks | Seven scoped documents/registry sections, 30 relative links, eight tables, balanced fences and whitespace checks pass; 6/6 steps and 5/5 DoDs; all 13 Python SHA256 hashes unchanged |

Strict MkDocs and Material checks were also rerun successfully after the
report and current-state synchronization. Exactly seven documentation paths
changed; source/tests and protected configuration/archive paths did not.

The supplemental mypy command includes `src` plus
`tests/_helpers/bundle_context_u151.py` and the six MT/OT/CT/PT/BT/F modules
listed above. Those six modules are also the property rerun scope.
Properties use seed `15120260908`, shrinking and normal CI; generated example
counts overlap the full suite and are not added to 5,204. Partial PBT enforced
rules 02/03/07/08/09 remain compliant, as recorded in the implementation summary.

The prior independent cumulative Step 6 review is historical evidence, not a
new independent review in this invocation: all 13 Python files, five categories
Pass and 394 focused tests. Its original 304.88-second full gate and review
timings remain unchanged in historical records; the fresh result above is the
current cross-check gate. No additional reviewer was spawned.

## Preserved limitations and operational handoff

- Legacy display-only blocks do not infer typed keys; explicit caller thesis
  evidence is not reset. Cause-map and thesis allowlists remain independent.
- CFTC is excluded from shared/core selection, not removed from original
  routed inputs, close-state inference, legitimate positioning or watchpoints.
- Snapshot/survivor copies preserve base selected keys while filtering only
  original thesis signals. Intentional None/minimal numeric contexts remove
  semantic evidence; the prompt retains its existing five-field projection.
- Ordinary BundleContext JSON is covered. Internal MappingProxy snapshots
  have no new whole-model JSON guarantee, and unchecked model_copy is not
  globally replaced. Existing older-fixture mypy diagnostics are not claimed
  clean or included in the supplemental type scope.
- The unchanged positioning renderer checks required nonblank strings, not
  arbitrary numeric/date semantics. Fixed-original-draft repeat is covered;
  arbitrary sealed-output-as-new-draft replay can lose a second equal-zero
  %OI parenthetical through the pre-existing glossary path. The minimized
  original-input regression and zero-valued generated inputs are retained.
- These known, bounded limitations are not new u151 compliance gaps. No new
  implementation task or debt is created, and no unrelated baseline is fixed.

Current state/plan/unit/story map and summary now distinguish completed branch
commit/push and this approved cross-check from pending report delivery,
main integration and production acceptance. Historical step/audit records are
preserved. The original root HEAD and its three unrelated dirty paths remain
unchanged; all 13 reviewed Python hashes are unchanged.

Next proposed scope: commit/push this documentation, then explicitly approved
main integration with a fresh combined gate. Live production acceptance remains
separate; no merge, source/LLM call, live pipeline dispatch, deploy, Telegram
send, archive rewrite or next-unit work was performed here.

## Supporting records

- [Approved Functional Design](../../aidlc-docs/construction/u151-shared-macro-positioning-kind-boundary/functional-design/design-validation.md)
- [Code Generation plan](../../aidlc-docs/construction/plans/u151-shared-macro-positioning-kind-boundary-code-generation-plan.md)
- [Implementation summary](../../aidlc-docs/construction/u151-shared-macro-positioning-kind-boundary/code/summary.md)
- [Independent cumulative Step 6 review](../../aidlc-docs/construction/u151-shared-macro-positioning-kind-boundary/code/step-6-code-review.md)
- [Step 4 transport audit](../../aidlc-docs/construction/u151-shared-macro-positioning-kind-boundary/code/step-4-context-transport-audit.md)
- [Step 5 finalizer investigations](../../aidlc-docs/construction/u151-shared-macro-positioning-kind-boundary/code/step-5-finalized-positioning-regression.md)
- [Commit/push handoff](../sessions/2026-09-09-u151-commit-push.md)

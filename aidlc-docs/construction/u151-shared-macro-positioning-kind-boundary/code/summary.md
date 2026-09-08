# u151 — Shared macro positioning boundary: implementation summary

**Date**: 2026-09-08
**Status**: Code Generation complete — 6/6; cross-check APPROVE (2026-09-09), six ACs/five DoDs Pass; DEBT-076 resolved locally.
**Closed at**: 2026-09-08T11:24:45Z
**Next**: Cross-check report delivery, main integration and production acceptance remain pending.
**Scope**: Approved Functional Design Q1=A / Q2=A; historical Code Generation record with subsequent branch delivery and cross-check handoff below.
**Traceability**: US-002/003/005, FR-002/008/013/015,
NFR-003/005/006/007-R13, DEBT-076. This is u151 contribution evidence,
not a global requirements cross-check or production acceptance.

## Implementation

Latest checkpoint (2026-09-09 KST): implementation commit/push is complete,
`bf9d52b839143f166238dcf30ef32e8bd127d6f8` matches the remote branch.
Cross-check APPROVE, 6/6 ACs and no new gap/task/debt. Fresh full gate:
5,204 passed in 329.62s; source/supplemental mypy 254/261, full Ruff/format,
policy guards, strict MkDocs/Material and ten properties/500 examples pass.
Only report/current-state documentation changes were made during cross-check.
See the [cross-check report](../../../../docs/cross-checks/2026-09-09-u151-shared-macro-positioning-kind-boundary.md).
The implementation and Step 6 evidence below preserve their original timings
and historical no-commit/no-cross-check boundaries.

Only three production owners changed:

- `src/investo/models/bundle_context.py`: closed SharedMacroKey literal,
  additive default-empty frozenset, canonical sorted JSON field projection.
- `src/investo/orchestrator/bundle_context.py`: exact CFTC producer exclusion
  at the common matcher used by detection and thesis. Preserve distinct-segment
  threshold, matching canonical UST prerequisite, original representative
  rank and all-key collection. Derive typed keys/display from final pairs;
  each eligible occurrence emits its first matching selected canonical key.
- `src/investo/publisher/cross_market_cause_map.py`: typed oil/Fed mapping,
  with nonempty-block and independent allowlist gates. No mirrored label
  matching. Deduplicate/order as before; systemic risk remains dormant.

Steps 4/5 add transport/finalizer evidence without additional production edits.
Original routed items, close states, generation inputs, explicit minimal prompt
fields, active-survivor policy, intentional None/minimal context, delayed
positioning rows and terminal seal/notification ownership remain unchanged.

## Acceptance reconciliation

The listed executable evidence passed in the full 5,204-test gate and the
independent cumulative review. All six local acceptance criteria pass.

| AC | Implementation and executable evidence | Local result |
|---|---|---|
| AC-151.1 | Common exact-producer exclusion; all six US groups, crypto, absent/model-valid malformed metadata and misleading all-key titles in orchestrator and finalized regression suites | Pass |
| AC-151.2 | One eligible segment plus arbitrary CFTC routes cannot qualify; two eligible segments retain UST prerequisite and representative ranking; original u60 examples retained | Pass |
| AC-151.3 | Keys/block project final pairs; selected subsets and overlap emit at most one canonical signal per occurrence; CFTC never supplies a core source ID | Pass |
| AC-151.4 | Cause-map relabel invariance, display-only empty-key legacy, keys-without-block, dedup/order and forbidden suppression; real finalized relabel/legacy controls | Pass |
| AC-151.5 | Real three-segment finalizer/seal/notification; native US/crypto group/order/cap/net/%OI/as-of/release/weekly-lag rows retained; no domestic row or deterministic CFTC promotion | Pass |
| AC-151.6 | Structured candidate permutations, all selected subsets/overlap, fixed-original repeat, model JSON order and four interpreter hash seeds; no adapter/routing/network contract edit | Pass |

Five unit DoDs correspond to source exclusion, typed/legacy evidence,
cause/thesis eligibility with preserved gates, finalized delayed-row
preservation, and passing typed/relabel/copy/order/forbidden regressions
followed by DEBT-076 closure. All five registry checkboxes are now complete;
DEBT-076 moved to Resolved Items and the active Low count changed from 34 to
33. This is verified local implementation closure, not production acceptance.

## Test inventory and reproducibility

Cumulative additions from Steps 1–5: 254 collected cases
(244 example cases and ten property tests). Step 1's ten defect assertions
were converted to required repaired behavior in Step 2; no old/new conditional
expectation, skip or xfail. Step 6 adds no tests or Python edits.

| Test module / helper | Principal evidence |
|---|---|
| `tests/unit/models/test_bundle_context_allowlist.py` | Closed keys, empty/default/invalid/null, duplicates, sorted JSON and ordinary round-trip |
| `tests/unit/orchestrator/test_bundle_context.py` | Producer boundary, thresholds, ranking, Q2 subsets, original inputs, safe diagnostics and hash seeds |
| `tests/unit/publisher/test_cross_market_cause_map.py` | Relabel/legacy/independent gating, exact wording/order, partition and injection |
| `tests/_helpers/bundle_context_u151.py` | Shared valid BundleContext strategies and all key/active subsets |
| `tests/unit/publisher/test_bundle_context_transport_u151.py` | 64 key/survivor combinations, frozen snapshots, broader keys/narrower signals and absent/minimal branch |
| `tests/unit/briefing/test_bundle_context_transport_u151.py` | Exact input identity, self-pending/noop copies and existing five-field prompt |
| `tests/unit/publisher/test_shared_macro_positioning_regression_u151.py` | 51 real-finalizer cases including two structured properties and retained minimized examples |
| Existing `test_daily_thesis_owner_u144.py`, `test_public_document_types_u144.py`, `test_bundle_reconciliation.py` | Explicit keys in proven oil/UST fixtures, unchanged legacy/thesis/pipeline contracts |

All ten new properties have `@seed(15120260908)`, failure seed notes and
default shrinking. Four use 40 examples, two cause-map properties use 80,
two transport properties use 60, and two finalizer properties use 30.
These are configured maxima, not an additive full-suite test count.
Independent statistics also verified all 500 passing generated examples with
zero failures (64 internal invalid draws reported separately).
Four separate Python interpreter hash seeds are 1, 2, 42 and 20260908;
the larger Hypothesis seed is not passed to PYTHONHASHSEED.

## PBT Compliance

Enforcement is Partial. No property is excluded from ordinary pytest CI.

| Rule | Status / scope | Evidence |
|---|---|---|
| PBT-01 | Compliant, advisory | Three approved FD artifacts identify properties and lossy/no-property boundaries |
| PBT-02 | Compliant | Generated ordinary-context JSON round-trip, sorted field projection; no inverse promise for minimal prompts or Markdown |
| PBT-03 | Compliant | Generated eligibility/threshold/selection, one-signal, cause partition, copies, fixed-original output invariants |
| PBT-04 | Compliant within claimed operations, advisory | Cause injection idempotence; finalizer repeat uses unchanged original drafts, not a universal sealed-input F(F(x)) claim |
| PBT-05 | Compliant, advisory | Existing rank/decision examples and independent expected cause/channel-row projections |
| PBT-06 | N/A | No new mutable stateful service or delivery state machine |
| PBT-07 | Compliant | Structured domain objects, valid scalar defects, bounded dates/counts/percentages, empty subsets/zero/overlap and shared transport strategies |
| PBT-08 | Compliant | Fixed per-test seed, failure notes, shrinking and normal CI; Step 5 counterexamples/timing investigated and retained |
| PBT-09 | Compliant | Existing Hypothesis/pytest dependencies and quality workflow; no dependency/workflow change |
| PBT-10 | Compliant, advisory | 244 example cases complement ten new properties; minimized watchpoint/zero-row cases retained |

The full local gate and independent rerun passed all ten new properties.
Blocking PBT findings: none.

## Local quality gate

Commands mirror the checkout's `.github/workflows/quality.yml`.
The checkout defines dev/docs extras, not sector. Lockfile is unchanged.

```sh
uv sync --locked --extra dev --extra docs
uv run ruff check src tests scripts
uv run ruff format --check src tests scripts
uv run mypy src
uv run python -m pytest -q
uv run python scripts/check_no_anthropic_sdk.py
uv run python scripts/check_no_paid_apis.py
uv run python scripts/check_curated_assets.py
uv run python scripts/check_image_store.py
uv run mkdocs build --strict
uv run python scripts/check_material_theme_contract.py
```

All local gates passed: locked sync; Ruff all checks/581 formatted files; source
mypy 254 files; no-SDK/no-paid guards; curated library 19 filed/0 deferred;
image store 0 binaries/sidecars; strict MkDocs (4.64s); built Material CSS
light/dark and exact rendered-pair contracts. Full pytest: **5,204 passed in
304.88s**, exit 0.

Supplemental cumulative source plus seven typed u151 test/helper files:
mypy 261 files passed. Initial uv cache permission denial was rerun via the
approved escalated command; it was not a type diagnostic.
This does not include three older fixture modules with the previously
verified 13 baseline-identical mypy diagnostics in four files. Source-only
CI and the explicitly listed supplemental scope are the passing type gates.

Final scoped Markdown validation passes: 31 documents/touched registry
sections, 74 relative links, 58 tables and balanced fences. Verified 6/6
code steps, 5/5 DoDs and exactly one resolved DEBT-076/33 active Low items.
Post-closeout strict MkDocs/Material rerun passes. All 13 Python hashes and
protected original-root/archive/site/dependency/workflow paths are unchanged.

## Independent cumulative review

All 13 Python files (5,492 lines) and the approved design/AC/DoD/PBT artifacts
were fully read. Correctness, Safety, Reliability, Maintainability and Test
Coverage all Pass; no new issue/debt. Independent focused suite: 394 passed
in 14.88s. Property rerun: 10 passed, 297 deselected in 4.56s; 500 generated
examples pass. Scoped Ruff/format, 261-file mypy and diff checks pass.

Independent extra guard rerun stalled on uv cache escalation and was stopped;
it is not reported as an independent Pass. Main had already passed these
guards in this same checkout. Full details:
[independent review](step-6-code-review.md).

## Limits and operational boundary

- Exact existing producer exclusion is not a universal positioning taxonomy
  or arbitrary LLM causal-prose validator. Other source matchers stay u60.
- Legacy nonempty blocks may display without keys; an explicitly supplied
  legacy thesis is not silently reset. Cause-map allowlist and thesis global
  allowlist are intentionally independent.
- Internal MappingProxy snapshots have no new full JSON round-trip guarantee;
  unchecked model_copy validation is not globally replaced.
- The unchanged positioning renderer checks required string presence, not
  general numeric/date semantics. Nonblank malformed strings remain its
  existing policy.
- Reusing sealed Markdown as a new draft can lose a second equal-zero %OI
  parenthetical through the pre-existing glossary deduplication path. The
  fixed-original-draft repeat contract passes in Step 5; zero-value generator
  inputs and the minimized example are retained. No glossary repair or
  universal sealed-input repeat claim is included.
- Full-unit local tests do not constitute the separate global Build and Test
  stage, requirements cross-check, main integration or production acceptance.

No commit/push/merge, live pipeline/source/LLM call, deployment, Telegram send,
archive backfill, source/workflow/dependency change or next-unit work.
Cross-check is the next proposed approval. Code Generation is now locally
complete; other unit queues and the separate global Build and Test stage
remain unchanged.

## Evidence

Subsequent Git handoff: the user approved commit/push on 2026-09-09 KST,
targeting the isolated branch only. Step 6's no-commit statements above
describe its original checkpoint. The later cross-check is approved above;
main/production remain pending;
see the [commit/push handoff](../../../../docs/sessions/2026-09-09-u151-commit-push.md).

- [Approved Functional Design](../functional-design/design-validation.md)
- [Code Generation plan](../../plans/u151-shared-macro-positioning-kind-boundary-code-generation-plan.md)
- [Step 6 execution plan and results](step-6-local-gate-and-closeout.md)
- [Step 6 independent review](step-6-code-review.md)
- [Step 6 session](../../../../docs/sessions/2026-09-08-u151-code-generation-step6.md)
- [Step 4 transport audit](step-4-context-transport-audit.md)
- [Step 5 finalizer regression and investigations](step-5-finalized-positioning-regression.md)

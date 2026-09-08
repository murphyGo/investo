# u151 Code Generation Step 4 — context transport and fixture audit

**Status**: Complete — Step 4/6, recorded 2026-09-08T09:50:08Z.

## Approval and bounded execution plan

- User: `진행시켜`, recorded 2026-09-08T08:34:39Z after Step 3 handoff.
- Skill: dev-investo, one step, written plan before test/code edits and
  separate independent review. No Plan-mode tool is available.
- Preserve isolated baseline `17d859ab19ab693bc04747abe36d1ab4a4e6a874`,
  recovered design/Steps 1–3 and original dirty root.
- Inputs: approved BLM section 5, BR-151-04/08/09, entities sections 5/6,
  Code Generation Step 4, FR-013/015 and NFR-003/005/006/007-R13.
  Health: no Critical/High/Medium debt; DEBT-076 and all unit DoDs stay open.

## Execution plan

1. Inventory every in-repo BundleContext constructor, model validation,
   copy, snapshot, survivor projection and serialization site, including
   explicit minimal prompts and wrapper pass-throughs. Record exact owners
   and test-fixture intent; distinguish proven evidence, display-only legacy,
   absent semantic context and unrelated close-state-only fixtures.
2. Inspect existing model_copy owners rather than adding redundant field
   assignments. Preserve selected keys/block across self-pending, defensive
   publisher snapshot and survivor redecision; change production only if an
   actual field-loss path is found. Keep original signals/decision ranking.
3. Update constructor fixtures intending proven evidence with explicit
   typed keys. Leave intentional display-only/empty/close-state fixtures
   empty and document why; never infer keys from display labels in a helper.
4. Add example/structured seeded tests for all three copy boundaries,
   original-object isolation, ordinary JSON transport, None/minimal numeric
   context and unchanged minimal prompt fields. Cover all valid key subsets,
   survivor sets and broader selected keys than surviving thesis support.
   Use seed 15120260908, shrinking, failure notes and normal pytest discovery.
5. Run focused tests and relevant expanded suites, scoped Ruff/format/mypy,
   policy/diff checks. Obtain independent review, resolve findings and update
   the step to 4/6 only after verification.

## Non-goals

No new full-snapshot MappingProxyType JSON contract, global model_copy override,
key regeneration, rematching/rerouting, thesis ranking change or new prompt
field. Intentional numeric semantic removal remains None; never restore
removed context. Do not execute Step 5's new CFTC finalizer/positioning-row
acceptance, Step 6 full gate/closure, another unit, or any commit/push/merge,
archive/site/dependency/workflow/debt edit, live source/LLM/deploy/send.

## Inventory and results

The audit found no field-loss path requiring a production edit. The only
production constructor already supplies the final selected keys (Step 2);
all three existing BundleContext model-copy owners preserve untouched fields.
Adding redundant key assignments or a global copy override would not improve
the contract. Step 4 changes six test/helper files only.

### Production and script inventory

Paths below are relative to `src/investo/`, except the explicit script.

| Owner / site | Transport behavior and disposition |
|---|---|
| `orchestrator/bundle_context.py::compute_bundle_context` | Only production constructor; final selected pairs supply keys and display block together |
| `models/bundle_context.py::with_self_pending` | Copy updates only segments; missing/already-pending segment returns self; keys retained |
| `publisher/public_document.py::_snapshot_bundle_context` | Copy freezes the two dict-backed containers; immutable keys retained; None stays None |
| `_internal/daily_thesis_decision.py::redecide_daily_thesis_for_active_segments` | Copy filters original signals and replaces decision only; full selected keys/block retained, no re-matching |
| `publisher/public_document.py::PublicDocumentContext.__post_init__` | Snapshots nested context; repeated dataclass replacement preserves the same contract |
| `publisher/public_document.py::_context_for_active_segments` | Existing neutral redecision then snapshot; None branch skips redecision exactly |
| `publisher/public_document.py::_context_for_minimal_segment` | Intentionally sets bundle_context=None and removes numeric semantic inputs; never restore keys |
| `orchestrator/pipeline.py` generation/public-context wrappers | Compute once, pass same context to GenerationInput and public wrapper; computation failure and nonsegmented path keep None |
| `briefing/generation_contract.py::GenerationInput` | Exact object pass-through, including None; no serialization/reconstruction |
| `briefing/pipeline.py` legacy wrapper and request consumer | Pass-through into GenerationInput, then explicit renderer |
| `briefing/_reader_enhance/context_render.py::_render_bundle_context_block` | Self-pending copy then the existing five-field minimal JSON projection; no typed-key or thesis field added |
| `briefing/prompts.py` and `briefing/_core/orchestration.py` | Wrap/pass the already-rendered string only; no model dump or key reconstruction |
| `publisher/segment_reader_format.py`, `cross_segment_lint.py`, `cross_market_cause_map.py` | Read-only consumers; formatting wrapper in public_document passes context through |
| `scripts/benchmark_public_document_finalizer.py` | Explicit bundle_context=None; synthetic performance fixture has no shared evidence to supply |

The prompt payload remains bundle_id, target_kst_date, segments,
shared_macro_present and sorted cross_market_core_allowed. Presence remains
`block is not None` (including empty-string presence); it is not the
cause-map's nonempty evidence gate. Display text never reconstructs keys.
The ordinary model's JSON key array stays sorted. Full JSON serialization of
internal MappingProxyType snapshots is deliberately not promised.

Search coverage: BundleContext constructors/validation/copy/dump,
with_self_pending and all bundle_context references in src/scripts/tests;
no checked-in JSON/YAML transport fixture was found. Other hits in
publisher/daily_thesis.py and shared_macro.py are decision imports or
documentation, while briefing/_core/section_planning.py contains a classifier
term string, not a context transport path.

### Constructor and prompt fixture decisions

| Fixture | Intent and action |
|---|---|
| `tests/integration/test_bundle_reconciliation.py::_ctx` | Add optional explicit typed keys; only proven oil macro-injection case supplies oil |
| `tests/unit/publisher/test_daily_thesis_owner_u144.py::_base_context` | Three-segment UST core signals explicitly supply ust_yield; retain original block/decision policy |
| `tests/unit/publisher/test_public_document_types_u144.py::_three_segment_thesis_context` | Explicit ust_yield and assertion on every observed survivor pass |
| Public-document defensive-freeze legacy constructor | Generic decision/isolation fixture, not proven shared evidence; leave keys empty |
| Model allowlist/default/invalid/round-trip constructors | Step 2 already distinguishes explicit typed keys from intentional legacy/default cases |
| Cause-map constructors | Step 3 already distinguishes typed positive evidence from explicit legacy-empty tests |
| Cross-segment lint/logging and reconciliation close-state cases | No shared-evidence intent; leave keys empty |
| Orchestrator tests | Use real compute_bundle_context; typed selection supplied by production constructor |
| Prompt formatting and direct shared-block string tests | Not context constructors; retain minimal projection and display-only contracts |
| New `tests/_helpers/bundle_context_u151.py` | Synthetic validated keys/signals supplied explicitly, never inferred from Korean labels |

### Added coverage

78 collected tests (76 examples, two structured properties):

- 64 cases: all eight key subsets crossed with all eight survivor subsets;
  selected keys/block unchanged, original signals filtered, actual decision
  modes asserted and original object unchanged.
- Snapshot isolation mutates the caller's dicts and verifies frozen copies.
  Full selected keys can be broader than remaining thesis signal support.
- None/minimal cases fail immediately if redecision is called. Numeric
  semantic removal is tested as intentional absence, not a transport defect.
- GenerationInput identity/None and eight self-pending key subsets, including
  both no-op branches and ordinary JSON round-trip.
- Generated JSON/snapshot/survivor and minimal-prompt invariants, 60 examples
  per property, seed 15120260908, failure notes and default shrinking.

### Validation

- Focused five modules: 140 passed in 2.73s.
- Cumulative twelve changed Python files: Ruff/check and format pass.
- Source plus three new helper/test files: mypy 257 files pass.
- Expanded scope adding the three existing fixture modules: 13 mypy
  diagnostics in four files, reproduced with the original HEAD versions of
  all three modules via --shadow-file. Categories/messages match; line
  shifts reflect the added fixture fields/assertions. This is baseline
  evidence, not a passing expanded type gate; no unrelated annotations fixed.
- No-paid guard and diff check pass. New tests are synthetic/offline and
  introduce no dependency, SDK or source/API call.
- Independent review: all five categories Pass; 140 tests in 2.71s,
  six-file Ruff/check+format, 257-file mypy and diff check independently pass.
- Related expanded pytest: publisher/orchestrator/models/briefing unit suites
  plus bundle reconciliation and reader-format integration, 3,252 passed
  in 124.45s. Counts overlap the focused gate; this is not the full repository
  gate or Step 5's new rendered acceptance.
- Original root HEAD and its three dirty paths unchanged; isolated HEAD
  remains 17d859ab19ab693bc04747abe36d1ab4a4e6a874. No protected production,
  source/dependency/workflow/archive/site/debt path changed in this step.
- Initial test collection found one wrong model import in the new test,
  corrected to models.facts before the passing focused/expanded/review gates.
- Scoped documentation validation: 23 u151 documents/touched registry
  sections, 46 relative links and 43 tables pass; fences balanced and Code
  Generation progress is exactly four completed/two remaining steps.

### Partial property-testing extension

| Requirement | Status | Evidence |
|---|---|---|
| PBT-01 | Compliant, advisory | Approved copy/transport and projection invariants |
| PBT-02 | Compliant | Ordinary model JSON round-trip before internal snapshot wrapping |
| PBT-03 | Compliant | Keys/block/allowlist retention, exact original signal filtering, input preservation |
| PBT-04 | Compliant, advisory | Self-pending no-op branches; exact absent/minimal context behavior |
| PBT-05 | Compliant, advisory | Independently asserted payload field set and expected decision modes |
| PBT-06 | N/A | No new stateful service or lifecycle |
| PBT-07 | Compliant | Shared structured validated context strategy; bounded key/signal/survivor subsets |
| PBT-08 | Compliant | Seed 15120260908, failure notes, default shrinking, ordinary pytest discovery |
| PBT-09 | Compliant | Existing locked Hypothesis/pytest; no dependency or CI configuration change |
| PBT-10 | Compliant, advisory | 76 explicit examples complement two generated properties |

## Scope handoff

Step 4 verifies transport and fixture intent only. Step 5 must add the new
finalizer-backed CFTC WTI/positioning-row rendered acceptance. Step 6 owns
the full local gate and any DEBT-076 closure; all unit DoDs remain open.
See [independent review](step-4-code-review.md) and
[session log](../../../../docs/sessions/2026-09-08-u151-code-generation-step4.md).

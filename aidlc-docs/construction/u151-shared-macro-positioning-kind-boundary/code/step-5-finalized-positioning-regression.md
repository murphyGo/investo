# u151 Code Generation Step 5 — finalized positioning regression

**Status**: Complete — Step 5/6, recorded 2026-09-08T10:40:26Z.

## Approval and execution plan

- User `진행시켜`, observed 2026-09-08T10:23:36Z after Step 4 handoff,
  authorizes Step 5 only through dev-investo.
- Isolated baseline 17d859ab19ab693bc04747abe36d1ab4a4e6a874; preserve
  recovered design and uncommitted Steps 1–4 plus original dirty root.
- No Plan-mode tool available; this written plan precedes test/code edits.
- Inputs: all three approved Functional Design artifacts, especially
  BR-151-01/02/03/06/07/08/09/10/12, AC-151.3/4/5/6, FR-013/015,
  NFR-003/005/006/007-R13 and existing u107/u144 row/finalization owners.
- Health: no Critical/High/Medium debt; no escalation. u150/u153
  cross-check records present; u151 DoDs and DEBT-076 remain open.

1. Use the existing u144/u153 validated generated-briefing fixture pattern
   in the planned new
   `tests/unit/publisher/test_shared_macro_positioning_regression_u151.py`.
   Feed synthetic model-valid original routed items to compute_bundle_context
   and unchanged finalize_public_bundle; no stubbed matcher, phase or gate.
2. Assert three sealed documents, SHA-256, notification identity/conclusion
   from terminal Markdown, no deterministic CFTC shared/cause/core-thesis
   promotion, and exact delayed US/crypto positioning rows. Add one-eligible
   segment and legitimate selected-key subset controls, relabel/legacy gates,
   original-input preservation and repeat rendering.
3. Pin existing group allowlists, three-row order/cap, required-string
   omission and nonblank malformed-string compatibility. Fixtures remain
   flat scalar metadata; no new numeric/date validator or domestic row.
4. Add structured seeded properties for generated position metadata and
   fixed-input repeated rendering plus equivalent candidate permutations.
   Fix drafts, active segments, close-state inputs and positioning row order;
   do not claim global invariance under first-item insertion into empty segments.
5. Run focused/related expanded tests, scoped static/policy checks and
   independent read-only review. Repair only genuine in-scope defects.
   Record current results, then mark Step 5/6; leave Step 6 full gate/closure.

## Non-goals

No new source/adapter/routing, model/decision policy, prompt/LLM validator,
terminal gate/seal/DTO, dependency/workflow, archive/site/debt or historical
backfill. No commit/push/merge, live source/LLM, pipeline/deployment/send.
Rendered Markdown is lossy; no inverse/full snapshot JSON promise.

## Results

Implementation: one new test file, no additional production edit. Existing
constructor/matcher, typed cause-map, finalizer, native row, watchpoint,
glossary, terminal validator and seal owners are unchanged in Step 5.

### Finalized coverage

51 collected cases: 49 explicit examples and two structured properties.
Each successful case requires all three segments to be `finalized`, not
silently omitted or numerically degraded, with matching sealed Markdown
SHA-256 and a clean terminal-derived notification conclusion.

| Test family | Cases | Contract evidence |
|---|---|---|
| CFTC-only original WTI and all-key misleading titles | 2 | No shared block/cause/core thesis; original source items and exact US/crypto dates, net/%OI and weekly lag retained; no domestic row |
| One eligible oil segment plus CFTC | 3 | Every possible supporting segment still fails the two-eligible-segment threshold |
| All selected key subsets with real eligible controls | 8 | Real two-segment producer selection, canonical thesis choice, oil/Fed deduplication and sealed output |
| Relabel and legacy-empty evidence | 1 | Renamed typed block still emits; display-only legacy block does not infer a cause |
| Missing/blank/non-string required metadata | 24 | Six fields by four defects; no reconstructed channel row or shared promotion |
| Nonblank semantically malformed strings | 1 | Existing presence-only native renderer contract preserved; no new date/number validator |
| Existing US group allowlist and crypto separation | 6 | US groups retained, crypto isolated, unknown/domestic rows absent |
| Three-row cap and order | 1 | Group filtering precedes original-order cap |
| Legitimate delayed watchpoint alongside native rows | 1 | Minimal generated counterexample fixes an overly broad test oracle |
| Equal-zero position rows | 1 | Both %OI values remain under fixed-original-draft repeat |
| Forbidden cause | 1 | Shared evidence display allowed, forbidden cause absent; thesis global allowlist remains independent |
| Generated position batches and candidate permutations | 2 | 30 passing examples each; same original drafts/state/position order, repeated bytes/SHA/DTO |

The synthetic Briefing.market_summary intentionally differs from the safe
terminal conclusion. The notification assertion checks the final Markdown's
known conclusion and excludes the generated-only sentinel/CFTC oil-rise text.
No finalization phase, matcher, trust gate, seal or DTO derivation is stubbed.

### Investigation and test corrections

Initial 14 example cases passed in 1.39s. Expanded generated coverage exposed:

1. **Oracle scope**: native row caps cannot be checked by counting
   `순포지션` throughout the document. The existing
   `publisher/watchpoint_matrix.py::_cftc_candidate` also builds legitimate
   delayed-position watchpoints. The shrunk rates case (+4/-1840 contracts)
   is now an explicit regression; cap/count checks select the exact channel
   table row without removing watchpoint content.
2. **Different-input replay**: feeding already-sealed Markdown back as a
   new generated draft can run the existing
   `publisher/reader_format/glossary.py::dedupe_glossings` over injected
   rows. Two equal-zero crypto rows then lose the second `(0.00% OI)`
   parenthetical. No u151 production code caused or repairs that path.
   The approved full-byte contract fixes generated drafts (BLM section 9,
   BR property boundary, entities section 7 and AC-151.6): the property now
   repeats the exact original generated inputs. Same-original repeat and
   both zero-row percentages pass; arbitrary sealed-to-generated replay is
   not certified. The two simple CFTC examples additionally retain their
   observed successful sealed-input replay assertion, not a universal claim.
3. **Timing, not flaky content**: six actual segment finalizations per
   generated example exceeded Hypothesis's default 200 ms on a cold run
   (450.53 ms, replay 60.19 ms). A finite 1,000 ms deadline is used only for
   these two expensive properties; shrinking/seed/failure notes stay enabled.
   No retry-to-green, disabled deadline, discarded failed values or production
   performance-policy change.
4. One invariant dict annotation in the generator was corrected to the
   existing flat string/integer/float metadata type. No model relaxation.

The fixes above adjust the test oracle and approved input boundary; they do
not suppress an in-scope final-output failure or rewrite production behavior.
The equal-zero counterexample is retained in an explicit test, not filtered
from the structured generator.

### Validation

- Final focused suite: 51 passed in 6.49s.
- Generated positions: 30 passing examples, zero failing/invalid examples;
  typical example runtimes 52–66 ms.
- Candidate permutations: 30 passing examples, zero failures, nine internal
  invalid draws; typical runtimes 0–64 ms. No skipped/xfail test.
- Source plus this test module: mypy 255 files pass.
- Cumulative source and typed u151 tests/helpers: mypy 261 files pass.
- All thirteen cumulative changed Python files: Ruff/check and format pass.
- No-paid guard and diff check pass. Protected production and operational
  paths are unchanged; all fixtures are synthetic/offline.
- The Step 4 existing-fixture 13 baseline mypy diagnostics are outside the
  scoped passing type command; no clean expanded-fixture claim is made.

- Expanded related gate: publisher/orchestrator/models/briefing unit suites
  plus bundle reconciliation and reader-format integration, 3,303 passed in
  136.91s. Counts overlap focused tests; not the full repository Step 6 gate.
- Independent read-only review: all five categories Pass, no new u151
  finding/debt. Focused 51 passed in 6.56s; related/policy subset 254 passed
  in 12.70s; four-file Ruff/format and 255-file mypy independently pass.
- Reviewer independently reproduced the sealed-input glossary limitation
  using unchanged HEAD glossary code and confirmed it is outside the
  fixed-original-draft acceptance. It remains a separate follow-up candidate,
  not silently certified or fixed here.
- Original root HEAD/three dirty paths and isolated HEAD unchanged.
  No previous implementation, operational or debt path was edited in Step 5.
- Scoped documentation validation passes: 26 u151 documents/touched registry
  sections, 52 relative links, 49 tables and balanced fences. Code Generation
  has exactly five completed steps and one remaining step.

## Partial property-testing compliance

| Rule | Status | Evidence |
|---|---|---|
| PBT-01 | Compliant, advisory | Approved final composition/evidence properties reused |
| PBT-02 | N/A for new rendering | Markdown/notification projection is lossy, no new inverse; model round-trip already covered |
| PBT-03 | Compliant | No positioning promotion, exact valid native rows, bounded cap and fixed-input byte/DTO invariants |
| PBT-04 | Compliant, advisory, bounded | Fixed original input repeat and known simple replay examples; no arbitrary sealed-input promise |
| PBT-05 | Compliant, advisory | Independently generated expected rows and explicit selected-key/thesis oracle |
| PBT-06 | N/A | No new stateful service |
| PBT-07 | Compliant | Shared structured PositionBatch and model-valid permutation strategies, bounded counts/dates/net/%OI |
| PBT-08 | Compliant | Seed 15120260908, notes, shrinking, finite timing budget, retained minimal cases and ordinary pytest discovery |
| PBT-09 | Compliant | Existing locked Hypothesis/pytest; no dependency or CI configuration change |
| PBT-10 | Compliant, advisory | 49 explicit examples complement two properties; discovered counterexamples retained |

## Remaining boundary

Step 6 owns the full repository gate, final AC/DoD reconciliation and
DEBT-076 closure. No commit/push/integration, live operational acceptance
or universal sealed-document re-finalization guarantee is included.
See [independent review](step-5-code-review.md) and
[session log](../../../../docs/sessions/2026-09-08-u151-code-generation-step5.md).

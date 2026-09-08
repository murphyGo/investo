# u151 Code Generation Step 3 — typed-key cause-map consumption

**Status**: Complete — Step 3/6, recorded 2026-09-08T08:29:55Z.

## Approval and bounded execution plan

- User: `진행시켜`, recorded 2026-09-08T08:21:30Z, after Step 2 handoff.
- Skill: dev-investo, one plan step and independent post-implementation review.
  No Plan-mode tool is available; this written plan precedes implementation.
- Worktree: `.tmp/u151-functional-design-recovery-20260908`; HEAD
  `17d859ab19ab693bc04747abe36d1ab4a4e6a874`. Preserve approved design,
  uncommitted Steps 1–2 and unrelated original-root changes.
- Inputs: approved business logic section 6, BR-151-07/08, entities section 4;
  Code Generation fixed contracts 5/6, AC-151.4 and Step 3;
  FR-013/015, NFR-003/005/006/007-R13 and existing u74 cause-map contract.
- Health: zero Critical/High/Medium debts; DEBT-076 remains open.
  Existing u150/u153 cross-check reports present; other unit queues unchanged.

## Implementation and validation

1. Replace the rendered-label parser in the existing cause-map module with
   a typed SharedMacroKey-to-cause mapping. Delete the three mirrored Korean
   label constants. Keep the existing cause wording and emission-order tuple.
2. Require the existing nonempty shared block and mapped selected keys.
   Then partition candidates through the independent context allowlist:
   forbidden candidates are suppressed, never demoted. Keep systemic risk
   dormant and the CauseMapDecision/injection shapes unchanged.
3. Update existing cause-map positive fixtures with explicit proven keys.
   Add legacy omitted/empty-key negatives, relabel and misleading-label
   controls, no-block-with-keys, Fed deduplication, mixed suppression and exact
   rendered wording/order tests. Do not infer keys inside test helpers.
4. Add structured seeded properties for candidate partition/relabel invariance
   and idempotent injection. Use seed 15120260908, failure notes, normal
   shrinking and pytest CI. Rendering is lossy, with no inverse promised.
5. Run focused source/model/cause-map tests and related publisher/orchestrator
   regressions, Ruff/format/mypy and policy/diff checks. Review actual failed
   fixtures before a minimal intent-preserving update; do not implement
   Step 4's exhaustive constructor/copy audit or Step 5's new finalizer suite.
6. Obtain independent read-only review; resolve in-scope findings, record
   evidence and update Code Generation to 3/6 only after successful validation.

## Scope boundary

No source/adapter/routing/model/thesis-policy changes in this step. Preserve
Steps 1–2 implementation, explicit prompt fields, snapshots and survivor
ownership, numeric containment, source rows, gates, seals and DTOs.
No new source/API/LLM call, dependency, workflow, archive/site edit, historical
backfill, commit/push/integration/deployment/send or DEBT-076 closure.
Step 4 copy audit, Step 5 finalizer acceptance and Step 6 full gate remain
separately approved work. Unit DoDs remain open.

## Results

Modified only the existing cause-map production owner and its unit test
module in Step 3. Removed three mirrored display labels and mapped the closed
selected-key set to deduplicated causes. The existing ordered partition,
observational wording, empty-block check and injection code are unchanged.
No second detector or fallback label parser was added.

Existing positive fixtures now supply explicit keys. The test helper uses
normal typed construction instead of a heterogeneous kwargs dictionary and
its broad argument-type ignore. It preserves None-vs-empty allowlist behavior
and never guesses evidence from a label.

Added 34 tests (32 parameterized examples and two properties): display-only
legacy contexts with omitted/empty keys, all eight subsets with absent/empty
blocks, relabel and contradictory-label controls, exact oil/Fed order/wording,
Fed deduplication, independent emitted/suppressed partition and dormant
systemic risk. The original truthiness check still treats a whitespace-only
block as truthy; this is not a new block-normalization contract.

| Validation | Result |
|---|---|
| Before-edit existing cause-map tests | 10 passed in 0.72s |
| New-contract red subset, before production edit | 9 failed / 3 passed / 32 deselected; proves label coupling and legacy leakage |
| Repaired focused cause-map module | 44 passed in 1.40s; final test-docstring revision rerun 44 in 1.93s |
| Two new structured properties | 80 passing examples each, seed 15120260908, zero failing examples |
| Cumulative scoped Ruff / format | Pass, six source/test files |
| Mypy | Pass, 254 production files plus three changed test files |
| No-paid / no-Anthropic-SDK guards | Pass |
| Expanded publisher/orchestrator/model gate | 2,197 passed in 95.02s |
| Existing reader-format integration gate | 13 passed in 1.03s |
| Independent review | Five categories Pass; 178 focused tests passed in 4.84s |
| Diff / protected-tree / original-root checks | Pass; original root HEAD and three dirty paths preserved |
| Scoped documentation validation | 20 u151 documents/touched registry sections, 42 relative links, 36 tables and balanced fences; plan 3/6 |

Expanded command: `uv run python -m pytest tests/unit/publisher tests/unit/orchestrator tests/unit/models -q`.
Integration command: `uv run python -m pytest tests/integration/test_briefing_reader_format.py -q`.
No other fixture required an update. The only edit after the expanded run
clarified the test module's opening docstring (ungrounded vs suppressed);
the final focused run and independent 178-test run include that correction.
No executable source/test change followed the expanded gate. This is not the
full repository gate or Step 5's new rendered acceptance suite.
Review: [independent report](step-3-code-review.md).

Counts overlap and are not additive. Hypothesis discarded 15 and 13 examples
during generation in the focused run; these were not assertion failures.
Default shrinking and failure seed notes remain enabled. No runtime regression
was hidden with retries, skip/xfail or old/new conditional expectations.

## PBT compliance — Step 3 scope

| Rule | Status | Evidence / boundary |
|---|---|---|
| PBT-01 | Compliant, advisory | Approved cause-map and composition properties reused |
| PBT-02 | N/A for new transform | Cause rendering is lossy; no inverse or new serializer; prior model round-trip retained |
| PBT-03 | Compliant | Generated mapped/gated partition, label independence and input preservation |
| PBT-04 | Compliant, advisory | Generated injection idempotence, empty/sentinel no-op and section placement |
| PBT-05 | Compliant, advisory | Simplified independent conditional oracle for typed candidate partition; old parser is intentionally not the oracle |
| PBT-06 | N/A | No new stateful service |
| PBT-07 | Compliant | Shared structured BundleContext strategy, bounded key/allowlist subsets and display variants |
| PBT-08 | Compliant | Explicit seed 15120260908, failure notes, default shrinking and ordinary pytest CI |
| PBT-09 | Compliant | Existing locked pytest/Hypothesis framework; no dependency/configuration changes |
| PBT-10 | Compliant, advisory | Explicit examples complement two properties; pre-repair failures demonstrate regression sensitivity |

## Handoff boundary

Step 3 verifies the cause-map contribution to AC-151.4: renamed labels cannot
change the decision, missing keys do not supply evidence, and forbidden
mapped types are suppressed. It is not a full-unit AC/DoD closeout. Next is
Step 4's explicit constructor/copy/serialization audit. Keep DEBT-076 open.

# u151 Code Generation Step 1 — Synthetic incident characterization

**Date**: 2026-09-08 KST
**Status**: Complete — Step 1/6, recorded 2026-09-08T04:23:50Z.
**Approval recorded at**: 2026-09-08T04:17:23Z
**User**: `진행시켜`, following the completed design and Step 1 handoff.
**Baseline**: `17d859ab19ab693bc04747abe36d1ab4a4e6a874`
**Skill**: dev-investo; one step, then separate review.

## Approved bounded execution plan

Plan-mode switching is not available in this session. Read the design,
requirements and implementation before editing; record this written plan
and execute it in Default mode. Preserve the existing recovered design and
original dirty root in the project-local isolated worktree.

1. Extend the existing `tests/unit/orchestrator/test_bundle_context.py`.
   Construct clearly synthetic, model-valid CFTC WTI items; preserve the
   incident title but do not represent invented metadata as captured API data.
2. Characterize the public `compute_bundle_context` path: positioning-only
   routed evidence incorrectly becomes shared oil/core thesis; one eligible
   oil-news segment plus positioning in another incorrectly meets the
   distinct-segment threshold. Exercise full, missing and scalar-defect metadata.
3. Separate the thesis leak from threshold selection with two already-eligible
   oil segments plus positioning. Include positive eligible-only and
   same-segment duplicate controls. Assert observable block, signal identities,
   decision modes and original-input preservation, not private matcher returns.
4. Add a bounded structured Hypothesis strategy over these synthetic inputs
   to check unchanged repeated-result/input-immutability and controlled
   candidate-permutation properties. Use per-test seed 15120260908, normal
   shrinking and no networking, source calls or LLM. New exclusion/typed-key/
   overlap/serialization properties belong to later implementation steps.
5. Run focused/broader relevant tests and scoped Ruff/format/mypy, check no
   production/dependency/generated-file change, then obtain an independent
   skill-mandated code review and address in-scope findings.

The characterization tests assert current observed defects so Step 1 can be
verified without implementing Step 2. They are named as baseline
characterization, not acceptance tests. Step 2 must convert their assertions
to the approved rejection contract; never keep them by adding conditional
old/new assertions, skips or xfails. Six unit ACs and five DoDs remain open.

## Evidence provenance and scope

Historical source is `d553035:archive/us-equity/2026/09/2026-09-04.md:27`
(WTI contract title under international oil) and line 36 (oil cause-map).
The current baseline archive has since been regenerated and does not contain
that same oil row; it is not substituted for the historical incident.
The current baseline classifier still has title-only matching and a separate
thesis matcher path without the proposed source exclusion.

No production source code, typed model field, cause-map implementation,
finalizer acceptance, new adapter/API/secret/dependency, historical archive,
schedule, deploy, publish/send, commit/push or DEBT-076 closure in this step.

## Results

Modified one existing test module: 15 added cases (13 parameterized example
cases and two property tests), no skip/xfail. The current source incorrectly
promotes CFTC-only oil evidence, accepts CFTC as a second shared segment,
and emits CFTC core signals even when two real news segments already qualify.
Positive two-news and negative same-segment controls pass.

The existing make_item helper now uses the existing Category type; its
obsolete unused-ignore comment was removed after scoped mypy detected it.
This changes no runtime behavior or production code.

| Validation | Result |
|---|---|
| Before-edit existing bundle-context tests | 37 passed in 2.92s |
| Focused module after additions | 52 passed; independent final rerun 52 in 1.42s |
| New u151 cases with Hypothesis statistics | 15 passed, 37 deselected in 0.89s |
| Hypothesis, fixed seed 15120260908 | 40 passing examples per property; zero failing examples |
| Expanded seven-module gate, final tree | 103 passed in 2.21s |
| Scoped Ruff check / format | Pass |
| Scoped test mypy / source mypy | Pass: one test module / 254 source files |
| Diff / protected-tree checks | Pass; only one test module and scoped documentation changed |
| Independent review | Pass in all five categories; no open finding or new debt |

Expanded gate includes orchestrator bundle-context, model allowlist, publisher
cause-map, shared-macro block, daily thesis, u144 daily-thesis owner and channel
anchor tests. This is not the full repository gate or u151 finalizer acceptance.
The permutation property's two discarded Hypothesis examples were normal
generation rejections, not malformed model fixtures or failing examples.
Normal shrinking remains enabled and failure notes print the fixed seed.

During final static checks, uv cache access once hit a sandbox permission
error; the same check was rerun with explicit escalation and passed. No cache
permission workarounds or dependency changes were used.

## PBT Compliance — current Step 1 scope

| Rule | Status | Evidence / remaining obligation |
|---|---|---|
| PBT-01 | Compliant, advisory | Approved three-artifact properties referenced by code plan |
| PBT-02 | N/A for this step | No serializer introduced; typed context round-trip belongs to Steps 2/4 |
| PBT-03 | Compliant for scoped invariants | Generated repeated-result, input-preservation and controlled permutation checks; repaired exclusion invariants remain Step 2 |
| PBT-04 | N/A, advisory | No new idempotent transform/service; repeated invocation covered as determinism, not f(f(x)) |
| PBT-05 | N/A, advisory | No optimized replacement; explicit baseline examples document known behavior |
| PBT-06 | N/A | No stateful service or new mutable state |
| PBT-07 | Compliant | Bounded structured routes, model constructors, metadata variants and signed contract counts |
| PBT-08 | Compliant | Per-test seed 15120260908, failure seed notes, default shrinking, ordinary pytest discovery/CI |
| PBT-09 | Compliant | Existing Hypothesis/pytest dev dependencies, locked local environment |
| PBT-10 | Compliant, advisory | Thirteen explicit example cases plus two properties, no skip/xfail |

No blocking finding within Step 1. This does not mark the future repair
properties or any of the six unit acceptance criteria as passed.

## Handoff

See [independent review](step-1-code-review.md) and
[session log](../../../../docs/sessions/2026-09-08-u151-code-generation-step1.md).
Next: Step 2 common source exclusion, typed selected-key field and canonical
one-signal production; convert the three baseline-defect test methods to
desired assertions, retaining positive controls and properties.
All five unit DoDs and DEBT-076 remain open. No automatic next step or commit.

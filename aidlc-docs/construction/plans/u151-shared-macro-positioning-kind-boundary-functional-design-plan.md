# Functional Design Plan: u151 shared-macro-positioning-kind-boundary

**Date**: 2026-09-08
**Status**: Complete — final user approval recorded 2026-09-08T04:17:23Z (7/7).
**Baseline**: `17d859ab19ab693bc04747abe36d1ab4a4e6a874`
**Skill**: `dev-investo` — one approved step per invocation.
**Approval scope**: Q1=A and Q2=A were approved by `모두 A로 승인`;
subsequent `진행시켜` messages authorized individual drafting/validation steps.
The earlier `gogo` resumed interrupted Step 7. After the final design
presentation, `진행시켜` approves that design and Code Generation Step 1.

## Recovery provenance

The former `/private/tmp/investo-u151-functional-design-20260908` path is
missing. These documents are reconstructed from the retained conversation
design record and rechecked against the exact baseline, not a byte-for-byte
restoration. Historical per-step session files are not fabricated. See the
[recovery session](../../../docs/sessions/2026-09-08-u151-functional-design-recovery-step7.md).
The original dirty main worktree and all other branches remain untouched.

## Context and stage decision

The September 4 CFTC WTI contract count was promoted to a shared oil-price
premise and deterministic oil cause/thesis. Extend u57/u60 selection, u74
cause-map, u107 positioning preservation and u124 thesis evidence boundaries.
US-002/003/005; FR-002/008/013/015; NFR-003/005/006/007-R13.
DEBT-076 remains open until implementation validation.

Functional Design is required for typed cross-component transport and legacy
compatibility. NFR Requirements is skipped: existing reliability, fixture,
secret and cost rules suffice; no new I/O, dependency or runtime policy.
NFR Design and Infrastructure Design remain skipped under the execution plan.
No frontend component design is needed: existing Markdown owners are retained.

## Approved questions

### Q1 — Legacy context without typed keys

What should a nonempty legacy shared block with absent/default-empty typed keys do?

A) Keep its display, but emit no deterministic cause-map line; never infer keys from labels.
B) Reject the whole context when a shared block lacks typed keys.
C) Other (describe after the answer).

[Answer]: A

This does not reset a caller-supplied daily-thesis decision. Typed keys without
a block do not synthesize one. Normal model validation still rejects invalid keys.

### Q2 — An eligible item matching multiple selected macro keys

How many thesis signals should one routed item produce per segment?

A) At most one, choosing the first matching final selected key in `fomc, oil, ust_yield` order.
B) Emit a signal for every matching final selected key.
C) Other (describe after the answer).

[Answer]: A

The first-match rule applies only to thesis signal emission. Candidate
collection and shared-key/block projection retain every qualified key.
Only final selected keys are inspected; unselected FOMC cannot shadow selected oil.

## Steps

- [x] Step 1 — Analyze unit, stories, source owners, prior units and debt.
- [x] Step 2 — Create the scoped plan and compatibility/overlap questions.
- [x] Step 3 — Validate A/A answers, resolve ambiguity and reconcile fixed contracts.
- [x] Step 4 — Draft business logic, selection flow and testable properties.
- [x] Step 5 — Draft business rules, acceptance examples and preservation boundaries.
- [x] Step 6 — Draft domain entities, copy/serialization boundaries and properties.
- [x] Step 7 — Validate all three artifacts, eight contracts, six ACs and PBT; present for final approval.

Checked steps represent drafting/validation progress, not final user approval.
Do not auto-advance to code from checkbox count.

## Artifacts

- [Business logic model](../u151-shared-macro-positioning-kind-boundary/functional-design/business-logic-model.md)
- [Business rules](../u151-shared-macro-positioning-kind-boundary/functional-design/business-rules.md)
- [Domain entities](../u151-shared-macro-positioning-kind-boundary/functional-design/domain-entities.md)
- [Design validation and review actions](../u151-shared-macro-positioning-kind-boundary/functional-design/design-validation.md)
- [Code Generation plan](u151-shared-macro-positioning-kind-boundary-code-generation-plan.md)

## Continuity and handoff

Steps 4–6 were individually drafted before interruption; their substantive
contracts are restored here. Step 7 reconciles them with baseline ownership,
including precise positioning metadata omission and per-test seed obligations.
No new business-policy choice is introduced by those clarifications.

Final approval: **Approved — `진행시켜`, recorded 2026-09-08T04:17:23Z.**
The approved next step is Code Generation Step 1, synthetic incident
characterization only. No commit, push, merge,
deployment, pipeline dispatch, Telegram send or next-unit authorization is implied.

# Session Log: 2026-09-08 — u151 Code Generation Step 5

## Outcome

Code Generation 5/6 complete at 2026-09-08T10:40:26Z. User `진행시켜`
was observed at 2026-09-08T10:23:36Z after the Step 4 handoff.
dev-investo constrained execution to Step 5 and required independent review.
No Plan-mode tool exists; written research plan preceded edits.

## Changes

- Created `tests/unit/publisher/test_shared_macro_positioning_regression_u151.py`:
  51 cases (49 examples, two structured properties) use real finalizer,
  terminal validation, seal and notification derivation without stubs.
- Updated AIDLC state, unit/story map, code plan and audit; added Step 5
  execution and independent review records.
- No extra production edit. The stale Step 3 code-plan header was corrected
  to the actual Step 4 starting state and then current Step 5 completion.

The cases verify no shared CFTC promotion, genuine eligible-key controls,
legacy/relabel/allowlist rules, native US/crypto group/order/cap/date/lag rows,
strict required-string omission and unchanged nonblank malformed-string
compatibility. All three outcomes must be finalized and all SHA/notification
conclusions must match terminal Markdown; a generated-only sentinel cannot
replace the public summary.

## Investigation and decisions

| Decision | Evidence |
|---|---|
| Count positions only inside the native channel row | Existing CFTC watchpoints legitimately add other mentions; minimized rates example retained |
| Repeat exact original drafts for full-byte property | FD/AC-151.6 fixes generated inputs; sealed output is a different input |
| Preserve equal-zero row example | Both %OI values survive same-original rendering; failure values were not excluded |
| Use finite one-second PBT deadline | Six actual segment finalizations exceeded default 200 ms on cold run; 450.53 ms versus 60.19 ms replay |

An exploratory stronger sealed-input replay check exposed unchanged glossary
deduplication removing a second `(0.00% OI)` from equal-zero channel rows.
Same-original repeat is stable. Independent review reproduced both behaviors
and reproduced the loss with HEAD glossary code. This limitation remains
explicitly outside the approved u151 fixed-original contract; no universal
re-finalization promise or glossary fix is claimed. It is a separate possible
follow-up, not a newly registered u151 debt.

## Validation

Initial 14 examples passed in 1.39s. After investigating oracle/timing/replay
boundaries and correcting one generator dict annotation, final focused:
51 passed in 6.49s. Two properties each have 30 passing examples, seed
15120260908, failure notes and default shrinking; finite 1,000 ms deadline.

Related expanded publisher/orchestrator/models/briefing unit suites plus two
integration modules: 3,303 passed in 136.91s. Counts overlap, not additive;
this is not Step 6's full repository gate.

Cumulative thirteen-file Ruff/check+format, source/typed u151 test/helper
mypy 261 files, no-paid/no-SDK and diff/protected-path checks pass. The prior
Step 4 existing-fixture 13 baseline type diagnostics are excluded from the
passing typed-test scope, not claimed fixed or re-certified clean.
Scoped document validation: 26 u151 documents/touched registry sections,
52 relative links, 49 tables and balanced fences pass; progress is 5/6.

| Independent review category | Result |
|---|---|
| Correctness | Pass |
| Safety | Pass |
| Reliability | Pass |
| Maintainability | Pass |
| Test Coverage | Pass |

Read-only `u151_step5_review`: focused 51 in 6.56s, related/policy subset
254 in 12.70s, scoped four-file Ruff/format and 255-file mypy pass.
No new u151 finding/debt; full protocols and scope judgment in review record.

## Preservation and next step

Worktree `.tmp/u151-functional-design-recovery-20260908`, branch
`codex/u151-functional-design-recovery-20260908`, HEAD
`17d859ab19ab693bc04747abe36d1ab4a4e6a874`.
Recovered design and Steps 1–4 remain uncommitted. Original root HEAD
`985b7e4063a8037bf46f7e6f87426a816cf715f7` and its three dirty paths unchanged.

No production, source adapter/routing/LLM, dependency/workflow, archive/site,
requirements/DESIGN or TECH-DEBT edit in Step 5. No commit/push/merge, live
source/generation/pipeline/deployment or send. Other unit queues unchanged.

Next approval: Step 6 full local gate, final AC/DoD reconciliation and
DEBT-076 closure only after required checks. All unit DoDs/debt remain open.

Evidence:
[execution record](../../aidlc-docs/construction/u151-shared-macro-positioning-kind-boundary/code/step-5-finalized-positioning-regression.md),
[independent review](../../aidlc-docs/construction/u151-shared-macro-positioning-kind-boundary/code/step-5-code-review.md).

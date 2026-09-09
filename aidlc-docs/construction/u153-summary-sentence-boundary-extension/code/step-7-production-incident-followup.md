# u153 Code Generation Step 7 — Production incident follow-up

**Date**: 2026-09-09 KST
**Status**: Complete — Step 7/7; follow-up cross-check APPROVE and production re-verification closed
**Baseline**: `origin/main` at `28b95f8c41894f0e6a3240fde7ea0696117d799b`
**Workspace**: `/private/tmp/investo-u153-fix.G4IkCe`

## Incident and approved boundary

Scheduled daily run `34172164168` generated all three drafts but rejected US
equity with `summary.truncated_mid_token`. Domestic and crypto were published
in bot commit `f93def42`, Telegram delivery succeeded, and Pages run
`34172964321` completed. The rejected US draft was not persisted, so the exact
sentence cannot be recovered. The production policy path is nevertheless
reproducible: the generic terminal-syllable regex treated complete body labels
such as `미 국채` and `기관` as truncated and routed the summary-owned code from
`segment_body` to a segment-wide block.

The user's `개발 진행해줘` approved only this Step 7 root correction. No live
run, publish, notification, commit, push, merge, dependency or next-unit work
was authorized.

## Implementation

1. Removed terminal Korean syllables as evidence. The shared predicate now
   recognizes only observable structural clipping: an attached ASCII/Unicode
   ellipsis or unmatched terminal Markdown delimiters. Complete nouns remain
   byte-identical.
2. Kept `summary.truncated_mid_token` exclusive to the indexed first viewport.
   Meaning callouts emit `meaning.truncated_surface`; watchpoint headings emit
   `watchpoint.title_truncated_surface`. Both codes are registered in the closed
   policy matrix, use only their expected owner, and fail closed elsewhere.
3. Mapped a genuine meaning defect to its indexed `section_body` fallback and
   a genuine watchpoint-title defect to the `watchpoints` fallback. Repeated
   finalization preserves Markdown bytes and SHA-256.
4. Made terminal-marker repair explicit in the existing summary owner. A pure
   terminal marker uses the canonical per-prefix fallback; simultaneous harder
   link evidence retains its original bytes for u150's policy.
5. Preserved hard-gate precedence. Before a mutating presentation disposition,
   the projected bytes are checked for numeric, entity and compliance findings.
   Coexistence blocks before evidence can be erased and reports every actionable
   surface code without exposing evidence. Domestic numeric-only input still
   follows u149 containment when no presentation mutation competes with it.
6. Link and body truncation are classified in one scanner pass. The body owner
   examines only reader-visible residue after a safe link repair, so an
   incomplete link's internal `...`, `(` or `[` cannot impersonate a second
   truncation; a real visible suffix after the link still produces both codes
   and one strongest regional action.

## Acceptance evidence

- Safe endings include `기관`, `미 국채`, and the former `[채확민관]` terminal
  family. A seeded 80-example property (`15320260909`) varies complete Korean
  stems and owner lines and proves no blocking truncation finding.
- Structural `...`, `…`, `(` and `[` cases remain blocked or locally contained
  according to their owner. Historical u131 meaning/watchpoint fixtures now
  assert the distinct machine codes rather than a summary code.
- Real finalizer tests prove safe US output survives unchanged; meaning and
  watchpoint defects use one regional fallback and repeat with identical bytes
  and SHA. A valid sibling survives a blocked domestic numeric-plus-meaning
  case.
- Coexistence regressions cover recoverable link plus visible truncation,
  incomplete-inline without false owner truncation, numeric/entity/compliance
  plus a mutating fallback, and numeric plus mutating fallback plus a separate
  protected link. The typed error retains all bounded actionable codes.
- The existing first-viewport caution and summary paths, spaced cosmetic
  ellipsis repair, u149 numeric-only degradation, u150 link shapes, terminal
  entity scan count, notification DTO and sealed-output contracts remain in
  the combined regression gate.

## Validation

- Final related gate: **571 passed in 14.58s** across the surface, summary,
  public-document policy/containment, numeric containment, u153 finalizer and
  terminal entity validation modules.
- Exact final full repository gate: **5,229 passed in 299.25s (4m59s)**.
- Ruff: all checks pass; all **581 files** formatted.
- Mypy: **254 source files**, no issues.
- `uv lock --check`, no-paid-API, no-Anthropic-SDK, curated-assets
  (**19 filed, 0 deferred**), image-store, strict MkDocs/Material-theme and
  `git diff --check` gates pass. No dependency or generated-output change.
- Partial PBT is compliant: PBT-03/07/08/09 apply; PBT-02 remains N/A for the
  lossy display repair. The new property is finite, seeded, shrinking-enabled
  and collected by ordinary pytest.

## Independent review

The required fresh-eyes review ran in three passes. The first pass found that
regional replacement could erase a non-surface hard-gate claim and that a link
finding could defer an independent visible truncation to a second pass. The
second pass found incomplete links being double-classified and a separate
`block_segment` surface code missing from early aggregation. Each finding was
fixed with a failing regression before implementation and re-review. The final
review passed correctness, security, error-contract propagation and test-gap
checks with **11 related tests**, scoped Ruff/format, production mypy and diff
integrity; no finding remains.

No ADR or TECH-DEBT entry is needed: this changes no architecture, dependency,
I/O, secret, retry or performance contract. The original six-step u153
cross-check remains historical evidence; at construction handoff this new Step 7
required its own follow-up cross-check and production re-verification before
operational closeout.

## Delivery follow-up

After the completed development handoff, the user explicitly requested
`커밋, 푸시 해줘`. The validated 15-file slice was committed as
`c5cdfa48b637f07f4c95afa75c6c992b74251453` (`fix: contain u153 truncation
false positives`) and pushed to
`origin/codex/u153-operational-fix-20260909`; `git ls-remote` returned that
exact SHA. The earlier no-commit/no-push boundary records the construction
turn before this later authorization. Cross-check, main integration and live
production re-verification remain unperformed.

## Main integration follow-up

The user's later `main에 병합해줘` authorized integration. Freshly fetched
`origin/main` was `a63f863f44fb62ce81993bcda7ed7d351737273e` and included the
2026-09-08 partial briefing outputs. A separate clean worktree merged source
`f55e3a446a05b67a36b482e060f8c4286c997308` without conflict as
`64747390541a7cd5d4eab6ab16651e7c351a9d8b`; no archive/site path changed from
the main parent. The exact combined code tree passes 5,229 full and 571 focused
tests, Ruff/mypy, all policy/asset guards and strict docs/Material checks.
At integration handoff, cross-check and production re-verification remained
separate pending work.

## Follow-up cross-check

The user later requested the Step 7 follow-up cross-check. Current main
`71c1db17fab62dde0caf981b909e51c2d6564c4c` passes a fresh **571-test** related
gate in 16.69s and a fresh **5,229-test** full gate in 316.94s, plus lock,
Ruff/581-file format, source mypy 254, policy/assets and strict docs/Material
checks. GitHub Quality run `34309893210` is successful for the same SHA.

Verdict: **APPROVE, 6/6 Step 7 contracts Complete**, with no new gap, task or
TECH-DEBT. The original rejected US draft was not persisted, so production
re-verification was retained as a distinct operational closeout item. Report:
`docs/cross-checks/2026-09-09-u153-step7-production-incident-followup.md`.

## Production re-verification closeout

The user's subsequent `진행시켜` authorized the remaining live verification.
Exact-incident-date daily run `34328379033` (`2026-09-07`) and no-input
current-date run `34330763708` (resolved `2026-09-08`) both generated 3/3,
finalized and published all three segments, sent Telegram successfully and
exited 0. US equity finalized normally in both runs with no u153 surface code;
domestic alone used the established u149 `numeric.anchor_assertion`
`finalized_degraded` containment. Bot commits `978d37ed49039f20aeca60e67836f7a0f7713f64`
and `eb137d788209917bd972e6790169e0b02b37fe97` reached `main`; Pages runs
`34329717519` and `34332491487` succeeded, and all six live segment URLs
returned HTTP 200.

The two pipeline durations were `847.442s` and `1083.996s`, so existing
`DEBT-090` receives additional evidence for the NFR-001 performance miss. No
new correctness gap, task or duplicate debt is created. Step 7 is now
requirements-approved, main-integrated and operationally closed.

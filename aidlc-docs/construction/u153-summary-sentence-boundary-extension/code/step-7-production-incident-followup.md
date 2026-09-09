# u153 Code Generation Step 7 — Production incident follow-up

**Date**: 2026-09-09 KST
**Status**: Complete — Step 7/7; follow-up cross-check and production re-verification pending
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
cross-check remains historical evidence; this new Step 7 requires its own
follow-up cross-check and production re-verification before operational closeout.

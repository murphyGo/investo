# u145 Step 4 — Renderer and derived-only store

## Current disposition — 2026-09-27

Step 4 is **closed with a user-approved visual-validation waiver**. The user requested that
the repeatedly blocked Browser screen check be skipped. Actual mobile/desktop inspection is
`WAIVED / NOT_EXECUTED`, not PASS; prior static/pair checks remain valid for their recorded
sources. Browser recovery is no longer required to begin Step 5. All data/security checks,
five production-adapter probes, and separate Step 6 activation remain required. The historical
open-gate statements below are superseded by this decision, not by new screenshot evidence.
See `docs/sessions/2026-09-27-u145-viewport-waiver.md` and the AC-5.4 exception.

## Outcome

- Added a deterministic renderer for the approved C1-C7 public surface. Every state retains the
  fixed eleven-sector table, keeps XLRE explicitly `provider 미지원`, and places the four scope
  qualifications before the metrics table.
- Added canonical UTF-8 Markdown/JSON pair verification. The verifier reparses the typed model,
  independently recomputes the SHA-256 identity, requires canonical bytes and exact rendered
  Markdown, validates cross-record rank ordinals/denominators, and rejects raw shapes, secrets,
  source URLs, provider text, and prohibited whole-market/flow/advice wording.
- Added the fixed `site_docs/sectors/index.md` plus `latest.json` derived-only store with unchanged
  detection, pair-integrity validation, fresh partial/normal promotion, first-publish fail-closed,
  byte-identical last-good hold, and closed failure outcomes.

## Recovery and filesystem boundary

- Readers and writers use one non-blocking repository-scoped advisory lock. An active reader can
  no longer interpret an in-progress writer marker as abandoned recovery.
- Promotion pins both `site_docs` and `site_docs/sectors` with `O_DIRECTORY | O_NOFOLLOW` file
  descriptors and inode checks. Output, staging directories, marker updates, reads, rollback, and
  cleanup use descriptor-relative I/O; parent/output symlink swaps cannot write outside the
  repository boundary.
- The versioned marker records `promoting` or fsynced `rolled_back`. A failed call always restores
  the prior pair or removes the first partial pair, while restart recovery may finalize a fully
  written new pair. Cleanup interruption after rollback is recoverable from the visible prior id.
- Owner-validated cleanup removes markerless prepared/backup directories and exact atomic temp
  files. Deep JSON, malformed pair/marker content, OS read failures, paths, and provider details
  remain behind closed projection/store errors.

## Tests and review

- The Step 4 renderer/store file has 36 tests for C1-C7 order and content, eleven rows, warming
  suppression, attribution, two-decimal half-even formatting, deterministic/canonical bytes,
  rehashed rank attacks, recursion/resource bounds, raw/secret/wording guards, no client network,
  idempotency, mismatch rejection, last-good behavior, crash phases, orphan cleanup, concurrency,
  error closure, and parent/output symlink swaps.
- Combined u145 model, adapter, metrics, renderer/store, redaction, and no-paid-policy scope passed
  405 tests on the final implementation.
- Full repository regression passed 4,540 tests in 405.98 seconds.
- Fresh-eyes review found and closed active-reader recovery, post-snapshot failure rollback,
  rollback-cleanup crash, parent/output symlink TOCTOU, orphan cleanup, error disclosure/class,
  recursive JSON, OS read closure, and rank-negative-test gaps. Final re-review reported zero
  remaining Critical, High, or Medium code findings.

## Static and activation boundary

An ephemeral synthetic projection passed `mkdocs build --strict`. Its built HTML contains the
responsive viewport meta tag, semantic H1/H2 and table header elements, the four leading columns
in approved order, all eleven rows including XLRE, and descriptive HF/IEX links. The configured
browser surface exposed no available browser instance, so the required visual checks at 390x844
and desktop width were not executed. That acceptance item remains explicitly open and blocks Step
4 completion and all Pages activation.

This step made no live provider call and added no generated public pair to the repository, probe
or scheduled workflow, navigation, Pages deployment, Telegram path, or daily-briefing coupling.

## 2026-09-22 resumed validation and repairs

The preserved Step 1–4 overlay now also exists on current main `c286f500` in
`.tmp/u145-resume-20260922`. A new independent review reproduced and repaired two defects:
complete records incorrectly showed a missing-metric label, and cleanup could destroy the
backup before a synchronous failed promotion attempted rollback. Cleanup failure now persists
the already verified prior projection as a new recovery backup before restoring it.

Seven regression cases cover complete-row labeling and three cleanup destruction stages, each
with and without a second interruption during restore. The reviewer approved the fixes. Exact
test results, current-main compatibility, preview evidence, and the still-open Browser gate are
recorded in `docs/sessions/2026-09-22-u145-step4-resume-and-repair.md`. Historical test counts above
describe the 2026-09-06 implementation and do not substitute for current validation.

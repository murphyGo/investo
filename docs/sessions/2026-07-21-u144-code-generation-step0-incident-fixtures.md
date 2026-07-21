# Session: u144 Code Generation Step 0.2

## Overview

- **Date**: 2026-07-21
- **Unit**: u144 public-document-finalization-contract
- **Stage**: Code Generation
- **Step**: Step 0, checklist 2 of 6 — freeze redacted incident fixtures
- **Outcome**: Complete; Step 0 checklist 3 is next

## Work Summary

Added immutable JSON baselines for the three producer/gate mismatch families
that motivate u144. The fixtures isolate the minimum Markdown transition and
expected legacy observation without copying a complete production briefing or
raw collection data.

The run-29707052598 fixture records the bounded live outcome: three generated
segments, zero generation failures, a watchpoint default that recreated the raw
public label after projection, the terminal `public_diagnostic.raw_label`
finding, and a partial pipeline result. The first-viewport fixture covers an
unbalanced strong delimiter, an unclosed parenthesis, and a literal ellipsis.
The body-evidence fixture records that the old accounting signal is present
before projection and absent afterward even though the known public evidence
link remains.

## Files Changed

- Added `tests/fixtures/u144/README.md`.
- Added three redacted JSON fixtures under `tests/fixtures/u144/`.
- Marked Step 0 checklist 2 complete in the u144 code-generation plan.
- Updated AIDLC state/audit and added this session log.

Unrelated dirty u140, generated archive/site, settings, and worktree changes
were not edited.

## Validation

- `jq empty tests/fixtures/u144/*.json`
- Exact current-producer equality for the watchpoint and public-projection
  before/after Markdown fields
- `git diff --check`
- Secret/sensitive-content review of the new fixture directory

## Code Review Results

Fresh-eyes review found one Medium fixture-accuracy issue: the initial
body-evidence `markdown_after_projection` collapsed three repeated public
source-detail replacements into one. The fixture now preserves the exact
legacy output for the `0건`, `실패`, and `본문 사용` substitutions. Re-review
confirmed the watchpoint fixture is byte-equal to the current producer, all
three truncation shapes reproduce the expected issue, the body-evidence gate
is present before projection and absent afterward, and no sensitive or
out-of-scope data is included.

## TECH-DEBT

No new TECH-DEBT item was introduced. Characterization tests intentionally
remain the next checklist item so the fixture contract is pinned before any
production behavior changes.

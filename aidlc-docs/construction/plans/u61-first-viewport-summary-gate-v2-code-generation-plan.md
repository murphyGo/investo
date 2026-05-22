# Code Generation Plan: `u61 first-viewport-summary-gate-v2`

**Date**: 2026-05-23
**Unit**: u61 first-viewport-summary-gate-v2
**Stage**: Code Generation
**Status**: Complete (7/7)
**Source**: 2026-05-23 10-subagent review of latest generated segmented briefings
**Estimated Effort**: ~3-5 h
**Dependencies**:
- u21 summary quality gate
- u25 summary fidelity and content trust
- u51 TL;DR block and reader formatting

---

## Problem Statement

The latest generated briefings still exposed broken first-viewport summary text:

- Markdown headings such as `### ...` leaked into `핵심 동인`.
- Summary lines were truncated mid-thought.
- Stray generation residue such as `ROS` appeared in the reader-facing summary.
- Malformed emphasis such as `**-**0.10%**p**` survived publisher formatting.

These are reader-trust defects because they appear before the article body and quality diagnostics.

---

## Goal

Block publication of malformed first-viewport summaries and provide deterministic repair or fallback before archive writes.

---

## Scope Boundary

In scope:
- Strengthen summary extraction, cleanup, and validation.
- Reject heading residue, broken emphasis, dangling tokens, and non-terminal truncation.
- Add sanitized fallback text for data-limited segments.
- Add regression tests using the observed bad snippets.

Out of scope:
- Rewriting the Stage 2 prompt wholesale.
- Backfilling old archive files.
- Changing the visual-card layout.

---

## Implementation Steps

### Step 1 - Pin observed malformed snippets

- [x] Add unit tests for `###` heading leakage in summary values.
- [x] Add unit tests for stray terminal tokens such as `ROS`.
- [x] Add unit tests for malformed bold around signs and percentage-point suffixes.
- [x] Add unit tests for summary values ending without terminal punctuation or an intentional ellipsis.

### Step 2 - Harden summary extraction

- [x] Update summary extraction to strip leading markdown headings regardless of list-marker presence.
- [x] Treat heading-only candidates as invalid, not as text to truncate.
- [x] Preserve legitimate ticker symbols and numeric values while removing markdown control syntax.

### Step 3 - Expand summary quality validation

- [x] Reject unescaped heading markers in `핵심 동인`, `주의할 점`, and equivalent first-viewport fields.
- [x] Reject odd or structurally invalid bold markers.
- [x] Reject summaries that end with a Korean/English conjunction, dangling noun phrase, or unclosed punctuation.
- [x] Reject known generator residue tokens only when they appear as isolated terminal tokens.

### Step 4 - Add deterministic fallback

- [x] When summary validation fails, replace the field with a concise data-status-aware fallback.
- [x] Fallback must mention limited data only when coverage status supports it.
- [x] Fallback must avoid investment-advice verbs and price targets.

### Step 5 - Wire gate before archive write

- [x] Ensure the strengthened gate runs after reader-format transforms and before segmented archive writes.
- [x] Make failures fail the publish stage with actionable diagnostics unless a deterministic fallback was applied.
- [x] Log sanitized evidence snippets bounded by length and without raw secrets.

### Step 6 - Verify notifier reuse

- [x] Ensure Telegram summaries use the same cleaned first-viewport values.
- [x] Add a notifier regression test so malformed summary text cannot bypass the site gate through notification code.

### Step 7 - Documentation and gate

- [x] Update relevant reader-format or quality-gate docs.
- [x] Run targeted summary/publisher/notifier tests.
- [x] Run `uv run ruff check` on changed files and targeted `mypy --strict` scope.

---

## Definition of Done

- [x] The observed `###` leakage, truncation, `ROS`, and malformed bold snippets are pinned by tests.
- [x] First-viewport summary validation blocks or repairs all pinned malformed cases.
- [x] Valid summaries containing tickers, signs, percentages, and Korean punctuation still pass.
- [x] Archive and Telegram surfaces share the same cleaned summary contract.
- [x] No LLM call, network call, paid source, or archive backfill is introduced.

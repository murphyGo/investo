# Code Generation Plan: `u15 coverage-confidence-badges`

**Date**: 2026-05-07
**Unit**: u15 coverage-confidence-badges
**Stage**: Code Generation

---

## Goal

Expose segment coverage and confidence so readers know whether a briefing is normal, partial, or insufficient.

---

## Definition of Done

- [x] Segment coverage status is computed from source/category results.
- [x] Briefings render coverage status and missing core categories near the top.
- [x] Partial/insufficient coverage constrains market-direction language.
- [x] Coverage status is available to Telegram summary generation.

---

## Steps

### Step 1 — Coverage Model

- [x] Define per-segment required categories and thresholds.
- [x] Compute source success, zero-result, failure, and category coverage.
- [x] Preserve existing source diagnostics log contracts.

### Step 2 — Rendering and Prompt Constraints

- [x] Render coverage status in segment markdown.
- [x] Feed coverage status into briefing prompt or deterministic fallback.
- [x] Render data-limited Telegram labels.

### Step 3 — Regression Tests

- [x] Test normal, partial, and insufficient segments.
- [x] Test source failure vs zero-result distinction.
- [x] Test archived markdown includes coverage status.

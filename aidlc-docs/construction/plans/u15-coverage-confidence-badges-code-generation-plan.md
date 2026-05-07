# Code Generation Plan: `u15 coverage-confidence-badges`

**Date**: 2026-05-07
**Unit**: u15 coverage-confidence-badges
**Stage**: Code Generation

---

## Goal

Expose segment coverage and confidence so readers know whether a briefing is normal, partial, or insufficient.

---

## Definition of Done

- [ ] Segment coverage status is computed from source/category results.
- [ ] Briefings render coverage status and missing core categories near the top.
- [ ] Partial/insufficient coverage constrains market-direction language.
- [ ] Coverage status is available to Telegram summary generation.

---

## Steps

### Step 1 — Coverage Model

- [ ] Define per-segment required categories and thresholds.
- [ ] Compute source success, zero-result, failure, and category coverage.
- [ ] Preserve existing source diagnostics log contracts.

### Step 2 — Rendering and Prompt Constraints

- [ ] Render coverage status in segment markdown.
- [ ] Feed coverage status into briefing prompt or deterministic fallback.
- [ ] Render data-limited Telegram labels.

### Step 3 — Regression Tests

- [ ] Test normal, partial, and insufficient segments.
- [ ] Test source failure vs zero-result distinction.
- [ ] Test archived markdown includes coverage status.

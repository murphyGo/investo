# Code Generation Plan: `u21 summary-quality-gate`

**Date**: 2026-05-07
**Unit**: u21 summary-quality-gate
**Stage**: Code Generation

---

## Goal

Prevent broken first-viewport segmented briefing summaries from being published.

---

## Definition of Done

- [x] Broken summary lines such as `주의할 점: 1.` are rejected before publish.
- [x] Truncated markdown/bold/link artifacts in first-viewport summary are rejected or cleaned.
- [x] Data-limited fallback summaries remain allowed when intentionally conservative.
- [x] Validation failure produces an operator-visible stage error without publishing broken markdown.

---

## Steps

### Step 1 — Summary Validator

- [x] Add a validation helper for the first-viewport `오늘의 결론`, `핵심 동인`, and `주의할 점` lines.
- [x] Reject list-marker-only, empty, markdown-broken, or truncated emphasis/link artifacts.
- [x] Keep conservative data-limited fallback copy valid.

### Step 2 — Publish Gate

- [x] Run the validator before segmented publish.
- [x] Roll back/skip publish when invalid summaries are detected.
- [x] Surface a clear stage error for operator diagnosis.

### Step 3 — Verification

- [x] Add briefing/orchestrator tests for broken and valid summaries.
- [x] Run targeted and full quality gates.

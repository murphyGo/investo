# Code Generation Plan: `u21 summary-quality-gate`

**Date**: 2026-05-07
**Unit**: u21 summary-quality-gate
**Stage**: Code Generation

---

## Goal

Prevent broken first-viewport segmented briefing summaries from being published.

---

## Definition of Done

- [ ] Broken summary lines such as `주의할 점: 1.` are rejected before publish.
- [ ] Truncated markdown/bold/link artifacts in first-viewport summary are rejected or cleaned.
- [ ] Data-limited fallback summaries remain allowed when intentionally conservative.
- [ ] Validation failure produces an operator-visible stage error without publishing broken markdown.

---

## Steps

### Step 1 — Summary Validator

- [ ] Add a validation helper for the first-viewport `오늘의 결론`, `핵심 동인`, and `주의할 점` lines.
- [ ] Reject list-marker-only, empty, markdown-broken, or truncated emphasis/link artifacts.
- [ ] Keep conservative data-limited fallback copy valid.

### Step 2 — Publish Gate

- [ ] Run the validator before segmented publish.
- [ ] Roll back/skip publish when invalid summaries are detected.
- [ ] Surface a clear stage error for operator diagnosis.

### Step 3 — Verification

- [ ] Add briefing/orchestrator tests for broken and valid summaries.
- [ ] Run targeted and full quality gates.


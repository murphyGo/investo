# Code Generation Plan: `u14 summary-quality-contract`

**Date**: 2026-05-07
**Unit**: u14 summary-quality-contract
**Stage**: Code Generation

---

## Goal

Make the reader-facing summary header deterministic, clean, and trustworthy.

---

## Definition of Done

- [ ] Header fields are generated through a validated summary contract rather than brittle markdown sentence extraction.
- [ ] Markdown syntax, links, and numbered-list markers cannot leak into `conclusion`, `driver`, or `caution`.
- [ ] Data-limited segments produce conservative header text.
- [ ] Telegram segmented summary can reuse the same stable summary fields.

---

## Steps

### Step 1 — Contract and Extraction

- [ ] Define the summary header contract and its fallback behavior.
- [ ] Replace or harden `_first_sentence` usage for header fields.
- [ ] Keep existing 7-section markdown parsing and disclaimer behavior unchanged.

### Step 2 — Tests

- [ ] Add regression tests for `주의할 점: 1.`-style list-marker leakage.
- [ ] Add regression tests for cut markdown emphasis/link syntax.
- [ ] Add data-limited summary tests.
- [ ] Add Telegram summary reuse tests if notifier output changes.

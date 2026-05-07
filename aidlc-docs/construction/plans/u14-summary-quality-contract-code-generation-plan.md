# Code Generation Plan: `u14 summary-quality-contract`

**Date**: 2026-05-07
**Unit**: u14 summary-quality-contract
**Stage**: Code Generation

---

## Goal

Make the reader-facing summary header deterministic, clean, and trustworthy.

---

## Definition of Done

- [x] Header fields are generated through a validated summary contract rather than brittle markdown sentence extraction.
- [x] Markdown syntax, links, and numbered-list markers cannot leak into `conclusion`, `driver`, or `caution`.
- [x] Data-limited segments produce conservative header text.
- [x] Telegram segmented summary can reuse the same stable summary fields.

---

## Steps

### Step 1 — Contract and Extraction

- [x] Define the summary header contract and its fallback behavior.
- [x] Replace or harden `_first_sentence` usage for header fields.
- [x] Keep existing 7-section markdown parsing and disclaimer behavior unchanged.

### Step 2 — Tests

- [x] Add regression tests for `주의할 점: 1.`-style list-marker leakage.
- [x] Add regression tests for cut markdown emphasis/link syntax.
- [x] Add data-limited summary tests.
- [x] Add Telegram summary reuse tests if notifier output changes.

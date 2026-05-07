# Code Generation Plan: `u20 archive-trust-and-latest-index`

**Date**: 2026-05-07
**Unit**: u20 archive-trust-and-latest-index
**Stage**: Code Generation

---

## Goal

Make the public site and archive index reliably point to the latest segmented briefings while separating legacy single-briefing pages from the primary discovery path.

---

## Definition of Done

- [x] Latest domestic/us/crypto links are generated or updated automatically.
- [x] Legacy single briefing archive entries are clearly labeled as legacy or moved out of the primary path.
- [x] Stale hard-coded latest dates are prevented by tests.
- [x] MkDocs strict build remains green.

---

## Steps

### Step 1 — Discovery Contract

- [x] Identify the canonical latest segmented archive source.
- [x] Define how Home and Archive pages should represent latest vs legacy content.
- [x] Add tests for latest-link rendering.

### Step 2 — Publish Integration

- [x] Update publish flow or a helper script to refresh latest index content.
- [x] Ensure generated site/index changes are staged with briefing archive commits.
- [x] Keep legacy links visible but clearly labeled.

### Step 3 — Verification

- [x] Run targeted site/publisher tests.
- [x] Run full quality gate and `mkdocs build --strict`.

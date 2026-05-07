# Code Generation Plan: `u20 archive-trust-and-latest-index`

**Date**: 2026-05-07
**Unit**: u20 archive-trust-and-latest-index
**Stage**: Code Generation

---

## Goal

Make the public site and archive index reliably point to the latest segmented briefings while separating legacy single-briefing pages from the primary discovery path.

---

## Definition of Done

- [ ] Latest domestic/us/crypto links are generated or updated automatically.
- [ ] Legacy single briefing archive entries are clearly labeled as legacy or moved out of the primary path.
- [ ] Stale hard-coded latest dates are prevented by tests.
- [ ] MkDocs strict build remains green.

---

## Steps

### Step 1 — Discovery Contract

- [ ] Identify the canonical latest segmented archive source.
- [ ] Define how Home and Archive pages should represent latest vs legacy content.
- [ ] Add tests for latest-link rendering.

### Step 2 — Publish Integration

- [ ] Update publish flow or a helper script to refresh latest index content.
- [ ] Ensure generated site/index changes are staged with briefing archive commits.
- [ ] Keep legacy links visible but clearly labeled.

### Step 3 — Verification

- [ ] Run targeted site/publisher tests.
- [ ] Run full quality gate and `mkdocs build --strict`.


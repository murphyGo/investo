# Code Generation Plan: `u22 source-coverage-transparency`

**Date**: 2026-05-07
**Unit**: u22 source-coverage-transparency
**Stage**: Code Generation

---

## Goal

Expose source-level collection status and coverage reasons so readers understand why each market segment is normal, partial, or insufficient.

---

## Definition of Done

- [ ] Segment coverage exposes reason codes such as missing price/news, source failed, and zero items.
- [ ] Reader-facing markdown explains why a segment is partial or insufficient.
- [ ] Data confidence visual card includes source names or reason categories.
- [ ] Sensitive source errors are redacted before public rendering.

---

## Steps

### Step 1 — Coverage Reasons

- [ ] Extend coverage diagnostics with reason codes.
- [ ] Preserve source-level success/zero/failure distinctions without leaking secrets.

### Step 2 — Reader Surfaces

- [ ] Render a concise source coverage table/callout in segmented markdown.
- [ ] Add reason/source names to the data-confidence visual card.

### Step 3 — Verification

- [ ] Add source, briefing, and visual tests.
- [ ] Run targeted and full quality gates.


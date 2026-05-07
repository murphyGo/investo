# Code Generation Plan: `u24 visual-provenance-and-layout`

**Date**: 2026-05-07
**Unit**: u24 visual-provenance-and-layout
**Stage**: Code Generation

---

## Goal

Preserve visual asset provenance and reduce first-viewport visual crowding in public archive pages.

---

## Definition of Done

- [x] External/AI images write provenance metadata without secrets.
- [x] Public markdown shows concise image provenance captions.
- [x] First viewport prefers one hero visual and moves secondary cards closer to relevant sections.
- [x] Corrupt or dimension-invalid images are rejected before publish.

---

## Steps

### Step 1 — Provenance Manifest

- [x] Define a visual manifest schema for AI, external, and generated SVG assets.
- [x] Write provenance files beside generated assets without secrets.

### Step 2 — Public Captions and Layout

- [x] Add concise captions for AI/external images.
- [x] Limit first-viewport images to a hero visual and reposition secondary cards.

### Step 3 — Verification

- [x] Add visual asset validation and layout tests.
- [x] Run targeted and full quality gates.

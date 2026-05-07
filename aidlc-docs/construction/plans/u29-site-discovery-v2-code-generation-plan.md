# Code Generation Plan: `u29 site-discovery-v2`

**Date**: 2026-05-08
**Unit**: u29 site-discovery-v2
**Stage**: Code Generation

---

## Goal

Reframe the public site so the first screen surfaces today's briefing content (not site-meta copy), and give weekend retrospect readers a time-axis traversal layer.

---

## Definition of Done

- [x] `docs/index.md` hero is auto-generated on every publish: three latest-segment conclusion quote cards (domestic / us / crypto). No hardcoded "최신 묶음 YYYY-MM-DD".
- [x] About content (current 7-section / sources / disclaimer meta copy) is moved to a separate About page; nav is updated.
- [x] `docs/archive/index.md` includes a calendar heatmap SVG keyed on publish date and segment coverage color.
- [x] Weekly retrospective auto-page (`archive/weekly/YYYY-WNN.md`) is published by the Saturday 09:00 KST cron with a 5-day conclusion list.
- [x] mkdocs nav has explicit segment entry points (`Archive › 미국 증시`, `Archive › 크립토`, `Archive › 국내 증시`).
- [x] Each publish writes an OG image meta (`<meta property="og:image">`) referencing the rendered hero SVG (or PNG twin).

---

## Steps

### Step 1 — Hero Auto-Refresh and About Split

- [x] Generate the three-card hero into `docs/index.md` from publisher.
- [x] Move About copy out and link from nav.

### Step 2 — Calendar Heatmap

- [x] Render a deterministic heatmap SVG into `docs/archive/index.md` from publish history + coverage status.

### Step 3 — Weekly Retrospective

- [x] Schedule the Saturday cron to also render `archive/weekly/YYYY-WNN.md`.
- [x] Aggregate 5-day conclusion lines per segment.

### Step 4 — Segment Nav and OG Image

- [x] Add segment-prefixed archive entry points to mkdocs nav.
- [x] Write OG image meta on each segmented publish.

### Step 5 — Verification

- [x] Run targeted publisher / mkdocs tests and the full quality gate (`mkdocs build --strict`).

---

## Source

Persona evaluation 2026-05-07: persona #2 (P0 + P1 + wish-list).

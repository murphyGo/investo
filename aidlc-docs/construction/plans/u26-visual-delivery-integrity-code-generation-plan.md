# Code Generation Plan: `u26 visual-delivery-integrity`

**Date**: 2026-05-08
**Unit**: u26 visual-delivery-integrity
**Stage**: Code Generation

---

## Goal

Diagnose and fix the post-u24 regression where archive pages no longer render embedded SVG cards, then standardize visual trust signals (font, version fallback, dark-mode legibility).

---

## Definition of Done

- [x] A test guarantees that on the segmented publish path `assets.insert_visual_links` runs and the produced markdown contains `![](...)` references for staged SVG assets.
- [x] Staged assets are verified to land beside the archive markdown after a dry-run publish (path layout regression pin).
- [x] 2026-05-06 segment archives (us / crypto / domestic) are backfilled with visual links (re-publish or curated patch).
- [x] Generated SVG cards declare `font-family` including `Noto Sans KR` with Arial fallback so Korean glyphs render on GitHub Pages.
- [x] `_investo_version()` fallback returns `"dev"` (or git short SHA when available) instead of `"0"`.
- [x] `DataConfidenceCard` and `WatchlistCard` provide a dark-mode-readable variant (CSS `prefers-color-scheme` rule or dark variant asset) so the cards are legible on the mkdocs dark theme.

---

## Steps

### Step 1 — Pipeline Regression Diagnosis and Test Pin

- [x] Reproduce missing-link regression with a publish dry-run against a synthesized segment.
- [x] Identify the call-path gap (segments pipeline vs. assets insertion) and add a regression test that fails on that gap.
- [x] Land the minimal fix that re-establishes asset insertion on the segmented publish path.

> **Diagnosis**: not a code regression. The 2026-05-06 segmented briefings
> (commits `605744a`, `879cddf`, `9215b97`, `e3cc413`) were all published
> *before* the visual-asset stage landed in the orchestrator (closing
> commit `e695bfb` arrived on 2026-05-08). Publishing them now would
> rebuild visual delivery, but to avoid disturbing already-public
> narrative content we curated a one-shot backfill instead (Step 2).
> The new regression pin
> (`test_run_pipeline_segmented_publish_inserts_visual_links_and_stages_svgs`)
> guarantees future segmented runs always emit `![](...)` references
> and stage SVGs beside the markdown.

### Step 2 — Backfill 2026-05-06

- [x] Generate a backfill plan for the three 2026-05-06 archive segments (republish or curated patch).
- [x] Validate the backfilled markdown renders the cards on the public site.

> **Approach**: curated patch via `scripts/backfill_2026_05_06_visuals.py`.
> The script repairs the truncated `> **주의할 점**: 1.` /
> `> **핵심 동인**: **입법 가속화 vs.` quote-block lines, renders the three
> SVG cards (data-confidence, market-snapshot, watchlist-relevance)
> with their JSON manifests, and inserts the markdown image links via
> the production `insert_visual_links`. 9 SVGs + 9 manifests landed,
> all pass `validate_visual_asset` and `briefing.leak_guard.scan`.

### Step 3 — Font, Version Fallback, Dark Mode

- [x] Add `Noto Sans KR` to the SVG card `font-family` stack.
- [x] Replace the `"0"` version fallback with `"dev"` / git short SHA.
- [x] Add dark-mode-readable styling (or a dark variant) to `DataConfidenceCard` and `WatchlistCard`.

> **Dark mode**: option (a) — embedded `<style>` block with
> `@media (prefers-color-scheme: dark)` rules driving classed
> `<rect>` / `<text>` elements. The same SVG asset adapts to either
> theme without a second variant file.
>
> **Version fallback**: `investo.__version__` → `git rev-parse
> --short=7 HEAD` (validated against a 7-hex-char regex) → `"dev"`.

### Step 4 — Verification

- [x] Run targeted visuals/publisher tests and the full quality gate.

---

## Source

Persona evaluation 2026-05-07: persona #2 (P0 + P1).

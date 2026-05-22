# Code Generation Plan: `u62 quality-status-publish-reconciliation`

**Date**: 2026-05-23
**Unit**: u62 quality-status-publish-reconciliation
**Stage**: Code Generation
**Status**: Complete (8/8)
**Source**: 2026-05-23 review of source-status, quality page, history, and archive-index mismatches
**Estimated Effort**: ~4-6 h
**Dependencies**:
- u15 coverage confidence badges
- u22 source coverage transparency
- u42 quality KPI history
- u54 source-status severity and quality KPI

---

## Problem Statement

The latest generated artifacts showed inconsistent quality/status surfaces:

- Segment markdown reported `본문 사용 0` while the body and trace showed source use.
- `site_docs/quality.md` showed `n/a / 0회` and zero failed/limited segments.
- `archive/_meta/quality_history.jsonl` showed failed sources and `worst_severity: limited`.
- `archive/index.md` labeled a date as `정상` or `부분` while segment artifacts had `제한`.

These contradictions make the status layer less trustworthy than the briefing itself.

---

## Goal

Make segment markdown, quality history, quality page, and archive index derive from one canonical publish snapshot for each run/date.

---

## Scope Boundary

In scope:
- Reconcile `body_used_count`, failed/zero/stale counts, and worst severity.
- Make same-date index and quality pages use worst-wins semantics.
- Add tests for limited/partial/normal status propagation.
- Fix quality chart clipping if the generated SVG viewBox excludes plotted labels.

Out of scope:
- Changing source adapter behavior.
- Reclassifying what counts as a core source beyond the existing u54 contract.
- Backfilling historical quality history unless a separate operator script is requested.

---

## Implementation Steps

### Step 1 - Pin artifact mismatch fixtures

- [x] Add fixture data representing `body_used_count=0` with traced/cited body evidence.
- [x] Add fixture data where quality history has `limited` but index attempts to render `normal` or `partial`.
- [x] Add fixture data where failed/zero sources exist but quality page aggregate counters render zero.

### Step 2 - Define canonical publish snapshot

- [x] Identify or introduce a single structured object that owns per-segment status, source outcomes, body-used count, and run-level worst severity.
- [x] Ensure segment markdown, quality history, quality page, and index receive the same snapshot rather than recomputing independently.
- [x] Keep the object pure and serializable for tests.

### Step 3 - Reconcile `body_used_count`

- [x] Compute body-used count from actual citation/source assignment data when available.
- [x] If body attribution is unavailable, render `미집계` or omit the count instead of rendering misleading `0`.
- [x] Add tests for both attributed and unattributed bodies.

### Step 4 - Apply worst-wins status propagation

- [x] Ensure date-level status is the worst segment status for that date.
- [x] Ensure same-day history updates cannot downgrade from `limited` to `partial` or `normal`.
- [x] Ensure archive index, quality page, and latest-bundle summary agree.

### Step 5 - Repair quality page counters

- [x] Make failed sources, zero-item sources, core-missing segments, and limited-or-worse segments use the canonical snapshot.
- [x] Render `n/a` only when denominator data is truly unavailable, not when failures exist.
- [x] Add regression tests for aggregate values.

### Step 6 - Check generated quality SVG bounds

- [x] Add a deterministic test for SVG viewBox dimensions covering labels and polylines.
- [x] Expand the viewBox or internal plotting bounds so labels are not clipped.

### Step 7 - Operator diagnostics

- [x] Log a bounded warning when any public status surfaces disagree before publish.
- [x] Include segment/date/status fields but no raw source payload or secret-shaped values.

### Step 8 - Documentation and gate

- [x] Update quality/status documentation for canonical snapshot semantics.
- [x] Run targeted publisher/quality-history/site-index tests.
- [x] Run `uv run mkdocs build --strict` because site pages are touched.

---

## Definition of Done

- [x] Segment markdown, quality history, quality page, and archive index agree for normal, partial, limited, and failed cases.
- [x] `본문 사용 0` is never rendered when body evidence is present or count is unknown.
- [x] Date-level archive status uses worst segment status.
- [x] Quality SVG content is fully inside its viewBox.
- [x] No source adapter, LLM, or notification behavior changes are included.

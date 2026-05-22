# Code Generation Plan: `u63 partial-bundle-navigation-and-absence-state`

**Date**: 2026-05-23
**Unit**: u63 partial-bundle-navigation-and-absence-state
**Stage**: Code Generation
**Status**: Complete (6/6)
**Source**: 2026-05-23 review of latest partial segmented bundle navigation
**Estimated Effort**: ~2-4 h
**Dependencies**:
- u7 segmented briefing
- u16 public site discovery
- u20 archive trust and latest index
- u31 operations resilience

---

## Problem Statement

The latest bundle navigation linked only the segments generated for the latest date and did not clearly explain that crypto was absent from the 2026-05-21 bundle while its latest available artifact was 2026-05-20.

For users, this looks like the crypto segment silently disappeared rather than a partial bundle state.

---

## Goal

Make partial segmented bundles explicit and navigable: every latest-bundle surface should show generated segments, missing segments, and the latest available fallback date for missing segments.

---

## Scope Boundary

In scope:
- Archive index latest-bundle block.
- Per-segment navigation.
- Site home/latest links if they consume the same bundle metadata.
- Tests for all-present and partial-bundle cases.

Out of scope:
- Changing generation retry policy.
- Forcing all-three-or-fail behavior.
- Backfilling missing segment markdown.

---

## Implementation Steps

### Step 1 - Pin partial bundle metadata

- [x] Add tests for a bundle date with domestic/us generated and crypto missing.
- [x] Add tests where crypto has a previous latest artifact.
- [x] Add tests where a missing segment has no fallback artifact.

### Step 2 - Define absence state model

- [x] Represent segment state as generated, missing-with-fallback, or missing-without-fallback.
- [x] Keep generated segment URLs and fallback URLs distinct.
- [x] Make status labels Korean and concise.

### Step 3 - Update archive index rendering

- [x] Render latest bundle generated segments.
- [x] Render missing segments with explicit absence text.
- [x] Link to fallback latest artifact when available.
- [x] Ensure date-level status matches u62 canonical worst status.

### Step 4 - Update per-segment nav

- [x] Show all expected segments in nav.
- [x] Disable or label missing same-date segments instead of omitting them.
- [x] Link fallback segments with a date label when available.

### Step 5 - Reuse metadata across site surfaces

- [x] Ensure home/latest pages do not invent a different latest-segment set.
- [x] Add tests so archive index and home page agree.

### Step 6 - Build verification

- [x] Run targeted publisher/site-index tests.
- [x] Run `uv run mkdocs build --strict`.

---

## Definition of Done

- [x] Latest bundle surfaces make missing segments explicit.
- [x] Missing segments link to the latest previous artifact when available.
- [x] Per-segment nav does not silently omit expected segments.
- [x] Normal all-three bundle output remains unchanged except for shared rendering internals.

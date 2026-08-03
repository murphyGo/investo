# U-141 Image Selection and Insertion — Code Summary

**Date**: 2026-08-03
**Status**: Code Generation complete; production replay not performed in this local construction slice

## Delivered contract

U-141 now selects images from the finalizable reader narrative, not the raw
news pool. `visuals/image_selection.py` builds a deterministic semantic
snapshot from the conclusion, key drivers, and `## ②`; feed candidates need
exact article-URL lineage, while curated `person:*` assets need an explicit
person name. Generic office/institution terms can only match topic assets.

## Implementation

- Added `ImageNarrativeContext`, `StoredHeroSelection`, and
  `ImageUsageSelection`, exact-URL ranking, current rights-file recheck,
  store binary/sidecar/content-hash validation, 600x338 hero gate, and a
  metadata-only article card renderer/placement function.
- Removed `FOMC`, `Fed Chair`, `연준 의장`, `President`, and `White House`
  from person portrait aliases. Jerome Powell and Donald Trump portraits now
  require explicit names in the primary narrative.
- Added local cleared-store copying into the existing
  `external-context-image` hero slot. Metadata-only images never emit
  `image_url`; the optional card carries title, credit/source, and
  `item_url` only.
- Extended visual provenance with the validated metadata keys
  `selection_contract`, `match_reason`, `matched_key`/`candidate_id`, and
  `narrative_sha256`.
- Moved the U-137 candidate stage before visual preparation. Selection,
  curated matching/copy, stored copy, and source-card insertion fail open to
  the existing visual chain on a per-segment basis.

## Data-backed decisions

The construction snapshot held 11 ledger dates, 804 rows, 748 unique
candidates, and 42 recurrent candidates (5.6%). Recurrence therefore does
not rank U-141 v1. Current US candidates are 130x86 Yahoo thumbnails and the
cleared store is empty, so production stored-hero use remains dark until an
operator clears and fetches a qualifying asset. Credit absence falls back to
the source name.

Applying the new curated contract to the eight US briefings from 2026-07-22
through 2026-07-31 selected zero Powell portraits. It selected Wall Street or
Federal Reserve topic assets only when the primary narrative contained that
topic, and selected no curated image on 2026-07-24.

## Verification

- New/updated semantic, rights, provenance, source-card, curated-identity,
  property, pipeline-order, and three-segment failure-isolation tests pass.
- Focused visual/orchestrator/public-document scope: 405 passed; the final
  escaping and reader-visible-text regression slice passed 84 tests.
- Final full suite after rebasing onto current `origin/main`: 4,158 passed in
  418.95 seconds. The obsolete pre-U-141
  expectation that a raw FOMC title produces a Powell portrait was replaced
  by the approved named-person contract before this clean rerun.
- Ruff and format clean; strict mypy passed for 249 source files;
  `check_no_paid_apis.py`, `check_image_store.py` (empty-store green),
  `check_curated_assets.py` (13 filed), strict MkDocs, and `git diff --check`
  passed.

## Scope boundaries

No new dependency, HTTP call, secret, rights transition, Telegram media
delivery, perceptual matching, embedding/model call, or past-archive rewrite
was added. U-142 remains the separate Telegram-photo unit.

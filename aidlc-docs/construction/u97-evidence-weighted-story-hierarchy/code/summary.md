# u97 evidence-weighted-story-hierarchy — Code Summary

Date: 2026-06-11
Status: Complete

## Scope

Add deterministic story hierarchy metadata before Stage 2 synthesis so core evidence survives prompt caps and lower-tier watchlist/context rows do not define the main thesis.

## Implementation

- Added `StoryTier`, `StoryMetadata`, `story_identity()`, and `assign_story_metadata()` in `briefing._core.section_planning`.
- Extended `SectionPlan` with `story_metadata` while keeping existing fields backward-compatible.
- Assigned fixed tiers and scores for required macro actuals, segment-native market state, approved cross-market core rows, supporting rows, context rows, and watchlist-only rows.
- Sorted grouped Stage 2 evidence by story score before per-section and total caps in both render and lineage cap helpers.
- Serialized compact prompt-only `[tier=... score=...]` metadata in grouped evidence bullets.
- Updated the Stage 2 system prompt to lead with `core` evidence and prevent `watchlist_only` evidence from defining the thesis when core evidence exists.

## Validation

- `uv run --extra dev pytest tests/unit/briefing/test_section_planning_story_hierarchy.py tests/unit/briefing/test_pipeline_unit.py tests/unit/briefing/test_prompts.py -k "section_plan or grouped_sections or story or stage2"`
- `uv run --extra dev ruff check src/investo/briefing/_core/section_planning.py src/investo/briefing/_assembly/markdown_render.py src/investo/briefing/_core/orchestration.py src/investo/briefing/prompts.py src/investo/briefing/pipeline.py tests/unit/briefing/test_section_planning_story_hierarchy.py`
- `uv run --extra dev mypy src/investo/briefing/_core/section_planning.py src/investo/briefing/_assembly/markdown_render.py src/investo/briefing/_core/orchestration.py src/investo/briefing/pipeline.py`

# Code Generation Plan: `u97 evidence-weighted-story-hierarchy`

Date: 2026-06-10
Last Updated: 2026-06-11
Status: Complete
Source: 2026-06-10 ten-subagent reader review and stage-specific design discussion of the 2026-06-09 generated bundle

## Problem Statement

The 2026-06-09 briefings contained many facts, but the story hierarchy was too flat. Low-signal items, isolated watchlist mentions, and contextual news could receive similar placement to core macro or market-wide evidence. The result was informational but less persuasive as a briefing narrative.

The system needs to tell Stage 2 which evidence carries the story and which evidence only supports or contextualizes it.

## Goal

Add deterministic story-tier metadata before Stage 2 synthesis so the model leads with core evidence, uses supporting evidence for explanation, keeps context in background, and avoids letting watchlist-only items define the market thesis.

## Existing Coverage / Deduplication

- u13 caps candidate count.
- u57 constrains narrative scope.
- u59 prioritizes macro actuals and lineage.
- u64/u73 handle watchlist matching and impact grouping.
- This unit adds hierarchy metadata; it does not change source collection or delete lower-tier evidence.

## Scope Boundary

In scope:
- Add `StoryMetadata` to `SectionPlan` as deterministic metadata keyed by a stable `story_identity(item)` helper.
- Tiers are `core`, `supporting`, `context`, and `watchlist_only`.
- Use existing macro priority and required-macro detection.
- Feed tier labels into prompt/evidence serialization.

Out of scope:
- Changing the six-section briefing structure.
- Rewriting source adapters.
- Removing watchlist evidence from the briefing.
- Replacing shared macro block or cross-market cause-map logic.

## Stage Decision

Functional Design: skip. This is a metadata refinement inside existing briefing generation.

NFR Requirements: skip. This adds deterministic ranking and prompt labels without external dependencies or new runtime services.

## Fixed Contracts

### Data Model

Add these symbols in `src/investo/briefing/_core/section_planning.py`:

```python
StoryTier = Literal["core", "supporting", "context", "watchlist_only"]

@dataclass(frozen=True, slots=True)
class StoryMetadata:
    tier: StoryTier
    score: int
    reasons: tuple[str, ...]
```

Extend `SectionPlan` with:

```python
story_metadata: dict[str, StoryMetadata] = field(default_factory=dict)
```

Use `story_identity(item: NormalizedItem) -> str` as the key. It must be deterministic and include `source_name`, `title`, `url or ""`, and `published_at.isoformat()`. Add a round-trip test proving metadata survives `build_section_plan()` through `_grouped_stage2_rendered_items()`.

### Tier Decision Table

Apply this precedence in order:

| Condition | Tier | Reason code |
|-----------|------|-------------|
| `is_required_macro_actual(item)` | `core` | `required_macro_actual` |
| Segment-native market anchor, primary price/flow snapshot, or segment-wide breadth indicator | `core` | `segment_native_market_state` |
| Cross-segment background already approved by u57 shared macro or u74 `cross_market_core_allowed` | `core` | `approved_cross_market_core` |
| Sector, company, asset, policy, or flow item that explains a core item | `supporting` | `supports_core` |
| Background news or calendar item without direct segment-wide implication | `context` | `background_context` |
| Existing u64/u73 watchlist match or impact output without broader market signal | `watchlist_only` | `watchlist_only` |

Cross-segment background that is not u57/u74-approved must be `context`, never `core`.

### Score Formula

Compute `story_score` as:

```text
tier_base + required_macro_bonus + approved_cross_market_bonus + recency_bonus + stable_source_bonus
```

Values:
- tier base: `core=300`, `supporting=200`, `context=100`, `watchlist_only=50`
- required macro bonus: `+80` when `is_required_macro_actual(item)` is true
- approved cross-market bonus: `+40` when reason includes `approved_cross_market_core`
- recency bonus: `+20` for target-date items, `+10` for previous calendar day, `+0` otherwise
- stable source bonus: `+10` for `category in {"macro", "market", "price"}` or existing source-tier metadata that marks the item as primary; `+0` when unavailable

Tie-break order is `score desc`, `published_at desc`, `source_name asc`, `title asc`, `story_identity asc`.

### Cap Ownership

u97 owns ordering before every cap that can drop Stage 2 evidence:
- section buckets in `build_section_plan()`
- `_grouped_stage2_rendered_items()` in `src/investo/briefing/_assembly/markdown_render.py`

Do not change u13 total candidate count. u97 only reorders within the already selected candidate set and section buckets.

### Output Contract

Tier labels are prompt-only metadata. Published markdown must not contain raw strings `story_tier`, `story_score`, `watchlist_only`, `supporting`, or `context` as mechanical labels.

The §①/first §② requirement is a prompt-input ordering contract, not a post-render rewrite. The implementation must not reorder rendered markdown in publisher or reader-format paths.

## Implementation Steps

1. Inspect current section-planning data structures in `src/investo/briefing/_core/section_planning.py`.
   - Add `StoryMetadata`, `StoryTier`, `story_identity()`, and `assign_story_metadata()`.
   - Extend `SectionPlan` with `story_metadata`.
   - Preserve the existing `items_by_section`, `unassigned`, and `required_macro_items` fields.

2. Add deterministic tier assignment.
   - `core`: required macro actuals, segment-native market anchors, u57/u74-approved cross-market drivers, and segment-primary price/flow evidence.
   - `supporting`: sector/company/asset evidence that explains or confirms the core move.
   - `context`: background policy/news items that frame the day but do not establish the main direction.
   - `watchlist_only`: evidence whose primary relevance is a matched watchlist item without broader market signal.
   - Compute `story_score` from the fixed score formula above.

3. Preserve core rows through caps.
   - When a section cap forces competition, sort by tier and score before lower-tier items.
   - Keep stable ordering within equal tier/score groups to avoid noisy diffs.
   - Confirm u13 total candidate cap remains unchanged.

4. Expose tier labels to Stage 2.
   - Update `src/investo/briefing/_assembly/markdown_render.py` to include compact tier metadata in evidence bullets or prompt-only serialized rows.
   - Update `src/investo/briefing/prompts.py` so Stage 2 leads with `core`, supports with `supporting`, and uses `context` only after the main line is established.
   - Add one bounded instruction that preserves existing u57/u59/u64/u74 prompt contracts.
   - Add an explicit instruction that `watchlist_only` evidence must not be used as the main thesis source when `core` evidence exists.

5. Add tests in `tests/unit/briefing/`.
   - Tier assignment for macro actuals, market anchor rows, sector/company rows, context-only news, and watchlist-only rows.
   - Cap-preservation fixture where a core row survives over lower-tier rows.
   - Prompt serialization fixture that includes tier labels.
   - Regression fixture for required macro actual behavior.
   - Replay fixture based on the 2026-06-09 defect shape where §① uses the `core` evidence line first and lower-tier evidence appears only as support/context.
   - Published-markdown fixture proving mechanical tier labels do not leak.

## Acceptance Criteria

- Each planned candidate has deterministic tier and score metadata.
- `core` evidence wins section-cap competition over lower-tier evidence.
- The serialized Stage 2 input presents `core` evidence ahead of `watchlist_only` or pure `context` evidence when core evidence is available.
- Required macro actuals keep u59 priority and lineage behavior.
- Lower-tier evidence remains available in `_grouped_stage2_rendered_items()` and existing watchpoint/watchlist surfaces.
- The implementation is deterministic across repeated runs with the same inputs.
- Published markdown does not expose mechanical tier labels.

## Tests / Validation

```bash
uv run --extra dev pytest tests/unit/briefing -k "section_plan or story or macro or prompt"
uv run --extra dev pytest tests/unit/briefing/test_section_planning_story_hierarchy.py tests/unit/briefing/test_markdown_render_story_hierarchy.py tests/unit/briefing/test_prompts.py
uv run --extra dev ruff check src/investo/briefing tests/unit/briefing
uv run --extra dev mypy src
```

## Non-Goals

- No new LLM call.
- No section-count change.
- No adapter changes.
- No watchlist matcher changes.
- No post-render text reordering.

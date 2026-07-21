# U144 Current Public-Markdown Mutation Graph Baseline

**Date**: 2026-07-21
**Scope**: Default segmented production path before u144 implementation
**Purpose**: Freeze the pre-u144 `Briefing.rendered_markdown` construction,
post-generation mutation order, terminal consumers, and known ownership gaps.

## Method

The inventory was derived from the production call graph rooted at
`GenerateStage.execute()` and `PublishStage.execute()`, then checked against
every direct `Briefing.model_copy(update={"rendered_markdown": ...})` site under
`src/investo/`. The example in the `publisher/charts.py` module docstring is not
an executable mutation site. Read-only consumers and validators are listed only
where they establish the ordering boundary around a mutation.

## Construction Boundary

`briefing.pipeline.generate_briefing_from_input()` constructs the first
`Briefing` value in this order:

1. synthesize or deterministically build the six-section body;
2. `_enhance_reader_experience()`;
3. `_append_traceability_footer()` on the LLM path;
4. `append_disclaimer()`;
5. `_finalize_briefing()` post-validation and `Briefing(...)` construction.

This is generated content, not a post-generation mutation. The legacy
non-segmented path publishes this value directly. The default segmented path
continues through the mutations below.

## Default Segmented Call Order

| Order | Production owner and call | Markdown effect | Direct replacement site | Gate/I/O relationship |
|---|---|---|---|---|
| 1 | `GenerateStage.execute()` -> `_stage_prepare_segment_visual_assets()` -> `visuals.assets.prepare_segment_visual_assets()` -> `insert_visual_links()` | Inserts hero and section-scoped visual Markdown. | `visuals/assets.py:205` | Asset files and manifests are written before later reader gates. |
| 2 | `GenerateStage.execute()` -> `_inject_carryover_into_segments()` -> `publisher.carryover.inject_carryover_block()` | Inserts, replaces, or removes the `## Watchlist Carryover` block. | `orchestrator/pipeline.py:1767` | Pure text transform after visual preparation. |
| 3 | `GenerateStage.execute()` -> `_inject_chart_blocks_into_segments()` -> `publisher.charts.inject_chart_block()` | Inserts the chart placeholder block under section ⑤. | `orchestrator/pipeline.py:1639` | Chart sidecars are written before later reader gates. |
| 4 | `GenerateStage.execute()` survivor loop -> `publisher.segment_reader_format.apply_reader_format_to_segments()` | Runs the ordered assembly, premature public projection, repair, and surface-gate chain detailed below. | `publisher/segment_reader_format.py:303` | A `SurfaceQualityError` drops one segment and restarts the survivor loop with a recomputed daily-thesis decision. |
| 5 | `GenerateStage.execute()` -> `_filter_entity_fact_violations()` | No byte mutation; scans and drops entity-fact-invalid segments. | none | First entity-fact drop path, after the reader-format gate. |
| 6 | `PublishStage.execute()` -> `_stage_publish_segments()` entity scan | No byte mutation; scans and drops entity-fact-invalid segments again. | none | Second entity-fact drop path. |
| 7 | `_stage_publish_segments()` -> `_rewrite_segment_nav_for_published_segments()` | Rewrites the segment-navigation line to mark absent siblings. | `orchestrator/pipeline.py:1991` | Occurs after the reader-format surface gate and entity scans. |
| 8 | `_stage_publish_segments()` -> `emit_first_viewport_disclaimer()` defensive pass | Inserts or moves the segment-aware short disclaimer. | `orchestrator/pipeline.py:1233-1239` | Occurs after the apparent terminal surface gate. |
| 9 | `_stage_publish_segments()` -> `ensure_canonical_disclaimer()` | Repairs the canonical footer when its anchor exists but its bytes are non-canonical. | `orchestrator/pipeline.py:1257-1259` | Occurs after the apparent terminal surface gate. |
| 10 | `_stage_publish_segments()` -> `repair_first_viewport_summary()` | Repairs/replaces malformed first-viewport summary material. | `orchestrator/pipeline.py:1266-1268` | Occurs after the apparent terminal surface gate. |
| 11 | `_stage_publish_segments()` -> `render_body_used_count()` | Rewrites the reader-visible body-evidence count. | `orchestrator/pipeline.py:1285-1287` | Last current text producer before the publish-boundary validator registry. |
| 12 | `_stage_publish_segments()` -> `build_publish_boundary_registry(...).run()` | Read-only summary/canonical-disclaimer/short-disclaimer gates. | none | Last orchestrator registry before write, but it does not cover every u108/u112 issue class. |
| 13 | `_stage_publish_segments()` -> `write_briefing()` | Re-verifies the canonical disclaimer, then writes the publish-local `Briefing.rendered_markdown` atomically. | none | First archive write. Index, OG, quality, forecast, weekly, and watchlist consumers use the publish-local late-mutated mapping before git staging/push. |
| 14 | `NotifyStage.execute()` -> `_stage_notify_segmented_briefing()` | No byte mutation; builds notification input from `accumulated["segment_briefings"]`. | none | The publish-local mapping is not returned, so notifier reads the earlier GenerateStage mapping without orders 7-11 rather than the exact archive-byte object. |

## Order Inside `apply_reader_format_to_segments()`

For each active segment, the current reader-format collaborator applies this
exact sequence before returning one replacement `Briefing`:

1. render and insert/replace the market-anchor table;
2. `enforce_anchor_assertions()` deterministic numeric-claim rewrite/block;
3. `apply_reader_format()`:
   1. `ensure_tldr_block()`;
   2. `enforce_h3_subheadings()`;
   3. `wrap_numbers_bold()`;
   4. `dedupe_glossings()`;
   5. `normalize_meaning_lines()`;
   6. `escape_krx_stock_code_link_fragments()`;
   7. `normalize_data_limited_reader_copy()` — the current premature u108
      public-language projection;
   8. read-only action-ratio and watchpoint-actionability checks;
4. `inject_shared_macro_block()` when bundle context exists, followed by
   read-only cross-segment lint;
5. `inject_crypto_indicator_block()` for crypto when indicator items exist;
6. `inject_channel_anchor_block()`;
7. `inject_cause_map_line()` when bundle context exists;
8. `inject_daily_thesis_line()` when bundle context exists;
9. `repair_compliance_language()`;
10. read-only `scan_compliance()`;
11. `render_watchpoint_matrix()` — currently able to reintroduce raw limitation
    labels after step 3.7 projected them;
12. read-only `scan_compliance()`;
13. `emit_first_viewport_disclaimer()`;
14. `reflow_first_viewport()`;
15. read-only pre-repair `find_surface_quality_issues()`;
16. `repair_surface_artifacts()`;
17. read-only post-repair `find_surface_quality_issues()` and blocking
    `SurfaceQualityError` decision;
18. final read-only compliance, sentence-ending, and filler-density checks;
19. one `Briefing.model_copy(update={"rendered_markdown": markdown})`.

## Direct Post-Generation Replacement Sites

The current executable tree contains nine direct post-generation
`rendered_markdown` replacement sites:

1. `src/investo/visuals/assets.py:205` — visual insertion;
2. `src/investo/orchestrator/pipeline.py:1767` — carryover injection;
3. `src/investo/orchestrator/pipeline.py:1639` — chart injection;
4. `src/investo/publisher/segment_reader_format.py:303` — combined reader chain;
5. `src/investo/orchestrator/pipeline.py:1991` — partial-bundle navigation;
6. `src/investo/orchestrator/pipeline.py:1233-1239` — short disclaimer;
7. `src/investo/orchestrator/pipeline.py:1257-1259` — canonical disclaimer;
8. `src/investo/orchestrator/pipeline.py:1266-1268` — summary repair;
9. `src/investo/orchestrator/pipeline.py:1285-1287` — body-used count.

`src/investo/briefing/pipeline.py:330` is the original `Briefing` construction,
not a post-generation replacement. `src/investo/publisher/charts.py:41` is a
docstring example, not executable production code.

## Frozen Defects and U144 Migration Targets

- Public-language projection currently runs before shared macro, indicators,
  channel anchors, cause map, thesis, watchpoint rendering, nav, disclaimer,
  summary, and evidence-count producers have finished.
- The surface gate in `segment_reader_format.py` is not terminal: five direct
  Markdown replacement sites still run afterward in `_stage_publish_segments()`.
- Entity-fact filtering is duplicated before and inside publish.
- Visual and chart files reach public-destination paths before the segment has
  passed its later text gates.
- The survivor decision is split across the reader-format retry loop, entity
  filters, and publish-stage navigation rewrite rather than one typed bundle
  finalization result.
- Archive/index/quality/notification consumers accept mutable `Briefing` values;
  there is no sealed digest-verified public-document type.
- Publish-local late mutations are not written back to pipeline accumulation;
  the notifier therefore derives its summary from an earlier Markdown version
  than the archive/index/quality consumers.

This file is the Step 0 baseline. Later u144 steps must update architecture tests
against this list rather than silently adding a tenth direct mutation site.

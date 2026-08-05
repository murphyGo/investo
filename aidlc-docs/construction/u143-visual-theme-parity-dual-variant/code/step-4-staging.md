# u143 Step 4 — Companion staging and file accounting

## Outcome

- Added each dark companion as a first-class staged `visual` artifact.
- Bound primary SVG, dark SVG, and the single primary manifest to the same
  `VisualMarkdownBlock.artifact_ids` set so u144 E1→E5→E6 lifecycle and
  promotion cannot omit one theme.
- Confirmed the normal three-segment pipeline stages exactly 27 visual files:
  three cards × three files × three segments.
- Updated pipeline regressions to assert paired Markdown, dark-file promotion,
  no dark sidecar, and dark companion presence in git add.

## Current-main ownership correction

The July plan referenced an older direct `pipeline.py` path loop. Current main
uses u144 staged artifact descriptors: `prepare_segment_visual_assets` creates
them, `_stage_prepare_visual_assets` forwards them, and terminal promotion/git
consumes the descriptors. The implementation therefore joins companions at the
descriptor owner rather than reintroducing a second orchestrator path loop.
This preserves the approved behavior while respecting the current lifecycle.

Non-paired PNG/JPEG assets still produce two descriptors (binary + manifest).
Paired card blocks produce three (light + dark + primary manifest).

## Validation

- Asset + exact orchestrator/integration path: 23 passed.
- Full run-pipeline unit + integration files: 121 passed.
- Ruff/format and scoped source mypy: passed.
- `git diff --check`: passed.
- Fresh-eyes review: approved with no findings across u144 lifecycle,
  non-paired image compatibility, data integrity, and resource lifecycle.

## Next boundary

Step 5 will replace OS-media dark styling on inline heatmap and quality
sparkline surfaces with Material body-ancestor selectors, without adding files.

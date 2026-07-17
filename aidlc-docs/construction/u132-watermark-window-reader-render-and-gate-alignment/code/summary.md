# u132 Watermark Window Reader Render and Gate Alignment

## Status

Code Generation is in progress. Step 1 of 7 is complete.

## Step 1 Trace Finding

The legacy half-open watermark line survives `apply_reader_format()`,
`reflow_first_viewport()`, and `repair_first_viewport_summary()` byte-for-byte.
A spy on the production segment chain captures the legacy line immediately
before `repair_surface_artifacts()` and the stripped line immediately after it.
In the first viewport,
`_repair_unmatched_markdown_markers()` sees the single `[` as an unmatched
Markdown marker and removes it, leaving the dangling `)`.

`_internal.summary_quality` is not the writer: its repair loop only visits the
three summary-prefix values and never processes the watermark line.

The regression test
`test_legacy_watermark_bracket_is_removed_by_surface_artifact_repair_u132`
pins the intermediate transforms, the production repair call's input/output,
and the complete `apply_reader_format_to_segments()` result. The bracket
repair remains unchanged because it is valid for genuinely broken Markdown;
Step 2 will replace the renderer's inherently unbalanced notation.

## Validation

- `uv run --extra dev pytest tests/unit/publisher/test_segment_reader_surface_quality.py -q`: 7 passed.
- `uv run ruff check tests/unit/publisher/test_segment_reader_surface_quality.py`: passed.
- `uv run ruff format --check tests/unit/publisher/test_segment_reader_surface_quality.py`: passed.
- Fresh-eyes review: no remaining findings after the production-call spy was added.

## Step 2 Renderer Change

`_render_timestamp_watermark()` now emits the fixed reader-facing contract:

`**기준 시각**: {date} {timezone} · 수집창 {start} ~ {end} (종료 미포함)`

The UTC window computation and KST/NY/UTC market-clock mapping are unchanged.
The three segment renderer tests and the enhanced-header assertion pin the
complete new line. Gate alignment remains Step 3, so this Step 2 worktree state
is not a standalone production checkpoint.

Step 2 validation:

- Focused briefing and segment-reader tests: 47 passed.
- Scoped Ruff and format checks: passed.
- Fresh-eyes review: no findings; confirmed no Step 3 gate changes leaked in.

## Step 3 Gate Alignment

`_WATERMARK_LINE_RE` now accepts only the pinned KST/NY/UTC reader shape.
`_bad_watermark_window()` keeps non-watermark lines out of scope, then blocks
unbalanced parentheses, the legacy `Z, Z)` tail, and every other watermark
shape that does not fully match the new contract. The existing
`watermark.window_bracket` issue code remains the single enforcement surface.
The Step 1 production-call spy now also confirms that a repaired legacy line is
blocked after repair instead of surviving to the returned briefing.
Direct gate acceptance tests cover all three timezone labels.

Step 3 validation:

- Focused surface, renderer, and segment-chain tests: 68 passed.
- Scoped Ruff and format checks: passed.
- Fresh-eyes review: no findings; the NY-only residual test risk was closed by
  adding direct KST and UTC gate-acceptance cases.

## Step 4 Full-Chain Stability

An integration fixture now builds a complete six-section US-equity body and
passes it through the actual `_enhance_reader_experience()` producer. The test
extracts the producer watermark, pins the exact contract, and compares that
same line after `repair_first_viewport_summary()`,
`repair_surface_artifacts()`, and `_apply_reader_format_to_segments()`.

The full chain returns exactly one byte-identical watermark and preserves the
`Briefing.target_date` and disclaimer field. The shared integration fixture was
updated from its obsolete abbreviated watermark so the complete file remains
green under the fail-closed Step 3 gate.

Step 4 validation:

- Full reader-format integration plus focused surface tests: 35 passed.
- Scoped Ruff and format checks: passed.
- Fresh-eyes review: no remaining findings after strengthening the producer-to-chain comparison.

## Step 5 Publish-Gate Regressions

Full segment-gate tests now pin all three required paths with a
`Briefing.target_date` matching the watermark date:

- The fixed `수집창 ... ~ ... (종료 미포함)` line passes and appears once.
- The verbatim published 2026-06-30 `Z, Z)` legacy line blocks.
- A new-contract line missing its closing parenthesis blocks.

Both invalid cases raise `SurfaceQualityError` with exactly one
`watermark.window_bracket` issue whose evidence is the malformed line.

Step 5 validation:

- Full reader-format integration plus focused gate tests: 38 passed.
- Scoped Ruff and format checks: passed.
- Fresh-eyes re-review: no remaining findings after aligning fixture dates.

## Step 6 Consumer Sweep

The repository-wide `기준 시각` sweep found no parser coupled to the old
window syntax. `_internal/briefing_extract.py` extracts the canonical prefix
value without parsing its contents, so no application-code change was needed.

Seven general test consumers now use the reader-facing contract. Archive
fixtures whose date or segment varies call `_render_timestamp_watermark()`
instead of carrying a fixed NY/KST example, keeping the timezone and UTC
window consistent with the file being modeled. The only remaining old shapes
are explicit repair-path and publish-gate rejection fixtures.

Step 6 validation:

- Consumer, parser, orchestrator, model, publisher, surface, and integration tests: 200 passed.
- Scoped Ruff and format checks plus `git diff --check`: passed.
- Fresh-eyes review: date/segment fixture mismatches were fixed; final re-review found no issues.
- No u132 archive or generated-site file is part of the Step 6 keep-set.

## Step 7 Quality Gate

The cumulative u132 Python diff passes scoped Ruff and format checks, and
`mypy src` reports no issues across 226 source files. The planned internal,
briefing, and publisher pytest scope completed with 1,440 passes and the two
known DEBT-081 failures.

Both failures reproduce unchanged at the pre-u132 baseline commit `0af9c7a`,
and no u132 commit touches either failing test or its implicated application
code. Re-running the same scope with those two baseline failures deselected
produced 1,440 passes.

The final cumulative fresh-eyes review found no issues in the 13 changed
Python files and confirmed AC-132.1 through AC-132.5. The committed unit diff
contains no `archive/` or generated-site changes.

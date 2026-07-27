# u130 Code Generation Step 4 — Production Metadata Wiring

## Scope Delivered

- Loaded previous domestic anchor closes once in each segmented `GenerateStage` run.
- Passed the same mapping to domestic anchor assembly.
- Preserved the mapping in accumulated stage data for publish and notification consumers.
- Applied the mapping to quality-history withheld metadata.
- Applied the mapping to notification-side trusted domestic price filtering.

## Runtime Contract

The archive lookup runs after price fallback reconciliation and before domestic anchor assembly. Its returned mapping is not copied or reloaded:

1. `_build_kr_anchors_from_items` uses it to suppress discontinuous reader-facing anchors.
2. `PublishStage` passes it through `_stage_publish_segments` to `_build_quality_snapshot`.
3. `NotifyStage` passes it to `trusted_domestic_price_items`.

This keeps anchor tables, quality diagnostics, and notifications on one continuity decision for the run.

Legacy/unsegmented generation does not call the archive loader. Empty or absent accumulated mappings use the existing fail-open behavior.

## Quality Metadata

`_build_quality_snapshot` now supplies the mapping to `domestic_anchor_verdicts`. Every non-trusted verdict continues to increment `domestic_anchor_withheld_count`, and `discontinuous` is appended to the existing deterministic reason order:

1. `unavailable`
2. `stale`
3. `implausible`
4. `provenance_missing`
5. `discontinuous`

## Tests

- Anchor assembly excludes a discontinuous KOSDAQ candidate while retaining a continuous KOSPI candidate.
- Quality snapshot records one withheld anchor with reason `discontinuous`.
- A segmented pipeline regression proves:
  - the archive loader is called exactly once;
  - the expected archive root and target date are used;
  - the exact same mapping object reaches anchor assembly, publish, and notification consumers.

## Review

Fresh-eyes review approved Step 4 with no Critical, High, Medium, or Low findings. It independently confirmed the one-scan contract, same-object propagation, deterministic metadata ordering, partial-segment safety, and unsegmented compatibility.

## Validation

- Focused Step 4 and domestic-anchor tests: 31 passed.
- `uv run pytest -q tests/unit/orchestrator`: 433 passed.
- Scoped Ruff and format checks: passed.
- `uv run mypy src`: passed for 248 source files.
- `git diff --check`: passed.

## TECH-DEBT

None added.

## Next Step

Step 5 adds the rendered 2026-06-30 regression fixture and proves no precise KOSPI level survives the reader-format and assertion-gate chain.

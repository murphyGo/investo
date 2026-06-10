# Code Generation Plan: `u96 quality-current-run-snapshot-sync`

Date: 2026-06-10
Last Updated: 2026-06-11
Status: Complete
Source: 2026-06-10 ten-subagent reader review and stage-specific design discussion of the 2026-06-09 generated bundle

## Problem Statement

The 2026-06-09 generated bundle exposed a public-status contradiction. Segment markdown showed `[데이터부족]`, `데이터 상태: 제한`, and core price source failures, while `site_docs/quality.md` still reported a healthier state such as `데이터 부족 폴백 0.0%` and `제한/실패 세그먼트 0`.

This is a reader trust problem. The dashboard is the public source of quality truth, so it must not imply normal data health when the published segment body says the opposite.

## Goal

Extend the existing u62/u69 canonical quality snapshot so `quality.md`, `quality_history.jsonl`, segment/index labels, and the u69 consistency gate agree for the current publish. Existing quality concepts stay intact; this unit adds the missing current-run fields and comparison rules.

## Existing Coverage / Deduplication

- u54, u62, and u65 already define quality metrics and replay checks.
- u69 already blocks cross-surface quality contradictions.
- This unit extends the existing u62/u69 snapshot and gate with current-run fields and marker detection.
- Do not change `CoverageStatus`, severity enums, source adapter behavior, core-source membership, or `HealthTrackingStage` ordering.

## Scope Boundary

In scope:
- Recognize segment-level `[데이터부족]`, `데이터 상태: 제한`, and core-missing markers.
- Persist and render current-run fields through the existing snapshot/KPI path.
- Block a publish when dashboard metrics are healthier than segment markdown for the same target date.

Out of scope:
- Adding new source adapters.
- Reclassifying sources as core or non-core.
- Redesigning the quality dashboard layout beyond the new metrics.
- Backfilling old archive files.

## Stage Decision

Functional Design: skip. This is a refinement of existing quality/publication surfaces and does not introduce a new product entity.

NFR Requirements: skip. The unit enforces existing data-integrity and graceful-degradation expectations without new dependencies, secrets, or runtime services.

## Fixed Contracts

### Current-Run Snapshot Fields

Extend `CanonicalQualitySnapshot` in `src/investo/publisher/quality_consistency.py` and the rendered `QualityKPIs` reconciliation path with these exact fields:

| Field | Type | Source | Legacy default | Rendered meaning |
|-------|------|--------|----------------|------------------|
| `current_run_zero_item_sources` | `int` | current `coverage.jsonl` outcomes with `status == "zero"` | `0` | dashboard `0건 반환 소스 누적` floor for the target date |
| `current_run_core_missing_segments` | `int` | current `coverage.jsonl.severities` values in `{"limited", "failed"}` | `0` | dashboard `핵심 소스 결손 세그먼트` floor |
| `current_run_segments_limited_or_worse` | `int` | final segment markdown status blocks with labels `제한` or `실패`, reconciled with current severities | `0` | dashboard `제한/실패 세그먼트` floor |
| `current_run_data_limited_briefings` | `int` | final segment markdown containing `[데이터부족]`, `데이터 부족 안내`, or `실시간 안내` | `0` | numerator for `데이터 부족 폴백` |
| `current_run_briefings_observed` | `int` | successful final segment markdown artifacts for the target date | `0` | denominator for `데이터 부족 폴백` |

For a 2026-06-09-shaped fixture with 12 observed briefings and 3 data-limited briefings, `render_quality_page()` must show `데이터 부족 폴백 25.0% | 12 건`.

### Marker Rules

Allowed positive markers:
- Data-limited body markers: literal `[데이터부족]`, `데이터 부족 안내`, `실시간 안내`.
- Limited-or-failed status markers: status block values parsed by `parse_segment_status_block()`, specifically `**데이터 상태**: 제한` and `**데이터 상태**: 실패`.
- Core-missing signal: current `coverage.jsonl.severities` for a segment is `limited` or `failed`. Text-only fallback is allowed only when the final segment status block says `제한` or `실패`; do not match broad words such as `core`, `failure`, `결손`, or `누락` outside the status block.

Negative examples:
- A normal segment body that discusses "데이터가 제한적일 수 있다" outside the status block does not increment `current_run_segments_limited_or_worse`.
- A glossary or diagnostics paragraph containing "실패 가능성" does not increment failed evidence.
- Collapsed diagnostics copied from a previous run do not override current `coverage.jsonl.severities`.

### Publish-Time Order

Implementation must preserve this order:

1. Final segment markdown is produced after reader-format, watchpoint, thesis, surface-quality, compliance, disclaimer, and public consistency transformations for the segment.
2. Build the current-run quality snapshot from the final segment markdown, current `coverage.jsonl`, and current `quality_history.jsonl` row.
3. Render `site_docs/quality.md`, append or reconcile `archive/_meta/quality_history.jsonl`, and update latest/archive index labels from the same snapshot.
4. Run the u69 consistency comparison against the rendered artifacts.
5. Only then allow archive/index/site writes to be committed or published.

### Gate Comparison Rules

For the target date, the dashboard/history/index values must be at least as severe as final segment evidence:

- `dashboard.data_limited_briefings >= snapshot.current_run_data_limited_briefings`
- `dashboard.briefings_observed >= snapshot.current_run_briefings_observed`
- `dashboard.zero_item_sources >= snapshot.current_run_zero_item_sources`
- `dashboard.core_missing_segments >= snapshot.current_run_core_missing_segments`
- `dashboard.segments_limited_or_worse >= snapshot.current_run_segments_limited_or_worse`

Old history rows missing these fields load with `0` defaults, but the publish-boundary gate applies only to the current target date.

## Implementation Steps

1. Extend marker detection in `src/investo/briefing/quality_eval.py`.
   - Treat `[데이터부족]` as a data-limited fallback marker.
   - Treat `데이터 부족 안내` and `실시간 안내` as data-limited fallback markers.
   - Treat status block labels `제한` and `실패` as limited-or-worse.
   - Keep core-missing detection derived from `coverage.jsonl.severities`; status-block fallback only.
   - Keep existing quality-eval public functions backward-compatible.

2. Extend the quality snapshot model in `src/investo/briefing/quality_history.py`.
   - Add optional fields matching the current-run snapshot field table.
   - Load older JSONL rows with defaults so historical pages keep rendering.
   - Preserve deterministic serialization order for snapshot tests.

3. Build the current-run snapshot at publish time in `src/investo/orchestrator/pipeline.py`.
   - Use current segment markdown strings, current coverage outcomes, and current source outcomes.
   - Count zero-item sources from the current run, not from a stale history aggregate.
   - Pass the same snapshot to dashboard rendering and consistency checks.

4. Strengthen `src/investo/publisher/quality_consistency.py`.
   - Compare dashboard fields with segment markdown markers for the same target date.
   - Raise the existing quality consistency error when the dashboard understates limited/fallback/core-missing state.
   - Keep old-history compatibility by gating only current-run artifacts.

5. Render the new fields in `src/investo/publisher/site_index/quality_dashboard.py`.
   - Show data-limited fallback count and percentage from the current snapshot.
   - Show core-missing segment count.
   - Show limited-or-failed segment count.
   - Show zero-item source count.

6. Update index label ownership.
   - Use `src/investo/publisher/site_index/__init__.py::update_latest_index_pages` as the index entry point.
   - Add one fixture where latest/archive index labels show degraded status when the same snapshot shows limited-or-worse segments.
   - Do not add notifier behavior; FR-007 is covered because operator-facing public status becomes truthful.

7. Add focused tests.
   - Unit tests for marker detection in `tests/unit/briefing/`.
   - Snapshot load/render tests for older and current rows.
   - Publisher consistency tests where segment markdown is limited but dashboard is normal.
   - Orchestrator/publisher fixture for the 2026-06-09 contradiction shape.
   - Use these target files: `tests/unit/briefing/test_quality_eval_current_run.py`, `tests/unit/briefing/test_quality_history_current_run.py`, `tests/unit/publisher/test_quality_consistency_current_run.py`, `tests/unit/publisher/test_quality_dashboard_current_run.py`, and `tests/unit/orchestrator/test_pipeline_quality_snapshot_current_run.py`.

## Acceptance Criteria

- `[데이터부족]` in any published segment increments data-limited fallback count.
- `데이터 상태: 제한` increments limited-or-worse segment count.
- A core-missing marker increments core-missing segment count.
- A 2026-06-09-shaped fixture renders:
  - `데이터 부족 폴백 25.0% | 12 건`
  - `핵심 소스 결손 세그먼트 3`
  - `제한/실패 세그먼트 3`
  - zero-item source count greater than or equal to 7
- The u69 gate fails when `quality.md` says zero limited/fallback segments while segment markdown contains limited/fallback markers.
- The u69 gate fails when segment/current coverage shows core-missing evidence but dashboard/history/index surfaces show zero core-missing segments.
- Older `quality_history.jsonl` rows without the new fields still load and render.

## Tests / Validation

Run the narrow tests first:

```bash
uv run --extra dev pytest tests/unit/briefing tests/unit/publisher tests/unit/orchestrator -k "quality or consistency or current_run"
```

Then run scoped static checks:

```bash
uv run --extra dev ruff check src/investo/briefing/quality_eval.py src/investo/briefing/quality_history.py src/investo/publisher/quality_consistency.py src/investo/publisher/site_index/quality_dashboard.py src/investo/orchestrator/pipeline.py tests/unit/briefing tests/unit/publisher tests/unit/orchestrator
uv run --extra dev mypy src
```

## Non-Goals

- No new source collection behavior.
- No severity taxonomy change.
- No archive backfill.
- No prompt rewrite.
- No dashboard redesign beyond truthful current-run fields.

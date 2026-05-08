# u42 quality-kpi-history closeout

Date: 2026-05-09
Status: Complete

## Delivered

- Added `src/investo/briefing/quality_history.py` with atomic same-day upsert for `archive/_meta/quality_history.jsonl`.
- Extended `src/investo/briefing/quality_eval.py` with `QualityHistoryRow` and `compute_quality_history(days=30, *, history_path, today=...)`, preserving missing-day gaps.
- Added `src/investo/visuals/quality_sparkline.py` for deterministic 600x180 inline SVG sparklines with u26 dark-mode style hooks and u24-compatible provenance metadata.
- Extended `publisher/site_index.py::update_quality_page` so `site_docs/quality.md` renders the sparkline, current 7-day KPI table, and `최근 30일 추세`.
- Wired segmented publish to append the quality snapshot inside the publish snapshot/rollback envelope; `INVESTO_DRY_RUN=1` skips the history append.

## Tests

- `tests/unit/briefing/test_quality_history.py`
- `tests/unit/briefing/test_quality_eval.py`
- `tests/unit/visuals/test_quality_sparkline.py`
- `tests/unit/publisher/test_quality_page.py`
- `tests/unit/orchestrator/test_run_pipeline.py`

## Verification

- `uv run ruff check .`
- `uv run ruff format --check .`
- `uv run mypy --strict src/`
- `uv run pytest -q`
- `uv run mkdocs build --strict`

Manual browser color-scheme inspection was not run in this commit loop; SVG determinism, missing-gap behavior, and strict docs build are covered by tests.

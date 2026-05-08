# u44 retrospective-and-prediction-tracker closeout

Date: 2026-05-09
Status: Complete

## Delivered

- Added deterministic monthly retrospective rendering in `briefing/monthly_retrospective.py`.
- Added month-boundary publish wiring: first publish of a new month can write `archive/monthly/YYYY-MM.md` and refresh `archive/monthly/index.md`.
- Added `briefing/forecast_log.py` for atomic same-day replacement of forecast log rows.
- Added `briefing/accuracy.py` for closed-set action-tag hit-rate aggregation with injectable price lookup.
- Added `publisher/site_index.update_accuracy_page`, `site_docs/accuracy.md`, and mkdocs nav entries for `데이터 품질 › 예측 정확도` and `Archive › 월간 회고`.
- Wired segmented publish to snapshot and write `forecast_log.jsonl` + `accuracy.md`; dry-run skips those writes.

## Tests

- `tests/unit/briefing/test_monthly_retrospective.py`
- `tests/unit/briefing/test_forecast_log.py`
- `tests/unit/briefing/test_accuracy.py`
- `tests/unit/orchestrator/test_run_pipeline.py`

## Verification

- `uv run ruff check .`
- `uv run ruff format --check .`
- `uv run mypy --strict src/`
- `uv run pytest -q`
- `uv run mkdocs build --strict`

Manual browser inspection was not run in this commit loop. Accuracy page pricing uses an injectable lookup; the default public page degrades to `표본 누적 중` until a price lookup is supplied by a future enrichment.

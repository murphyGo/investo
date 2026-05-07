# Code Summary: u15 coverage-confidence-badges

**Date**: 2026-05-07

## Completed

- Added segment coverage modeling with `normal`, `partial`, and `insufficient` statuses.
- Defined required categories for domestic, US, and crypto segments.
- Rendered a first-viewport `데이터 상태` badge with item/source counts and missing core categories.
- Fed computed partial/insufficient coverage into the existing data-limited prompt path.
- Added coverage labels to segmented Telegram summaries when rendered coverage metadata exists.

## Files Changed

- `src/investo/briefing/segments.py`
- `src/investo/briefing/pipeline.py`
- `src/investo/notifier/summary.py`
- `tests/unit/briefing/test_segments.py`
- `tests/unit/briefing/test_budget_happy_path.py`
- `tests/unit/notifier/test_summary.py`

## Verification

- `uv run pytest tests/unit/briefing/test_segments.py tests/unit/briefing/test_budget_happy_path.py tests/unit/notifier/test_summary.py -q` (35 passed)
- `uv run ruff check .`
- `uv run ruff format --check .`
- `uv run mypy --strict src/`
- `uv run pytest -q` (981 passed)

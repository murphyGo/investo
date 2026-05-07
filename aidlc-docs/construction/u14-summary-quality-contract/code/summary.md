# Code Summary: u14 summary-quality-contract

**Date**: 2026-05-07

## Completed

- Added a validated summary header contract for segmented briefing first-viewport fields.
- Replaced brittle `_first_sentence` header extraction with markdown/list-aware summary cleaning.
- Updated segmented Telegram summary generation to prefer the clean rendered `오늘의 결론` line when present.
- Added regression tests for numbered-list leakage, markdown fragment leakage, data-limited fallback headers, and Telegram summary reuse.

## Files Changed

- `src/investo/briefing/pipeline.py`
- `src/investo/notifier/summary.py`
- `tests/unit/briefing/test_budget_happy_path.py`
- `tests/unit/notifier/test_summary.py`

## Verification

- `uv run pytest tests/unit/briefing/test_budget_happy_path.py tests/unit/notifier/test_summary.py -q`
- `uv run ruff check .`
- `uv run ruff format --check .`
- `uv run mypy --strict src/`
- `uv run pytest -q` (979 passed)

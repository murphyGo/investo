# Code Summary: u18 watchlist-relevance

**Date**: 2026-05-07

## Completed

- Added a non-secret JSON watchlist config surface at `config/watchlist.json`.
- Added `config/watchlist.example.json` with tickers, crypto assets, sectors, and keywords.
- Implemented watchlist matching against collected `NormalizedItem` title/summary/source/category text.
- Rendered a first-viewport `내 관심 자산 영향` callout in segmented briefings.
- Added watchlist context to the LLM prompt when configured.
- Added compact watchlist impact text to segmented Telegram summaries when matches exist.
- Explicitly handles no-config and no-match cases without inventing impact.

## Files Changed

- `config/watchlist.example.json`
- `src/investo/briefing/watchlist.py`
- `src/investo/briefing/pipeline.py`
- `src/investo/notifier/summary.py`
- `tests/unit/briefing/test_watchlist.py`
- `tests/unit/briefing/test_budget_happy_path.py`
- `tests/unit/notifier/test_summary.py`

## Verification

- `uv run pytest tests/unit/briefing/test_watchlist.py tests/unit/briefing/test_budget_happy_path.py tests/unit/notifier/test_summary.py -q` (33 passed)
- `uv run ruff check .`
- `uv run ruff format --check .`
- `uv run mypy --strict src/`
- `uv run pytest -q` (987 passed)

# Code Summary: u17 operations-visibility

**Date**: 2026-05-07

## Completed

- Added GitHub Actions Step Summary output for pipeline results.
- Included pipeline status, target date, briefing URL, duration, per-stage statuses, and per-stage timings.
- Preserved the existing exit-code contract: `SUCCESS` and `PARTIAL` return 0; `FAILED` returns 1.
- Added redaction for configured secret values, bot-token-like values, and chat-id-like values before diagnostics are written.
- Chose not to add a separate doctor command in this slice; the Step Summary covers the immediate partial-success visibility gap.

## Files Changed

- `src/investo/__main__.py`
- `tests/unit/orchestrator/test_main.py`

## Verification

- `uv run pytest tests/unit/orchestrator/test_main.py -q` (52 passed)
- `uv run ruff check .`
- `uv run ruff format --check .`
- `uv run mypy --strict src/`
- `uv run pytest -q` (982 passed)

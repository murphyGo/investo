# Code Summary: u23 notification-actionability

**Date**: 2026-05-07

## Completed

- Updated segmented public alerts so each market block includes an icon, compact status tag when available, inline detail link, and one-line summary.
- Kept a readable link collection footer so all segment URLs remain preserved under truncation.
- Added a clean plain-text fallback for Telegram Markdown parse failures, preventing raw `*`/markdown markers from leaking to users.
- Made public notification failure operator-visible while preserving the existing `PARTIAL` pipeline status and non-fatal exit-code semantics.

## Files Changed

- `src/investo/notifier/summary.py`
- `src/investo/notifier/briefing_publisher.py`
- `src/investo/orchestrator/pipeline.py`
- `tests/unit/notifier/test_summary.py`
- `tests/unit/notifier/test_briefing_publisher.py`
- `tests/unit/orchestrator/test_run_pipeline.py`
- `aidlc-docs/construction/plans/u23-notification-actionability-code-generation-plan.md`
- `aidlc-docs/aidlc-state.md`

## Verification

- `uv run pytest tests/unit/notifier/test_summary.py tests/unit/notifier/test_briefing_publisher.py tests/unit/orchestrator/test_run_pipeline.py -q` (78 passed)
- `uv run ruff check src/investo/notifier src/investo/orchestrator/pipeline.py tests/unit/notifier tests/unit/orchestrator/test_run_pipeline.py`
- `uv run mypy --strict src/investo/notifier src/investo/orchestrator/pipeline.py`
- `uv run ruff format --check .`
- `uv run ruff check .`
- `uv run mypy --strict src/`
- `uv run pytest -q` (1026 passed)
- `uv run mkdocs build --strict`

# Code Summary: u21 summary-quality-gate

**Date**: 2026-05-07

## Completed

- Added a publish-time first-viewport summary validator for segmented briefings.
- Rejected missing, empty, list-marker-only, unbalanced bold marker, and unbalanced markdown-link summary lines.
- Wired the validator into segmented publish before archive files are written.
- Added orchestrator coverage proving invalid summaries fail the publish stage, alert the operator, skip notification, and write no markdown.

## Files Changed

- `src/investo/briefing/summary_quality.py`
- `src/investo/orchestrator/pipeline.py`
- `tests/unit/briefing/test_summary_quality.py`
- `tests/unit/orchestrator/test_run_pipeline.py`
- `tests/integration/test_pipeline.py`
- `aidlc-docs/construction/plans/u21-summary-quality-gate-code-generation-plan.md`
- `aidlc-docs/aidlc-state.md`

## Verification

- `uv run pytest tests/unit/briefing/test_summary_quality.py tests/unit/orchestrator/test_run_pipeline.py tests/integration/test_pipeline.py -q` (59 passed)
- `uv run ruff check src/investo/briefing/summary_quality.py src/investo/orchestrator/pipeline.py tests/unit/briefing/test_summary_quality.py tests/unit/orchestrator/test_run_pipeline.py tests/integration/test_pipeline.py`
- `uv run mypy --strict src/investo/briefing/summary_quality.py src/investo/orchestrator/pipeline.py`
- `uv run ruff format --check .`
- `uv run ruff check .`
- `uv run mypy --strict src/`
- `uv run pytest -q` (1035 passed)
- `uv run mkdocs build --strict`

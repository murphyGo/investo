# Code Summary: u20 archive-trust-and-latest-index

**Date**: 2026-05-07

## Completed

- Added a publisher helper that refreshes Home and Archive latest segmented links for the current target date.
- Wired segmented publish to refresh and stage `site_docs/index.md` and `archive/index.md` when running against the production relative archive path.
- Labeled legacy single-briefing archive links as pre-segmentation legacy content.
- Added tests for latest-link rendering, legacy labels, and publish staging of index pages.

## Files Changed

- `src/investo/publisher/site_index.py`
- `src/investo/orchestrator/pipeline.py`
- `archive/index.md`
- `tests/unit/publisher/test_site_index.py`
- `tests/unit/orchestrator/test_run_pipeline.py`
- `aidlc-docs/construction/plans/u20-archive-trust-and-latest-index-code-generation-plan.md`
- `aidlc-docs/aidlc-state.md`

## Verification

- `uv run pytest tests/unit/publisher/test_site_index.py tests/unit/orchestrator/test_run_pipeline.py tests/integration/test_pipeline.py -q` (53 passed)
- `uv run ruff check src/investo/publisher/site_index.py src/investo/orchestrator/pipeline.py tests/unit/publisher/test_site_index.py tests/unit/orchestrator/test_run_pipeline.py tests/integration/test_pipeline.py`
- `uv run mypy --strict src/investo/publisher/site_index.py src/investo/orchestrator/pipeline.py`
- `uv run ruff format --check .`
- `uv run ruff check .`
- `uv run mypy --strict src/`
- `uv run pytest -q` (1037 passed)
- `uv run mkdocs build --strict`

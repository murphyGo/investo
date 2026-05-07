# Code Summary: u19 briefing-visual-assets

**Date**: 2026-05-07

## Completed

- Added the `investo.visuals` package as the u19 visual asset contract surface.
- Added markdown-adjacent visual asset path helpers for segmented archive pages.
- Added strict card input models for data confidence, market snapshot, price snapshot, and watchlist relevance cards.
- Added an explicit external image policy that disables third-party image scraping by default.
- Added unit tests for path invariants, card contracts, and external image policy enforcement.
- Added card builders for `SegmentCoverage`, known `yfinance-price` / `coingecko-price` metadata, and `WatchlistImpact`.
- Added a deterministic SVG renderer for data confidence, market snapshot, price snapshot, and watchlist relevance cards.
- Added markdown cleanup, text wrapping, fixed SVG dimensions, and long-text/no-data render tests.
- Added visual asset preparation that writes segment/date SVG files and inserts relative markdown image links.
- Connected segmented pipeline publish flow so generated markdown and `.assets` files are staged in the same commit.
- Added visual asset validation to prevent missing, tiny, or malformed SVG links from reaching public archive pages.
- Added `visual_assets` stage diagnostics to pipeline results and GitHub Step Summary output.
- Added text-only publish fallback: visual generation failures mark the run partial while allowing markdown publish and Telegram notification to continue.
- Completed the full quality gate after u19.

## Files Changed

- `src/investo/visuals/__init__.py`
- `src/investo/visuals/cards.py`
- `src/investo/visuals/paths.py`
- `src/investo/visuals/policy.py`
- `src/investo/visuals/render.py`
- `src/investo/visuals/assets.py`
- `src/investo/orchestrator/pipeline.py`
- `tests/unit/visuals/__init__.py`
- `tests/unit/visuals/test_assets.py`
- `tests/unit/visuals/test_cards.py`
- `tests/unit/visuals/test_paths.py`
- `tests/unit/visuals/test_policy.py`
- `tests/unit/visuals/test_render.py`
- `tests/integration/test_pipeline.py`
- `tests/unit/orchestrator/test_run_pipeline.py`
- `tests/unit/orchestrator/test_main.py`
- `aidlc-docs/construction/plans/u19-briefing-visual-assets-code-generation-plan.md`

## Verification

- `uv run pytest tests/unit/visuals -q` (23 passed)
- `uv run pytest tests/unit/visuals tests/integration/test_pipeline.py -q` (30 passed)
- `uv run pytest tests/unit/orchestrator/test_run_pipeline.py tests/unit/orchestrator/test_main.py tests/integration/test_pipeline.py tests/unit/visuals -q` (125 passed)
- `uv run ruff check .`
- `uv run ruff format --check .`
- `uv run mypy --strict src/`
- `uv run pytest -q` (1011 passed)
- `uv run mkdocs build --strict`

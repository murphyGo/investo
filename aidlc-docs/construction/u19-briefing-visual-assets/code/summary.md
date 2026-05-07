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
- Added optional OpenAI-powered PNG hero generation for briefing visuals. It is gated by `INVESTO_OPENAI_VISUALS=1` and `OPENAI_API_KEY`, defaults the Responses model to `gpt-5.5`, and falls back to deterministic SVG cards when disabled or unavailable.
- Added optional licensed external image fetching for contextual briefing visuals. It is gated by `INVESTO_EXTERNAL_IMAGE_ASSETS=1`, requires per-item image license metadata, blocks private hosts, and falls back to AI/SVG assets when no compliant image is present.

## Files Changed

- `src/investo/visuals/__init__.py`
- `src/investo/visuals/cards.py`
- `src/investo/visuals/paths.py`
- `src/investo/visuals/policy.py`
- `src/investo/visuals/render.py`
- `src/investo/visuals/assets.py`
- `src/investo/visuals/external_image.py`
- `src/investo/visuals/openai_image.py`
- `src/investo/orchestrator/pipeline.py`
- `tests/unit/visuals/__init__.py`
- `tests/unit/visuals/test_assets.py`
- `tests/unit/visuals/test_cards.py`
- `tests/unit/visuals/test_external_image.py`
- `tests/unit/visuals/test_openai_image.py`
- `tests/unit/visuals/test_paths.py`
- `tests/unit/visuals/test_policy.py`
- `tests/unit/visuals/test_render.py`
- `tests/integration/test_pipeline.py`
- `tests/unit/orchestrator/test_run_pipeline.py`
- `tests/unit/orchestrator/test_main.py`
- `aidlc-docs/construction/plans/u19-briefing-visual-assets-code-generation-plan.md`

## Verification

- `uv run pytest tests/unit/visuals -q` (37 passed)
- `uv run pytest tests/unit/visuals tests/integration/test_pipeline.py -q` (44 passed)
- `uv run pytest tests/unit/orchestrator/test_run_pipeline.py tests/unit/orchestrator/test_main.py tests/integration/test_pipeline.py tests/unit/visuals -q` (125 passed)
- `uv run ruff check .`
- `uv run ruff format --check .`
- `uv run mypy --strict src/`
- `uv run pytest -q` (1025 passed)
- `uv run mkdocs build --strict`

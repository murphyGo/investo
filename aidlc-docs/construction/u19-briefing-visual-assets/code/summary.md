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

## Files Changed

- `src/investo/visuals/__init__.py`
- `src/investo/visuals/cards.py`
- `src/investo/visuals/paths.py`
- `src/investo/visuals/policy.py`
- `src/investo/visuals/render.py`
- `tests/unit/visuals/__init__.py`
- `tests/unit/visuals/test_cards.py`
- `tests/unit/visuals/test_paths.py`
- `tests/unit/visuals/test_policy.py`
- `tests/unit/visuals/test_render.py`
- `aidlc-docs/construction/plans/u19-briefing-visual-assets-code-generation-plan.md`

## Verification

- `uv run pytest tests/unit/visuals -q` (20 passed)
- `uv run ruff check src/investo/visuals tests/unit/visuals`
- `uv run mypy --strict src/investo/visuals`

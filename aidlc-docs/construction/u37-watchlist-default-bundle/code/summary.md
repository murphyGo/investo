# u37 watchlist-default-bundle Code Summary

**Date**: 2026-05-09
**Status**: Complete

## Implementation

- Activated `DEFAULT_CORE_ALIASES` through `WatchlistConfig.from_default_bundle()` when `load_watchlist()` sees a missing path, blank `INVESTO_WATCHLIST_CONFIG`, unreadable JSON, or empty JSON.
- Preserved authored on-disk configs as the exclusive source of truth; the default bundle is not layered onto real user configs.
- Added the `default_bundle` watchlist impact status and `DEFAULT_BUNDLE_BADGE_LABEL` chokepoint.
- Rendered `(기본 바스켓)` on the site watchlist line, Telegram one-line summary, and watchlist visual-card subtitle.

## Verification

- `uv run ruff check .`
- `uv run ruff format --check .`
- `uv run mypy --strict src/`
- `uv run pytest -q`
- `uv run mkdocs build --strict`

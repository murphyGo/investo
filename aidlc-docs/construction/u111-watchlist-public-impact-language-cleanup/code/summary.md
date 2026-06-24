# u111 watchlist-public-impact-language-cleanup - Code Summary

**Date**: 2026-06-24
**Status**: Complete
**Stage**: Code Generation

## Summary

Closed the u111 public watchlist language cleanup. Matching, confidence, alias
behavior, and u73 grouping are unchanged; public renderers now project
watchlist matches through reader-safe labels and keep raw matcher reasons only
in diagnostics.

## Changes

- `src/investo/briefing/watchlist.py`
  - Added canonical public projection helpers:
    `public_watchlist_match_group`, `public_watchlist_match_label`, and
    `public_watchlist_match_summary`.
  - `render_watchlist_impact()` now renders `직접 관련` / `관련 맥락` style
    labels instead of `[structured-symbol]`, `[boundary-term]`, or
    `[alias:*]`.
- `src/investo/publisher/watchlist_pages.py`
  - Daily public Direct/Related sections use the same public summary helper.
  - Raw alias display was removed from public bullets; collapsed diagnostics
    still retain bounded reason-code context.
- `src/investo/visuals/cards.py`
  - Watchlist relevance card rows now carry public labels and filter to
    direct/related public impacts.
- `src/investo/_internal/surface_quality.py`
  - Added a public-surface blocker for bracketed matcher reason codes and
    `matched_alias` leakage outside protected/collapsed diagnostics.
- Tests
  - Added u111 coverage for site/Telegram public projection, daily page public
    sections, visual card rows, and surface-quality blocking.

## Validation

```bash
uv run --extra dev pytest tests/unit/briefing/test_watchlist.py tests/unit/briefing/test_watchlist_impact.py tests/unit/publisher/test_watchlist_daily_page.py tests/unit/visuals tests/unit/notifier/test_summary.py tests/unit/internal/test_surface_quality.py
# 288 passed

uv run --extra dev ruff check src/investo/_internal/surface_quality.py src/investo/briefing/watchlist.py src/investo/briefing/watchlist_impact.py src/investo/publisher/watchlist_pages.py src/investo/visuals src/investo/notifier tests/unit/briefing/test_watchlist.py tests/unit/briefing/test_watchlist_impact.py tests/unit/publisher/test_watchlist_daily_page.py tests/unit/visuals tests/unit/notifier/test_summary.py tests/unit/internal/test_surface_quality.py
# All checks passed

uv run --extra dev mypy src
# Success: no issues found in 211 source files
```

## TECH-DEBT

None.

# Code Summary: u108 reader-facing-quality-language-boundary

## Overview

Implemented a deterministic public-language boundary for quality and coverage diagnostics. Reader-visible surfaces now project internal labels such as `데이터 부족`, `[데이터부족]`, `본문 사용 미집계`, and `확인 소스 미상` into Korean reader copy, while collapsed diagnostics and structured metadata retain operational detail.

## Application Changes

- Added `src/investo/_internal/public_quality_language.py` with shared projection strings, forbidden public phrase/pattern detection, and a narrow text projection helper.
- Extended `src/investo/_internal/surface_quality.py` so the existing u100 gate blocks raw diagnostic labels in `segment_first_viewport` and `segment_body` regions.
- Updated reader-format reflow so public status chips no longer expose `본문 사용`, `실패 N`, or `0건 N` counts; raw counts stay inside collapsed diagnostics.
- Updated site index hero conclusion extraction, Telegram summary extraction, visual card text cleaning, and quality sparkline empty state copy to use reader-safe wording.

## Tests

- Added and updated regression tests for surface-quality blocking, collapsed-diagnostics allowance, reader-format projection, Telegram summaries, site hero cards, visual cards, and quality sparkline empty states.
- Validation run: `uv run --extra dev pytest tests/unit/internal/test_surface_quality.py tests/unit/publisher/test_reader_format.py tests/unit/publisher/test_reader_format_reflow_u71.py tests/integration/test_briefing_reader_format.py tests/unit/notifier/test_summary_extract.py tests/unit/notifier/test_summary.py tests/unit/visuals/test_quality_sparkline.py tests/unit/visuals/test_render.py tests/unit/publisher/test_site_index.py` -> 167 passed.
- Validation run: scoped `ruff check` over changed source/test areas -> passed.
- Validation run: `uv run --extra dev mypy src` -> passed.

## Notes

- No source adapters, network calls, secrets, paid APIs, quality KPI schema, or archive backfill were added.
- Watchpoint structural readability remains owned by u110; watchlist matcher reason cleanup remains owned by u111.

# u62 quality-status-publish-reconciliation Code Summary

**Date**: 2026-05-23
**Status**: Complete

## Delivered

- Changed first-viewport source-count rendering so successful source collection with unknown body attribution renders `본문 사용 미집계` instead of misleading `본문 사용 0`.
- Expanded the quality sparkline SVG height so all four metric panels fit inside the viewBox without clipped lower labels/lines.
- Preserved existing quality-history worst-wins and severity propagation paths.
- Added regression coverage for body-used unknown rendering and sparkline bounds.

## Verification

- `uv run pytest tests/unit/briefing/test_render_coverage_badge.py tests/unit/visuals/test_quality_sparkline.py -q`
- Included in combined targeted gate: 192 passed.


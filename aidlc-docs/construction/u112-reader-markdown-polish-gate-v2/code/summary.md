# u112 reader-markdown-polish-gate-v2 - Code Summary

**Date**: 2026-06-24
**Status**: Complete
**Stage**: Code Generation

## Summary

Closed the u112 markdown polish gate follow-up. The existing u100
surface-quality repair/block path was extended with bounded watermark,
numeric-emphasis, href-ellipsis, truncation-residue, and Korean particle
checks. The segment reader-format path already runs repair followed by a
blocking scan before publish, so the stricter issue matrix now applies before
archive/index writes.

## Changes

- `src/investo/_internal/surface_quality.py`
  - Added watermark `수집창 [...]` bracket validation for new first-viewport
    watermark lines.
  - Added safe repairs for `민감도을` and fixed broken numeric-bold fragments
    such as `**-**0.04%**p**`, `$2.30**T`, and nested signed dollar/percent
    tokens.
  - Added blockers for residual broken numeric bold, href ellipsis in markdown
    link targets, and bounded first-viewport truncation residue.
  - Kept protected-region behavior for code fences, tables, collapsed details,
    and disclaimers.
- `src/investo/publisher/reader_format/emphasis.py`
  - Extended numeric wrapping so signed percent-point, signed dollar, scale
    suffix, and dollar/percent compound tokens are bolded as one token.
- `src/investo/briefing/_assembly/summary_extraction.py`
  - Summary sentence extraction now rejects raw lines with blocking
    surface-quality issues before markdown cleaning can turn them into a
    seemingly valid candidate.
- `src/investo/briefing/summary_quality.py`
  - Preserved existing specific error-message ordering while retaining the
    broader surface-quality safety net.

## Validation

```bash
uv run --extra dev pytest tests/unit/internal/test_surface_quality.py tests/unit/publisher/test_reader_format.py tests/unit/publisher/test_segment_reader_surface_quality.py tests/unit/briefing/test_summary_quality.py tests/unit/briefing/test_summary_extraction_surface_quality.py
# 79 passed

uv run --extra dev ruff check src/investo/_internal src/investo/publisher/reader_format src/investo/publisher/segment_reader_format.py src/investo/briefing/_assembly/summary_extraction.py src/investo/briefing/summary_quality.py tests/unit/internal tests/unit/publisher tests/unit/briefing/test_summary_quality.py tests/unit/briefing/test_summary_extraction_surface_quality.py
# All checks passed

uv run --extra dev mypy src
# Success: no issues found in 211 source files
```

## TECH-DEBT

None.

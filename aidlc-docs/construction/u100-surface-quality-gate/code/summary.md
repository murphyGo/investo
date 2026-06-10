# u100 surface-quality-gate — Code Summary

Date: 2026-06-11
Status: Complete

## Scope

Add deterministic first-viewport repair and blocking for known surface artifacts without adding a spellchecker, LLM rewrite, or broad grammar policy.

## Implementation

- Added `investo._internal.surface_quality` with shared issue codes, first-viewport extraction, repair, and scan helpers.
- Repaired known bad token `불강한성` to `불확실성` and removed dangling first-viewport `...` artifacts outside protected regions.
- Blocked first-viewport broken markdown links and raw trace fragments via `SurfaceQualityError`.
- Preserved fenced code blocks, markdown tables, disclaimers, and diagnostic details.
- Integrated surface repair/scan after first-viewport reflow and before final compliance/tone checks in `segment_reader_format`.
- Routed `SurfaceQualityError` through the publish failure path.
- Updated summary extraction and summary-quality validation to reject blocking surface artifacts.
- Narrowed compliance scanning so `불확실성` does not trip the standalone certainty phrase `확실`.

## Validation

- `uv run --extra dev pytest tests/unit/internal/test_surface_quality.py tests/unit/publisher/test_segment_reader_surface_quality.py tests/unit/briefing/test_summary_extraction_surface_quality.py tests/unit/briefing/test_summary_quality.py tests/unit/publisher/test_compliance_language.py -k "surface or summary_quality or first_viewport or uncertainty_word"`
- `uv run --extra dev ruff check src/investo/_internal/surface_quality.py src/investo/publisher/errors.py src/investo/publisher/__init__.py src/investo/publisher/segment_reader_format.py src/investo/publisher/compliance_language.py src/investo/orchestrator/pipeline.py src/investo/briefing/summary_quality.py src/investo/briefing/_assembly/summary_extraction.py tests/unit/internal/test_surface_quality.py tests/unit/publisher/test_segment_reader_surface_quality.py tests/unit/briefing/test_summary_extraction_surface_quality.py tests/unit/publisher/test_compliance_language.py`
- `uv run --extra dev mypy src/investo/_internal/surface_quality.py src/investo/publisher/errors.py src/investo/publisher/segment_reader_format.py src/investo/publisher/compliance_language.py src/investo/orchestrator/pipeline.py src/investo/briefing/summary_quality.py src/investo/briefing/_assembly/summary_extraction.py`

# u127 Code Summary: Summary Quality Reject Contract Unification

## Outcome

Completed the behavior-preserving summary reject contract cleanup. First-viewport summary candidate rejection now has one authoritative predicate in `_internal.summary_quality`.

## Changes

- Added `_internal.summary_quality.is_unsafe_summary_value(value: str) -> bool`.
- Refactored `_validate_summary_value` to reuse the same shared issue helper while keeping existing prefix-specific `SummaryQualityError` messages.
- Re-exported `is_unsafe_summary_value` from `briefing.summary_quality` for compatibility.
- Replaced duplicated producer-side reject regex ownership in `briefing/_assembly/summary_extraction.py` with delegation to the canonical predicate.
- Extended summary tests so producer candidate rejection and publish gate rejection stay aligned across current unsafe value shapes.

## Validation

- `uv run --extra dev pytest tests/unit/briefing/test_summary_fidelity.py tests/unit/briefing/test_summary_quality.py tests/unit/briefing/test_summary_extraction_surface_quality.py`
- `uv run --extra dev ruff check src/investo/_internal/summary_quality.py src/investo/briefing/summary_quality.py src/investo/briefing/_assembly/summary_extraction.py tests/unit/briefing/test_summary_fidelity.py tests/unit/briefing/test_summary_quality.py tests/unit/briefing/test_summary_extraction_surface_quality.py`
- `uv run --extra dev ruff format --check src/investo/_internal/summary_quality.py src/investo/briefing/summary_quality.py src/investo/briefing/_assembly/summary_extraction.py tests/unit/briefing/test_summary_fidelity.py tests/unit/briefing/test_summary_quality.py tests/unit/briefing/test_summary_extraction_surface_quality.py`
- `uv run --extra dev mypy src`

## Debt

- Closed `DEBT-047`.

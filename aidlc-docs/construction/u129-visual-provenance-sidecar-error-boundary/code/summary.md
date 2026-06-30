# u129 Code Summary: Visual Provenance Sidecar Error Boundary

## Outcome

Completed the visual provenance caption error-boundary hardening. Existing corrupt or schema-invalid sidecars no longer silently produce captionless public images.

## Changes

- Updated `_provenance_caption_for` to return `None` only when the sidecar is missing.
- Converted existing sidecar parse/validation failures into `VisualAssetError` with exception chaining.
- Kept error messages path-scoped and avoided including raw manifest contents.
- Added tests for missing optional sidecar behavior, corrupt JSON, and schema-invalid JSON.

## Validation

- `uv run --extra dev pytest tests/unit/visuals/test_assets.py tests/unit/visuals/test_provenance.py tests/unit/orchestrator/test_run_pipeline.py`
- `uv run --extra dev ruff check src/investo/visuals/assets.py tests/unit/visuals/test_assets.py tests/unit/visuals/test_provenance.py tests/unit/orchestrator/test_run_pipeline.py`
- `uv run --extra dev ruff format --check src/investo/visuals/assets.py tests/unit/visuals/test_assets.py tests/unit/visuals/test_provenance.py tests/unit/orchestrator/test_run_pipeline.py`
- `uv run --extra dev mypy src`

## Debt

- Closed `DEBT-041`.

# Code Generation Plan: `u129 visual-provenance-sidecar-error-boundary`

**Date**: 2026-06-29
**Unit**: u129 visual-provenance-sidecar-error-boundary
**Stage**: Code Generation
**Status**: Planned
**Source**: Clean Code & Software Architecture guide re-audit, 2026-06-29. Focus: never swallow exceptions silently, explicit error boundaries, and visual provenance trust. Converts existing `DEBT-041` into a bounded AIDLC unit.
**Estimated Effort**: ~1 h
**Dependencies**:
- u19/u24 visual asset generation and provenance captions are complete.
- u78 filesystem write primitives and u120 archive context boundary are complete.
- u113 publish rollback semantics are complete; preserve publish failure behavior.

---

## Problem Statement

`src/investo/visuals/assets.py::_provenance_caption_for` reads a visual asset sidecar and builds the Korean provenance caption. When the sidecar JSON is corrupt or schema-invalid, the current helper can return `None`, causing the markdown to render an image without a provenance caption. The supported `prepare_segment_visual_assets` path writes and validates manifests, so this is not normally reachable today, but future backfill or operator scripts could bypass that path.

Per the guide's error-boundary rule, corrupt provenance metadata must fail loudly at the visual asset boundary instead of silently degrading into a captionless public image.

## Goal

Make corrupt or schema-invalid visual provenance sidecars raise `VisualAssetError` at caption-render time, while preserving the existing optional-caption behavior for genuinely missing/unsupported assets where the current contract intentionally returns no caption.

## Existing Coverage / Deduplication

- `validate_visual_binary` already raises `VisualAssetError` for missing/invalid manifests on the main preparation path.
- `visuals.provenance.read_manifest` and `manifest_path_for` already own manifest parsing; reuse them.
- u24/u26/u86 own provenance policy and asset library constraints. Do not add a new provenance model.
- This unit is narrower than DEBT-049/061 theme parity; no dark-mode rendering work belongs here.

## Scope Boundary

In scope:
- Identify the exact caption helper path in `visuals/assets.py` that catches manifest read/validation failures and returns `None`.
- Change corrupt/schema-invalid sidecars to raise `VisualAssetError` with the sidecar path in the message and the original exception chained.
- Keep no-manifest/no-supported-caption cases behavior-compatible only where that is already an intentional contract.
- Add focused tests for corrupt JSON, schema-invalid JSON, valid sidecar caption, and intentionally absent caption behavior.
- Ensure any publish/orchestrator caller either propagates `VisualAssetError` through the existing visual fallback path or handles it consistently with current visual asset failures.

Out of scope:
- No visual card redesign.
- No provenance schema change.
- No asset path layout change.
- No archive backfill.
- No theme/dark-mode fix.

## Stage Decision

Functional Design: skip. This is a behavior-preserving observability hardening slice over an existing visual provenance boundary.

NFR Requirements: skip. No new dependency, external source, secret, network call, workflow, runtime budget, or deploy surface.

## Fixed Contracts

### Caption Error Contract

- Missing sidecar where the asset type never promised a caption may still return `None`.
- Existing sidecar path that exists but cannot be parsed or validated raises:

```python
raise VisualAssetError(f"visual asset manifest invalid: {sidecar}") from exc
```

- A sidecar with valid schema but no captionable provenance follows the current renderer policy; do not invent a caption.
- Error messages must not include raw manifest contents.

### Publish Boundary Contract

- `prepare_segment_visual_assets` remains the supported path.
- Any `VisualAssetError` raised during caption insertion follows the existing visual asset failure policy already used by orchestrator/publish tests.
- Do not soften this into a warning unless the existing caller already treats `VisualAssetError` as a visual fallback.

## Implementation Steps

- [ ] Inspect `_provenance_caption_for` and any helper it calls for `except ValueError: return None`.
- [ ] Convert corrupt/schema-invalid sidecar handling to `VisualAssetError` with exception chaining.
- [ ] Add tests in `tests/unit/visuals/test_assets.py` or the existing visual provenance test file for invalid JSON and invalid schema.
- [ ] Verify valid captions still render and missing optional captions retain existing behavior.
- [ ] Write `aidlc-docs/construction/u129-visual-provenance-sidecar-error-boundary/code/summary.md`.

## Acceptance Criteria

1. Corrupt or schema-invalid visual provenance sidecars no longer produce captionless public images silently.
2. Supported valid sidecars render the same caption text as before.
3. Optional no-caption cases remain optional and do not become hard failures.
4. Errors include path context and chain the parse/validation cause without leaking manifest contents.
5. No new dependency direction violates the component DAG.

## Tests / Validation

```bash
uv run --extra dev pytest tests/unit/visuals/test_assets.py tests/unit/visuals/test_provenance.py tests/unit/orchestrator/test_run_pipeline.py
uv run --extra dev ruff check src/investo/visuals/assets.py tests/unit/visuals/test_assets.py tests/unit/visuals/test_provenance.py tests/unit/orchestrator/test_run_pipeline.py
uv run --extra dev ruff format --check src/investo/visuals/assets.py tests/unit/visuals/test_assets.py tests/unit/visuals/test_provenance.py tests/unit/orchestrator/test_run_pipeline.py
uv run --extra dev mypy src
```

## Non-Goals

- No visual layout change.
- No generated asset regeneration.
- No archive migration.
- No MkDocs theme parity work.

# u119 adapter-contract-ports-cleanup Code Summary

**Date**: 2026-06-25
**Stage**: Code Generation
**Status**: Complete

## Summary

u119 moved the remaining pure cross-adapter contracts behind inward owners while preserving legacy import compatibility.

## Changes

- Added `_internal.summary_quality` as the canonical first-viewport summary validation/repair owner.
- Added `_internal.disclaimer` as the canonical disclaimer text/helper owner.
- Added `_internal.crypto_indicators` as the canonical crypto indicator renderer owner.
- Added `models.quality_history.QualityHistoryRow` and exported it from `investo.models`.
- Kept compatibility exports in `briefing.summary_quality`, `briefing.disclaimer`, `briefing.crypto_indicators`, and `briefing.quality_eval`.
- Updated publisher and visuals consumers to import the inward owners directly.
- Updated `briefing.numeric_verify` to consume `CORE_FACT_METADATA_PREFIX` from `models.core_fact`.
- Moved the shared meaningful-text regex to `_internal.text` so `_internal.summary_quality` does not import the briefing adapter.
- Removed the adapter-boundary allowlist entries from `tests/unit/_internal/test_module_boundary.py`.

## Validation

```bash
uv run --extra dev pytest tests/unit/_internal/test_module_boundary.py tests/unit/briefing/test_summary_quality.py tests/unit/briefing/test_disclaimer.py tests/unit/briefing/test_numeric_verify.py tests/unit/publisher/test_briefing_replay.py tests/unit/publisher/test_verifier.py tests/unit/publisher/test_crypto_indicators.py tests/unit/visuals/test_quality_sparkline.py tests/unit/models/test_init.py tests/unit/models/test_shared_domain_contracts.py tests/unit/briefing/test_pattern_dedup_guard.py
uv run --extra dev ruff check src/investo/_internal src/investo/briefing src/investo/models src/investo/publisher src/investo/visuals tests/unit/_internal tests/unit/briefing tests/unit/publisher tests/unit/visuals tests/unit/models
uv run --extra dev ruff format --check src/investo/_internal src/investo/briefing src/investo/models src/investo/publisher src/investo/visuals tests/unit/_internal tests/unit/briefing tests/unit/publisher tests/unit/visuals tests/unit/models
uv run --extra dev mypy src
```

All commands passed.

## Notes

- No rendered markdown, prompt, quality KPI, disclaimer text, crypto indicator output, or source adapter behavior was intentionally changed.
- Legacy imports remain available for compatibility.
- Independent review findings were accepted: `_internal.summary_quality` no longer imports briefing text patterns, and the legacy briefing crypto-indicator import path has an identity regression test.
- No TECH-DEBT item was added.

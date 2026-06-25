# Session Log: u119 adapter-contract-ports-cleanup Code Generation

**Date**: 2026-06-25
**Skill**: dev-investo
**Unit**: u119 adapter-contract-ports-cleanup
**Stage**: Code Generation
**Status**: Complete

## Summary

Implemented the clean-code architecture follow-up that removes the remaining pure shared-contract sibling adapter imports. Publisher and visuals now depend inward on `_internal` / `models` contracts, while legacy `briefing.*` imports remain available as compatibility exports.

## Changes

- Added `_internal.summary_quality`, `_internal.disclaimer`, and `_internal.crypto_indicators` as canonical pure shared-contract owners.
- Added `models.quality_history.QualityHistoryRow` and exported it through `investo.models`.
- Updated publisher and visual consumers to import canonical inward contracts.
- Updated `briefing.numeric_verify` to import `CORE_FACT_METADATA_PREFIX` from `models.core_fact` instead of `sources._core_fact_map`.
- Removed adapter-boundary allowlist entries for pure shared contracts.
- Accepted review findings by moving `MEANINGFUL_TEXT` to `_internal.text` and adding a compatibility identity test for `briefing.crypto_indicators`.

## Validation

```bash
uv run --extra dev pytest tests/unit/_internal/test_module_boundary.py tests/unit/briefing/test_summary_quality.py tests/unit/briefing/test_disclaimer.py tests/unit/briefing/test_numeric_verify.py tests/unit/publisher/test_briefing_replay.py tests/unit/publisher/test_verifier.py tests/unit/publisher/test_crypto_indicators.py tests/unit/visuals/test_quality_sparkline.py tests/unit/models/test_init.py tests/unit/models/test_shared_domain_contracts.py tests/unit/briefing/test_pattern_dedup_guard.py
uv run --extra dev ruff check src/investo/_internal src/investo/briefing src/investo/models src/investo/publisher src/investo/visuals tests/unit/_internal tests/unit/briefing tests/unit/publisher tests/unit/visuals tests/unit/models
uv run --extra dev ruff format --check src/investo/_internal src/investo/briefing src/investo/models src/investo/publisher src/investo/visuals tests/unit/_internal tests/unit/briefing tests/unit/publisher tests/unit/visuals tests/unit/models
uv run --extra dev mypy src
```

Result: all commands passed. Focused pytest result was 110 passed.

## TECH-DEBT

None.

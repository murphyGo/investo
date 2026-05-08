# u39 boot-alert-dispatch Code Summary

**Date**: 2026-05-09
**Status**: Complete

## Implementation

- Kept the existing `ConfigError` boot-alert wiring in `__main__` and hardened it with STRICT redaction before constructing the operator alert context.
- Added WARNING logging when boot-alert dispatch itself raises; the process still exits non-zero and the dedup ledger is not recorded unless delivery succeeds.
- Aligned ConfigError operator alerts with the Korean boot-failure format: `🚨 Investo 부팅 실패`, error type/message, suggested action, and KST timestamp.
- Added regression coverage for redaction, dispatch exception behavior, and Korean boot-alert formatting.

## Verification

- `uv run pytest tests/unit/orchestrator/test_main.py tests/unit/notifier/test_operator_alerter.py tests/unit/orchestrator/test_boot_alert_dedup.py -q`
- `uv run ruff check .`
- `uv run ruff format --check .`
- `uv run mypy --strict src/`
- `uv run pytest -q`
- `uv run mkdocs build --strict`

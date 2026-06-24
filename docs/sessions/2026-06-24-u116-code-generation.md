# Session Log: 2026-06-24 - u116 repo-quality-guardrails-ci - Code Generation

## Overview

- **Date**: 2026-06-24
- **Unit**: u116 repo-quality-guardrails-ci
- **Stage**: Code Generation

## Work Summary

Added the repo-local quality workflow and hardened policy guardrails around
dependency scanning, paid-provider references, and adapter-package boundaries.

## Files Changed

- Created:
  - `.github/workflows/quality.yml`
  - `tests/unit/_internal/test_quality_workflow.py`
  - `aidlc-docs/construction/u116-repo-quality-guardrails-ci/code/summary.md`
- Modified:
  - `scripts/check_no_anthropic_sdk.py`
  - `scripts/check_no_paid_apis.py`
  - `tests/unit/briefing/test_no_anthropic_sdk.py`
  - `tests/unit/sources/test_no_paid_apis.py`
  - `tests/unit/_internal/test_module_boundary.py`
  - `tests/unit/_internal/test_redaction.py`
  - `tests/unit/briefing/test_summary_fidelity.py`
  - Full-repo ruff formatting normalization for files surfaced by the new
    format gate.
  - AIDLC plan/state/audit files.

## Key Decisions

| Decision | Rationale |
|----------|-----------|
| Keep a separate `quality` workflow | Production daily and Pages workflows should stay focused on deployment/runtime duties. |
| Parse `pyproject.toml` with `tomllib` | PEP 621 dependency arrays are structured TOML, not pseudo table headers. |
| Use a narrow paid-provider blocklist | The repo intentionally supports free official API keys, so broad `API_KEY` bans would be false positives. |
| Explicitly allowlist current cross-adapter imports | Existing behavior calls can remain, but any new top-level sibling edge must be reviewed deliberately. |
| Normalize repo formatting now | The new workflow runs full format check; the current tree must pass before the workflow lands. |

## Review Follow-up

- Code review found the first boundary scanner missed `from investo import
  briefing` and package-relative sibling imports such as `from ..briefing
  import disclaimer`.
- Added resolver support and synthetic regression tests for both cases.

## Validation

- `uv run --extra dev pytest tests/unit/briefing/test_no_anthropic_sdk.py tests/unit/sources/test_no_paid_apis.py tests/unit/_internal/test_module_boundary.py tests/unit/_internal/test_quality_workflow.py` - 40 passed
- `uv run --extra dev ruff check src tests scripts` - passed
- `uv run --extra dev ruff format --check src tests scripts` - passed
- `uv run --extra dev mypy src` - passed
- `uv run python scripts/check_no_anthropic_sdk.py` - passed
- `uv run python scripts/check_no_paid_apis.py` - passed
- `uv run --extra dev pytest` - 3170 passed

## TECH-DEBT

None.

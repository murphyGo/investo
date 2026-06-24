# u116 repo-quality-guardrails-ci - Code Summary

**Date**: 2026-06-24
**Status**: Complete
**Stage**: Code Generation

## Summary

Added a dedicated repository quality workflow and strengthened local policy
guards so PRs and pushes fail before production workflows see lint, type,
test, dependency, paid-provider, or module-boundary regressions.

## Changes

- Added `.github/workflows/quality.yml`
  - Triggers on `pull_request`, `push` to `main`, and `workflow_dispatch`.
  - Uses read-only `contents: read` permission and no `secrets.*` references.
  - Runs ruff check, ruff format check, mypy, pytest, Anthropic guard, and
    paid-API guard.
- Updated `scripts/check_no_anthropic_sdk.py`
  - Parses PEP 621 dependency arrays with stdlib `tomllib`.
  - Flags `anthropic` in `project.dependencies` and each
    `project.optional-dependencies` group.
  - Normalizes dependency names before extras, versions, and markers.
  - Fails closed on malformed `pyproject.toml`.
- Updated `scripts/check_no_paid_apis.py`
  - Added a conservative non-empty paid-first provider blocklist for Bloomberg,
    Refinitiv/Eikon, FactSet, Capital IQ, Morningstar Direct, and Nasdaq Data
    Link/Quandl provider-specific references.
  - Kept free/public official-provider key shapes allowed.
- Extended module-boundary tests
  - Scans all top-level sibling imports between `sources`, `briefing`,
    `publisher`, `notifier`, and `visuals`.
  - Requires each existing cross-adapter top-level import to be explicitly
    allowlisted by source package, target package, file, module, and reason.
  - Detects direct absolute imports, `from investo import <adapter>` alias
    imports, and package-relative sibling imports.
  - Preserves the hard `publisher <-> visuals` top-level edge-free invariant.
  - Adds synthetic unallowed/allowlisted edge tests.
- Updated supporting tests
  - Added workflow text tests.
  - Added Anthropic dependency-array, optional-dependency, extras/marker, and
    malformed TOML fixtures.
  - Added paid-provider block and free-provider allow fixtures.
  - Updated redaction single-source test for the already-registered
    `EIA_API_KEY`.
  - Updated the summary-fidelity gate test to include the production
    public-quality-language projection before validation.
- Normalized full-repo ruff formatting so the new format gate passes on the
  current tree.
- Code review follow-up:
  - Added scanner coverage for `from investo import briefing` and
    `from ..briefing import ...` sibling-import bypass cases.

## Validation

```bash
uv run --extra dev pytest tests/unit/briefing/test_no_anthropic_sdk.py tests/unit/sources/test_no_paid_apis.py tests/unit/_internal/test_module_boundary.py tests/unit/_internal/test_quality_workflow.py
# 40 passed

uv run --extra dev ruff check src tests scripts
# All checks passed

uv run --extra dev ruff format --check src tests scripts
# 485 files already formatted

uv run --extra dev mypy src
# Success: no issues found in 217 source files

uv run python scripts/check_no_anthropic_sdk.py
# exit 0

uv run python scripts/check_no_paid_apis.py
# exit 0

uv run --extra dev pytest
# 3170 passed
```

## TECH-DEBT

None.

# Code Generation Plan: `u116 repo-quality-guardrails-ci`

**Date**: 2026-06-24
**Unit**: u116 repo-quality-guardrails-ci
**Stage**: Code Generation
**Status**: Complete
**Source**: 2026-06-24 repo-local CI and policy-guard audit.
**Estimated Effort**: ~2-4 h
**Dependencies**:
- u6 infra/CI is complete.
- u27 secret hygiene and cost guard surfaces are complete.
- u78 boundary/atomic primitives are complete.
- u102 source-adapter registry completeness is complete.

---

## Problem Statement

The repo has workflows for production daily briefing and Pages deploy, but no repo-local quality workflow that consistently runs lint, format check, type check, tests, and policy guard scripts on PR/push.

Current gaps:

- `daily-briefing.yml` runs the production pipeline, not quality gates.
- `pages.yml` runs MkDocs only.
- `check_no_anthropic_sdk.py` scans pseudo TOML table headers and can miss actual PEP 621 `dependencies = [...]` arrays.
- `check_no_paid_apis.py` has an empty blocklist.
- `test_module_boundary.py` currently protects only the `publisher <-> visuals` top-level pair.

## Goal

Add a dedicated quality workflow and strengthen repo-local guard scripts/tests so violations fail before reaching the production daily pipeline.

## Existing Coverage / Deduplication

- Keep `daily-briefing.yml` focused on scheduled production execution.
- Keep `pages.yml` focused on MkDocs/Pages.
- Reuse existing guard scripts.
- Extend the existing AST boundary test rather than adding an unrelated scanner.

## Scope Boundary

In scope:
- Add `.github/workflows/quality.yml`.
- Run quality checks on `pull_request`, `push` to `main`, and `workflow_dispatch`.
- Fix Anthropic SDK dependency scanning with stdlib `tomllib`.
- Populate a conservative paid-provider blocklist and allowlist tests for current free/public providers.
- Extend module-boundary scanning to all adapter packages with explicit allowlist entries.
- Add focused tests for workflow text and guard behavior.

Out of scope:
- No production daily pipeline behavior change.
- No Pages deploy behavior change.
- No source adapter addition/removal.
- No broad module refactor.
- No runtime dependency addition.
- No blanket ban on all API keys.

## Stage Decision

Functional Design: skip. This is CI and guardrail hardening over existing workflows and scripts.

NFR Requirements: skip. No new runtime dependency, source provider, secret, paid service, or deployed behavior is introduced.

## Fixed Contracts

### Quality Workflow Contract

Create `.github/workflows/quality.yml`:

- triggers: `pull_request`, `push` to `main`, `workflow_dispatch`
- permissions: `contents: read`
- no `secrets.*` usage
- setup uv and Python 3.11
- install dev dependencies
- run:
  - `uv run ruff check src tests scripts`
  - `uv run ruff format --check src tests scripts`
  - `uv run mypy src`
  - `uv run pytest`
  - `uv run python scripts/check_no_anthropic_sdk.py`
  - `uv run python scripts/check_no_paid_apis.py`

### Anthropic Guard Contract

Use `tomllib` to parse `pyproject.toml` and flag `anthropic` dependencies in:

- `[project] dependencies = [...]`
- every `[project.optional-dependencies]` group

Match dependency names case-insensitively before extras/version specifiers/markers. Fail closed on malformed TOML.

### Paid API Guard Contract

Populate a narrow blocklist for paid-first market-data providers/SDKs such as Bloomberg/`blpapi`, Refinitiv/Eikon, FactSet, S&P Capital IQ, Morningstar Direct, Nasdaq Data Link/Quandl provider/SDK references, and paid-provider-specific env vars.

Do not block broad terms such as `API_KEY`, `token`, or `key`; this repo intentionally uses free/public API keys for several official providers.

### Module Boundary Contract

Replace the single-pair assertion with a top-level adapter edge scanner over:

- `sources`
- `briefing`
- `publisher`
- `notifier`
- `visuals`

Any top-level import from one adapter package to another must be explicitly allowlisted with source package, target package, file, imported module prefix, and reason. Preserve the hard invariant that `publisher` and `visuals` remain top-level edge-free in both directions.

## Implementation Steps

- [x] Add `.github/workflows/quality.yml`.
- [x] Add workflow text tests proving required triggers/commands, `contents: read`, and no `secrets.` usage.
- [x] Update `scripts/check_no_anthropic_sdk.py` to parse PEP 621 dependencies with `tomllib`.
- [x] Extend `tests/unit/briefing/test_no_anthropic_sdk.py` with actual dependency-array fixtures.
- [x] Populate `scripts/check_no_paid_apis.py` with a conservative non-empty blocklist.
- [x] Extend `tests/unit/sources/test_no_paid_apis.py` with blocked paid-provider and allowed free-provider fixtures.
- [x] Extend `tests/unit/_internal/test_module_boundary.py` to scan all adapter-package top-level sibling imports against an explicit allowlist.
- [x] Add synthetic tests proving a new unallowed sibling edge fails.
- [x] Run the focused guard tests and the full local quality command set.
- [x] Write `aidlc-docs/construction/u116-repo-quality-guardrails-ci/code/summary.md`.

## Acceptance Criteria

1. A `quality` workflow runs on PRs, pushes to `main`, and manual dispatch.
2. The workflow runs ruff check, ruff format check, mypy, pytest, Anthropic guard, and paid-API guard.
3. The workflow requires no secrets and uses read-only repository contents permission.
4. Anthropic guard catches actual PEP 621 dependency arrays.
5. Existing `pyproject.toml` passes the Anthropic guard.
6. Paid-API guard has a non-empty conservative blocklist.
7. Paid-API guard catches representative paid-first providers and does not flag current approved official/free providers.
8. Module-boundary tests fail on new unallowed top-level sibling adapter imports.
9. Existing allowed edges are documented with reasons.
10. No runtime code path changes.

## Tests / Validation

```bash
uv run --extra dev pytest tests/unit/briefing/test_no_anthropic_sdk.py tests/unit/sources/test_no_paid_apis.py tests/unit/_internal/test_module_boundary.py
uv run --extra dev ruff check scripts/check_no_anthropic_sdk.py scripts/check_no_paid_apis.py tests/unit/briefing/test_no_anthropic_sdk.py tests/unit/sources/test_no_paid_apis.py tests/unit/_internal/test_module_boundary.py
uv run --extra dev ruff format --check scripts/check_no_anthropic_sdk.py scripts/check_no_paid_apis.py tests/unit/briefing/test_no_anthropic_sdk.py tests/unit/sources/test_no_paid_apis.py tests/unit/_internal/test_module_boundary.py
uv run --extra dev mypy src
uv run --extra dev pytest
uv run python scripts/check_no_anthropic_sdk.py
uv run python scripts/check_no_paid_apis.py
```

## Non-Goals

- No production workflow redesign.
- No source adapter work.
- No broad module refactor.
- No new runtime package dependency.
- No blanket API-key ban.

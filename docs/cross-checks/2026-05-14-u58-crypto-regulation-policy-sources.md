# Cross-Check: u58 Crypto-Regulation Policy Sources

**Scope**: u58 crypto-regulation-policy-sources
**Date**: 2026-05-14
**Checked by**: Codex

## Summary

| Status | Count |
|--------|-------|
| Complete | 8 |
| Deferred | 1 |
| Gap | 0 |

**Overall Compliance**: Complete for the u58 source/routing/candidate-priority
scope. Full-repo format normalization remains out of scope and is tracked as an
existing repository drift, not a u58 code gap.

## DoD Mapping

| DoD Item | Status | Evidence |
|----------|--------|----------|
| Congress.gov adapter | Complete | `src/investo/sources/official_policy.py`; tests for success, no key, 403, empty actions, malformed payload. |
| Congress graceful degradation | Complete | Missing key and 403 paths raise sanitized `SourceFetchError`; `CONGRESS_API_KEY` added to shared redaction catalog. |
| Senate Banking official HTML adapter | Complete | Fixture-backed executive-session and release parsing in `tests/unit/sources/fixtures/api/official-policy/`. |
| House Financial Services RSS adapter | Complete | RSS fixture keeps crypto-policy item, drops non-crypto item, and covers empty/malformed/HTTP-error paths. |
| Metadata contract | Complete | All official items emit primitive `policy_priority`, `official_source`, `bill_id`, `committee`, and `event_type` metadata. |
| Crypto routing | Complete | `test_segments_exclusivity.py` pins source-name and metadata-based routing to `crypto`. |
| Candidate preservation | Complete | `test_pipeline_unit.py` pins official crypto-policy preservation before generic caps. |
| Prompt behavior | Complete | `briefing/prompts.py` adds observational official-policy rules and forbids legal/investment-advice claims. |

## Verification

- `uv run ruff check .` — passed.
- `uv run ruff format --check <changed code/test files>` — passed.
- `uv run mypy --strict src/` — passed, 127 source files.
- `uv run pytest tests/unit/sources/test_official_policy.py tests/unit/sources/test_plugin_contract.py tests/unit/briefing/test_segments_exclusivity.py tests/unit/briefing/test_pipeline_unit.py tests/unit/_internal/test_redaction.py tests/integration/test_pipeline.py -q` — 154 passed.
- `uv run pytest -q` — 2326 passed.
- `uv run mkdocs build --strict` — passed.

## Residual Risk

Senate Banking official pages can deny automated clients or change HTML shape.
The adapter is intentionally configured-watch-URL based and fails closed with
source diagnostics rather than blocking the daily run.

Full-repo `ruff format --check .` currently reports four out-of-scope files that
would be reformatted. u58 changed-file formatting is clean.

## Status

u58 construction and cross-check complete.

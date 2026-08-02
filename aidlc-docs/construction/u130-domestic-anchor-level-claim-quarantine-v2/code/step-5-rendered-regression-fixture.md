# u130 Code Generation Step 5 — Rendered Regression Fixture

## Scope Delivered

- Added a redacted trimmed fixture for the 2026-06-30 domestic Stage-2 incident.
- Preserved the four affected public surfaces:
  - 오늘의 결론;
  - 핵심 동인;
  - section ① 요약;
  - section ② 전일 핵심 이슈.
- Added a regression that runs the fixture through the real segment reader-format and anchor-assertion gate chain.

## Fixture Contract

The fixture contains exactly four `150.00` KOSPI level claims and retains the mixed KOSPI/KOSDAQ sentence shape that escaped the pre-u130 gate. Unrelated source details and market values are replaced with deterministic placeholders. The canonical disclaimer is appended by the test rather than copied into the fixture.

The empty prepared anchor set matches the completed u130 incident decision: the KOSPI candidate is statically implausible and the KOSDAQ 477-to-344 candidate is discontinuous, so neither is reader-trusted for the run.

## Regression Assertions

The test proves:

1. the input contains exactly four `150.00` claims;
2. the real reader-format chain removes every `150.00` value;
3. a KOSPI-specific data-limited replacement is present;
4. neighboring supported prose in the mixed sentences survives;
5. the terminal `scan_anchor_assertions` result is empty.

This is a characterization/regression fixture only; no production code changes are part of Step 5.

## Review

Fresh-eyes review approved with no Critical, High, Medium, or Low findings. It confirmed fixture fidelity, real-chain execution, KOSPI-specific evidence, supported-prose preservation, cwd-independent fixture resolution, and test-only scope.

## Validation

- `uv run pytest -q tests/unit/publisher/test_u130_rendered_regression.py` — 1 passed.
- `uv run pytest -q tests/unit/publisher` — 977 passed.
- Scoped Ruff and format checks — passed.
- `uv run mypy src` — passed for 248 source files.
- `git diff --check` — passed.

## Extensions

- Property-Based Testing: not applicable because Step 5 adds no pure production function or serialization boundary.
- Security Baseline: disabled by project opt-in state; fixture redaction was still reviewed explicitly.

## TECH-DEBT

None added.

## Next Step

Step 6 proves existing US and crypto gate fixtures remain byte-unchanged.

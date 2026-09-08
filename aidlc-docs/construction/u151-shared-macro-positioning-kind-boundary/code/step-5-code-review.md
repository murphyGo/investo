# Independent Code Review — u151 Step 5

**Date**: 2026-09-08
**Reviewer**: Separate read-only `u151_step5_review`, required by dev-investo.
**Result**: All five categories Pass; no new u151 finding or debt.

Full-read scope: new 555-line finalized regression test, cumulative three
changed production files, three approved FD artifacts and CG/Step 5 plans.
Real finalizer/channel/watchpoint/glossary/terminal/DTO paths were traced.

| Category | Result | Evidence |
|---|---|---|
| Correctness | Pass | Actual producer-to-finalizer path, zero positioning promotion and legitimate selected-key controls |
| Safety | Pass | No matcher/phase/trust/seal/DTO stubs; safe terminal conclusion excludes generated-only sentinel |
| Reliability | Pass | Three finalized outcomes required; no degraded/blocked escape, exact row and SHA preservation |
| Maintainability | Pass | New test only; production owners/ranking/gates unchanged |
| Test Coverage | Pass | 51 cases, two structured seeded properties, explicit minimized boundary cases |

## Independent checks

- Focused new module: 51 passed in 6.56s.
- Related cumulative core regressions and module/free-API policy: 254 passed
  in 12.70s.
- Four scoped new-test/cumulative-production files: Ruff/check+format pass.
- Source plus new test: mypy 255 files pass.
- Actual compute_bundle_context, finalizer, terminal validation, seal and
  notification derivation used, not replaced by test doubles.

Independent 254-test command:

```bash
uv run python -m pytest tests/unit/_internal/test_module_boundary.py tests/unit/sources/test_no_paid_apis.py tests/unit/orchestrator/test_bundle_context.py tests/unit/models/test_bundle_context_allowlist.py tests/unit/publisher/test_cross_market_cause_map.py tests/unit/publisher/test_shared_macro_positioning_regression_u151.py -q
```

## Scope judgments

The cap of three belongs to the channel table cell. An existing independent
CFTC watchpoint can add legitimate delayed positioning elsewhere. Narrowing
the row-count oracle and retaining its minimal rates example is correct.

Fixed original generated drafts repeat exactly. Sealed output fed back as
new generated input loses the second equal-zero %OI parenthetical. Reviewer
reproduced this independently and with unchanged HEAD glossary code; the
finalizer/channel/watchpoint/glossary files are unchanged. FD/AC-151.6 fixes
generated drafts, so universal F(F(x)) is not an added u151 obligation.
The zero-position case remains in examples and the generator.

The finite one-second property deadline is justified for six real segment
finalizations. Seed/shrinking remain enabled; there is no skip, xfail,
failure-value filtering or retry suppression.

## Protocols applied

| Protocol | Evidence / result |
|---|---|
| Security Boundary | Producer identity precedes title/metadata; bounded/redacted diagnostics retained |
| Data Integrity | Original snapshots, terminal Markdown/SHA/DTO, fixed-input repeat; no durable I/O change |
| Error Contract | Actual terminal gates and finalized outcomes; no degraded or blocked success substitute |
| Memory | Bounded fixture batches and three-key domain, no new long-lived state |
| Performance | Three-key bound and finite real-finalizer properties |
| Concurrency / Resource Lifecycle | N/A — no new concurrent task or external resource acquisition |

## Review checklist

- [x] Changed test and cumulative production files read fully with approved contracts.
- [x] Exact native rows, dates, %OI and weekly lag survive real finalization.
- [x] None of the CFTC items become core shared/thesis evidence.
- [x] Positive keys, legacy display, relabel and independent allowlist are exercised.
- [x] Source tuples and generated inputs preserved; valid zero values not filtered away.
- [x] Sealed-input replay limitation independently reproduced, not masked as a pass.
- [x] SDK, sibling-module and paid-API policy checks pass.
- [x] Disclaimer, CLI subprocess and separated chat-ID paths unchanged.
- [x] No reviewer writes, network/operational action, commit/push or deployment.

Critical/High/Medium/Low: no new u151 issue. Existing glossary handling of
numeric parentheses is a separate possible follow-up, not an in-scope fix or
reason to close DEBT-076. Step 6 full gate/AC/DoD/debt reconciliation remains.

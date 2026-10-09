# Code Generation Plan: u165 source-lifecycle-and-failure-truth

Date:2026-10-09. Status:PLANNED, Functional Design/NFR draft not approved.
Priority:P1-1. Estimate:12–20h. [Design](../u165-source-lifecycle-and-failure-truth/design-brief.md).
Coverage:US-001/005/007/008; FR-001/006/007/017/021; NFR-001/002/003/005/006/007/008.

## Scope and steps

Extend u1 retry/registry, u22 outcome, u31 health, u54 severity, u102 source-spec and u161 lifecycle follow-up. Preserve u161 completion; upstream503 is independent from its already repaired transport/schema. No new provider/import/source name.

- [ ] 1. Characterize Naver/BEA all/one-child errors, genuinezero and3×request budget. Define skipped invariants, legacy loader cases and sparse-news cadence cases.
- [ ] 2. Extend `src/investo/models/coverage.py` skipped enum/reason/builders. Use `rg` to enumerate and update every status switch and historic serialization reader together.
- [ ] 3. Add activation metadata to `_internal/source_specs.py`, parse overrides once, then emit deterministic skipped/attempted outcomes in `sources/aggregator.py`. Registered import/spec/tier parity remains canonical.
- [ ] 4. Repair `sources/krx_foreign_flows.py` all-failure propagation and `sources/bea_macro_actuals.py` failure-vs-zero/60s adapter budget. Reuse `_retry.py`, retain successful children and programmer exceptions, redact diagnostics.
- [ ] 5. Update `briefing/segments.py`, `briefing/_reader_enhance/coverage_badge.py`, `orchestrator/source_health.py`, `weekly_ops_digest.py`, `orchestrator/pipeline.py` and other located quality/visual/Step Summary consumers. Ensure skipped does not produce full u160 observation receipts; preserve cursor mode.
- [ ] 6. Wire explicit lifecycle override configuration where needed in public/private workflowtemplates and env/runtime tests. Document CONTRIBUTING recovery probe and evidence rules. Validate remaining usable news and disclosed policy gaps before rollout.
- [ ] 7. Run focused/full/static/policy checks; record source disablement separately from genuine source recovery.
- [ ] 8. After authorized reviewed-code/pin rollout, observe10distinct scheduled runs; re-enable only after current same-provider parse/useful rows/terms/GHA evidence.

## Test and registration surfaces

`tests/unit/models/test_coverage.py`; `tests/unit/sources/test_krx_foreign_flows.py`, `test_bea_macro_actuals.py`, `test_aggregator.py`, `test_source_specs.py`, `test_plugin_contract.py`, `test_retry.py`, `test_news_window_coverage.py`; `tests/unit/briefing/test_segments.py`, `test_coverage_badge.py`; `tests/unit/orchestrator/test_source_health.py`; located weekly digest/private-runtime/quality/window receipt suites. Offline MockTransport/injected clock fixtures, focused/fullpytest/Ruff/format/mypy/no-paid/source-policy guards, `git diff --check`.

44existing adapters remain registered; no plugin-count bump. Tier/window/item/outcome lists remain derived from SOURCE_SPECS. No automatic cross-run stateful quarantine; deliberate skip is visible and never recovery or successful data. New BOK/provider adapter requires a separate qualified plan.

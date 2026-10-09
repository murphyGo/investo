# Code Generation Plan: u165 source-lifecycle-and-failure-truth

Date:2026-10-09. Status:CODE COMPLETE7/8; operational step8 pending, Functional Design/NFR authorized by explicit user instruction.
Priority:P1-1. Estimate:12–20h. [Design](../u165-source-lifecycle-and-failure-truth/design-brief.md).
Coverage:US-001/005/007/008; FR-001/006/007/017/021; NFR-001/002/003/005/006/007/008.

## Scope and steps

## Stage Decision

Functional Design and NFR Requirements: Required and completed in unit artifacts; four-state outcome/lifecycle/history and total budget contract need explicit rules. NFR Design: reuse u1/u31/u54/u95 isolation/deadline/history patterns, separate stage skipped (no new logical component). Infrastructure Design: skipped, existing workflows and per-run variables only. Source requirements are listed FR/US/NFR IDs,25-run audit and explicit user development/per-unit commit/push instruction. Source recovery/public rights/runtime activation remain separate.

Extend u1 retry/registry, u22 outcome, u31 health, u54 severity, u102 source-spec and u161 lifecycle follow-up. Preserve u161 completion; upstream503 is independent from its already repaired transport/schema. No new provider/import/source name.

- [x] 1. Characterize Naver/BEA all/one-child errors, genuinezero and3×request budget. Define skipped invariants, legacy loader cases and sparse-news cadence cases.
- [x] 2. Extend `src/investo/models/coverage.py` skipped enum/reason/builders. Use `rg` to enumerate and update every status switch and historic serialization reader together.
- [x] 3. Add activation metadata to `_internal/source_specs.py`, parse overrides once, then emit deterministic skipped/attempted outcomes in `sources/aggregator.py`. Registered import/spec/tier parity remains canonical.
- [x] 4. Repair `sources/krx_foreign_flows.py` all-failure propagation and `sources/bea_macro_actuals.py` failure-vs-zero/60s adapter budget. Reuse `_retry.py`, retain successful children and programmer exceptions, redact diagnostics.
- [x] 5. Update `briefing/segments.py`, `briefing/_reader_enhance/coverage_badge.py`, `orchestrator/source_health.py`, `weekly_ops_digest.py`, `orchestrator/pipeline.py` and other located quality/visual/Step Summary consumers. Ensure skipped does not produce full u160 observation receipts; preserve cursor mode.
- [x] 6. Wire explicit lifecycle override configuration where needed in public/private workflowtemplates and env/runtime tests. Document CONTRIBUTING recovery probe and evidence rules. Validate remaining usable news and disclosed policy gaps before rollout.
- [x] 7. Run focused/full/static/policy checks; record source disablement separately from genuine source recovery.
- [ ] 8. After authorized reviewed-code/pin rollout, observe10distinct scheduled runs; re-enable only after current same-provider parse/useful rows/terms/GHA evidence.

## Test and registration surfaces

`tests/unit/models/test_coverage.py`; `tests/unit/sources/test_krx_foreign_flows.py`, `test_bea_macro_actuals.py`, `test_aggregator.py`, `test_source_specs.py`, `test_plugin_contract.py`, `test_retry.py`, `test_news_window_coverage.py`; `tests/unit/briefing/test_segments.py`, `test_coverage_badge.py`; `tests/unit/orchestrator/test_source_health.py`; located weekly digest/private-runtime/quality/window receipt suites. Offline MockTransport/injected clock fixtures, focused/fullpytest/Ruff/format/mypy/no-paid/source-policy guards, `git diff --check`.

44existing adapters remain registered; no plugin-count bump. Tier/window/item/outcome lists remain derived from SOURCE_SPECS. No automatic cross-run stateful quarantine; deliberate skip is visible and never recovery or successful data. New BOK/provider adapter requires a separate qualified plan.

## Validation progress

Steps1–6 implemented;44 identities retained. New60 tests PASS; source/news regression1065 PASS; independent final166+1 real GenerateStage PASS, review CLOSED with no open findings. Ruff/format682/mypy292/policy4 PASS. All-child request failure, nullable/non-finite BEA values, shared60s deadline, public finalizer/canonical/replay/hash, same-date cohort and Yahoo history guard tested. Existing source/window/event fixture tests explicitly enable their synthetic adapters so transport characterization remains independent of lifecycle defaults; new default-skip tests verify non-attempts separately. Full regression and strict docs precede step7 completion; ten scheduled observations remain step8 pending.

Final local gate2026-10-10:6357 tests PASS541.11s; independent final311 PASS/no open findings; Ruff/format682/mypy292/policy4/strict docs/Material/diff PASS. Full exhaustive contracts caught old synthetic activation, model export and public limitation-map expectations; corrected contracts and real finalizer coverage pass. u164 exact remote CI37944367981 SUCCESS6292 PASS336.93s.

# Code Generation Plan: u166 domestic-price-source-qualification

Date:2026-10-09. Status:PLANNED, Functional Design/NFR draft not approved.
Priority:P1-2. Estimate:4–8h diagnosis; qualification depends on externalaccess/terms.
[Design](../u166-domestic-price-source-qualification/design-brief.md). Debt:DEBT-068.
Coverage:US-001/002/003/007/008; FR-001/006/008/010/017/021; NFR-001/002/003/005/006/007/008.

## Steps and scope

- [ ] 1. Reconfirm official fields, nextbusinessday update, permitteduse and free/accountlimits. Obtain authorized private response through existingkeypath for an availabledate; expose counts/resultcodesonly.
- [ ] 2. Characterize `sources/fsc_krx_index_price.py` `_extract_rows`, `_rows_to_items`, `_candidate_dates`: actualnames/totalCount/paging/badfields/schema/dategap. Record precise cause; syntheticfixture alone is not evidence of livenames/data.
- [ ] 3. Add fixed diagnostics and entire60s budget using sharedretry; repair request/parser only with currentofficial evidence, retain sourceerror isolation and datebounds.
- [ ] 4. Verify basisdate/freshness through `briefing/segments.py`, domesticpublic projection, snapshots/watchpoints/verifiedfacts and u148/u149containment. Validstale remainswithheld,200alone does not restorecorehealth.
- [ ] 5. Evaluate KRX OpenAPI separatekey/publicdisplay/indexfields/GHA versus existingYonhap fallback. Produce ship-now/defer/reject. Do notadd adapter or swapowner on unresolvedqualifications.
- [ ] 6. Run focused/full/static/policy validation. Record diagnosticcode completion separately fromblocked sourcequalification. DEBT-068 staysopen unless qualifiedfallback is integrated/accepted.

## Required surfaces and tests

Existing identity price/tierS/domesticKST and `_DOMESTIC` item/outcome SOURCE_SPECS routing, core in `briefing/segments.py`, existing secret/config names and44plugin registration retained. No new import/spec/tierentry in initialdiagnostic work.

Tests: `tests/unit/sources/test_fsc_krx_index_price.py`, `test_fsc_krx_stock_price.py`, `test_retry.py`, `test_aggregator.py`, `test_source_specs.py`, `test_plugin_contract.py`; `tests/unit/briefing/test_segments.py`; domesticprice/u148/u149containment suites located with `rg`. Offline MockTransport and schema-onlysynthetic fixtures; focused/fullpytest, Ruff/format, mypy, no-paid/sourcepolicy guards, `git diff --check`.

Newqualified source requires its own module/name/auth/cost/rate/license/fields/cadence/source-spec/tier/window/config/plugin/diagnostics/consumer plan. A justified no-qualified-source decision is a validqualification result; it is not productionrecovery.

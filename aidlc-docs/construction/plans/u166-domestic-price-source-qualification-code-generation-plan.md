# Code Generation Plan: u166 domestic-price-source-qualification

Date:2026-10-09. Status:CODE COMPLETE6/7; source-only post-push probe step7 pending; Functional Design/NFR authorized by explicit user development/per-unit commit instruction.
Priority:P1-2. Estimate:4–8h diagnosis; qualification depends on externalaccess/terms.
[Design](../u166-domestic-price-source-qualification/design-brief.md). Debt:DEBT-068.
Coverage:US-001/002/003/007/008; FR-001/006/008/010/017/021; NFR-001/002/003/005/006/007/008.

## Stage Decision

Functional Design and NFR Requirements required and finalized in unit artifacts: bounded authenticated diagnosis, truthful schema/paging/date/error exclusions and public rights gates. NFR Design reuses u1/u95 deadline/parse-isolation and u109/u148/u149 public containment patterns; separate stage skipped because no new logical service. Infrastructure Design skipped: one manually dispatched read-only GitHub Actions probe in the existing public runner, existing source keys and no publisher/model/notifier permissions. Listed FR/US/NFR IDs and25-run source audit are requirements. User's development instruction authorizes implementation and per-unit integration; private runtime/source-public-use activation remains separate.

## Steps and scope

- [x] 1. Reconfirm official fields/V2 endpoint/page count, nextbusinessday update, permitteduse and free/accountlimits from primary catalog/current downloadable guide. Manual authenticated runner diagnosis is explicitly step7 after workflow delivery; no raw response is public.
- [x] 2. Characterize `sources/fsc_krx_index_price.py` `_extract_rows`, `_rows_to_items`, `_candidate_dates`: actualnames/totalCount/paging/badfields/schema/dategap. Record confirmed V2 URL/one-page mismatch and precise live receipts in step7; synthetic fixtures alone are not evidence of live names/data or historical25-run cause.
- [x] 3. Add fixed diagnostics and entire60s budget using sharedretry; repair request/parser only with currentofficial evidence, retain sourceerror isolation and datebounds.
- [x] 4. Verify basisdate/freshness through `briefing/segments.py`, domesticpublic projection, snapshots/watchpoints/verifiedfacts and u148/u149containment. Validstale remainswithheld,200alone does not restorecorehealth.
- [x] 5. Evaluate KRX OpenAPI separatekey/publicdisplay/indexfields/GHA versus existingYonhap fallback. Produce ship-now/defer/reject. Do notadd adapter or swapowner on unresolvedqualifications.
- [x] 6. Run focused/full/static/policy validation. Record diagnosticcode completion separately fromblocked sourcequalification. DEBT-068 staysopen unless qualifiedfallback is integrated/accepted.

- [ ] 7. After reviewed code/workflow push, dispatch source-only probe on exact main SHA and availabledate. Record sanitized receipt; keep public rights, private activation and ten scheduled recovery separate.

## Required surfaces and tests

Existing identity price/tierS/domesticKST and `_DOMESTIC` item/outcome SOURCE_SPECS routing, core in `briefing/segments.py`, existing secret/config names and44plugin registration retained. No new import/spec/tierentry in initialdiagnostic work.

Tests: `tests/unit/sources/test_fsc_krx_index_price.py`, `test_fsc_krx_stock_price.py`, `test_retry.py`, `test_aggregator.py`, `test_source_specs.py`, `test_plugin_contract.py`; `tests/unit/briefing/test_segments.py`; domesticprice/u148/u149containment suites located with `rg`. Offline MockTransport and schema-onlysynthetic fixtures; focused/fullpytest, Ruff/format, mypy, no-paid/sourcepolicy guards, `git diff --check`.

Newqualified source requires its own module/name/auth/cost/rate/license/fields/cadence/source-spec/tier/window/config/plugin/diagnostics/consumer plan. A justified no-qualified-source decision is a validqualification result; it is not productionrecovery.

Implementation: normal fetch delegates to immutable per-call diagnostics report; no adapter instance state. V2 URL/page fields validated, total count/row completeness and cross-page count checked, incomplete-without-usable is failure; existing usable siblings survive. Fixed enums only, no provider message/cause/query URL. Numeric zero/exact integer and basis-date bounds validated. New37 tests PASS; focused source/retry/plugin/domestic/u149 regression152 PASS before final3 paging cases. Full final gate on u16521c979e4 follows.

Final local gate2026-10-10:6400 PASS516.48s. Fresh independent144 PASS3.44s/review CLOSED, Ruff/format684/mypy292/policy4/strict docs/Material/diff PASS. Source qualification may remain defer after a successful diagnosis; neither public redistribution nor private deployment is approved by this code validation.

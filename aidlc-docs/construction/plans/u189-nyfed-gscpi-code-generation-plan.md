# u189: nyfed-gscpi

## Stage Decision

- Functional Design: Required, completed in [shared design](../macro-sources-20261030/functional-design/design.md).
- NFR Requirements: Required, completed in [NFR](../macro-sources-20261030/nfr-requirements/requirements.md).
- Reason: new external source contract, observation clock and public attribution.
- Source of requirements: user “진행시켜”, FR-001/002, US-001/002/008, NFR-001/002/003/004/005/008.
- NFR Design / Infrastructure Design: reuse streaming retry, registry/aggregator and publisher; no new service.

## Source facts / deduplication

- Source: [NY Fed GSCPI](https://www.newyorkfed.org/research/policy/gscpi); no-key structured access and dated response hashes: [qualification](../macro-sources-20261030/qualification.json).
- Cadence: fourth business day of month, approximately 10am ET. Cost: free successful requests; fixed rate limit unverified, bounded daily collection and one retry.
- Coverage gain: Monthly global supply/transport pressure context absent from current CPI/PPI/rates. Existing treasury-auctions, treasury-rates, nyfed-reference-rates, fred-macro, cboe-volatility-indices remain distinct.
- Terms and numeric/clock limits: shared NFR; parser, fields and output contracts: shared FD.
- Adapter: `src/investo/sources/nyfed_gscpi.py::NyfedGscpiAdapter`, name `nyfed-gscpi`; category macro, US-only.
- Surfaces: sources/__init__.py import, _internal/source_specs.py descriptor (derives tier/window/segment/outcomes), plugin-contract fixture registry; optional macro reference, not core health or required macro-actual classification. Generic skipped/failed/zero diagnostics unchanged. No env or provider key.
- Public output: validated shared model → native market panel and legacy channel anchor block, canonical attribution and observation date. No new public dashboard metrics or LLM-specific source branches.

## Execution

- [x] 1. Qualify source and complete FD/NFR contracts above.
- [x] 2. Implement adapter and shared metadata validation.
- [x] 3. Register US routing and deterministic native/legacy output.
- [x] 4. Add fixture/edge/integration tests, source failure isolation and no-paid guards.
- [x] 5. Run independent code review, resolve findings and record build/cross-check evidence.

## Acceptance

At most one source item; correct latest complete observation and units; observation/cutoff/collection/vintage clocks distinct. Missing, stale, malformed, oversized or conflicting data never renders an invented zero or current release. Output source-bound and attributed, unchanged news reservation and sibling source behavior. Tests: tests/unit/sources/test_macro_sources_20261030.py, tests/integration/test_macro_sources_publication.py, tests/unit/sources/test_plugin_contract.py, plus existing publication/reader/aggregator regression suites and scripts/check_no_paid_apis.py. No commit/deploy by this implementation stage.

Completion2026-10-30: implementation/review/quality/cross-check complete locally. [Validation](../macro-sources-20261030/validation.md). Registry47→50;211 integrated regression tests; full7,847PASS/3initialfail/1knownskip followed by15PASS correcting all failures. Release and first scheduled runtime observation remain separate.

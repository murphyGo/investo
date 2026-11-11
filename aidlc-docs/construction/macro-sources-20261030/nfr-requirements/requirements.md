# NFR and source qualification

- [x] Reuse Python/httpx/shared streaming retry and aggregator failure isolation; no dependencies or keys.
- [x] Set explicit memory/request/row/clock limits before implementation.
- [x] Bound publication rights to agency-produced statistics and index aggregates.

FR-001/002, US-001/002/008, NFR-001/002/003/004/005/008 and R10/R13 apply. No additional LLM call, subscription, key or runtime service. Fixed endpoints only. Shared retry max 2 attempts, total 30s/source, response decoded-byte caps: TGA 64KiB, GSCPI 512KiB, OFR 5MiB. Parse caps: TGA32 rows, GSCPI600 observation rows/240 columns, OFR10000 aggregate points. Nonfinite values, booleans, malformed dates, duplicate conflicting values, oversized payloads and schema changes are rejected. Network/schema failures raise SourceFetchError and preserve siblings; stale or absent observations produce empty/zero outcomes, never zero numeric values.

Primary-source research and successful no-key HTTP probes are in qualification.json. Fixed provider rate limits were not documented/verified: this implementation makes one successful GET per source per collection run, with at most one transient retry; OFR retains only one normalized aggregate item. Existing aggregator collection is the per-run reuse boundary.

Treasury: Fiscal Service's own Daily Treasury Statement cash-account numbers, attributed and linked to the official dataset/API. Open Data Policy https://fiscaldata.treasury.gov/data/about-us/901-1%20Open%20Data%20Policy.pdf ; factual government account data only, no seals or third-party prose. Site HTML returned403 to browser tooling; direct JSON200 established structured access. No blanket rights inference for other content.

NY Fed: https://www.newyorkfed.org/privacy/termsofuse permits automated access/storage/distribution subject to attribution, notices, modifications clearly attributed and no endorsement. Preserve the index title, © Federal Reserve Bank of New York, terms link and research-index disclaimer; formatting/selection by Investo, no raw third-party input redistribution. Official GSCPI page and CSV are linked in qualification.json.

OFR: https://www.financialresearch.gov/legal-notices/ distinguishes federal employee work from third-party copyright. Scope is OFR's published aggregate index only, with OFR attribution; no vendor constituent data or logo. https://www.financialresearch.gov/financial-stress-index/ documents daily updates with two-business-day lag and possible corrections. Display both caveats.

Tests use clearly marked synthetic edge payloads plus byte-exact live source fixtures with endpoint/time/sha256 provenance. No auth values in logs, metadata or fixtures. Independent review and full quality gate required before completion. Operational schedule/first-run acceptance is separate from local code completion.


## 2026-11-11 deployment qualification correction

The current official CSV was fetched before production promotion: decoded338194bytes, sha256`ef5109319ee888d704a5512ec4790b929c38d07069085138765f1229125f4328`. It uses Excel1900 month serial headers, `#N/A` missing cells and up to18 fractional digits, unlike the October30 fixture. The adapter now accepts the observed serial representation (ASCII5digits, epoch1899-12-30, month-first, years2000–2099) alongside named-month vintages; equivalent duplicate vintages still fail. Sparse vintage months are valid.

GSCPI values remain finite plain decimals with absolute magnitude≤100, maximum18 fractional digits and3 integer digits. Bounds and conflicting duplicates are checked before rounding; display uses six decimal places with half-even rounding under an explicit32-digit Decimal context. Both publication paths disclose this formatting. Unknown missing/error strings, scientific notation, malformed/future vintages and conflicts remain closed failures or empty future-cutoff results as specified. Existing network/row/byte/time caps are unchanged. New byte-exact fixture retains NYFed attribution/terms and is paired with precision, stale-cutoff, duplicate and malformed-input tests.

Local correction verification:142 tests pass on public and runtime candidates; Ruff/format and mypy pass. Exact final-SHA CI and production pin readback will be recorded in the release receipt.

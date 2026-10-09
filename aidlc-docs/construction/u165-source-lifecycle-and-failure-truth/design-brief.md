# u165 Functional Design / NFR: source lifecycle and failure truth

Status:DRAFT, 2026-10-09; not approved. Priority:P1-1.
Evidence: [source review](../source-reliability-20261009/review.md).

## Problem, facts and scope

Binance/CNBC/FSC policy failed25/25, Yahoo news now404. Naver two-market410 is swallowed intozero21times; BEA catches every child fetch error and once spends180.069s beforezero. u1 retry already treats403/404/410/451 as terminal. u31 health cannot see swallowed failures; u161 HTTPS/date repair is already implemented, while current FSC problem is upstream503.

One output behavior is extended: truthful bounded source attempts and explicit inactive-source state. Reuse u1/u22/u31/u54/u102/u161. No second registry, generic circuit-breaker service, persistent automatic quarantine, paid/provider/proxy bypass or body-enrichment activation.

## Fixed lifecycle rules

- Extend canonical `SourceSpec` with `default_enabled=True` and bounded reason enum. Retain registered historical sources, names and routing.
- Proposed default disabled: `binance-crypto-market` (region_denied), `cnbc-top-news` (access_denied), `yahoo-finance-news` (endpoint_removed), `korea-policy-rss` (upstream_unavailable), `krx-foreign-flows` (endpoint_removed). Remaining news coverage is checked before rollout; unavailable policy/supply functions remain visible.
- Parse `INVESTO_SOURCE_ENABLE` / `INVESTO_SOURCE_DISABLE` as exact comma-separated known names before I/O. Unknown names/conflicting lists fail explicitly. Recovery probe requires explicit enable; it does not establish public rights or recovery.
- Add `SourceStatus=skipped`; `SourceOutcome.skipped` requires0items, enumerated skipreason, no failure/transient/latest_item timestamp. It is never ok/zero/failed. Historic three-status ledgers remain readable without rewrite.
- Attempted counts exclude skipped; configured/skipped count and reason remain visible. Missing-category/core/macro capability is not restored by skipping. All-core-skipped cannot become normal.
- Update history, badges, ops alerts, weekly digest, Step Summary and status switches together. Same target-date reruns do not count as multiple days. u160 skipped-source observation receipts are not successful/full observations; cursor completeness cannot be fabricated.

## Failure and budget rules

- Naver all child `SourceFetchError` → aggregate failure; one successful market survives with sanitized partial-child counts. Valid empty market is distinct fromHTTP410. Programmer exceptions propagate.
- BEA all child request/API errors → failure; valid API with no rows →zero. Preserve completed successful series; expose enum counts for API/schema/line/period exclusions, no raw payload/value/key URLs.
- BEA entire adapter budget60s, not3×60s. Requests use remaining budget, expire with completed valid children retained or failed if none. Cancellation cleans children; don't swallow programmer errors. Existing shared retry/Retry-After/bodycap remain.
- Sparse Congress/senate/Fed publications are not declared failures fromzero alone; expected cadence and request/parser evidence determine health. No synthetic macro actuals or future estimates.

## Candidate boundaries

Existing endpoints/auth/source owners and current responses are in the review. No adapter added here. Nasdaq/Fed/SEC/CFTC news can retain usable US news; a verified coverage check precedes CNBC/Yahoo deactivation. Korea policy gaps are shown honestly after FSC is skipped.

BOK policy RSS is defer: official no-key RSS100items locally, announcement-driven, numerical rate not published in inspected material. Per-work copyright/attribution, GHA and date schema remain unverified. A later qualified `bok-policy-rss` needs its own module/name, tierS/domestic spec, news-window opt-in, fixtures/dedup/plugin-count checks. It must not impersonate FSC policy identity or equalcoverage.

## Acceptance and NFR

1. Inactive sources make0HTTP calls, emit skipped+reason; overrides and invalid names tested.
2. All-child failures become failed, validzero stayszero, partial success survives; programmer errors still propagate.
3. BEA attempt≤60s with valid siblings retained; R13 sentinel keys absent from logs/metadata/fixtures.
4. History compatibility/accounting/public gaps remain truthful; skip cannot create core health or observed-news receipts.
5.44existing plugin/spec/tier/routing parity retained; no event/body mode change.

NFR-001/002/003/005/006/007/008: no new external persistence/secret, bounded per-run I/O and diagnostics, no paid fallback, rawdata/private credentials remain private. Feed recovery and alternate source qualification remain separate deployment gates.

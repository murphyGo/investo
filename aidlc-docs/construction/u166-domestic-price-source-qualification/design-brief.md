# u166 Functional Design / NFR: domestic price source qualification

Status:DRAFT, 2026-10-09; not approved. Priority:P1-2.
Primary-source facts: [review](../source-reliability-20261009/review.md).

## Facts, unresolved diagnosis and scope

`fsc-krx-index-price`/`sources/fsc_krx_index_price.py`, price/tierS/domesticKST/core. OwnerFSC/sourceKRX, [official dataset](https://www.data.go.kr/data/15094807/openapi.do); endpoint `https://apis.data.go.kr/1160100/service/GetMarketIndexInfoService/getStockMarketIndex`. Existing keys `INVESTO_KRX_SERVICE_KEY` / `INVESTO_DATA_GO_KR_SERVICE_KEY`; names 코스피/코스닥/코스피 200. Fields include basisdate/name/close/change/OHLC/volume.

25runs0usable (23zero/2network). Raw authenticated response unavailable locally; HTTP200 does not distinguish totalCount0, actualname mismatch, pagination/schema exclusion or date gaps.7-daylookback already exists. Official description says nextbusinessday13KST update despite generic realtime metadata. Delay alone cannot explain sustainedzero.

Current official text says KOGL4 and prohibits unauthorized third-party provision/redistribution. Free API access alone does not qualify new public fallback/expanded use; this phase does private diagnosis and qualification. No paid purchase/accountupgrade is proposed.

Connect DEBT-068/u36/u67/u138/u148/u149; no reintroduced Stooq, OTP/browser/scraper bypass, stale-to-current promotion, fabricatedindex or numeric-gate weakening. Scope is one family: domesticindex diagnostics/source qualification. Investorflow replacement needs independent field/access evidence.

## Fixed rules

- Record only status/resultcode, total_count, returned_rows, wanted_match_count, valid_row_count, selecteddate and bounded enumerated exclusions.
- Reasons:provider_no_rows/publication_lag/market_closed/name_mismatch/schema_invalid/page_incomplete/auth_or_api_error/network_failed. Marketclosed requires verified calendar evidence, not justzero.
- Keys/queryURLs/rawrowvalues/fullbodies never public. Private authorized capture/replay is in memory or ignored operatorstorage; public fixtures mirror schema, notrestricted originalvalues.
- Entire adapter≤60s. Existing retries respect remaining budget. Page size100, max2pages only if totalCount demands; don't multiply8dates×45s.
- Preserve basisdate/retrievaltime/freshness separately. Old validdata staysstale/withheld under existing public projection, no timestamp rewrite or freshness reset.

## Candidates and decision

FSC: private diagnostics can proceed; public replacement/expanded use rejected without rights basis. KRX OpenAPI: defer, separate key/publicderiveddisplay/basisdate/indexfields/GHA unverified. Existing `yonhap-index-close`: keep best-effort prose-derived fallback with original provenance/freshness; not guaranteed structuredindices. No current qualified YahooKR/Stooq/HTMLmirror substitute established.

A qualified different provider requires a new bounded adapter unit: name/module/auth/free rate/fields/cadence/attribution, source-spec/tier/window/item/outcome registration, plugin count/names, config/fixtures and perindex fallback precedence/corecapability rules. No silent provider swap under FSCname.

## Acceptance / NFR

1. Authorized response/schema replay identifies exactzero cause; tests cover actual names/totalCount/paging/schema/lag without restricted raw publicfixtures.
2. HTTP/API failures differ fromvalidempty; unknowncalendar/permission/keyfacts remain explicit.
3. Sourcequalification has primary publicuse/free/auth/rate/cadence/GHA evidence; unresolved field →defer.
4. No unqualified publicfallback/corepromotion, no stalepass; existing numericcontainment/siblingsegments remaincorrect.
5. Diagnostic codecompletion and sourcegate separate; DEBT-068 closes only when qualifiedstructuredfallback is integrated/accepted.

NFR-001/002/003/005/006/007/008: boundedsourcebudget, zero paid tier, R13/private payloads, actualbasisdate preserved. Public activation/oldarchive rewrite is outside this planning task.

# u166 Functional Design / NFR: domestic price source qualification

Status:AUTHORIZED for implementation, 2026-10-10 KST; user requested unit development/per-unit commit and push. Priority:P1-2.
Primary-source facts: [review](../source-reliability-20261009/review.md).

## Facts, unresolved diagnosis and scope

`fsc-krx-index-price`/`sources/fsc_krx_index_price.py`, price/tierS/domesticKST/core. OwnerFSC/sourceKRX, [official dataset](https://www.data.go.kr/data/15094807/openapi.do); Historical endpoint `https://apis.data.go.kr/1160100/service/GetMarketIndexInfoService/getStockMarketIndex`; current official guide sample uses `https://apis.data.go.kr/1160100/GetMarketIndexInfoService_V2/getStockMarketIndex_V2`. Existing keys `INVESTO_KRX_SERVICE_KEY` / `INVESTO_DATA_GO_KR_SERVICE_KEY`; names 코스피/코스닥/코스피 200. Fields include basisdate/name/close/change/OHLC/volume.

25runs0usable (23zero/2network). Raw authenticated response unavailable locally; HTTP200 does not distinguish totalCount0, actualname mismatch, pagination/schema exclusion or date gaps.7-daylookback already exists. Official description says nextbusinessday13KST update despite generic realtime metadata. Delay alone cannot explain sustainedzero.

Current official text says KOGL4 and prohibits unauthorized third-party provision/redistribution. Free API access alone does not qualify new public fallback/expanded use; this phase does private diagnosis and qualification. No paid purchase/accountupgrade is proposed.

Connect DEBT-068/u36/u67/u138/u148/u149; no reintroduced Stooq, OTP/browser/scraper bypass, stale-to-current promotion, fabricatedindex or numeric-gate weakening. Scope is one family: domesticindex diagnostics/source qualification. Investorflow replacement needs independent field/access evidence.

## Fixed rules

- Record only status/resultcode, total_count, returned_rows, wanted_match_count, valid_row_count, selecteddate and bounded enumerated exclusions.
- Closed reasons: usable/provider_no_rows/name_mismatch/all_filtered/page_incomplete/schema_error/api_error/transport_error/deadline/missing_key. No automatic publication_lag/market_closed classification: verified calendar/publication evidence is required, not merely zero.
- Keys/queryURLs/rawrowvalues/fullbodies never public. Private authorized capture/replay is in memory or ignored operatorstorage; public fixtures mirror schema, notrestricted originalvalues.
- Entire adapter≤60s. Existing retries respect remaining budget. Page size100, max2pages per basis date only if totalCount demands; don't multiply8dates×45s.
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

Manual read-only qualification probe: existing public source key is declared by name only; authenticated response stays in process. Emit closed diagnostics/counts, never raw row values/bodies/key URLs. No schedule, model, publish, notification, private owner/pin/activation or raw artifact upload. The source-only run may establish precise live failure/exclusion facts, not public redistribution rights.

Current guide evidence (2026-10-10): [official DOCX](https://www.data.go.kr/cmm/cmm/fileDownload.do?atchFileId=FILE_000000007632162&fileDetailSn=1), downloaded through the normal catalog download check (needCaptcha=false). V2 endpoint and declared totalCount168 support migration and bounded second-page retrieval. They do not alone prove the historical25-run zero cause. No raw authenticated response is committed. See [qualification](qualification.md).

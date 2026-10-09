# u166 source qualification — 2026-10-10

The existing FSC index adapter can be repaired and diagnosed. A new public fallback does not qualify on the current evidence. DEBT-068 remains open; no new source, provider substitution, private runtime pin or public activation is included.

| Candidate | Verified primary evidence | Decision and remaining gate |
| --- | --- | --- |
| Existing FSC/data.go.kr index service | Current official guide gives V2 service/operation, JSON/XML result types, basis-date/name/OHLC/change/volume fields, pageNo/numOfRows/totalCount. Sample totalCount168 exceeds one100-row page. Catalog says next-business-day13KST, free API, development10,000 requests and approved operating quota extensions. | Ship existing-adapter V2 request, bounded paging and safe diagnosis. Authenticated runner37955145349 on exact e9fb0c9c returned3 useful items for2026-10-07; first100 rows had0 target matches, second71 had3. HTTP200 alone is insufficient. Public expanded/replacement redistribution is unqualified. |
| KRX OpenAPI | Official access steps require an API key application/administrator approval and separate service application/approval. Index catalog exists. | Defer. No existing key is assumed; exact available fields/basis-date/cadence/quota/derived public display and GitHub Actions behavior are unverified. |
| Existing Yonhap numeric headline extraction | Existing registered prose-source path; no new account or provider identity. | Keep best effort with original provenance and date. It does not guarantee a structured KOSPI/KOSDAQ fallback. |
| YahooKR/Stooq/HTML mirrors | No current primary proof of complete usable index data and public rights in this unit. | Reject as an immediate substitute; no scrape/OTP/region bypass or renamed-provider fallback. |

Primary references checked2026-10-10:

- [FSC catalog](https://www.data.go.kr/data/15094807/openapi.do), updated2026-09-07, explicitly states KOGL4/noncommercial/no changes and prohibits unauthorized third-party provision/redistribution even for noncommercial use. Free access does not grant public redistribution permission.
- [Current official FSC usage guide](https://www.data.go.kr/cmm/cmm/fileDownload.do?atchFileId=FILE_000000007632162&fileDetailSn=1). Catalog download check returned needCaptcha=false; the normal downloadable document was inspected locally. Service URL omits the old `/service/` component and uses `GetMarketIndexInfoService_V2/getStockMarketIndex_V2`. Public sample/schema evidence only; no private API rows are used as public fixtures.
- [KRX access steps](https://openapi.krx.co.kr/contents/OPP/INFO/OPPINFO003.jsp) and [index service catalog](https://openapi.krx.co.kr/contents/OPP/USES/service/OPPUSES001_S1.cmd).

The historical25-run audit found23zero/2network outcomes. The old URL and one-page implementation are confirmed differences from current official guidance, but their contribution to all historicalzero outcomes remains unproven without authenticated receipts. Diagnoses must distinguish provider-empty, name filtering, invalid fields/dates, pagination, schema, API and transport failures. No calendar/permission inference is made from an empty body.

Manual live procedure: dispatch `domestic-index-source-probe.yml` on the exact reviewed main commit with an available ISO basis date (initial2026-10-07). Only the existing KRX source secret names are wired; response data remains in memory. Console output is limited to date/status/closed result codes/counts/exclusion reasons. There is no model, publisher, notifier, schedule, raw upload or private runtime credential. The exact SHA/run/conclusion and sanitized receipts are recorded below. A runner success proves collection on that basis date, not public redistribution rights, ten-run recovery or private runtime deployment.

## Authenticated runner qualification receipt

[Source-only run37955145349](https://github.com/murphyGo/investo/actions/runs/37955145349), exact e9fb0c9c49308788871c49eedec5bf6efe498126, completed SUCCESS2026-10-09T15:54:26UTC (2026-10-10KST). [Sanitized counts](evidence/gha-index-source-20261007.json): API00/HTTP200, total171; first page100/target0/valid0, second page71/target3/valid3; selected basis2026-10-07, usable_items3. Thus first-page-only selection demonstrably loses all three target indices on this date; bounded paging restores them. Old URL failure was not separately proven and this receipt does not establish every historical25-run failure cause.

Existing key wiring, exact V2 request, useful rows and target basis-date are now verified in GitHub Actions. Public redistribution, private reviewed pin/activation and ten distinct scheduled recovery observations remain unqualified/pending. No raw price, provider message, index-name list or credentials are stored. Step7 source-only diagnosis is complete; DEBT-068 remains OPEN because no newly qualified structured public fallback was integrated.

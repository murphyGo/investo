# u140 Source Fact Sheet — NYSE Daily TAQ

**Checked**: 2026-07-22
**Candidate**: NYSE Daily TAQ consolidated CTA/UTP historical files
**Disposition**: Reject under current published pricing, licensing, and operational budget
**Probe status**: No agreement, purchase order, account, credential, sample download, provider payload, fixture, parser, local probe, or GitHub Actions probe; only official NYSE product, pricing, client-specification, contract, and policy materials were inspected at Step 0

## Source Facts

| Field | Value |
| --- | --- |
| Source owner | New York Stock Exchange LLC / NYSE Market Data |
| Data family | Daily historical files derived from the U.S. Consolidated Tape Association and UTP SIP feeds |
| Official docs | `https://www.nyse.com/data-products/catalog/daily-taq`, `https://www.nyse.com/market-data/historical`, the official Daily TAQ client specifications, historical pricing schedule, and NYSE policy/contract library |
| Endpoint/delivery | Current files are delivered through NYSE Managed File Transfer; historical files are available through FTP or AWS Cloud delivery. This is whole-market file delivery, not a public ticker-filtered API. |
| Auth/contract | Client setup requires the appropriate agreement, purchase order, NYSE approval, and issued credentials. The specification states that the latest five days are obtained through MFT and older files through historical delivery. |
| Cost and no-paid evidence | Fail. The current commercial schedule lists an ongoing Daily TAQ subscription at USD 3,800/month with a minimum 12-month subscription. It includes the preceding 12 months; earlier history is USD 500 per data-content month. One-time back history lists USD 3,800 per data-content month for the first 12 months and USD 500 thereafter. Academic pricing is contact-based, not a permanent-free entitlement. |
| Rate and request budget | No ticker-level request budget applies. Delivery is by large daily files; the reviewed specification gives representative sizes of about 649 MB/25 million rows for Trades, 17 GB/682 million rows for Quotes, and 2.2 GB/114 million rows for NBBO. |
| Format | Gzip-compressed pipe-delimited flat files for all trades, all quotes, NBBO, master, administrative, and related daily datasets. |
| Key fields | Trade timestamp, symbol, exchange, price, volume, sale condition, correction/cancel context; quote timestamps, bid/ask prices and sizes; NBBO and symbol/master metadata. |
| Required symbols | The catalog states all issues traded across NYSE, Nasdaq, and regional exchanges under CTA/UTP consolidation. SPY and the 11 Select Sector ETFs are therefore within the intended product universe, but exact dated rows were not downloaded because cost and rights fail first. |
| Update cadence | T+1/previous-trading-day product. The specification lists same-night publication targets that vary by file, approximately 9 p.m. to 2 a.m. Eastern, but no measured u140 run evidence was collected. |
| Historical range | 1993 to present, well beyond the 63-trading-day requirement, but access is paid. |
| Adjustment semantics | Raw SIP trades and quotes are not a split/dividend-adjusted daily series. Corporate actions and historical symbol changes require separate normalization before comparable bars can be published. |
| Venue/volume semantics | Consolidated CTA/UTP trades can support truthful consolidated tape OHLCV when sale-condition, cancel/correction, and eligibility rules are correctly applied. This is technically superior to venue-only feeds. |
| Attribution | Contract and policy obligations apply; no anonymous attribution-only public-display grant is published. |
| Caching and raw retention | Use, storage, and redistribution are governed by the purchased product agreement and NYSE market-data policies. The public catalog does not grant free indefinite public raw-file retention. |
| License/public display | Fail for the current public MVP. NYSE policy states that external redistribution of historical data requires a specific NYSE license and payment of the relevant fee. A product subscription does not itself establish a zero-cost public derived-display entitlement. |
| Existing Investo overlap | No Daily TAQ order, license, MFT/FTP/AWS credential, downloader, parser, adapter, `SourceSpec`, route, fixture, dependency, secret, or workflow exists. Other exchange-feed and daily-summary reviews are different products. |
| Proposed `source_name` | None; rejected before runtime design |
| Proposed adapter path | None; rejected before runtime design |
| Routing surfaces | None; no registry, tier, route, config, dependency, fixture, raw store, workflow, or public output change |
| Degradation behavior | Not applicable while rejected; missing files, symbol events, late/corrected trades, file revisions, and delivery failures were not probed |

## Dated Primary-Source Evidence

Checked on 2026-07-22:

1. `https://www.nyse.com/data-products/catalog/daily-taq`
   - describes all trades and quotes for all issues traded on NYSE, Nasdaq, and
     regional exchanges for the previous trading day;
   - identifies U.S. Consolidated Tape coverage, CTA/UTP markets, NBBO, master, and
     administrative files, with history from 1993 to present and a purchase flow.
2. `https://www.nyse.com/market-data/historical`
   - identifies Daily TAQ as end-of-day/T+1 historical market data and documents
     managed/cloud delivery families.
3. `https://www.nyse.com/publicdocs/nyse/data/NYSE_Historical_Market_Data_Pricing.pdf`
   - lists Daily TAQ commercial ongoing access at USD 3,800/month with a 12-month
     minimum and separately prices older back history;
   - provides contact-based academic pricing rather than a published permanent-free
     entitlement.
4. `https://www.nyse.com/publicdocs/nyse/data/Daily_TAQ_Client_Spec_v4.1b.pdf`
   - defines the CTA/UTP-derived archive, 1993-present range, file inventory,
     delivery timing, and representative file sizes/row counts;
   - documents whole-market trades, quotes, NBBO, master, and administrative files.
5. `https://www.nyse.com/publicdocs/nyse/data/Daily_TAQ_Client_Spec_v3.3b.pdf`
   - documents the agreement, purchase-order, approval, credential, and delivery
     setup needed before access.
6. `https://www.nyse.com/publicdocs/nyse/data/NYSE_Market_Data_Complete_Policy_Package.pdf`
   - requires a specific NYSE license and relevant fee for external redistribution
     of historical data.
7. `https://www.nyse.com/market-data/pricing-policies-contracts-guidelines`
   - is the current official hub for the governing pricing, policies, contracts,
     guidelines, and data-use declarations.

## Deduplication Evidence

A repository scan across runtime, tests, scripts, workflows, dependencies, AIDLC
state, and source-planning surfaces found no exact NYSE Daily TAQ integration,
purchase, agreement, delivery credential, downloader, parser, registry entry,
`SourceSpec`, route, fixture, dependency, secret, or workflow. Cboe DataShop Equity
EOD Summary is a different vendor's precomputed daily file; IEX, MIAX, and MEMX are
venue-only message products. None supplies or licenses consolidated NYSE Daily TAQ.

## Gate Decision

| Binding gate | Result | Reason |
| --- | --- | --- |
| Official terms and public derived-display rights | Fail as a free right | Historical external redistribution requires a specific NYSE license and relevant fee |
| Free access for 63+ daily OHLCV bars | Fail | History is deep, but the commercial subscription is USD 3,800/month with a 12-month minimum and back history is paid |
| Exact 12-symbol coverage | Strongly indicated, not payload-probed | Product scope is consolidated U.S. issues, but no file was purchased or sampled |
| At-most-36-hour freshness | Provisional technical pass, not measured | T+1 product with documented same-night file targets; no run evidence |
| Truthful volume/price semantics | Provisional technical pass | Consolidated trades can yield truthful OHLCV if corrections and sale conditions are handled correctly |
| Bounded local/GitHub Actions operation | Fail | Whole-market files are hundreds of MB to tens of GB per day; 63-day bootstrap is not a bounded 12-symbol API job |
| Five bounded GitHub Actions probes | Not run | Price, license, and operational gates fail before Step 1 and Step 2 |
| No paid plan/trial/secret exposure | Fail | Purchase, agreement, approval, credentials, and recurring payment are required |
| Public/raw retention contract | Fail as a free right | Retention and redistribution remain governed by the paid agreement/policy package |

**Disposition: `reject under current published pricing, licensing, and operational
budget`.** Reconsider only if NYSE publishes a permanent-free entitlement with an
explicit public derived-display license and a bounded ticker-filtered delivery surface.
Then repeat Step 0 and verify exact 12-symbol continuity, sale-condition/correction
rules, adjustment input, posting SLA, request/byte budget, raw retention, and five-run
reliability. No agreement, order, account, credential, sample, payload, fixture,
adapter, public output, workflow, local probe, GitHub Actions probe, or TECH-DEBT item
is created.

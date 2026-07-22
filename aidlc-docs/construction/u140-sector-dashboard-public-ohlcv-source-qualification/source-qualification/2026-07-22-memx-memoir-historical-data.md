# u140 Source Fact Sheet — MEMX MEMOIR Historical Data

**Checked**: 2026-07-22
**Candidate**: MEMX MEMOIR Historical Data using historical MEMOIR Last Sale, Top, or Depth
**Disposition**: Reject for current public MVP cost/rights certainty and metric fitness
**Probe status**: No agreement, order form, connectivity request, account, credential, provider payload, fixture, decoder, local probe, or GitHub Actions probe; only official MEMX FAQ, Rulebook, user manual, fee schedule, agreement/document library, and market-data policy materials were inspected at Step 0

## Source Facts

| Field | Value |
| --- | --- |
| Source owner | MEMX LLC / Members Exchange |
| Data family | Historical prior-day versions of proprietary MEMX venue Depth, Top of Book, and Last Sale message feeds |
| Official docs | `https://info.memxtrading.com/equities-trading-resources/us-equities-faq/`, `https://info.memxtrading.com/memx-user-manual/`, current Rulebook, fee schedule, and the agreements/policies linked from `https://info.memxtrading.com/membership-connectivity-and-market-data-documents/` |
| Endpoint/delivery | MEMX says historical products are available through modern cloud APIs, but the reviewed public FAQ does not publish an anonymous endpoint, request schema, or self-service daily-bar route. |
| Auth/contract | A market-data-only subscriber must execute a Market Data Agreement and request connectivity. Use and distribution, including derived data, must be described in an Exchange Data Order Form/System Description and approved by MEMX. |
| Cost and no-paid evidence | Fail as published evidence. No permanent-free historical API entitlement or exact historical-product fee is stated. The current corresponding feed schedule charges Last Sale USD 500/month internal, USD 2,000/month external, and USD 2,000/month Digital Media Enterprise; Top is USD 750/month internal and USD 2,000/month for either external or Digital Media Enterprise use. Top/Last non-display usage is listed as free, but that does not grant free source access or public distribution. |
| Rate and request budget | No historical cloud-API rate limit, daily request budget, or bounded GitHub Actions contract is published in the reviewed materials. |
| Format | Historical API over prior-day MEMOIR feed data. Exact response framing/serialization was not opened because agreement and rights gates fail; underlying products are protocol messages, not precomputed daily bars. |
| Key fields | Depth contains displayed orders, executions, cancellations, modifications, order identifiers, and administrative messages. Top contains MEMX top-of-book quotations. Last Sale contains MEMX execution information, including reporting/cancellation/correction behavior described by the FAQ. |
| Required symbols | MEMX trades thousands of Tape A/B/C securities, but exact historical trade continuity for SPY, XLB, XLC, XLE, XLF, XLI, XLK, XLP, XLRE, XLU, XLV, and XLY was not verified because the binding gates fail first. |
| Update cadence | The official user manual describes prior-day historical versions. Exact cloud posting time and the u140 at-most-36-hour SLA were not published or measured. |
| Historical range | Not stated in the reviewed product/FAQ materials. A 63-trading-day retained window cannot be assumed without entitlement or payload evidence. |
| Adjustment semantics | Raw venue messages provide no split/dividend-adjusted daily series. Corporate-action normalization requires a separate authoritative source. |
| Venue/volume semantics | MEMX-only quotes and executions. Any aggregated OHLCV would exclude away-market and off-exchange activity and cannot be labeled consolidated U.S. ETF volume. |
| Attribution | Delayed displays require an appropriate delay message; this is not a simple attribution-only license. Exact display wording and use must remain within approved MEMX materials. |
| Caching and raw retention | Storage, processing, and dissemination are governed by the Market Data Agreement and approved System Description. No anonymous public raw-retention grant is published. |
| License/public display | Fail as an explicit free self-service grant. Derived Data is generally described as non-fee-liable when not reversible or substitutive, but distributors still must declare it through the Order Form/System Description, obtain approval, and observe feed-specific exceptions and subscriptions. MEMX may require changes to use, and the current fee schedule separately prices external/digital-media distribution. |
| Existing Investo overlap | No MEMX/MEMOIR historical API, agreement, order form, decoder, adapter, `SourceSpec`, route, fixture, dependency, secret, or workflow exists. Direct IEX and MIAX venue-feed reviews are similar architectures but different exchange products. Issuer ticker strings such as `MEMX` are unrelated. |
| Proposed `source_name` | None; rejected before runtime design |
| Proposed adapter path | None; rejected before runtime design |
| Routing surfaces | None; no registry, tier, route, config, dependency, fixture, raw store, workflow, or public output change |
| Degradation behavior | Not applicable while rejected; entitlement expiry, missing days/symbols, corrections, protocol revisions, throttling, and posting delays were not probed |

## Dated Primary-Source Evidence

Checked on 2026-07-22:

1. `https://info.memxtrading.com/equities-trading-resources/us-equities-faq/`
   - defines MEMOIR Depth, Top, and Last Sale as MEMX venue order/quote/execution
     feeds and says historical versions are consumed through modern cloud APIs;
   - requires a market-data-only subscriber to complete a Market Data Agreement and
     request connectivity for distribution.
2. `https://info.memxtrading.com/memx-user-manual/` and the linked official manual
   - describe MEMOIR Historical Data as prior-day versions of Depth, Top, and Last
     Sale.
3. `https://info.memxtrading.com/wp-content/uploads/2026/06/MEMX-Rulebook-6.22.26clean.pdf`
   - Rule 13.8 defines Depth as displayed-order/execution/cancellation/modification
     messages, Top as MEMX top-of-book, Last Sale as MEMX execution information, and
     MEMOIR Historical Data as historical equities data.
4. `https://info.memxtrading.com/equities-trading-resources/us-equities-fee-schedule/`
   - currently lists Top and Last Sale external-distributor fees of USD 2,000/month
     and Digital Media Enterprise fees of USD 2,000/month;
   - lists internal-distributor fees of USD 750/month for Top and USD 500/month for
     Last Sale, while non-display usage alone is marked free;
   - defines an external distributor as sending Exchange Data outside its own
     organization and non-display use as machine access without natural-person
     display.
5. `https://info.memxtrading.com/membership-connectivity-and-market-data-documents/`
   - publishes the Market Data Agreement, Market Data Policies, Subscriber Agreement,
     and Exchange Data Order Form/System Description required for data access/use.
6. `https://info.memxtrading.com/wp-content/uploads/2023/01/MEMX-Market-Data-Policies.pdf`
   - requires approval and an Order Form/System Description for delayed-data external
     distribution;
   - says derived data is generally not fee-liable but may have feed-specific
     exceptions, and requires distributors to describe derived data in the Order Form
     and System Description;
   - makes entitled recipients liable for applicable fees and requires both internal
     and external fees when both distribution modes apply.

## Deduplication Evidence

A repository scan across AIDLC docs, runtime, configuration, tests, scripts,
workflows, dependencies, and source-planning surfaces found no exact `MEMOIR
Historical Data`, `memxtrading.com` market-data integration, agreement/order form,
decoder, registry entry, `SourceSpec`, route, fixture, dependency, secret, or workflow.
Direct IEX HIST and MIAX historical-feed reviews already establish the general risk of
venue-only messages, but neither supplies or licenses MEMX data. Symbols containing
`MEMX` in issuer/security reference data do not constitute source overlap.

## Gate Decision

| Binding gate | Result | Reason |
| --- | --- | --- |
| Official terms and public derived-display rights | Fail as an explicit free right | Agreement, Order Form/System Description, and MEMX approval are required; derived-data fee treatment has exceptions and cannot be presumed |
| Free access for 63+ daily OHLCV bars | Fail as published evidence | No anonymous/permanent-free historical entitlement, stated retained range, or precomputed daily bars are published |
| Exact 12-symbol coverage | Unproven | Broad NMS-symbol scope does not prove one qualifying MEMX trade on every symbol/date |
| At-most-36-hour freshness | Unproven | Prior-day versions exist, but the cloud posting deadline was not published or measured |
| Truthful volume/price semantics | Fail for the current product contract | Derived bars would be MEMX-only, not consolidated ETF OHLCV |
| Bounded local/GitHub Actions operation | Unproven | Cloud API is promising, but endpoint, auth, quota, response size, and daily-file shape are not publicly pinned |
| Five bounded GitHub Actions probes | Not run | Rights/cost certainty and venue-only metric fitness fail before Step 1 and Step 2 |
| No paid plan/trial/secret exposure | Fail as a public entitlement | Corresponding feed access/distribution is fee-scheduled and agreement-controlled; no application was submitted |
| Public/raw retention contract | Fail as an anonymous right | Retention and dissemination depend on the executed agreement and approved System Description |

**Disposition: `reject for current public MVP cost/rights certainty and metric
fitness`.** Reconsider only if MEMX publishes a permanent-free historical entitlement
with an explicit approved public derived-display configuration, and Investo explicitly
accepts MEMX-only price/volume labels. Then repeat Step 0 and verify the retained
range, exact 12-symbol continuity, API contract, corrections, posting SLA, corporate
actions, request/byte budget, and five-run reliability. No agreement, order form,
account, credential, provider payload, fixture, adapter, public output, workflow,
local probe, GitHub Actions probe, or TECH-DEBT item is created.

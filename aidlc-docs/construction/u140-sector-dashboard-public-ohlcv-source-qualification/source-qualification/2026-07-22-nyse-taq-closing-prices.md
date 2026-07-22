# u140 Source Fact Sheet — NYSE TAQ Closing Prices

**Checked**: 2026-07-22
**Candidate**: NYSE TAQ Closing Prices, especially the NYSE Arca daily summary file
**Disposition**: Reject under current published cost, public-rights, and volume-semantics terms
**Probe status**: No dashboard registration, agreement, purchase, entitlement, account, credential, sample download, provider payload, fixture, parser, local probe, or GitHub Actions probe; only official NYSE catalog, pricing, client-specification, and policy materials were inspected at Step 0

## Source Facts

| Field | Value |
| --- | --- |
| Source owner | New York Stock Exchange LLC / NYSE Market Data |
| Data family | Per-exchange daily proprietary Closing Prices summary files for NYSE, NYSE American, NYSE Arca, NYSE National, and NYSE Texas |
| Official docs | `https://www.nyse.com/data-products/catalog/taq-nyse-closing-prices`, current Closing Prices client specification, historical pricing schedule, and NYSE policy/contract library |
| Endpoint/delivery | Entitled daily files through dashboard online/email delivery, SFTP, or S3. This is a whole-exchange summary file, not a public ticker API. |
| Auth/contract | Dashboard registration and product entitlement are required; SFTP additionally requires dedicated source IP addresses and SSH keys. Historical paths are accessible according to client entitlements. |
| Cost and no-paid evidence | Fail. The current commercial schedule lists TAQ Closing Prices at USD 500/month with a 12-month minimum. The subscription includes 12 months of back history; additional history and a one-time historical purchase are USD 500 per data-content month. Academic access still requires qualification, an executed vendor agreement, and payment. |
| Rate and request budget | No per-symbol quota. One file is produced for each NYSE group exchange per trading day. Exact byte size is not published, but a pre-aggregated symbol summary is operationally much smaller than raw Daily TAQ. |
| Format | XML, Excel, or pipe-delimited ASCII files. |
| Key fields | Symbol, CUSIP, Open, High, Low, Last, net change, Total Volume, last-trade date, closing bid/ask and sizes, listing market. |
| Required symbols | SPY and Select Sector ETFs are expected in the NYSE Arca-listed universe, but exact 12-symbol rows were not sampled because binding cost and rights gates fail first. |
| Update cadence | Produced every trading day; the current specification lists a typical 10 p.m. Eastern availability time, within the u140 36-hour target if reliable. No measured run evidence exists. |
| Historical range | NYSE Arca from 5 December 2008 to present; other NYSE group exchanges have product-specific start dates. Depth exceeds 63 trading days but is paid. |
| Adjustment semantics | The file supplies exchange trade prices and no adjusted-close, dividend, split factor, or total-return field. Corporate-action normalization would require a separate authoritative source. |
| Venue/volume semantics | The specification defines the OHLC from securities traded on the named exchange and Total Volume as trade volume on that exchange. For the required NYSE Arca-listed ETFs, this is NYSE Arca venue activity, not consolidated U.S. tape OHLCV. |
| Attribution | Governing agreement and product policy apply; no anonymous attribution-only free license is published. |
| Caching and raw retention | Historical use and external distribution remain subject to the product entitlement, vendor agreement, and NYSE policies. |
| License/public display | Fail for the current public MVP. NYSE says historical external redistribution requires a specific license and the relevant fee. The USD 500 product subscription does not establish free public derived-display rights. |
| Existing Investo overlap | No Closing Prices entitlement, delivery credential, downloader, parser, adapter, `SourceSpec`, route, fixture, dependency, secret, or workflow exists. Daily TAQ is a separate consolidated raw-feed archive. |
| Proposed `source_name` | None; rejected before runtime design |
| Proposed adapter path | None; rejected before runtime design |
| Routing surfaces | None; no registry, tier, route, config, dependency, fixture, raw store, workflow, or public output change |
| Degradation behavior | Not applicable while rejected; missing/late/revised files, symbol changes, no-trade rows, and entitlement failures were not probed |

## Dated Primary-Source Evidence

Checked on 2026-07-22:

1. `https://www.nyse.com/data-products/catalog/taq-nyse-closing-prices`
   - advertises daily Open/High/Low/Last, Total Volume, closing bid/ask, and related
     fields for NYSE group securities, with history from 2001 or the applicable
     exchange start date;
   - exposes purchase and sample links rather than an anonymous production endpoint.
2. `https://www.nyse.com/publicdocs/nyse/data/TAQ_Closing_Prices_Client_Spec_v2.1.pdf`
   - documents daily files, typical 10 p.m. Eastern availability, NYSE Arca history
     from 5 December 2008, XML/XLS/text formats, and SFTP/S3/online delivery;
   - defines Total Volume as trade volume on that exchange and the price fields from
     exchange trades, so the result is not consolidated-tape OHLCV.
3. `https://www.nyse.com/publicdocs/nyse/data/NYSE_Historical_Market_Data_Pricing.pdf`
   - lists USD 500/month, a 12-month minimum, 12 months included back history, and
     USD 500 per additional historical data-content month.
4. `https://www.nyse.com/publicdocs/nyse/data/NYSE_Market_Data_Complete_Policy_Package.pdf`
   - requires a specific license and relevant fee for external historical
     redistribution and requires executed agreements/payment even for qualifying
     academic use.
5. `https://www.nyse.com/market-data/pricing-policies-contracts-guidelines`
   - is the official hub for applicable product pricing, policies, contracts,
     guidelines, and use declarations.

## Deduplication Evidence

A repository scan found no exact `TAQ Closing Prices` purchase, entitlement,
dashboard/SFTP/S3 path, parser, registry entry, `SourceSpec`, route, fixture,
dependency, secret, or workflow. NYSE Daily TAQ is the same owner's raw consolidated
CTA/UTP archive and was rejected separately for cost, rights, and file scale. Closing
Prices is a distinct, pre-aggregated NYSE-group proprietary summary whose volume is
venue-local, so it requires its own metric-fitness decision.

## Gate Decision

| Binding gate | Result | Reason |
| --- | --- | --- |
| Official terms and public derived-display rights | Fail as a free right | External historical redistribution requires a specific NYSE license and fee |
| Free access for 63+ daily OHLCV bars | Fail | History is deep, but access costs USD 500/month under a 12-month minimum |
| Exact 12-symbol coverage | Strongly indicated, not payload-probed | Required ETFs are expected on NYSE Arca, but no entitled/sample file was opened |
| At-most-36-hour freshness | Provisional technical pass, not measured | Typical 10 p.m. Eastern daily publication is documented |
| Truthful volume/price semantics | Fail for the consolidated-radar contract | OHLC and volume are local to the named NYSE group exchange, not all U.S. executions |
| Bounded local/GitHub Actions operation | Provisional technical pass, not measured | Pre-aggregated daily files avoid raw tick scale, but auth/bytes/reliability were not probed |
| Five bounded GitHub Actions probes | Not run | Cost, rights, and metric gates fail before Step 1 and Step 2 |
| No paid plan/trial/secret exposure | Fail | Purchase, entitlement, credentials, and recurring payment are required |
| Public/raw retention contract | Fail as a free right | Historical external use remains separately licensed and fee-bearing |

**Disposition: `reject under current published cost, public-rights, and
volume-semantics terms`.** Reconsider only if NYSE publishes a permanent-free
entitlement with explicit public derived-display rights and Investo accepts a clearly
labeled NYSE Arca-only metric rather than consolidated OHLCV. Then repeat Step 0 and
verify exact 12-symbol rows, no-trade behavior, corporate actions, file size, posting
SLA, retention, and five-run reliability. No account, agreement, order, entitlement,
credential, sample, payload, fixture, adapter, public output, workflow, local probe,
GitHub Actions probe, or TECH-DEBT item is created.

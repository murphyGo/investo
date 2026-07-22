# u140 Source Fact Sheet — MIAX Pearl Equities Historical Market Data

**Checked**: 2026-07-22
**Candidate**: MIAX Pearl Equities Historical Market Data, using Top of Market (`ToM`) or Depth of Market (`DoM`)
**Disposition**: Reject under current published cost, delivery, and rights terms
**Probe status**: No request form, agreement, purchase, USB device, feed payload, fixture, decoder run, or GitHub Actions probe; only official product, market-data, vendor-agreement, fee-page, and current fee-schedule materials were inspected at Step 0

## Source Facts

| Field | Value |
| --- | --- |
| Source owner | MIAX Pearl, LLC / MIAX Pearl Equities Exchange, part of Miami International Holdings |
| Data family | Proprietary historical ToM and DoM binary market-data feeds for the MIAX Pearl Equities venue |
| Official docs | `https://www.miaxglobal.com/markets/us-equities/pearl-equities/historical-market-data`, `https://www.miaxglobal.com/markets/us-equities/pearl-equities/market-data`, `https://www.miaxglobal.com/markets/us-equities/pearl-equities/market-data-vendor-agreements`, and the current fee schedule linked from `https://www.miaxglobal.com/markets/us-equities/pearl-equities/fees` |
| Endpoint/delivery | No public API or download endpoint. MIAX loads purchased historical feeds onto a MIAX-provided eight-terabyte USB device. |
| Auth/contract | Request form plus MIAX Exchange Data Agreement and applicable request/distribution schedules for direct or vendor receipt |
| Cost and no-paid evidence | Fail. The official historical page and May 1, 2026 fee schedule charge USD 500 per device for Members and Non-Members. |
| Rate and request budget | Not request-metered. One physical device can carry up to six months of the most recent data, capped at eight terabytes; this is incompatible with daily unattended GitHub Actions operation. |
| Format | Proprietary ToM/DoM feed bytes on a physical device; interface specifications and a decoder are required before messages can become rows |
| Key fields | ToM contains MIAX best bid/offer with aggregated displayed size, last sales, trade cancellations, symbol trading status, and system status. DoM adds displayed orders and order executions/cancellations. |
| Required symbols | MIAX trades U.S. exchange-listed securities, but exact daily message/trade continuity for SPY, XLB, XLC, XLE, XLF, XLI, XLK, XLP, XLRE, XLU, XLV, and XLY was not verified because the paid-device gate fails first. |
| Update cadence | Historical feed content is described as T+1, but receipt is purchase/device based rather than a measured automated daily delivery contract. |
| Historical range | Only the most recent six months are available per request, sufficient in depth for 63 trading days but not a durable rolling free archive. |
| Adjustment semantics | Raw venue messages do not supply a split/dividend-adjusted daily series; corporate-action normalization needs a separate source. |
| Venue/volume semantics | MIAX Pearl Equities only. Derived trades and volume cannot be labeled consolidated U.S. ETF OHLCV. |
| Attribution | Not established as a simple attribution license; receipt and distribution are governed by MIAX agreements, schedules, and market-data policies. |
| Caching and raw retention | Physical device may contain up to six months/eight terabytes. Retention and redistribution depend on the executed MIAX data contract rather than a free public grant. |
| License/public display | Fail as a free self-service right. All direct recipients must execute the Exchange Data Agreement; external distributors have separate requirements and fees. No no-cost public derived-display authorization was found. |
| Existing Investo overlap | No MIAX historical feed path, agreement, physical-device ingest, ToM/DoM decoder, adapter, `SourceSpec`, route, fixture, dependency, secret, or workflow exists. The Nasdaq directory's issuer ticker `MIAX` is unrelated. |
| Proposed `source_name` | None; rejected before runtime design |
| Proposed adapter path | None; rejected before runtime design |
| Routing surfaces | None; no registry, tier, route, config, dependency, fixture, raw store, workflow, or public output change |
| Degradation behavior | Not applicable while rejected; device shipping, corrupt media, binary-version drift, cancellation correction, absent trades, and update delays were not probed |

## Dated Primary-Source Evidence

Checked on 2026-07-22:

1. `https://www.miaxglobal.com/markets/us-equities/pearl-equities/historical-market-data`
   - offers historical MIAX Pearl Equities ToM and DoM feeds;
   - requires a purchase request and delivers up to the most recent six months on
     a MIAX-provided eight-terabyte USB device;
   - publishes a fee of USD 500 per device.
2. `https://www.miaxglobal.com/markets/us-equities/pearl-equities/market-data`
   - defines ToM fields as MIAX best bid/offer, last sales, trade cancellations,
     symbol status, and system status;
   - defines DoM as displayed-book messages plus executions and cancellations.
3. `https://www.miaxglobal.com/markets/us-equities/pearl-equities/market-data-vendor-agreements`
   - requires all firms receiving MIAX market data directly or through an approved
     distributor to execute the MIAX Exchange Data Agreement;
   - names separate schedules and policy requirements for receipt, affiliated use,
     service facilitators, subscribers, and external distribution.
4. `https://www.miaxglobal.com/markets/us-equities/pearl-equities/fees`
   - identifies the May 1, 2026 document as the current fee schedule reviewed here.
5. `https://www.miaxglobal.com/sites/default/files/fee_schedule-files/MIAX_Pearl_Equities_Fee_Schedule_05012026_0.pdf`
   - Section 3(c) charges Members and Non-Members USD 500 per historical-data
     device, describes T+1 proprietary feed data, and limits a request to the most
     recent six months subject to device capacity;
   - separately prices ToM external distribution at USD 2,000/month and ToM
     non-display use at USD 1,000/month, confirming that historical purchase alone
     is not a free public-display license.

## Deduplication Evidence

A repository scan across AIDLC docs, runtime, configuration, tests, scripts,
workflows, dependencies, and source-planning surfaces found no `miaxglobal.com`,
MIAX Pearl Equities historical-data product, ToM/DoM decoder, device-ingest path,
data agreement, registry entry, `SourceSpec`, route, fixture, dependency, secret, or
workflow. The one `MIAX` string in a Nasdaq symbol-directory fixture identifies Miami
International Holdings as a listed issuer and is not source overlap.

## Gate Decision

| Binding gate | Result | Reason |
| --- | --- | --- |
| Official terms and public derived-display rights | Fail for free self-service use | Receipt requires an exchange agreement, and external distribution has separate policy/fee requirements |
| Free access for 63+ daily OHLCV bars | Fail | Six months is deep enough, but access costs USD 500 per physical device |
| Exact 12-symbol coverage | Unproven | Venue eligibility does not prove a qualifying trade for every ETF/date; paid access blocks probing |
| At-most-36-hour freshness | Unproven for usable bars | Feed data is described as T+1, but device delivery and decoding are not an unattended daily refresh contract |
| Truthful volume/price semantics | Fail for the current product contract | Derived values would be MIAX-only, not consolidated ETF OHLCV |
| Bounded local/GitHub Actions operation | Fail | Physical delivery up to eight terabytes, binary decoding, and no daily API/download path |
| Five bounded GitHub Actions probes | Not run | Paid physical delivery fails before Step 1 and Step 2 |
| No paid plan/trial/secret exposure | Fail | USD 500/device purchase is mandatory; no purchase or agreement was initiated |
| Public/raw retention contract | Fail as a free right | Rights depend on an executed MIAX data agreement and distribution status |

**Disposition: `reject under current published cost, delivery, and rights terms`.**
Reconsider only if MIAX introduces a permanently free, automated, ticker-filtered
daily-bar surface with explicit public derived-display rights and truthful venue labels.
Then repeat Step 0 and verify exact-universe continuity, adjustments, posting time,
request limits, and five-run reliability. No request, agreement, purchase, device,
payload, fixture, adapter, public output, workflow, local probe, GitHub Actions probe,
or TECH-DEBT item is created.

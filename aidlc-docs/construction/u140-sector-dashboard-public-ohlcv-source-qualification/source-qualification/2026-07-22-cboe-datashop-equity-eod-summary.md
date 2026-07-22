# u140 Source Fact Sheet — Cboe DataShop Equity EOD Summary

**Checked**: 2026-07-22
**Candidate**: Cboe DataShop Equity EOD Summary
**Disposition**: Reject under current published cost and licensing terms
**Probe status**: No account, cart, quote, order, agreement, sample download, provider payload, fixture, local probe, or GitHub Actions probe; only official Cboe product, FAQ, academic-discount, related order-form, and market-data agreement materials were inspected at Step 0

## Source Facts

| Field | Value |
| --- | --- |
| Source owner | Cboe Global Markets / Cboe DataShop |
| Data family | Purchased historical or subscribed daily end-of-day summary files for U.S. exchange-listed equities and ETFs, excluding OTC securities |
| Official docs | `https://datashop.cboe.com/equity-eod-summary`, `https://datashop.cboe.com/faqs`, `https://datashop.cboe.com/academic-discount`, related equity/ETF order form at `https://datashop.cboe.com/equity-etf-quotes`, and `https://www.cboe.com/market_data_services/document_library/` |
| Endpoint/delivery | No free public API is published for this product. DataShop offers a historical purchase or daily file subscription after product/date/symbol selections and ordering. |
| Auth/contract | DataShop account and order flow; applicable Cboe agreement, data-policy, onboarding, fee, and distribution conditions depend on the ordered use |
| Cost and no-paid evidence | Fail. The product is presented as a purchase/subscription rather than a free entitlement. Cboe's qualifying academic program discounts standard prices by 50% but still imposes a USD 500 minimum charge, and Investo is not an accredited academic use case. |
| Rate and request budget | File-delivery product rather than a request-metered public API. No no-cost request quota or anonymous automated endpoint is published. |
| Format | The DataShop FAQ describes historical and subscription products as one CSV file per day. |
| Key fields | Open, high, low, close, trade volume, VWAP, 15:45 bid/ask, and end-of-day bid/ask. A supplement includes open/close marks, exchange identifiers, trade conditions, and primary exchange. Close is the last regular-trading-hours traded price. |
| Required symbols | Product scope advertises U.S. equities and ETFs, excluding OTC, but SPY, XLB, XLC, XLE, XLF, XLI, XLK, XLP, XLRE, XLU, XLV, and XLY were not ordered or payload-probed because the cost and rights gates fail first. |
| Update cadence | Historical one-time delivery or daily file subscription. The exact Equity EOD Summary page does not publish a measured posting deadline sufficient to prove the u140 at-most-36-hour SLA. |
| Historical range | January 2010 to present, comfortably beyond the 63-trading-day requirement if purchased |
| Adjustment semantics | The product page does not state that OHLC is split- or dividend-adjusted. The supplement's trade conditions and primary exchange fields do not establish corporate-action normalization. |
| Venue/volume semantics | The page labels the field `trade volume`, but the reviewed public description does not explicitly establish whether every value is consolidated across all U.S. venues or uses another inclusion rule. Investo therefore cannot label it consolidated volume without contract/sample validation. |
| Attribution | No simple attribution-only public license is published for this product; use is governed through DataShop ordering and applicable Cboe agreements/policies. |
| Caching and raw retention | File retention and reuse must follow the purchased product and applicable data agreement. No free public raw-retention grant was found. |
| License/public display | Fail as a free self-service right. Cboe's market-data library routes access through agreements, onboarding, policies, and fees, while the related Equity & ETF Quotes order form treats `External Distribution` as a separately selected use. No explicit permanently free public derived-display authorization was found for Equity EOD Summary. |
| Existing Investo overlap | No Equity EOD Summary order/download path, DataShop account integration, adapter, `SourceSpec`, route, fixture, dependency, secret, or workflow exists. Generic rejection of automated extraction from Cboe public display pages and existing Cboe VVIX/SKEW context adapters are different products and contracts. |
| Proposed `source_name` | None; rejected before runtime design |
| Proposed adapter path | None; rejected before runtime design |
| Routing surfaces | None; no registry, tier, route, config, dependency, fixture, raw store, workflow, or public output change |
| Degradation behavior | Not applicable while rejected; daily delivery delay, missing symbols, corrections, corporate actions, and field/provenance changes were not probed |

## Dated Primary-Source Evidence

Checked on 2026-07-22:

1. `https://datashop.cboe.com/equity-eod-summary`
   - advertises a U.S. equity and ETF end-of-day summary excluding OTC securities;
   - lists open, high, low, close, trade volume, VWAP, 15:45 and end-of-day
     bid/ask, plus a supplement with marks, exchange identifiers, trade conditions,
     and primary exchange;
   - defines close as the last traded price during regular trading hours;
   - offers history from January 2010 to present through historical purchase or a
     daily file subscription.
2. `https://datashop.cboe.com/faqs`
   - describes historical and subscription data sets as one CSV file per day;
   - describes equity data sets as U.S. equities and ETFs primarily listed on
     national securities exchanges.
3. `https://datashop.cboe.com/academic-discount`
   - limits eligibility to qualifying students and faculty at accredited academic
     institutions for approved academic use;
   - includes Equity EOD Summary and Equity & ETF Quotes/Trades among eligible
     products;
   - discounts standard pricing by 50% but applies a USD 500 minimum charge.
4. `https://datashop.cboe.com/equity-etf-quotes`
   - confirms the related U.S. equity/ETF order model, historical/date/symbol
     selection, and order-based delivery;
   - exposes `External Distribution` as a distinct use selection, which is evidence
     that public distribution is licensed rather than automatically granted by
     product access.
5. `https://www.cboe.com/market_data_services/document_library/`
   - directs market-data customers through the Cboe Global Data Agreement,
     applicable data policies, onboarding requests, and fee schedules.

## Deduplication Evidence

A repository scan across AIDLC docs, runtime, configuration, tests, scripts,
workflows, dependencies, and source-planning surfaces found no exact Cboe DataShop
Equity EOD Summary purchase, file delivery, adapter, registry entry, `SourceSpec`,
route, fixture, dependency, secret, or workflow. The pre-existing `Nasdaq/Cboe
website endpoints` row concerns scraping public display pages, not this official paid
file product. Existing Cboe VVIX/SKEW sources provide market-wide volatility context
and do not supply ETF OHLCV.

## Gate Decision

| Binding gate | Result | Reason |
| --- | --- | --- |
| Official terms and public derived-display rights | Fail for free self-service use | Access and external distribution are agreement/policy/license controlled; no no-cost public derived-display grant is published |
| Free access for 63+ daily OHLCV bars | Fail | History is sufficiently deep but available through purchase/subscription, not a permanent free tier; even eligible academic use has a USD 500 minimum |
| Exact 12-symbol coverage | Unproven | Broad ETF scope is promising, but exact symbols were not ordered or payload-probed after the binding gates failed |
| At-most-36-hour freshness | Unproven | Daily subscription exists, but the exact product page does not publish or prove the required posting SLA |
| Truthful volume/price semantics | Unproven | OHLC/volume fields exist, but corporate-action adjustment and consolidated-versus-other volume provenance are not explicit in the reviewed description |
| Bounded local/GitHub Actions operation | Unproven and out of scope | File subscription may be automatable after purchase, but no free endpoint/delivery contract was available to probe |
| Five bounded GitHub Actions probes | Not run | Permanent-free and explicit free public-rights gates fail before Step 1 and Step 2 |
| No paid plan/trial/secret exposure | Fail | Purchase/subscription is required; no account, cart, quote, order, or agreement was initiated |
| Public/raw retention contract | Fail as a free right | Retention and redistribution depend on the ordered license and applicable Cboe agreements |

**Disposition: `reject under current published cost and licensing terms`.**
Reconsider only if Cboe publishes a permanently free entitlement for this exact
dataset with explicit public derived-display and retention rights. Then repeat Step 0
and verify the exact 12 symbols, adjustment semantics, volume provenance, posting SLA,
correction behavior, file automation, and five-run reliability. No account, quote,
order, agreement, sample, provider payload, fixture, adapter, public output, workflow,
local probe, GitHub Actions probe, or TECH-DEBT item is created.

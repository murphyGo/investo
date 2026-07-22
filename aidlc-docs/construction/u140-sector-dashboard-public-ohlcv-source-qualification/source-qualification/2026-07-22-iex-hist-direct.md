# u140 Source Fact Sheet — Direct IEX Exchange HIST / TOPS

**Checked**: 2026-07-22
**Candidate**: Direct IEX Exchange Historical Data (`HIST`), using the TOPS feed
**Disposition**: Reject for current public MVP operational and metric fitness
**Probe status**: No HIST file, PCAP, provider payload, fixture, decoder run, or GitHub Actions probe; only official product, terms, download-catalog, feed-resource, and eligible-symbol pages were inspected at Step 0

## Source Facts

| Field | Value |
| --- | --- |
| Source owner | Investors' Exchange LLC (`IEX`) |
| Data family | Historical binary TOPS/DEEP market-data feeds; TOPS is the smallest candidate exposing IEX quotes and last-sale activity needed to derive bars |
| Official docs | `https://www.iex.io/products/equities/market-data-connectivity`, `https://www.iex.io/legal/hist-data-terms`, `https://iextrading.com/trading/market-data/`, `https://www.iex.io/resources/trading/market-data`, and `https://iextrading.com/trading/eligible-symbols/` |
| Endpoint/delivery | Public HIST catalog with one gzip-compressed PCAP per feed and trading date; no server-side symbol/date-range daily-bar query |
| Auth | Public download surface; the reviewed official pages state no credential requirement for HIST files |
| Cost and no-paid evidence | HIST is described as free historical data. The most recent 12 months are available, exceeding the 63-trading-day minimum. |
| Rate and request budget | No small request quota is relevant because one request downloads the whole daily feed. Current official catalog examples put a TOPS file at roughly 9–21 GB for one date; 63 dates imply hundreds of gigabytes before symbol filtering. |
| Format | `.pcap.gz` carrying binary IEX-TP messages; decode with the matching TOPS specification version, then aggregate last-sale messages into daily bars |
| Key fields | TOPS publishes best bid/offer plus last-sale price and size. Open, high, low, close, and volume are not native daily records and must be derived from eligible IEX trade messages. |
| Required symbols | IEX publishes an eligible-symbol surface, but exact daily presence and trade continuity for SPY, XLB, XLC, XLE, XLF, XLI, XLK, XLP, XLRE, XLU, XLV, and XLY were not verified because whole-feed operational fitness fails first. |
| Update cadence | Free HIST files are T+1. The official product page does not promise the exact intraday posting time needed to prove an at-most-36-hour usable derived-bar SLA. |
| Historical range | Most recent 12 months, sufficient for 63+ trading days if the symbol trades on IEX |
| Adjustment semantics | Raw exchange messages do not provide a split/dividend-adjusted daily series. Corporate-action normalization would require a separate source and contract. |
| Venue/volume semantics | IEX-only. TOPS does not report routed executions, does not reflect other exchanges, and IEX cautions that aggregate volume may not reflect all members. Derived volume cannot be labeled total ETF trading volume. |
| Attribution | Any distribution must include the IEX attribution text and link required by the HIST Terms. |
| Caching and raw retention | The HIST Terms permit use and distribution subject to attribution; no reviewed retention deadline was found. Large raw PCAP retention is nevertheless outside the bounded Investo/GitHub design. |
| License/public display | Preliminary pass. The HIST Terms permit use for any purpose and distribution when the required IEX attribution is included. |
| Existing Investo overlap | HF Data Library's upstream IEX rights and IEX-only volume semantics were assessed in iteration 16. No direct HIST downloader, IEX-TP/PCAP decoder, TOPS aggregator, adapter, `SourceSpec`, route, fixture, dependency, secret, or workflow exists. |
| Proposed `source_name` | None; rejected before runtime design |
| Proposed adapter path | None; rejected before runtime design |
| Routing surfaces | None; no registry, tier, route, config, dependency, fixture, raw store, workflow, or public output change |
| Degradation behavior | Not applicable while rejected; corrupt/truncated PCAP, specification-version drift, absent trades, late catalog posting, and download interruption were not probed |

## Dated Primary-Source Evidence

Checked on 2026-07-22:

1. `https://www.iex.io/products/equities/market-data-connectivity`
   - describes HIST as free T+1 historical downloads with the most recent 12
     months available;
   - states that TOPS/DEEP represent IEX data, that routed executions are not
     reported, and that the legacy IEX API was retired in 2021.
2. `https://www.iex.io/legal/hist-data-terms`
   - permits use of the data and distribution when the required IEX attribution
     text and Terms link are carried;
   - states that the data does not reflect markets other than IEX and is only a
     reference point, and warns that aggregate volume may not reflect all members.
3. `https://iextrading.com/trading/market-data/`
   - provides the official per-date download catalog and says files are T+1;
   - delivers gzip PCAP/IEX-TP feed output rather than ticker-filtered daily bars;
   - current catalog examples place one TOPS date at roughly 9–21 GB.
4. `https://www.iex.io/resources/trading/market-data`
   - publishes the TOPS and IEX-TP specifications plus sample PCAP resources needed
     to implement a binary decoder.
5. `https://iextrading.com/trading/eligible-symbols/`
   - provides the official eligible-symbol surface, but catalog eligibility alone
     cannot prove a last sale for every required ETF on every date.

The official delivery and rights evidence is sufficient to stop before a file probe.
The smallest relevant product still downloads every TOPS message for the date. A
63-trading-day bootstrap would move hundreds of gigabytes into or through a runner,
then require protocol-version-aware decoding and bar aggregation before selecting 12
symbols. This is not a bounded source adapter for the current Pages/GitHub Actions MVP.

## Deduplication Evidence

Repository scans found IEX HIST only as the upstream rights/venue boundary in the HF
Data Library fact sheet and session. No direct `iextrading.com` HIST endpoint,
download client, PCAP/IEX-TP parser, TOPS last-sale aggregator, registry entry,
`SourceSpec`, tier/window/segment route, fixture, dependency, secret, or workflow
exists. Nasdaq fixture rows whose ticker text happens to contain `PCAP` are unrelated.

Direct HIST is therefore not a duplicate runtime integration, but it does reuse the
already-established IEX rights and IEX-only semantic facts. The new evidence is its
official whole-feed delivery size and resulting operational boundary.

## Gate Decision

| Binding gate | Result | Reason |
| --- | --- | --- |
| Official terms and public derived-display rights | Preliminary pass | HIST data may be used and distributed with mandatory attribution |
| Free access for 63+ daily OHLCV bars | Pass on source history, fail on ready-bar shape | Twelve months are free, but IEX supplies binary messages rather than daily OHLCV rows |
| Exact 12-symbol coverage | Unproven | Eligible-symbol publishing does not prove a required ETF has eligible trades on every needed date |
| At-most-36-hour freshness | Unproven | T+1 is stated, but exact posting time plus decode completion was not measured |
| Truthful volume/price semantics | Fail for the current product contract | Derived values are IEX-only, exclude other markets and routed executions, and are not consolidated ETF OHLCV |
| Bounded local/GitHub Actions operation | Fail | Roughly 9–21 GB per date and hundreds of GB for bootstrap precede filtering and decoding |
| Five bounded GitHub Actions probes | Not run | Official delivery shape and size already fail the bounded runner gate |
| No paid plan/trial/secret exposure | Pass | Free public HIST surface; no account, key, or trial created |
| Public/raw retention contract | Rights pass, implementation N/A | Attribution permits distribution, but raw PCAP storage is outside this MVP and no file was retained |

**Disposition: `reject for current public MVP operational and metric fitness`.**
Reconsider only if IEX adds a bounded ticker-filtered daily-bar surface, or if Investo
funds an external feed-decoding pipeline and changes the product contract to label all
metrics explicitly as IEX-only. Either change requires a fresh Step 0 and exact-universe,
continuity, adjustment, posting-time, parser-version, and five-run reliability evidence.
No download, payload, fixture, adapter, public output, workflow, local probe, GitHub
Actions probe, or TECH-DEBT item is created.

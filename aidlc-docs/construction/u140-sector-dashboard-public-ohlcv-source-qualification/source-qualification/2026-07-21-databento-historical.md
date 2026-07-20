# u140 Source Fact Sheet — Databento Historical API / EQUS.SUMMARY

**Checked**: 2026-07-21
**Candidate**: Databento Historical API with `EQUS.SUMMARY` `ohlcv-1d`
**Disposition**: Reject under current published cost and rights evidence for public Pages
**Probe status**: Not run; the candidate failed the permanent-free gate first and exact public derived-display rights remain unproven

## Source Facts

| Field | Value |
| --- | --- |
| Source owner | Databento normalizes the Nasdaq NLS+ end-of-day summary; Nasdaq is the underlying publisher |
| Data family | Consolidated end-of-day OHLCV and statistics for US RegNMS equities |
| Official docs | `https://databento.com/docs/venues-and-datasets/equs-summary` and `https://databento.com/docs/api-reference-historical` |
| Endpoint | Historical `timeseries.get_range` over `https://hist.databento.com/v0/` with `dataset=EQUS.SUMMARY`, `schema=ohlcv-1d`, the 12 symbols, and bounded start/end dates |
| Auth | A secret 32-character API key beginning with `db-` is required; the official client defaults to `DATABENTO_API_KEY` |
| Cost and no-paid evidence | Historical data is billed by uncompressed bytes on a pay-as-you-go basis. New teams receive one $125 credit grant, but it expires after six months and each team is eligible only once. There is no durable zero-cost production tier. |
| Rate and request budget | Historical API limits include 100 concurrent connections and 100 time-series requests/second. One multi-symbol daily request is operationally small, but every returned byte is billable after the one-time credit. |
| Format | Databento Binary Encoding, CSV, or JSON through official HTTP/client-library paths |
| Key fields | `ts_event`, `publisher_id`, `instrument_id`, `open`, `high`, `low`, `close`, `volume`, and mapped `symbol` |
| Required symbols | The official equity examples describe all RegNMS symbols and multi-symbol `EQUS.SUMMARY` queries, making the 11 sector ETFs and SPY plausible; exact 12-symbol results were not probed after the cost failure |
| Update cadence | Nasdaq publishes EOD summaries around 16:15, 17:00, and 20:15 ET; Databento exposes the last 20:15 ET summary in `ohlcv-1d`. Historical access remains subject to the publisher's live-data cutoff, so the exact no-paid at-most-36-hour path was not proven. |
| Historical range | The official closing-price example queries one year of `EQUS.SUMMARY` daily data, which preliminarily clears 63 bars; exact ETF inception/continuity was not probed |
| Adjustment semantics | `ohlcv-1d` represents normalized market summaries rather than a documented total-return adjusted series. Corporate actions are a separate data family, so split/dividend treatment would require an explicit contract before use. |
| Attribution | No reviewed public page states an attribution-only path that grants `EQUS.SUMMARY` public derived-display rights |
| Caching and raw retention | A paid batch request may be downloaded repeatedly for 30 days, but that billing behavior is not a public redistribution or indefinite raw-retention grant |
| License/public display | Databento says redistribution rights depend on the underlying dataset and must be checked in the Data Catalog or License Manager. It says most datasets can be redistributed after 24 hours, but does not publish an exact `EQUS.SUMMARY` free public derived-display grant on the reviewed pages. External display is a licensing use case, not something inferred from API accessibility. |
| Existing Investo overlap | No Databento endpoint, `EQUS.SUMMARY` reference, API-key path, adapter, `SourceSpec`, route, dependency, fixture, or workflow exists |
| Proposed `source_name` | None; rejected before design |
| Proposed adapter path | None; rejected before design |
| Routing surfaces | None; no registry, spec, tier, market-window, segment, config, diagnostics, fixture, secret, dependency, or workflow change |
| Degradation behavior | Not applicable; no runtime path is registered |

## Dated Primary-Source Evidence

Checked on 2026-07-21:

1. `https://databento.com/docs/venues-and-datasets/equs-summary`
   - identifies `EQUS.SUMMARY` as Nasdaq NLS+ consolidated US-equities end-of-day
     data;
   - exposes `ohlcv-1d`, statistics, and definitions and documents the final
     20:15 ET daily summary.
2. `https://databento.com/docs/examples/equities/closing-prices`
   - demonstrates a multi-symbol Historical API request using
     `dataset="EQUS.SUMMARY"` and `schema="ohlcv-1d"` over a one-year range;
   - returns open, high, low, close, volume, and mapped symbols.
3. `https://databento.com/docs/api-reference-historical`
   - documents authenticated HTTP/client-library access, CSV/JSON/DBN encodings,
     metadata/error contracts, and 100 time-series requests per second;
   - requires a Databento API key and supports daily OHLCV schemas.
4. `https://databento.com/pricing`
   - prices historical data by usage rather than offering a permanent free tier;
   - advertises one $125 signup credit grant and states that redistribution rights
     depend on the dataset and underlying publisher;
   - routes exact licensing and redistribution selection through the Data Catalog
     and License Manager.
5. `https://databento.com/docs/faqs/usage-pricing-and-data-credits`
   - confirms every historical dataset/feed is priced per GB and each outbound byte
     is billed;
   - states that the $125 team credit expires after six months and is issued only
     once per team.
6. `https://databento.com/docs/quickstart`
   - requires an API key and describes the signup credits as initial integration
     funding rather than a recurring free allowance;
   - classifies historical access as usage-based or flat-rate.
7. `https://databento.com/docs/portal`
   - defines external display/distribution as a licensed commercial use case and
     explains that exact venue rights and fees are managed per dataset/use case.
8. `https://databento.com/docs/knowledge-base`
   - defines the `ohlcv-1d` field contract and notes that daily bars use UTC dates
     and may differ from official venue settlement/volume conventions.

The API shape, history depth, request capacity, and consolidated EOD dataset are
technically suitable for a bounded radar calculation. The economics are not: the
only free amount is a one-time expiring credit, after which every historical byte is
paid. Exact public derived-display permission for `EQUS.SUMMARY` is also dataset- and
use-case-specific rather than explicitly granted by the reviewed public pages.

## Deduplication Evidence

A repository scan across `src/`, `tests/`, `scripts/`, `.github/`, `CONTRIBUTING.md`,
dependency configuration, AIDLC plans, requirements, and session docs found no
`databento`, `EQUS.SUMMARY`, `hist.databento`, or `DATABENTO_API_KEY` surface. Adding
the source would introduce a new paid-metered external dependency and secret boundary.

## Gate Decision

| Binding gate | Result | Reason |
| --- | --- | --- |
| Official terms and public derived-display rights | Fail / unproven | Rights are dataset-specific and resolved through the Data Catalog/License Manager; the reviewed public pages do not expressly grant free public derived display for `EQUS.SUMMARY` |
| Free access for 63+ daily OHLCV bars | Fail | Historical bytes are usage-billed; the one-time $125 credit expires after six months and is not a sustainable free tier |
| Exact 12-symbol coverage and freshness | Not run | Fail-fast after the permanent-free failure; exact ETF rows, corporate actions, continuity, and at-most-36-hour availability remain unproven |
| Five bounded GitHub Actions probes | Not run | A metered account/key and possible charges are prohibited after Step 0 rejection |
| No paid plan/trial/secret exposure | Fail | Production depends on metered billing and a secret API key after the one-time credit |
| Public/raw retention contract | Fail / unproven | Repeat-download duration is a billing feature; no exact public raw-retention or derived-display grant was established for this dataset |

**Disposition: `reject under current published cost and rights evidence`.** Reconsider
only if Databento supplies a perpetual zero-cost production allowance sufficient for
the daily 12-symbol workload and a written or public dataset-specific grant covering
Investo's derived fields, caching, raw retention, GitHub Actions, and GitHub Pages.
No account/key, cost estimate request, local probe, GitHub Actions probe, adapter,
fixture, public output, or TECH-DEBT item is created.

# Functional Design: `u138 price-source-endpoint-lifecycle-repair`

**Date**: 2026-07-18
**Status**: Complete for implementation handoff
**Parent plan**: `aidlc-docs/construction/plans/u138-price-source-endpoint-lifecycle-repair-code-generation-plan.md`

## 1. Objective

Restore deterministic price snapshots after the Stooq quote endpoint retired and Yahoo `query1` became unavailable on GitHub Actions. The design removes dead endpoints rather than masking their status, uses the Yahoo `query2` path already proven on the affected runner, reconciles fresh same-run history as a bounded fallback, and gives the surviving Korean fallback legs truthful source identities.

## 2. Actors and Consumers

- **Source collector**: executes registered adapters and creates one `SourceOutcome` per adapter.
- **Generate stage**: loads Yahoo history/anchors and reconciles missing snapshot items before segmentation.
- **Segment router**: routes final items/outcomes to domestic, US, and crypto segments from `SourceSpec`.
- **Numeric trust gates**: consume ticker/core-fact/provenance metadata.
- **Reader/operator surfaces**: consume the final reconciled source status; they must never show a retired source as currently attempted.

## 3. Entities

### E1. `YahooChartRequest`

Logical request tuple:

- `ticker: str`
- `interval: Literal["1d"]`
- `range_param: Literal["1y"]`
- endpoint host fixed to `query2.finance.yahoo.com`

### E2. `YahooChartResult`

- `ticker: str`
- `rows: tuple[OHLCRow, ...]`, ascending by trading date
- explicit upstream chart errors raise `SourceFetchError`
- shape-invalid rows are omitted

### E3. `PriceFallbackDecision`

- `ticker: str`
- `direct_present: bool`
- `history_row: OHLCRow | None`
- `accepted: bool`
- internal rejection reason from `{direct-wins, missing-history, future, stale, invalid-numeric}`

Rejection reasons are operator diagnostics only and do not enter public prose.

### E4. `ReconciledPriceCollection`

- `items: tuple[NormalizedItem, ...]`
- `outcomes: tuple[SourceOutcome, ...]`
- `fallback_count: int`

The collection is produced once and becomes the accumulated pipeline state used by every downstream stage.

### E5. Korean replacement adapters

- `yonhap-index-close`: KOSPI/KOSDAQ close parsed from existing market RSS.
- `fred-fx-close`: DEXKOUS H.10 KRW-per-USD daily observation.

## 4. Business Rules

### R1. Retired-host prohibition

Production source code must not request:

- `https://stooq.com/q/l/`
- `https://query1.finance.yahoo.com/v8/finance/chart`

Historical documents and fixture evidence are not production source code.

### R2. Proven Yahoo request shape

Both snapshot and history callers use `query2`, `interval=1d`, `range=1y`, one browser User-Agent constant, and the shared parser.

### R3. Critical-first sequencing

The fixed critical basket runs before enrichment. Enrichment starts only if the critical pass emits at least one item. Each ticker is isolated; a ticker failure never cancels siblings.

### R4. Direct snapshot wins

A same-run history row never overwrites a direct `yfinance-price` item with the same canonical ticker.

### R5. Fallback freshness

A history row is eligible only when:

- its trading date is not after the target date;
- it is at most four calendar days old;
- OHLC values are finite and positive;
- volume is absent or non-negative.

### R6. Fallback provenance

Fallback items preserve the existing `yfinance-price` source identity and add:

- `provenance=query2-history-fallback`
- `history_range=1y`
- canonical ticker, OHLCV, and core-fact metadata

Direct items add `provenance=query2-snapshot` so the two paths are distinguishable without changing reader-facing source names.

### R7. Outcome reconciliation

If fallback adds at least one item, replace exactly one `yfinance-price` outcome with an `ok` outcome whose count and latest timestamp match the final item set. The original status is emitted in a structured operator log. If fallback adds zero items, preserve the original outcome.

### R8. Downstream consistency

Reconciled items/outcomes must replace the pipeline's accumulated values before:

- `segment_items`
- `segment_source_outcomes`
- coverage severity
- prompt candidate construction
- visual asset preparation
- quality snapshot/history
- publish and notify

### R9. Stooq identity removal

`stooq-price` and `stooq-kr-market` are not registered adapters, source specs, core sources, market-window sources, or routing members after this unit.

### R10. Yonhap replacement identity

The existing u67 RSS numeric parser is retained under `yonhap-index-close`. It fetches one RSS document and can emit KOSPI/KOSDAQ only. Absence of a matching numeric headline returns zero items and remains visible as fallback absence.

### R11. FRED FX source-of-truth

`fred-fx-close` requests fixed series `DEXKOUS` through the existing FRED API key path. It emits KRW per one USD and must not invert the value. Its timestamp represents New York noon on the observation date, not the KRX close.

### R12. FRED FX freshness and secret hygiene

- A valid observation older than seven calendar days is omitted.
- `.` placeholders are skipped.
- Missing `FRED_API_KEY` produces `SourceFetchError(transient=False)` naming only the env-var.
- The API key is absent from logs, fixtures, metadata, URLs, and errors.

### R13. License/no-paid boundary

- Cboe and Nasdaq quote-page JSON are forbidden adapter candidates under current official automated-extraction restrictions.
- Restricted FRED S&P/Dow/Nasdaq index series are not public fallbacks.
- No new vendor key, dependency, paid plan, or scrape/browser path is introduced.

## 5. Flow

1. Collector runs `yfinance-price` against query2 critical basket.
2. If critical emits at least one item, it runs the enrichment basket.
3. Collector runs `yonhap-index-close` and `fred-fx-close` with normal adapter isolation.
4. Collector returns items/outcomes; no Stooq adapter exists.
5. Generate stage loads query2 history for u49 anchors.
6. Reconciliation examines only missing critical Yahoo tickers.
7. Accepted fallback rows become `yfinance-price` items; its outcome is rebuilt.
8. Accumulated items/outcomes are replaced.
9. Segmentation, quality, generation, visuals, publish, and notify consume the same final collection.

## 6. Interface Contracts

### I1. Shared Yahoo parser

```python
async def fetch_chart_rows(
    client: httpx.AsyncClient,
    ticker: str,
    *,
    range_param: str = "1y",
    interval: str = "1d",
) -> tuple[OHLCRow, ...]: ...
```

### I2. Fallback reconciliation

```python
def reconcile_yahoo_history_fallback(
    *,
    items: Sequence[NormalizedItem],
    outcomes: Sequence[SourceOutcome],
    history_by_ticker: Mapping[str, Sequence[OHLCRow]],
    target_date: date,
) -> ReconciledPriceCollection: ...
```

### I3. Source specs

- `yfinance-price`: tier A, US market window, US item/outcome segment.
- `yonhap-index-close`: tier B, domestic market window/item/outcome segment.
- `fred-fx-close`: tier S, domestic market window/item/outcome segment.

### I4. Core facts

- Yahoo mappings remain unchanged for US indices/equities.
- `fred-fx-close` stamps the canonical `usd_krw` core-fact key for `KRW=X`.
- Yonhap stamps KOSPI/KOSDAQ core-fact keys.

### I5. Operator log

Event name: `price_fallback_reconciled`.

Fields:

- `source_name=yfinance-price`
- `original_status`
- `direct_count`
- `fallback_count`
- `final_count`

No response body, URL, headline, ticker list, or secret is logged by this event.

## 7. Edge Cases

- Query2 critical basket entirely 429: enrichment skipped; history can still recover later; otherwise coverage degrades.
- Query2 returns explicit delisted-symbol error: that ticker omitted; siblings continue.
- History contains Friday row for Monday target: age three, accepted.
- History contains row five days old: rejected.
- Direct and history disagree: direct wins; u70 reconciliation handles downstream anchors as before.
- FRED latest observation is `.`: walk to prior valid observation, then apply seven-day freshness.
- Yonhap feed contains no numeric close: zero items, no fabricated value.
- Existing historical docs mention Stooq: allowed; runtime registries do not.

## 8. Non-Goals

- Intraday data, order books, realtime prices, and trade execution.
- New LLM behavior or prompt sections.
- Archive backfill.
- Exact-index substitution with ETFs.
- A generic multi-provider abstraction before a second terms-compliant independent provider is available.

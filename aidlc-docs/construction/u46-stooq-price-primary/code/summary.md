# u46 Stooq Price Primary — Code Generation Summary

**Date**: 2026-05-10
**Unit**: u46 stooq-price-primary
**Status**: Complete (4/4 steps)

## Goal

Replace fundamentally-unreliable yfinance-price (HTTP 429 IP-level rate-limit on every GHA run, see 2026-05-09 diagnostic) with a Stooq primary adapter. Stooq is unauth, free, global, and serves CSV — perfect for GHA cron. yfinance retained as a parallel registered adapter so the candidate stream gets union of both.

## Steps

### Step 1 — New `stooq-price` adapter

- `src/investo/sources/stooq_price.py` — `@register`, `name="stooq-price"`, `category="price"`, tier `A`.
- Endpoint: `https://stooq.com/q/l/?s={sym}&i=d&h=1&f=sd2t2ohlcv` (header + 1 row CSV).
- Default 13 tickers, keyed in **yfinance vocabulary** so `INVESTO_STOOQ_TICKERS` env-var override accepts the same syntax as yfinance:
  - Indices: `^GSPC` → `^spx`, `^IXIC` → `^ndq`, `^DJI` → `^dji`, `^VIX` → `^vix` (no data → silent skip).
  - Big tech: `AAPL` → `aapl.us`, `MSFT`, `GOOGL`, `AMZN`, `NVDA`, `META`, `TSLA`.
  - Crypto: `BTC-USD` → `btc.v`, `ETH-USD` → `eth.v` (plan draft had `btcusd` / `ethusd` — `btcusd` is stale, `ethusd` is dead; corrected during the R10 recording session).
- Concurrency: default 3 (`INVESTO_STOOQ_CONCURRENCY` override).
- Per-ticker isolation: 5xx / malformed CSV / N/D placeholder / unmapped ticker all silent-skip + sibling unaffected.
- R11: `published_at` pinned to 16:00 ET → UTC for parity with yfinance.

### Step 2 — Routing wiring

- `src/investo/briefing/segments.py`: added `"stooq-price"` to `_US_ONLY_SOURCES` (single line).
- BTC/ETH stooq items auto-route to **crypto** via u45's `_has_strong_crypto_signal` ticker regex (`\b(BTC|ETH)\b`). No dual-segment registration needed — preserves u45's exclusivity contract.
- `src/investo/sources/__init__.py`: discovery import.
- `src/investo/sources/tiers.py`: tier `A` registry entry.

### Step 3 — R10 live fixture session (recorded 2026-05-10)

14 byte-equal CSV captures under `tests/unit/sources/fixtures/api/stooq-price/`:

| Fixture | Stooq sym | Bytes | Note |
|---------|-----------|-------|------|
| GSPC.csv | ^spx | 106 | live |
| IXIC.csv | ^ndq | 118 | live |
| DJI.csv | ^dji | 111 | live |
| VIX.csv | ^vix | 79 | N/D placeholder — Stooq does not carry CBOE indices |
| AAPL.csv | aapl.us | 108 | live |
| MSFT.csv | msft.us | 109 | live |
| GOOGL.csv | googl.us | 105 | live |
| AMZN.csv | amzn.us | 108 | live |
| NVDA.csv | nvda.us | 110 | live |
| META.csv | meta.us | 112 | live |
| TSLA.csv | tsla.us | 111 | live |
| BTC-USD.csv | btc.v | 127 | live (corrected from `btcusd`) |
| ETH-USD.csv | eth.v | 119 | live (corrected from `ethusd`) |
| NOTFOUND.csv | zzzznonexistent | 90 | N/D placeholder |

`meta.json` sidecar records URL template, recording timestamp, per-fixture notes. No auth surface → no redaction needed.

### Step 4 — Tests + quality gate

- New `tests/unit/sources/test_stooq_price.py` — **19 tests**: recorded-fixture happy path, AAPL field mapping, raw_metadata shape, BTC fractional-volume truncation, N/D placeholder skip, sibling-isolation invariants, malformed CSV row, empty body, unmapped ticker, R11 EDT/EST close-time anchors, R12 env-var override (subset + full default), branded UA, default + override concurrency caps.
- Extended `tests/unit/briefing/test_segments_exclusivity.py` — **+4 tests**: `^GSPC` / `BTC-USD` / `ETH-USD` / `AAPL` routing scenarios.
- Extended `tests/unit/sources/test_plugin_contract.py` — adapter count 18 → 19, name set + import + isolation fixture + leak guard.

| Gate | Result |
|------|--------|
| `ruff check src tests` | clean |
| `ruff format src tests` | clean (2 files reformatted at write, then clean) |
| `mypy --strict src` | 98 source files, no issues |
| `pytest -x` | **1621 passed** (+23) |
| `mkdocs build --strict` | clean |

## Files changed

- `src/investo/sources/stooq_price.py` (new, ~280 lines)
- `src/investo/sources/__init__.py` (1-line discovery import)
- `src/investo/sources/tiers.py` (tier registry entry)
- `src/investo/briefing/segments.py` (1-line `_US_ONLY_SOURCES` add)
- `tests/unit/sources/test_stooq_price.py` (new, 19 tests)
- `tests/unit/briefing/test_segments_exclusivity.py` (+4 tests)
- `tests/unit/sources/test_plugin_contract.py` (count 18→19)
- 14 fixture CSVs + `meta.json` under `tests/unit/sources/fixtures/api/stooq-price/`

## TECH-DEBT candidates surfaced (not filed)

1. **VIX gap on Stooq** — `vxx.us` ETF proxy could fill the volatility hole if the briefing needs VIX before u49 lands.
2. **Stooq multi-day history endpoint** — `&d1=YYYYMMDD&d2=YYYYMMDD` returns multi-row history. **u49 deterministic-market-anchor should reuse `_TICKER_MAP` and add a sibling `fetch_history(window, ticker, days=N)` helper** rather than building a parallel history fetcher. High-value candidate, directly enables u49.
3. **Crypto volume float→int truncation** — Stooq reports BTC/ETH volume as fractional crypto units (e.g. `14237.042997827913`); current adapter truncates. If u49 needs raw volume, switch raw_metadata field to string-of-float.

## Plan correction propagated

Plan draft listed `btcusd` / `ethusd` as Stooq symbols; live recording session showed `btcusd` is stale and `ethusd` is dead. Adapter ships with `btc.v` / `eth.v`. Fixture meta.json + adapter docstring document the correction so the next planner-side closeout doesn't propagate the stale recipe.

## Out of scope (per plan)

Source-level fallback logic (stooq fail → yfinance auto-trigger), anchor calculation (u49), chart embed (u50), headline RSS source (u48 demoted by user insight).

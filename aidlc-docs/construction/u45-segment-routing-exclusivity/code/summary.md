# u45 Segment Routing Exclusivity — Code Generation Summary

**Date**: 2026-05-10
**Unit**: u45 segment-routing-exclusivity
**Status**: Complete (4/4 steps)

## Goal

Close the if/if/if dual-routing bug in `segment_items()` (`src/investo/briefing/segments.py`). Replace it with priority-based, source-anchored routing where every item lands in at most one segment unless its source is in the explicit `_SHARED_SOURCES_BY_SEGMENT` allow-list. Triggered by 2026-05-09 cron US-equity quality regression: items #54 / #76 / #82 (theblock-crypto + "SEC", yahoo-finance + "Bitcoin", yahoo-finance + crypto-conference) leaked into the us-equity briefing.

## Steps

### Step 1 — Source allow-list refactor

- Split `_DOMESTIC_SOURCES` / `_US_SOURCES` / `_CRYPTO_SOURCES` into `*_ONLY_SOURCES` (single-segment anchored) and `_SHARED_SOURCES_BY_SEGMENT` (explicit fan-out registry).
- Today's only shared source: `treasury-rates` (us-equity + crypto, intentional).
- Backward-compatible aggregate views derived as `only ∪ shared`, so existing callers (`segment_source_outcomes`, `briefing/pipeline.py`, `orchestrator/pipeline.py`) keep working unchanged.

### Step 2 — Priority-based routing in `segment_items()`

- New decision order:
  1. shared fan-out
  2. crypto-only source
  3. domestic-only source
  4. us-only source (with strong-crypto-signal override that *moves*, not duplicates, to crypto)
  5. keyword fallback for orphan sources
- New helper `_has_strong_crypto_signal(item)` with three independent triggers:
  - `_CRYPTO_TITLE_PREFIX_RE`: `bitcoin|ethereum|btc|eth|crypto|stablecoin|defi` (start of title)
  - `_CRYPTO_TICKER_RE`: `\b(BTC|ETH)\b` in title or summary
  - `_CRYPTO_PRICE_PHRASES`: `bitcoin price` / `ethereum price` / `btc price` / `eth price` / `bitcoin and ethereum` (substring)
- `_is_us_equity` / `_is_crypto` renamed to `_matches_us_equity_keyword` / `_matches_crypto_keyword` and only run in the keyword-fallback path. `_US_MARKET_TERMS` and the `_CRYPTO_CROSS_MARKET_TERMS + Fed` combo can no longer drag a source-anchored item across segments — closing the leak structurally.

### Step 3 — Anti-regression test suite

- New `tests/unit/briefing/test_segments_exclusivity.py` with 17 tests covering R1-R7, ticker word-boundary, keyword-fallback paths, and the non-shared exclusivity invariant.
- Updated `tests/unit/briefing/test_segments.py`: replaced `test_fed_liquidity_item_can_route_to_us_and_crypto` (asserted OLD bug behaviour) with `test_us_only_source_with_fed_keywords_does_not_dual_route_to_crypto` and `test_shared_treasury_rates_source_fans_out_to_us_and_crypto`.

### Step 4 — Quality gate

| Gate | Result |
|------|--------|
| `ruff check` | passed |
| `ruff format --check` | 242 files already formatted |
| `mypy --strict src/` | no issues, 97 source files |
| `pytest -q` | 1575 passed |
| `mkdocs build --strict` | built in 0.43s |

## Behaviour delta (verified by tests)

| Scenario | Pre-u45 | Post-u45 |
|----------|---------|----------|
| theblock-crypto + body "SEC" (Item #54) | crypto + us-equity | **crypto only** |
| yahoo-finance + title "Bitcoin and ethereum prices today" (Item #76) | us-equity + crypto | **crypto only** |
| yahoo-finance + title "Crypto: 7 ideas from Consensus" (Item #82) | us-equity + crypto | **crypto only** |
| yahoo-finance + title "S&P 500 reaches new high" | us-equity (+ stray crypto) | us-equity only |
| fomc-rss + body "liquidity hits risk assets" | us-equity + crypto | **us-equity only** |
| treasury-rates (any) | us-equity + crypto | us-equity + crypto (preserved via explicit shared registry) |

## Files changed

- `src/investo/briefing/segments.py` (modified)
- `tests/unit/briefing/test_segments.py` (modified)
- `tests/unit/briefing/test_segments_exclusivity.py` (new, 17 tests)

## TECH-DEBT candidate (do not file yet)

English-only crypto title prefix regex — file DEBT entry only when the first Korean crypto source (e.g. 한경코인) is registered. Plan also flags this as an open question.

## Out of scope (per plan)

BTC/ETH narrative dominance prompt rules, Stooq price primary (u46), yahoo-finance news content filter (u47), deterministic market anchor (u49), chart embed (u50).

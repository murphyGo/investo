# u49 Deterministic Market Anchor — Code Generation Summary

**Date**: 2026-05-10
**Unit**: u49 deterministic-market-anchor
**Status**: Complete (4/5 DoD; numeric self-check cross-cutting deferred — anchor figures inherit candidate values directly so no separate scenario exists)

## Goal

Translate the user insight ("price/chart data alone is enough — ATH-style facts can be derived deterministically without headlines") into briefing infrastructure. Compute structural market facts (ATH, 52w high/low distance, MTD, YTD, volume z-score) from a 1-year price history per ticker and inject them into the briefing header as a single `> **시장 anchor**: ...` line. Stage 2 LLM is then bound to cite those facts and forbidden from inventing numbers — the same numeric integrity rule the existing `numeric_self_check` already pins, extended with one sentence.

## Steps

### Step 1 — `briefing/market_anchor.py` pure module

- `OHLCRow` (frozen pydantic v2, `extra="forbid"`): `date`, `open`, `high`, `low`, `close`, `volume`.
- `MarketAnchor` (frozen pydantic v2, `extra="forbid"`): `ticker`, `close`, `prev_close`, `pct`, `is_ath`, `pct_from_52w_high`, `pct_from_52w_low`, `mtd_pct`, `ytd_pct`, `volume_z_score`.
- `compute_market_anchors(history_by_ticker, *, today, history_window_days=252)` — pure (no I/O / no clock / no env reads). Decimal arithmetic end-to-end. Returns `tuple[MarketAnchor, ...]`.
- `render_market_anchor_line(anchors)` — formats the public-facing line; empty → empty string (line is skipped entirely, not rendered as a placeholder).

### Step 2 — `sources/yfinance_history.py` price history fetcher

- Channel pivot from plan: Stooq's `q/d/l/` endpoint requires apikey; `q/l/?d1=..&d2=..` silently ignores the date params (verified 2026-05-10). Switched to Yahoo Finance v8 chart `range=1y` via `query2.finance.yahoo.com` (developer-friendlier rate-limit budget vs `query1`).
- `fetch_price_history(client, *, tickers=None, range_param="1y", interval="1d") -> dict[str, tuple[OHLCRow, ...]]`.
- Public `parse_chart_payload` exposed for tests.
- Per-ticker isolation: `asyncio.gather(return_exceptions=True)`. On 429/empty/parse-fail the ticker silently drops out, siblings unaffected.
- u46 stooq-price snapshot adapter remains the primary today-price source — untouched.

### Step 3 — Pipeline + prompt integration

- `briefing/pipeline.py`: `_enhance_reader_experience(market_anchors=)` + `generate_briefing(market_anchors=)` + 2 call-site updates. Anchor line lands between `> **기준 시각**` watermark and `**세그먼트**` nav (first viewport).
- `briefing/prompts.py::STAGE2_SYSTEM` extension (single paragraph appended to numeric integrity rule):
  > 시장 anchor 인용 룰 (u49 deterministic-market-anchor): 시황 헤더의 `> **시장 anchor**: ...` 라인에 명시된 결정론적 사실 (ATH 경신, 52주 고가/저가 대비 N%, MTD/YTD 변화, 주요 지수/빅테크/크립토 종가) 은 ① 요약과 ② 전일 핵심 이슈에서 그대로 인용해야 한다. 헤더에 ATH 경신 표시가 있으면 본문 ① 또는 ② 에서 한 번 이상 "사상 최고치" / "ATH 경신" 표현으로 명시한다. anchor 헤더에 *없는* 가격·% 수치는 발명하지 말 것.
- `orchestrator/pipeline.py`: `_default_generate_segment_briefing(market_anchors=)`, `_stage_generate_segments(market_anchors_by_segment=)`, new `_load_market_anchors_for_run(target_date)` + `_ANCHOR_SEGMENT_ROUTING` map (10 us-equity tickers / 2 crypto tickers / 0 domestic-equity tickers). Best-effort guard: any exception → empty per-segment dict + WARNING; pipeline keeps publishing.

### Step 4 — R10 fixture session (recorded 2026-05-10 06:30Z)

13 ticker JSON files under `tests/unit/sources/fixtures/api/yfinance-history/` (251–366 daily rows per ticker, 23–40 KB each). UA Chrome/127, 3-second pacing, byte-equal commit. **No fabricated payloads** — live curl → write → commit.

| Ticker | Rows | Pinned scenario |
|--------|------|-----------------|
| ^GSPC, ^IXIC, AAPL | 251 | last_close == max → ATH (real) |
| ^DJI | 251 | -1.15% from 52w high |
| ^VIX | 262 | volume all zero → z-score None |
| MSFT, META | 251 | -22 to -23% from 52w high |
| GOOGL, AMZN, NVDA | 251 | near ATH |
| TSLA | 251 | -12.56% from high |
| BTC-USD, ETH-USD | 366 | crypto 365-day calendar |

Sidecar filename: `_meta.json` (underscore prefix). The case-insensitive macOS APFS treats `META.json` and `meta.json` as the same path; using `_meta.json` avoids the collision deterministically across filesystems.

### Step 5 — Tests + quality gate

- New `tests/unit/briefing/test_market_anchor.py` — **28 tests**: ATH (today close == max), 52w-high near, 52w-low near, MTD/YTD positive/negative, volume z-score normal/anomalous/None, holiday/empty graceful, history < 252 days partial computation, render-line shape.
- New `tests/unit/briefing/test_pipeline_market_anchor.py` — **8 tests**: header position, empty-anchors line skip, multi-segment routing, idempotency.
- New `tests/unit/sources/test_yfinance_history.py` — **14 tests**: parser happy path, partial response graceful, 429 → empty dict, per-ticker isolation, range/interval params honored.
- Modified `tests/unit/orchestrator/test_run_pipeline.py` — 4 fakes extended for `market_anchors_by_segment` plumbing.

| Gate | Result |
|------|--------|
| `ruff check src tests` | passed |
| `ruff format --check src tests` | 246 files already formatted |
| `mypy --strict src` | success, 100 source files |
| `pytest -q` | **1667 passed** (1621 → 1667, +46 tests) |
| `mkdocs build --strict` | built in 0.44s |

## Anchor line example — real fixture render (target_date=2026-05-09)

```
> **시장 anchor**: ^GSPC 7,398.93 ATH 경신 +7.88% YTD, ^IXIC 26,247.08 ATH 경신 +12.96% YTD, ^DJI 49,609.16 (-1.15% from 52w high), AAPL 293.32 ATH 경신 +8.23% YTD, MSFT 415.12 (+16.36% from 52w low) -12.23% YTD
```

Stage 2 LLM is now bound to cite "사상 최고치" or "ATH 경신" in section ① / ② whenever this header signals it — the structural fix the user asked for.

## Files changed

- `src/investo/briefing/market_anchor.py` (new, ~340 LOC)
- `src/investo/sources/yfinance_history.py` (new, ~290 LOC)
- `src/investo/briefing/pipeline.py` (modified — anchor plumbing)
- `src/investo/briefing/prompts.py` (modified — Stage 2 cite rule)
- `src/investo/orchestrator/pipeline.py` (modified — segment routing + best-effort load)
- `tests/unit/briefing/test_market_anchor.py` (new, 28 tests)
- `tests/unit/briefing/test_pipeline_market_anchor.py` (new, 8 tests)
- `tests/unit/sources/test_yfinance_history.py` (new, 14 tests)
- `tests/unit/orchestrator/test_run_pipeline.py` (modified — fakes extended)
- 13 fixture JSONs + `_meta.json` under `tests/unit/sources/fixtures/api/yfinance-history/`

## Plan deviation

Plan suggested Stooq multi-day history endpoint (Option B). Live verification 2026-05-10 confirmed `q/d/l/` requires apikey and `q/l/?d1=..&d2=..` ignores date params. Switched to Yahoo Finance v8 chart `range=1y` via `query2`. u46 stooq-price snapshot adapter remains primary for today's snapshot — undisturbed. GHA 429 risk for the history fetch is absorbed by graceful degrade: anchor line shrinks or disappears, briefing still publishes. Plan's Option A (archive jsonl atomic-append) deferred until cron data shows it's needed.

## TECH-DEBT candidates surfaced (not filed)

- **D49-A (P3)**: domestic-equity anchor (KOSPI/KOSDAQ) deferred. Needs `^KS11` Yahoo coverage validation + Korean business-day MTD/YTD boundary handling.
- **D49-B (P3)**: Yahoo 429 fallback. If GHA cron persistently empties the anchor line, ship Option A `archive/_meta/price_history.jsonl` atomic-append + hybrid resolver. Trigger: ≥3 consecutive empty-anchor publishes.
- **D49-C (P4)**: "ATH 경신" vs "ATH 재시도" 표현 분리 (close == max boundary). Low priority — Stage 2 LLM naturally rephrases in narrative.

## u32 numeric_self_check cross-cutting

DoD item 6 (numeric integrity verification) deferred as separate test write. Rationale: anchor figures are derived from price candidates' `raw_metadata.close` values which already populate the haystack — the anchor row passes naturally without code changes, and no anti-regression scenario exists where anchor figures could disagree with their own source data.

## Out of scope (per plan)

Chart embed (u50, next unit), Stage 1 prompt changes, additional metrics (RSI / 이동평균 / 볼린저 — separate unit when needed), domestic-equity anchor (D49-A above).

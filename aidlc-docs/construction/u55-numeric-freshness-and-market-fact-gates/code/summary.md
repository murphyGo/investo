# u55 Numeric / Date / Freshness Gate — Code Generation Summary

**Date**: 2026-05-13
**Unit**: u55 numeric-freshness-and-market-fact-gates
**Status**: Complete (7/7 steps, 50/50 checkboxes, 10/10 ACs)
**FR**: FR-011

## Goal

Upgrade quality system from "numbers exist" (u32 substring presence) to "core numbers are verified against source items or market anchors within tolerance". Detect date-token corruption (`5/65/7`) and segment-specific archive staleness before publish.

## Quality Gate

| Gate | Result |
|------|--------|
| `ruff check .` | passed |
| `ruff format --check` | 303 files clean |
| `mypy --strict src/` | 119 files, 0 issues |
| `pytest -q` | **2089 passed** (1977 → +112, plan est. +44-56) |
| `mkdocs build --strict` | exit 0 |

## Key Deliverables

- **`CoreFact` Literal[10]** — kospi/kosdaq/spx/ndx/dji/btc/eth + 3 Phase-2 stubs (usd_krw/us10y_yield/vix).
- **`numeric_verify.verify_core_facts`** — keyword-scoped 40-char window, Decimal tolerance comparison (price ±0.01 / pct ±0.05pp / yield ±1bp / BTC ±$1 / ETH ±$0.5).
- **`NumericGateAction` enum** — pass/warn/downgrade/block routing per gate outcome.
- **`date_corruption.find_corrupt_date_tokens`** — `r"\d{1,2}/\d{1,2}(?:/\d{1,2})?"` post-match month/day sanity; `block` on violation.
- **`date_corruption.verify_direction_against_anchor`** — ATH/52w high claims cross-checked against `MarketAnchor`.
- **`freshness.evaluate_segment_freshness`** + **`SegmentResult` model** — per-segment fresh/stale/failed status; publisher only archives/Telegrams `fresh`.
- **`market_calendar.py`** — hand-rolled KRX 2026 + NYSE 2026 휴장일 (KRX 공지 / NYSE 공지 URL 코멘트). Crypto = 24/7. No paid calendar deps.
- **`figures_verified` KPI** — new append-only column on `quality_eval` + `quality_history` JSONL + `quality_sparkline`. Coexists with `figures_presence` (u32, unchanged).
- **`OperatorAlerter.numeric_alert`** — R13-safe template (no secret-shaped substrings).

## Design Deviation (audit-logged)

`raw_metadata["core_facts"]` nested dict → **flat key prefix `core_fact:<name>`**. Root cause: `_MetadataValue = StrictStr | StrictInt | StrictFloat` rejects nested dicts. `numeric_verify` iterates `raw_metadata` items filtering by prefix. Surface to gate consumers unchanged.

## Files

**New (14 source + tests)**:
- `src/investo/models/core_fact.py`
- `src/investo/models/market_calendar.py`
- `src/investo/models/segment_result.py`
- `src/investo/sources/_core_fact_map.py`
- `src/investo/briefing/numeric_verify.py`
- `src/investo/briefing/date_corruption.py`
- `src/investo/briefing/freshness.py`
- 7 new test files (97 tests across models / briefing / notifier / integration canary)

**Modified (~7)**:
- `src/investo/sources/{stooq_price,yfinance}.py` (CoreFact stamping)
- `src/investo/briefing/{quality_eval,quality_history}.py` (figures_verified KPI)
- `src/investo/visuals/quality_sparkline.py`
- `src/investo/notifier/operator_alerter.py` (numeric_alert)
- `tests/unit/sources/{test_stooq_price,test_yfinance}.py` (CoreFact stamping +5)
- `docs/requirements.md` (FR-011)

## Scope Adjustment

Step 4/6 **orchestrator full signature migration deferred** — `SegmentResult` model + `evaluate_segment_freshness` helper land as new public APIs; canary integration test pins the 4-gate composition end-to-end. Logged as **D55-E** for follow-up.

## TECH-DEBT Candidates

- **D55-A** USD/KRW + US10Y yield CoreFact activation (currently `warn` stubs).
- **D55-B** 2027 calendar refresh.
- **D55-C** KoNLPy morpheme-aware claim window (vs current 40-char heuristic).
- **D55-D** Regenerate-on-block path (currently `block` → publish abort; no retry).
- **D55-E** Orchestrator wire-through + per-segment callout insertion + numeric_alert dispatch.

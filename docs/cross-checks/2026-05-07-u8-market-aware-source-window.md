# Cross-Check Report: u8 market-aware source window

**Date**: 2026-05-07
**Scope**: Unit `u8 market-aware source window` / FR-001 + FR-008 coverage correction
**Checked by**: Codex

## Summary

| Status | Count | Percentage |
|--------|-------|------------|
| ✅ Complete | 1 | 100% |
| ⚠️ Partial | 0 | 0% |
| ❌ Gap | 0 | 0% |
| **Total** | **1** | **100%** |

**Verdict**: ✅ Complete. The source collection window now matches each market's local day, preventing US equity and crypto segments from being emptied solely by the KST cutoff.

## Compliance Matrix

| ID | Description | Status | Evidence | Notes |
|----|-------------|--------|----------|-------|
| FR-001 / FR-008 | 시장별 데이터 수집 window와 세그먼트 커버리지 | ✅ Complete | `src/investo/sources/_window.py`, `src/investo/sources/aggregator.py`, `tests/unit/sources/test_window.py`, `tests/unit/sources/test_aggregator.py`, `tests/unit/briefing/test_segments.py`, `tests/unit/orchestrator/test_run_pipeline.py` | Domestic remains KST; US-market sources use America/New_York; crypto sources use UTC. |

## Acceptance Criteria Detail

| Criterion | Status | Evidence |
|-----------|--------|----------|
| 국내 소스는 기존 KST window를 유지한다. | ✅ | `FetchWindow.from_kst_date()` remains as the domestic/default path; existing window tests remain green. |
| 미국 증시/매크로/SEC/Nasdaq/FOMC/Yahoo/CNBC 소스는 New York 기준 target date window를 받는다. | ✅ | `_US_MARKET_SOURCES` and `_window_for_adapter()` in `aggregator.py`; covered by `test_fetch_all_passes_new_york_window_to_us_market_adapter`. |
| 크립토 소스는 UTC 기준 target date window를 받는다. | ✅ | `_CRYPTO_MARKET_SOURCES` and `_window_for_adapter()` in `aggregator.py`; covered by `test_fetch_all_passes_utc_window_to_crypto_adapter`. |
| KST window 밖이지만 미국/UTC 시장 당일인 데이터가 수집에서 빠지지 않는다. | ✅ | `test_fetch_all_keeps_same_day_us_and_crypto_items_after_kst_cutoff` pins `2026-05-06T18:00:00Z` for both US and crypto source items. |
| u7 segmented generation behavior remains compatible. | ✅ | `tests/unit/briefing/test_segments.py` and `tests/unit/orchestrator/test_run_pipeline.py` passed with the source-window change. |

## Verification

- `uv run pytest tests/unit/sources/test_window.py tests/unit/sources/test_aggregator.py tests/unit/briefing/test_segments.py tests/unit/orchestrator/test_run_pipeline.py -q` ✅ 88 passed
- `uv run ruff check .` ✅
- `uv run ruff format --check .` ✅ 140 files already formatted
- `uv run mypy --strict src/` ✅ 52 source files
- `uv run pytest -q` ✅ 964 passed
- `uv run mkdocs build --strict` ✅

## Gaps Analysis

No gaps found for the correction scope.

# u104 Code Generation Summary

## Overview

u104 adds bounded official SEC company facts and Nasdaq Trader symbol-directory metadata for watchlist-oriented US equity context. The unit adds no paid provider and no broad SEC bulk ingestion.

## Files Changed

- Created: `src/investo/sources/sec_company_facts.py`
- Created: `src/investo/sources/nasdaq_symbol_directory.py`
- Created: `tests/unit/sources/test_sec_company_facts.py`
- Created: `tests/unit/sources/test_nasdaq_symbol_directory.py`
- Created: `tests/unit/sources/fixtures/api/sec-company-facts/`
- Created: `tests/unit/sources/fixtures/api/nasdaq-symbol-directory/`
- Modified: `src/investo/sources/__init__.py`
- Modified: `src/investo/sources/aggregator.py`
- Modified: `src/investo/sources/tiers.py`
- Modified: `src/investo/briefing/segments.py`
- Modified: `tests/unit/sources/test_plugin_contract.py`
- Modified: `tests/unit/briefing/test_segments.py`

## Implementation

- Added `sec-company-facts`, backed by SEC `submissions` and `companyfacts` JSON endpoints.
- Added `nasdaq-symbol-directory`, backed by Nasdaq Trader `nasdaqlisted.txt` and `otherlisted.txt`.
- SEC company selection is bounded by `INVESTO_SEC_COMPANY_CIKS` and capped at 8 companies, with safe defaults matching the existing mega-cap watchlist bundle.
- SEC XBRL concept collection is fixed to revenue, net income, diluted EPS, assets, liabilities, operating cash flow, and shares outstanding.
- SEC requests carry the non-secret fair-access User-Agent, are spaced between calls, run under a 20s adapter-level budget, and isolate per-company failures so one bad configured CIK does not drop the whole source when other companies succeed.
- Nasdaq symbol selection is bounded by `INVESTO_NASDAQ_SYMBOLS` and capped at 16 symbols.
- Both adapters emit compact `macro` `NormalizedItem` summaries so static company/listing context cannot satisfy required `news` coverage or hide missing real news.

## Acceptance Criteria

| AC | Result | Evidence |
| --- | --- | --- |
| SEC company data fetches only configured watchlist companies and fixed concepts | Met | `test_fetch_returns_bounded_company_fact_item`, `test_env_config_is_bounded` |
| SEC requests use declared User-Agent and no API key | Met | `test_requests_carry_sec_user_agent`, `test_sec_requests_are_rate_limited_between_calls`, `test_adapter_total_budget_times_out_slow_sec_collection` |
| Nasdaq symbol directory records ETF flag and listing metadata | Met | `test_fetch_returns_configured_symbols_from_recorded_directory` |
| Company fact context is bounded and cannot exceed existing prompt candidate caps | Met | one compact item per configured company, capped at 8; source tests assert bounded request count |
| Missing concepts, malformed JSON, and SEC status errors degrade at adapter level | Met | missing concept, malformed JSON, status error, and partial company failure tests |
| No raw SEC payload, headers, cookies, or long filing excerpts are written to public markdown | Met | adapter emits compact title/summary/raw_metadata only; no renderer change |
| Static reference context cannot mask missing live coverage | Met | `test_static_company_reference_items_do_not_satisfy_news_coverage`, `test_static_company_reference_items_do_not_satisfy_item_threshold` |

## Validation

- `uv run pytest tests/unit/sources/test_sec_company_facts.py tests/unit/sources/test_nasdaq_symbol_directory.py tests/unit/sources/test_plugin_contract.py -q` -> 25 passed
- `uv run pytest tests/unit/briefing/test_segments*.py -q` -> 85 passed
- `uv run pytest tests/unit/briefing tests/unit/publisher -q -k 'fact or watchlist or source'` -> 169 passed, 1154 deselected
- `uv run ruff check src/investo/sources tests/unit/sources tests/unit/briefing/test_segments.py src/investo/briefing/segments.py` -> clean
- `uv run mypy --strict src/investo/sources src/investo/briefing` -> clean over 98 source files
- `uv run python scripts/check_no_paid_apis.py` -> clean

## Scope Notes

No SEC bulk archive, commercial fundamentals provider, analyst estimates, target prices, browser automation, or archive backfill was added.

# u103 Code Generation Summary

## Overview

u103 adds official, no-key Fed and SEC RSS sources so policy speeches, testimony, press releases, and statements can enter the briefing from source-of-record feeds instead of generic news.

## Files Changed

- Created: `src/investo/sources/fed_speech_rss.py`
- Created: `src/investo/sources/sec_newsroom_rss.py`
- Created: `tests/unit/sources/test_fed_speech_rss.py`
- Created: `tests/unit/sources/test_sec_newsroom_rss.py`
- Created: `tests/unit/sources/fixtures/api/fed-speech-rss/`
- Created: `tests/unit/sources/fixtures/api/sec-newsroom-rss/`
- Modified: `src/investo/sources/__init__.py`
- Modified: `src/investo/sources/aggregator.py`
- Modified: `src/investo/sources/tiers.py`
- Modified: `src/investo/briefing/segments.py`
- Modified: `tests/unit/sources/test_plugin_contract.py`
- Modified: `tests/unit/briefing/test_segments_exclusivity.py`

## Implementation

- Added `fed-speech-rss` over official Federal Reserve speeches and testimony RSS feeds.
- Added `sec-newsroom-rss` over official SEC press release and speech/statement RSS feeds.
- Both adapters use existing source-layer contracts: `retry_get`, `defusedxml`, `strip_html`, RFC 822 timestamp parsing to UTC, window filtering, and `SourceFetchError` for terminal malformed XML / transient status failures.
- SEC newsroom requests use the same non-secret fair-access User-Agent pattern as the existing SEC EDGAR adapter.
- Registered both adapters in the plugin surface, S-tier map, New York market-window set, and US segment source set.
- Reused u58 metadata routing by stamping SEC newsroom items with `policy_priority=crypto_regulation` only when text matches crypto-policy terms with crypto context.
- Recorded real RSS fixtures plus metadata declaring official source URLs, no auth, and no secret material.

## Acceptance Criteria

| AC | Result | Evidence |
| --- | --- | --- |
| Fed speeches and testimony are collected from official RSS without API key | Met | `test_fetch_returns_official_speech_items_from_recorded_fixtures` |
| SEC newsroom press releases and speeches/statements are collected from official RSS without API key | Met | `test_fetch_returns_official_sec_newsroom_items_from_recorded_fixtures` |
| Fed items route only to `us-equity` | Met | `test_fed_speech_rss_routes_only_to_us_equity` |
| SEC items route to `us-equity`; crypto routing requires explicit crypto-policy terms | Met | `test_sec_newsroom_generic_item_routes_only_to_us_equity`, `test_sec_newsroom_crypto_policy_metadata_routes_to_crypto` |
| Adapter failure is isolated by existing aggregator outcome handling | Met | adapter status-error tests plus existing `test_aggregator.py` failure isolation suite |
| Public markdown receives sanitized title/summary fields and no raw XML | Met | adapter HTML sanitation tests |

## Validation

- `uv run pytest tests/unit/sources/test_fed_speech_rss.py tests/unit/sources/test_sec_newsroom_rss.py tests/unit/sources/test_plugin_contract.py -q` -> 30 passed
- `uv run pytest tests/unit/briefing/test_segments*.py -q` -> 83 passed
- `uv run pytest tests/unit/sources/test_aggregator.py -q` -> 51 passed
- `uv run ruff check src/investo/sources tests/unit/sources tests/unit/briefing/test_segments_exclusivity.py src/investo/briefing/segments.py` -> clean
- `uv run python scripts/check_no_paid_apis.py` -> clean

## Scope Notes

No paid source, API key, browser automation, full speech HTML scraping, LLM prompt redesign, or archive backfill was added.

## Code Review

Subagent review found two High issues. Both were fixed before close: SEC newsroom requests now declare the SEC fair-access User-Agent, and generic non-crypto `market structure` items no longer receive crypto-policy metadata.

# u126 Code Summary: cftc-official-rss-policy-news

## Overview

u126 adds `cftc-policy-rss`, an official no-key CFTC RSS adapter for general press releases, enforcement releases, and speeches/testimony. It complements the existing delayed COT positioning adapter with source-of-record policy/news provenance.

## Files Changed

- `src/investo/sources/cftc_policy_rss.py` adds `CftcPolicyRssAdapter`, three-feed fetching, RSS parsing, item normalization, feed-level failure isolation, dedupe, UTC timestamps, and bounded max output.
- `src/investo/sources/__init__.py` registers the adapter for production discovery.
- `src/investo/_internal/source_specs.py` declares `cftc-policy-rss` as Tier S, US market-window, single-segment US routing.
- Tests add representative RSS fixtures and cover happy path, partial/all feed failure, malformed XML isolation, window filtering, URL/date validation, dedupe, metadata hygiene, crypto-policy priority stamping, plugin contract, source specs, tiers, and segment routing.

## Key Decisions

| Decision | Rationale |
|----------|-----------|
| Keep item routing single-segment US by default | CFTC agency releases are broadly US market policy/news unless explicitly crypto-policy prioritized. |
| Reuse u58 `policy_priority=crypto_regulation` metadata | Existing routing already preserves official crypto-policy items for the crypto segment without duplicating every CFTC item. |
| Isolate failures per RSS feed | A bad enforcement feed should not drop valid general press or speech/testimony items. |
| No full-page scraping | The adapter uses headline, RSS summary, publication time, and canonical CFTC URL only. |

## Validation

- `uv run --extra dev pytest tests/unit/sources/test_cftc_policy_rss.py tests/unit/sources/test_plugin_contract.py tests/unit/sources/test_source_specs.py tests/unit/sources/test_tiers.py tests/unit/sources/test_window.py tests/unit/briefing/test_segments.py tests/unit/sources/test_aggregator.py -q`
- `uv run --extra dev ruff check src/investo/sources/cftc_policy_rss.py src/investo/sources/__init__.py src/investo/_internal/source_specs.py src/investo/briefing/segments.py tests/unit/sources/test_cftc_policy_rss.py tests/unit/sources/test_plugin_contract.py tests/unit/sources/test_source_specs.py tests/unit/sources/test_tiers.py tests/unit/briefing/test_segments.py`
- `uv run --extra dev ruff format --check src/investo/sources/cftc_policy_rss.py src/investo/sources/__init__.py src/investo/_internal/source_specs.py src/investo/briefing/segments.py tests/unit/sources/test_cftc_policy_rss.py tests/unit/sources/test_plugin_contract.py tests/unit/sources/test_source_specs.py tests/unit/sources/test_tiers.py tests/unit/briefing/test_segments.py`
- `uv run --extra dev mypy src`
- `uv run --extra dev python scripts/check_no_paid_apis.py`

## TECH-DEBT

None.

# Code Generation Plan: `u104 sec-company-facts-and-symbol-directory`

**Date**: 2026-06-18
**Unit**: u104 sec-company-facts-and-symbol-directory
**Stage**: Code Generation
**Status**: Complete (9/9 steps — 2026-06-18)
**Source**: 2026-06-18 ten-agent data-source expansion review.
**Estimated Effort**: ~5-8 h
**Dependencies**:
- u102 source-adapter-registry-completeness
- u18/u73 watchlist relevance and impact center
- u55 numeric-freshness-and-market-fact-gates
- u101 verified fact context

---

## Problem Statement

US equity briefings currently have prices, generic market/news feeds, Nasdaq earnings calendar/news, and SEC current 8-K Atom filings. They do not have official watchlist CIK mapping, listing metadata, ETF flags, or bounded financial statement facts. This limits source-backed company explanations and makes watchlist/company context rely on ticker text rather than official identifiers.

## Goal

Add official SEC company submissions/companyfacts and Nasdaq Trader symbol directory anchors. The unit should supply bounded, source-backed company and listing facts for watchlist symbols without downloading the entire SEC corpus or overwhelming LLM candidate caps.

## Existing Coverage / Deduplication

- `sec-edgar-8k` covers current 8-K filings; it does not provide CIK maps, recent filing metadata by watchlist, or XBRL concepts.
- `nasdaq-earnings-calendar` covers earnings dates; it does not provide symbol universe metadata.
- `nasdaq-stocks-news` covers Nasdaq news RSS; it does not validate listing or ETF status.
- u55/u70 verify numeric claims; this unit provides source facts and leaves final numeric gate behavior unchanged.

## Scope Boundary

In scope:
- Bounded SEC company data for configured watchlist tickers/CIKs.
- Bounded concept allow-list for high-signal XBRL facts.
- Nasdaq Trader symbol directory parsing for listing exchange, ETF flag, test issue flag, and financial status.
- Context rendering that keeps company facts compact.

Out of scope:
- Bulk SEC ZIP ingestion.
- Full XBRL taxonomy support.
- Insider transaction parsing.
- Earnings-estimate, analyst-rating, or paid fundamental APIs.
- Changing the watchlist matcher.

## Stage Decision

Functional Design: skip. The unit composes established source adapter and prompt-context patterns.

NFR Requirements: skip. SEC fair-access and no-paid source constraints are defined in this plan.

## Implementation Steps

- [x] Add `src/investo/sources/sec_company_facts.py`.
- [x] Add `src/investo/sources/nasdaq_symbol_directory.py`.
- [x] Define env-configurable watchlist CIK/ticker list with safe defaults matching existing watchlist symbols.
- [x] Define a fixed XBRL concept allow-list for the first slice: revenue, net income, diluted EPS, assets, liabilities, operating cash flow, and shares outstanding.
- [x] Use SEC fair-access User-Agent and bounded request counts.
- [x] Parse Nasdaq `nasdaqlisted.txt` and `otherlisted.txt` pipe-delimited text files without browser automation.
- [x] Register adapters in source package imports, tiers, market windows, and segment routing.
- [x] Render compact context for Stage 2 using existing source item serialization limits.
- [x] Add R10 fixtures and unit tests for SEC and Nasdaq paths.

## Acceptance Criteria

1. SEC company data fetches only configured watchlist companies and fixed concepts.
2. SEC requests use a declared User-Agent and no API key.
3. Nasdaq symbol directory records ETF flag and listing metadata from official pipe-delimited files.
4. Company fact context is bounded and cannot exceed existing prompt candidate caps.
5. Missing CIKs, absent concepts, malformed JSON, and SEC 403/429 responses degrade at adapter level.
6. No raw SEC payload, headers, cookies, or long filing excerpts are written to public markdown.

## Tests / Validation

- `uv run pytest tests/unit/sources/test_sec_company_facts.py tests/unit/sources/test_nasdaq_symbol_directory.py tests/unit/sources/test_plugin_contract.py -q`
- `uv run pytest tests/unit/briefing tests/unit/publisher -q -k 'fact or watchlist or source'`
- `uv run ruff check src/investo/sources tests/unit/sources`
- `uv run mypy --strict src/investo/sources src/investo/briefing`
- `uv run python scripts/check_no_paid_apis.py`

## Source Declaration

- Source URL: `https://data.sec.gov/submissions/CIK##########.json`, `https://data.sec.gov/api/xbrl/companyfacts/CIK##########.json`, `https://www.sec.gov/files/company_tickers.json`, Nasdaq Trader symbol directory text files
- Auth: none
- Free-tier rate limit: SEC fair-access rules and bounded per-run watchlist requests; Nasdaq text files fetched once per run
- No paid tier required: official public endpoints

## Non-Goals

- No SEC bulk archive download.
- No commercial fundamentals provider.
- No analyst estimates or target prices.
- No archive backfill.

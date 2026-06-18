# Code Generation Plan: `u103 official-policy-speech-rss-sources`

**Date**: 2026-06-18
**Unit**: u103 official-policy-speech-rss-sources
**Stage**: Code Generation
**Status**: Complete (9/9 steps — 2026-06-18)
**Source**: 2026-06-18 ten-agent data-source expansion review.
**Estimated Effort**: ~3-5 h
**Dependencies**:
- u102 source-adapter-registry-completeness
- u35/u43 FOMC lookahead sources
- u58 crypto-regulation-policy-sources
- u101 verified fact context

---

## Problem Statement

Investo already collects FOMC releases/calendar events, SEC 8-K filings, Congressional bill actions, and committee crypto-policy surfaces. It does not collect official speeches/testimony from the Federal Reserve or SEC newsroom speech/statement feeds. As a result, rate-policy tone and market-structure or crypto-regulatory statements can enter through generic news instead of official source text.

## Goal

Add no-key official RSS adapters for Federal Reserve speeches/testimony and SEC newsroom press releases/speeches/statements. These feeds should enrich source-backed policy narratives without adding paid APIs, browser automation, or HTML portal scraping.

## Existing Coverage / Deduplication

- `fomc-rss` covers Federal Reserve press releases; it does not cover speeches/testimony.
- `fomc-calendar` covers scheduled Fed events; it does not collect speech body metadata.
- `sec-edgar-8k` covers company filings; it does not cover SEC policy statements or enforcement/newsroom releases.
- `official_policy.py` covers Congress and committee policy sources; it does not cover agency speech feeds.

## Scope Boundary

In scope:
- `fed-speech-rss` adapter using:
  - `https://www.federalreserve.gov/feeds/speeches.xml`
  - `https://www.federalreserve.gov/feeds/testimony.xml`
- `sec-newsroom-rss` adapter using:
  - `https://www.sec.gov/news/pressreleases.rss`
  - `https://www.sec.gov/news/speeches-statements.rss`
- Adapter registration, tier, market-window, segment routing, and R10 fixtures.
- Crypto-policy routing for SEC newsroom items only when item text matches existing crypto-policy terms.

Out of scope:
- Full speech HTML download or summarization.
- SEC litigation/admin proceeding feeds.
- Third-party news replacement.
- Broad named-person fact verification; u101 owns current-role facts.

## Stage Decision

Functional Design: skip. This is a bounded source-adapter extension following existing RSS adapter patterns.

NFR Requirements: skip. Source cost/auth/rate-limit declarations are pinned here and in PR checklist.

## Implementation Steps

- [x] Implement `src/investo/sources/fed_speech_rss.py` with `name="fed-speech-rss"`, `category="news"`, `retry_get`, XML parsing, text sanitation, and UTC timestamp handling.
- [x] Implement `src/investo/sources/sec_newsroom_rss.py` with `name="sec-newsroom-rss"`, `category="news"`, `retry_get`, XML parsing, text sanitation, and UTC timestamp handling.
- [x] Add imports in `src/investo/sources/__init__.py`.
- [x] Add explicit tiers in `src/investo/sources/tiers.py`; both are Tier S official sources.
- [x] Add market-window membership in `src/investo/sources/aggregator.py`.
- [x] Add segment routing in `src/investo/briefing/segments.py`.
- [x] Record real RSS fixtures under `tests/unit/sources/fixtures/api/fed-speech-rss/` and `sec-newsroom-rss/` with metadata.
- [x] Add unit tests covering happy path, out-of-window filtering, malformed XML, empty feed, status errors, and no-secret diagnostics.
- [x] Update plugin contract expected adapter names/count.

## Acceptance Criteria

1. Fed speeches and testimony feed items are collected from official RSS without an API key.
2. SEC newsroom press release and speech/statement items are collected from official RSS without an API key.
3. Fed items route only to `us-equity`.
4. SEC items route to `us-equity`; crypto routing occurs only for explicit crypto-policy terms.
5. Failure of either adapter contributes a failed source outcome but does not stop sibling source collection.
6. Public markdown receives sanitized titles/summaries with official source URLs and no raw XML.

## Tests / Validation

- `uv run pytest tests/unit/sources/test_fed_speech_rss.py tests/unit/sources/test_sec_newsroom_rss.py tests/unit/sources/test_plugin_contract.py -q`
- `uv run pytest tests/unit/briefing/test_segments*.py -q`
- `uv run pytest tests/unit/sources/test_aggregator.py -q`
- `uv run ruff check src/investo/sources tests/unit/sources`
- `uv run python scripts/check_no_paid_apis.py`

## Source Declaration

- Source URL: `https://www.federalreserve.gov/feeds/speeches.xml`, `https://www.federalreserve.gov/feeds/testimony.xml`, `https://www.sec.gov/news/pressreleases.rss`, `https://www.sec.gov/news/speeches-statements.rss`
- Auth: none
- Free-tier rate limit: public RSS; adapter uses existing bounded retry and one fetch per feed per run
- No paid tier required: confirmed by official public RSS access

## Non-Goals

- No paid news APIs.
- No speech full-text scraping.
- No LLM prompt redesign beyond source item availability.
- No archive backfill.

# Code Generation Plan: `u126 cftc-official-rss-policy-news`

**Date**: 2026-06-26
**Unit**: u126 cftc-official-rss-policy-news
**Stage**: Code Generation
**Status**: Planned
**Source**: 2026-06-25 news-source review.
**Estimated Effort**: ~3-5 h
**Dependencies**:
- u58 crypto-regulation-policy-sources
- u103 official-policy-speech-rss-sources
- u107 cftc-positioning-layer
- u115 source-spec-registry-unification

---

## Problem Statement

Investo already collects CFTC COT positioning through `cftc-cot-positioning`, but that adapter emits delayed weekly positioning context, not CFTC press releases, enforcement releases, or speeches/testimony. CFTC actions and statements can affect equity-index futures, commodities, swaps, prediction markets, and digital-asset policy, yet today they must enter through generic news or adjacent SEC/Congress policy sources.

## Goal

Add a bounded official CFTC RSS adapter that collects CFTC general press releases, enforcement press releases, and speeches/testimony from public RSS 2.0 feeds. The adapter must improve official policy-news provenance without adding paid APIs, browser automation, HTML scraping, or unbounded full-text downloads.

## Source Facts

| Field | Value |
| --- | --- |
| Source owner | U.S. Commodity Futures Trading Commission |
| Data family | news / official releases / speeches |
| Docs URL | `https://www.cftc.gov/RSS/index.htm` |
| Endpoint URL | `https://www.cftc.gov/RSS/RSSGP/rssgp.xml`, `https://www.cftc.gov/RSS/RSSENF/rssenf.xml`, `https://www.cftc.gov/RSS/RSSST/rssst.xml` |
| Auth | none |
| Cost and no-paid evidence | Official public CFTC RSS endpoints; no key, token, paid tier, SDK, or login |
| Rate limit | Operationally low-risk for daily briefing cadence: one GET per feed per run through existing bounded retry |
| Format | RSS 2.0 XML |
| Key fields | `title`, `link`, `description`, `pubDate`, `dc:creator`, `guid`, feed type |
| Update cadence | Event-driven CFTC publication cadence; RSS headers observed with public cache metadata |
| License or terms note | Use headline, summary, publication time, and canonical CFTC URL only; do not download or republish full release body beyond RSS-provided summary text |
| Existing Investo overlap | Complements `cftc-cot-positioning`; complements `congress-gov-bill-actions`, `house-financial-services-policy`, `senate-banking-policy`, `fed-speech-rss`, and `sec-newsroom-rss` |
| Proposed source_name | `cftc-policy-rss` |
| Proposed adapter path | `src/investo/sources/cftc_policy_rss.py` |
| Routing surfaces | registry import, source spec tier/window/routing, segment allow-list via source spec, plugin contract tests, coverage diagnostics |
| Degradation behavior | Per-feed malformed XML, HTTP failure, or empty feed contributes failed/zero source outcomes without blocking sibling sources |

Live availability was rechecked on 2026-06-26 KST with `curl -I -L --max-time 15` against the RSS index and all three XML endpoints. The three XML endpoints returned HTTP 200 and `application/rss+xml; charset=utf-8`.

## Existing Coverage / Deduplication

- `cftc-cot-positioning` is weekly delayed positioning data with `category="macro"` and `contract_group` routing. This unit does not modify COT/TFF parsing, delayed labels, channel-depth presentation, or `contract_group` routing.
- `official_policy.py` covers Congress, House Financial Services, and Senate Banking policy surfaces for crypto regulation. It does not cover CFTC agency press releases or CFTC speeches.
- `fed-speech-rss` and `sec-newsroom-rss` cover Federal Reserve and SEC official feeds. They do not cover CFTC.
- `yahoo-finance-news`, `nasdaq-stocks-news`, `cnbc-top-news`, `theblock-crypto`, and `yonhap-market` remain useful narrative feeds, but they are not CFTC source-of-record feeds.
- Treasury `/rss.xml` was deferred because it is a whole-site feed with FAQs, program pages, and stale non-market content. It is not part of this unit.

## Scope Boundary

In scope:
- New adapter `src/investo/sources/cftc_policy_rss.py`.
- Three official CFTC RSS feeds:
  - General Press Releases: `https://www.cftc.gov/RSS/RSSGP/rssgp.xml`
  - Enforcement Press Releases: `https://www.cftc.gov/RSS/RSSENF/rssenf.xml`
  - Speeches & Testimony: `https://www.cftc.gov/RSS/RSSST/rssst.xml`
- RSS 2.0 parsing with `defusedxml`, `retry_get`, `strip_html`, URL scheme validation, UTC timestamp conversion, half-open `FetchWindow` filtering, dedupe by canonical URL, and bounded max item count.
- `NormalizedItem(category="news")` with string-only metadata: `feed_type`, `guid`, `creator`, `official_source=true`, and policy priority metadata only for explicit crypto/prediction-market/digital-asset policy matches.
- Source registration, source spec descriptor update, tier/window/routing behavior, fixture tests, plugin contract, segment routing, aggregator failure isolation, and no-paid guard.

Out of scope:
- Full release page HTML scraping or body extraction.
- CFTC COT/TFF positioning changes.
- Public-comments RSS feeds from `comments.cftc.gov`.
- Federal Register proposed/final rule RSS feeds.
- Generic prediction-market scoring, trading advice, or signal ranking.
- Treasury, BOK, FSS, KRX, KIND, NewsAPI, Finnhub, Alpha Vantage, GDELT, or other generic news expansion.

## Functional Design Slice

### Adapter Contract

- Class: `CftcPolicyRssAdapter`
- Source name: `cftc-policy-rss`
- Category: `news`
- Tier: `S`
- Market window segment: `us-equity`
- Item routing: single-segment `us-equity` by default.
- Outcome routing: `us-equity`; crypto impact is expressed through bounded priority metadata and existing candidate preservation, not by duplicating every CFTC item into crypto.

### Feed Contract

Use a feed map with stable labels:

| feed_type | URL |
| --- | --- |
| `general_press` | `https://www.cftc.gov/RSS/RSSGP/rssgp.xml` |
| `enforcement_press` | `https://www.cftc.gov/RSS/RSSENF/rssenf.xml` |
| `speech_testimony` | `https://www.cftc.gov/RSS/RSSST/rssst.xml` |

Each feed is fetched independently. If one feed fails and another succeeds, return the successful items. If all feeds fail, raise the first `SourceFetchError` so the aggregator records `source_name=cftc-policy-rss` failure.

### Normalization Contract

For each RSS `<item>`:

- Drop entries missing `title`, `link`, or `pubDate`.
- Validate `link` scheme is `http` or `https`.
- Parse `pubDate` with `email.utils.parsedate_to_datetime`; drop naive or malformed timestamps.
- Convert `published_at` to UTC.
- Sanitize `title` and optional `description` through `strip_html`.
- Truncate summary through the existing source summary length constant.
- Emit `raw_metadata` with string values only.
- Dedupe across feeds by canonical URL first, title second.
- Sort newest first and cap to a bounded count after dedupe.

### Crypto-Policy Priority Contract

Only stamp crypto-policy priority metadata when title plus summary contains explicit CFTC policy context and crypto/prediction-market/digital-asset terms. Reuse the u58 style rather than broad source fan-out:

- `raw_metadata["official_source"] = "true"` for all items.
- `raw_metadata["policy_priority"] = "crypto_regulation"` only for explicit crypto/digital-asset/prediction-market policy matches.
- `raw_metadata["policy_source"] = "cftc"` when `policy_priority` is stamped.
- Do not stamp priority for ordinary commodities, agricultural, energy, fraud-only, or personnel releases unless crypto/prediction-market terms are present.

## NFR Source Contract

- **No paid API**: no key, token, paid SDK, or login path. Update `scripts/check_no_paid_apis.py` expectations only if the guard requires allow-list metadata for the new official domain.
- **Runtime budget**: three RSS GETs per run under existing `retry_get` timeout/retry policy.
- **Security**: no secrets, no cookies, no persisted response headers, and no raw author email expansion beyond RSS `dc:creator` if present.
- **R10 fixtures**: record real RSS bytes for each feed under `tests/unit/sources/fixtures/api/cftc-policy-rss/` with metadata describing URL, status, content-type, byte size, recording date, and item count.
- **R13 metadata hygiene**: raw metadata is diagnostic-safe and string-only; no full HTML body, cookies, request IDs, Cloudflare headers, or local paths.
- **Graceful degradation**: per-feed errors are isolated; all-feed failure becomes a source outcome failure and never crashes sibling adapters.

## Implementation Steps

- [ ] Add `src/investo/sources/cftc_policy_rss.py` with feed map, parser, normalization helper, dedupe, and per-feed failure handling.
- [ ] Add adapter discovery import in `src/investo/sources/__init__.py`.
- [ ] Add `cftc-policy-rss` to `src/investo/_internal/source_specs.py` as Tier S, US market window, US single-segment item/outcome routing.
- [ ] Add or update source/plugin contract tests so descriptor, registry import, tier map, market-window routing, and segment allow-list stay synchronized.
- [ ] Add fixtures under `tests/unit/sources/fixtures/api/cftc-policy-rss/` for general press, enforcement press, speeches/testimony, empty feed, malformed XML, and HTTP failure.
- [ ] Add `tests/unit/sources/test_cftc_policy_rss.py` covering happy path, per-feed partial failure, all-feed failure, window filtering, dedupe, metadata string hygiene, crypto-policy priority stamping, and non-crypto non-stamping.
- [ ] Add or extend segment/candidate preservation tests for explicit CFTC crypto/prediction-market policy items.
- [ ] Run no-paid API guard and scoped quality gates.

## Acceptance Criteria

1. `cftc-policy-rss` fetches CFTC general press, enforcement press, and speeches/testimony RSS feeds without API credentials.
2. RSS entries normalize into `NormalizedItem(category="news")` with sanitized title/summary, canonical URL, UTC timestamp, and string-only raw metadata.
3. A failure in one CFTC feed does not drop successful sibling CFTC feed items.
4. Failure of all CFTC feeds is visible as a single failed source outcome and does not stop unrelated adapters.
5. CFTC items route to `us-equity` by default.
6. Explicit crypto, digital-asset, or prediction-market CFTC policy items receive bounded u58-compatible priority metadata; unrelated CFTC releases do not.
7. Public briefing output can cite official CFTC URLs without exposing raw XML, request diagnostics, or full scraped release pages.
8. No paid API guard remains green.

## Tests / Validation

- `uv run pytest tests/unit/sources/test_cftc_policy_rss.py tests/unit/sources/test_plugin_contract.py -q`
- `uv run pytest tests/unit/sources/test_source_specs.py tests/unit/sources/test_tiers.py tests/unit/sources/test_window.py -q`
- `uv run pytest tests/unit/briefing/test_segments*.py -q`
- `uv run pytest tests/unit/sources/test_aggregator.py -q`
- `uv run ruff check src/investo/sources src/investo/_internal tests/unit/sources tests/unit/briefing`
- `uv run mypy --strict src/investo/sources src/investo/_internal src/investo/briefing`
- `uv run python scripts/check_no_paid_apis.py`

## Non-Goals

- No CFTC COT positioning rewrite.
- No rulemaking/public-comment RSS ingestion.
- No full-release HTML extraction.
- No generic news provider expansion.
- No archive backfill.
- No trading recommendation, score, or signal.

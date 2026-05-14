# Code Generation Plan: `u58 crypto-regulation-policy-sources`

**Date**: 2026-05-14
**Unit**: u58 crypto-regulation-policy-sources
**Stage**: Code Generation
**Status**: ✅ Complete (8/8, 2026-05-14)
**Source**: 2026-05-14 user request to check whether official `Senate Banking / Congress.gov / House Financial Services` sources can be added.
**Estimated Effort**: ~5-7 h
**Dependencies**:
- u22 source-coverage-transparency (`SourceOutcome`, source diagnostics, missing/failed source visibility).
- u36 source expansion bundles (official/free/public source selection discipline).
- u43 lookahead adapters (scheduled event category and candidate handling patterns).
- u45 segment-routing-exclusivity (strong crypto signal and source allow-list routing).
- u53 briefing-intelligence-signal-recall (source coverage and signal recall objective).
- u54 source-status-severity-and-quality-kpi (truthful source degradation if policy sources fail).
- u57 segment-narrative-scope-and-time-reconciliation (core issue scope and cross-segment context).

---

## Feasibility Summary

### Congress.gov

Status: **Addable with optional API key**.

Evidence:
- Library of Congress documents the Congress.gov v3 API as an official machine-readable Congress.gov data interface.
- Access requires an API key; live unauthenticated `api.congress.gov` probe returned HTTP 403, which matches key-required behavior.

Implementation implication:
- Add an adapter only when `CONGRESS_API_KEY` is configured.
- Missing or rejected key must return a sanitized source outcome, not fail the run.
- Configure watched bills explicitly, e.g. `INVESTO_CONGRESS_BILLS=119/hr/3633`.

### Senate Banking Committee

Status: **Addable as official static HTML, not as unverified RSS**.

Evidence:
- Official Senate Banking hearing page exposes the May 14, 2026 executive session for `H.R.3633, the Digital Asset Market Clarity Act of 2025`.
- Official Senate Banking majority release page exposes the May 12, 2026 market-structure bill-text release ahead of markup.
- RSS endpoints were not confirmed as stable in local probes, so RSS must not be the initial dependency.

Implementation implication:
- Use only official static HTML pages/listings that can be fetched and fixture-recorded.
- If a listing page is unstable, support configured watch URLs as the v1 source surface.
- No unofficial mirrors, social feeds, JS reverse-engineering, or browser-only extraction.

### House Financial Services Committee

Status: **Addable with official news/RSS filtering**.

Evidence:
- Official House Financial Services news page is available and lists schedule/news entries.
- `https://financialservices.house.gov/news/rss.aspx` responded HTTP 200 with `Content-Type: text/xml` in local probe.

Implementation implication:
- Consume the official RSS/news output.
- Filter aggressively to crypto-policy terms before emitting items because the committee feed covers many non-crypto topics.

---

## Goal

Ensure official U.S. crypto policy events such as CLARITY Act markup, digital-asset market-structure bills, stablecoin legislation, and committee schedule changes enter the crypto briefing candidate set and can be selected as core issues when market-structure relevant.

This unit addresses the miss where the CLARITY markup was important but not guaranteed to appear in the crypto market briefing.

---

## Scope Boundary

In scope:
- Official source adapters for Congress.gov, Senate Banking, and House Financial Services.
- Optional-secret behavior for Congress.gov.
- Fixture-backed parsing for all new sources.
- Crypto policy routing and candidate-priority rules.
- Prompt guidance that regulation/legislation events can be core market issues even without immediate price movement.

Out of scope:
- Paid APIs or unofficial legislative data vendors.
- Scraping third-party news aggregators as a substitute for official sources.
- General U.S. politics coverage unrelated to digital assets, market structure, stablecoins, or crypto enforcement jurisdiction.
- Legal interpretation of bill impact beyond source-backed event description.
- Broad rewrite of ranking/prompt architecture outside the minimum policy-priority path.

---

## Definition of Done

- [x] **AC-1 Congress.gov adapter**: supports configured bill identifiers such as `119/hr/3633`, fetches bill actions metadata when `CONGRESS_API_KEY` is present, and emits no secret-shaped values in errors or metadata.
- [x] **AC-2 Congress graceful degradation**: missing/invalid API key produces sanitized source failures and does not block Senate/House official sources.
- [x] **AC-3 Senate Banking official HTML adapter**: extracts hearing/markup/news release title, date, URL, committee, bill reference, and event type from fixture-backed official pages.
- [x] **AC-4 House Financial Services official feed adapter**: consumes official news/RSS output and emits only crypto-policy relevant items after keyword filtering.
- [x] **AC-5 Metadata contract**: new items include source-safe metadata such as `policy_priority=crypto_regulation`, `bill_id`, `committee`, `event_type`, and `official_source=true`.
- [x] **AC-6 Crypto routing**: CLARITY/market-structure/stablecoin/digital-asset markup items route to `crypto` even if they do not mention BTC/ETH or prices.
- [x] **AC-7 Candidate preservation**: official crypto-regulation items survive generic news caps and are available to Stage 1/Stage 2 as high-priority candidates.
- [x] **AC-8 Prompt behavior**: generated crypto briefings may promote source-backed regulation/legislation events to §② core issues when market-structure relevant, while keeping language observational and non-advisory.
- [x] Quality gate green for u58 scope: targeted source/routing/pipeline tests passed; `uv run ruff check .`, changed-file `ruff format --check`, `uv run mypy --strict src/`, and `uv run pytest` passed after correcting one stale visual-asset integration assertion. Full `ruff format --check .` is blocked by four pre-existing out-of-scope files listed in the summary.

---

## Proposed Source Names

| Source name | Segment | Category | Tier | Auth | Notes |
|-------------|---------|----------|------|------|-------|
| `congress-gov-bill-actions` | `crypto` after policy filter | `news` / `calendar` when scheduled | S | `CONGRESS_API_KEY` | Configured bill ids; no collection if key absent |
| `senate-banking-policy` | `crypto` after policy filter | `calendar` for hearings/markups, `news` for releases | S | none | Official HTML only; fixture-backed selectors |
| `house-financial-services-policy` | `crypto` after policy filter | `news` / `calendar` when schedule item | S | none | Official RSS/news page; filter non-crypto committee news |

Policy filter terms should include exact and normalized variants:
- `CLARITY Act`
- `Digital Asset Market Clarity Act`
- `digital asset`
- `crypto`
- `stablecoin`
- `market structure`
- `committee markup`
- `markup`
- `CFTC`
- `SEC`
- `GENIUS Act`
- `blockchain`

---

## Steps

### Step 1 — Freeze contracts and configuration

- [x] Add source definitions for the three official policy sources with tier S and crypto-policy routing.
- [x] Add `CONGRESS_API_KEY` documentation as optional; missing key should be normal degraded behavior.
- [x] Add `INVESTO_CONGRESS_BILLS` or equivalent config for explicitly watched bill ids.
- [x] Add `INVESTO_SENATE_BANKING_WATCH_URLS` only if the listing page is not stable enough for v1.
- [x] Decide final module placement (`sources/official_policy.py` vs three source-specific modules) before coding.

### Step 2 — Congress.gov adapter

- [x] Implement bill-id parser for configured entries such as `119/hr/3633`.
- [x] Fetch v3 bill action metadata with JSON responses.
- [x] Normalize actions into `NormalizedItem` with title, summary, URL, published date, source name, and policy metadata.
- [x] Treat 401/403 as sanitized auth failures; no key value or query string leaks.
- [x] Tests: success fixture, no-key case, invalid-key/403 case, empty actions, malformed payload.

### Step 3 — Senate Banking official HTML adapter

- [x] Fetch official hearing/markup/news pages or listing pages with a normal HTTP client and source identity headers.
- [x] Parse title, date/topic/body summary, URL, and event type.
- [x] Map hearing/markup pages with future date to `category="calendar"` and releases to `category="news"`.
- [x] Add selectors that fail closed if expected title/date/topic fields disappear.
- [x] Tests: May 14, 2026 CLARITY executive-session fixture; May 12, 2026 market-structure release fixture; selector-missing fixture.

### Step 4 — House Financial Services official feed adapter

- [x] Consume `https://financialservices.house.gov/news/rss.aspx` first; fall back to official news listing only if RSS is unavailable.
- [x] Parse RSS item title, date, link, description, and category/type when present.
- [x] Apply crypto-policy filter before emitting normalized items.
- [x] Tests: crypto-policy item kept, non-crypto committee item dropped, empty feed, malformed XML, HTTP error.

### Step 5 — Metadata, routing, and source outcomes

- [x] Add `raw_metadata["policy_priority"] = "crypto_regulation"` for matched official items.
- [x] Add `raw_metadata["official_source"] = "true"` or equivalent primitive-safe value.
- [x] Add committee/bill/event fields with primitive values only.
- [x] Extend strong crypto routing terms in `briefing/segments.py` without widening generic SEC/Fed macro leakage.
- [x] Tests: CLARITY markup item routes to crypto; unrelated House banking item does not route to crypto.

### Step 6 — Candidate priority preservation

- [x] Identify the current candidate cap chokepoint for Stage 1/Stage 2 input.
- [x] Preserve a bounded number of `policy_priority=crypto_regulation` official items before generic news truncation.
- [x] Keep cap bounded so policy items do not crowd out price/market structure data entirely.
- [x] Tests: CLARITY item survives with many generic crypto news items; non-official low-signal item remains droppable.

### Step 7 — Prompt updates

- [x] Update Stage 1/Stage 2 prompts to treat official regulation/legislation events as potentially market-moving for crypto.
- [x] Keep wording source-backed and observational; no legal advice, no investment instruction.
- [x] Explicitly mention committee markup, bill text release, stablecoin legislation, and market-structure jurisdiction as eligible core issues.
- [x] Tests: prompt contains official-policy rule and does not reintroduce blocked advisory wording.

### Step 8 — Integration and documentation

- [x] Add optional Congress.gov configuration documentation. The repo has no `.env.example`; entries live in `docs/tech-env.md`.
- [x] Add docs/requirements trace if a new FR is needed, otherwise link to FR-001/FR-002/FR-008.
- [x] Add an integration fixture where a Senate Banking CLARITY markup item reaches crypto briefing inputs.
- [x] Run quality gate and update `aidlc-state.md` with completion evidence.

---

## Risk Notes

- Congress.gov is official but key-gated; the adapter must not become a hard dependency for daily briefings.
- Senate Banking RSS was not confirmed as stable; HTML parsing is acceptable only with official pages and strict fixture coverage.
- House Financial Services covers many unrelated topics; aggressive crypto-policy filtering is required to avoid noisy crypto briefings.
- `SEC` and `CFTC` terms can be too broad; route them as crypto policy only when paired with digital asset, crypto, stablecoin, market-structure, or bill context.
- Official policy events are often scheduled/lookahead items; ranking must preserve them without replacing core price/liquidity data.

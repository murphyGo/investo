# u47 Yahoo Finance News Content Filter — Code Generation Summary

**Date**: 2026-05-10
**Unit**: u47 yahoo-finance-news-content-filter
**Status**: Complete (4/4 steps)

## Goal

Block generic personal-finance product-comparison headlines (CD rates / HELOC / mortgage / savings / insurance / retirement) at the `yahoo-finance-news` adapter layer so they never reach the Stage 1 LLM. Triggered by the 2026-05-09 cron US-equity quality retro: ~10/24 in-window items were such noise, costing Stage 1 token budget and diluting the Stage 2 candidate pool. A single batch-level INFO log emits the blocked count + matched patterns as a tuning canary; a 100%-block batch escalates to WARNING.

## Steps

### Step 1 — Deny patterns + helper

- New module-level constant `_PERSONAL_FINANCE_DENY_PATTERNS` (10 lowercase substring tokens — 9 plan-DoD patterns plus the `mortgage and refi rates` variant).
- New `_PERSONAL_FINANCE_BROAD_HAYSTACK_PATTERNS` frozenset (today: just `personal finance`) marks patterns matched against URL + `<source>` text rather than the title alone, because Yahoo flags product-comparison stories with the `finance.yahoo.com/personal-finance/...` URL prefix and a `Yahoo Personal Finance` source attribution rather than putting the phrase in the headline.
- New pure helper `_personal_finance_patterns_hit(title, url, rss_source) -> tuple[str, ...]` returns matched patterns sorted+deduped (sort = stable canary log line for CI grep). Empty tuple = not noise.
- The broad haystack normalises kebab-case path separators (`-`) and slashes (`/`) to spaces so `personal-finance/...` matches the literal `personal finance` pattern without requiring a hyphenated parallel pattern.

### Step 2 — Filter integration in `fetch()`

- Filter applies inside the existing `for entry in root.iter("item")` loop, **after** `_normalize_entry` and **after** the `window.contains(...)` check but **before** the item is appended. This keeps the canary metric measured against the in-window pool only.
- New `_emit_filter_canary(filtered, total, patterns_hit)`:
  - `total == 0` → quiet (aggregator already logs zero-item collection).
  - `filtered == 0` → quiet (steady state).
  - `0 < filtered < total` → INFO with structured `extra` (`source_name`, `filtered`, `total`, `patterns_hit`).
  - `filtered == total` → WARNING.
- Existing `_normalize_entry` body unchanged.

### Step 3 — Regression tests

New `tests/unit/sources/test_yahoo_finance_news_filter.py` (23 tests):

| Group | Count | Coverage |
|-------|-------|----------|
| Pure helper (parametrised + cases) | 14 | 9 deny-pattern hit titles, URL prefix, source-text, case-insensitivity, 5 market-signal negatives, dedup+sort, constant shape |
| Adapter integration via MockTransport | 9 | Pure-deny → 0 items, pure-market → all preserved, mixed → only normal pass, URL prefix filtered with neutral title, INFO canary partial, WARNING canary full, no log on clean batch, no log on empty in-window pool |

Existing `tests/unit/sources/test_yahoo_finance_news.py` (15 tests) unchanged — all pass against the recorded `feed.xml` fixture because every `personal-finance` item in that fixture falls **outside** the test window.

### Step 4 — Quality gate

| Gate | Result |
|------|--------|
| `uv run ruff check src tests` | passed |
| `uv run ruff format --check` | 239 files already formatted |
| `uv run mypy --strict src` | success, 97 source files |
| `uv run pytest -q` | **1598 passed** (1575 → 1598, +23 new tests) |
| `uv run mkdocs build --strict` | built in 0.44s |

## Files changed

- `src/investo/sources/yahoo_finance_news.py` (modified)
- `tests/unit/sources/test_yahoo_finance_news_filter.py` (new, 23 tests)

## Behaviour delta (verified by tests)

| Scenario | Pre-u47 | Post-u47 |
|----------|---------|----------|
| Title `Best CD rates today, May 8, 2026` | yielded | filtered, INFO/WARNING canary |
| Title `HELOC and home equity loan rates today` | yielded | filtered |
| Title `Is $7,000 Per Year Too High for Long-Term Care Insurance?` | yielded | filtered |
| URL `finance.yahoo.com/personal-finance/...` (neutral title) | yielded | filtered (broad haystack) |
| `<source>Yahoo Personal Finance</source>` (neutral title) | yielded | filtered |
| Title `S&P 500 reaches new high` | yielded | yielded (no change) |
| Title `Tesla Q1 earnings beat estimates` | yielded | yielded (no change) |
| Recorded `feed.xml` fixture, KST 2026-04-29 window | 36 in-window items, → 36 yielded | 36 in-window items, → 36 yielded (all `personal-finance` items post-window) |

## Plan deviation

Step 4 manual simulation (2026-05-08 fixture replay) is satisfied by deterministic synthetic tests (`test_mixed_batch_filters_only_deny_items` and `test_canary_info_log_emitted_on_partial_filter` verify `"filtered 3/5 items"` + structured `extra`). R10 prevents fabricating a fresh fixture without a live re-record session.

## TECH-DEBT candidate (not filed)

- **Deny-pattern staleness review** — patterns may drift as Yahoo's category labels evolve. File when (a) a second adapter adopts the same content-filter pattern, or (b) operator observes a regression in cron logs.
- **English-only patterns** — Korean Yahoo / Naver 금융 noise is a separate unit (out-of-scope per plan).

## Out of scope (per plan)

Other adapter content filters (cnbc, nasdaq-stocks-news, theblock-crypto), other noise categories (health / 연예 / 가십 / 정치-비경제), Stage 1 LLM unassigned-rule strengthening, operator dashboard for pattern-hit statistics.

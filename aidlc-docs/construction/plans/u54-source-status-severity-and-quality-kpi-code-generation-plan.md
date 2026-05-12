# Code Generation Plan: `u54 source-status-severity-and-quality-kpi`

**Date**: 2026-05-13
**Unit**: u54 source-status-severity-and-quality-kpi
**Stage**: Code Generation
**Status**: 📋 Planned
**Source**: 2026-05-13 10-subagent evaluation of generated market briefings, deduplicated against u51/u52/u53.
**Estimated Effort**: ~3-4 h
**Dependencies**:
- u22 source-coverage-transparency (existing `SourceOutcome`, `SegmentCoverage`, reason-code rendering).
- u32 trust-traceability-deep-dive (traceability and source-tier vocabulary).
- u42 quality-kpi-history (quality page/history surfaces).

---

## Deduplication Boundary

Excluded because already owned elsewhere:
- u51: first-viewport layout, TL;DR, anchor table, H3 headings, number bolding, glossary dedupe, action-ratio diagnostics.
- u52: prior-day carryover and event lifecycle.
- u53: domestic flow and US sector/macro ETF source expansion.

This unit owns only **truthful status semantics and quality KPI transparency**.

---

## Goal

Prevent generated briefings from showing `데이터 상태: 정상` when core sources failed or returned 0 items, and make `site_docs/quality.md` explain actual coverage risk instead of reporting misleading denominator-zero KPIs.

Observed failures from 2026-05-11 briefing review:
- Domestic segment shows `정상` while `korea-policy-rss` failed and `fsc-krx-index-price` returned 0 items.
- US segment shows `정상` while `cnbc-top-news` failed and multiple news sources returned 0 items.
- Crypto segment shows `정상` while `binance-crypto-market` failed and `coingecko-price` returned 0 items.
- Quality page reports `소스 라이브니스 0.0% / 0회` despite existing quality-history rows and failed source counts.

---

## Definition of Done

- [ ] Source count text separates `targeted / succeeded / zero / failed / body-used`.
- [ ] Reader-facing status labels use `정상 / 부분 / 제한 / 실패` based on conclusion usability, not just item count.
- [ ] Core source failures or zero core price sources downgrade segment status and explain impact.
- [ ] `site_docs/quality.md` shows observed run count, failed source count, zero-item source count, and core-missing count.
- [ ] Trace/collapsed diagnostics expose failed/excluded sources with sanitized messages and no secret-shaped values.

---

## Steps

### Step 1 — Severity policy and model

- [ ] Extend or wrap `SegmentCoverage` with a deterministic severity policy.
- [ ] Define core source categories per segment: price/index, primary market news, policy/calendar, crypto market data.
- [ ] Add Korean labels and short reader explanations for `normal`, `partial`, `limited`, `failed`.
- [ ] Pin downgrade cases: failed core price source, zero core price source, all news zero, all items zero.

### Step 2 — First-viewport status rendering

- [ ] Update briefing status rendering to show split source counts.
- [ ] Replace ambiguous `정상 — 수집 N건 / 소스 M개 / 누락 없음` with severity + short reason.
- [ ] Keep long per-source detail in collapsed diagnostics to avoid pushing the summary down.
- [ ] Ensure data-confidence visual card uses the same severity vocabulary.

### Step 3 — Quality KPI computation

- [ ] Update `quality_eval` to count observed runs even when source liveness is 0.
- [ ] Add `failed_sources`, `zero_item_sources`, `core_missing_segments`, and `segments_with_partial_status` KPIs.
- [ ] Separate publish success from source coverage quality.
- [ ] Preserve backward-compatible quality-history fields where possible; add new fields append-only.

### Step 4 — Trace and exclusion transparency

- [ ] Add source diagnostic rows for attempted/succeeded/zero/failed/body-used/excluded.
- [ ] Show exclusion reason for sources not used in the body when available.
- [ ] Reuse existing redaction chokepoints for failure reasons.

### Step 5 — Tests and gates

- [ ] Unit tests for severity downgrade matrix.
- [ ] Unit tests for quality KPI denominator correctness.
- [ ] Rendering tests for source count split and sanitized failure text.
- [ ] Run `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy --strict src/`, `uv run pytest -q`, `uv run mkdocs build --strict`.

---

## Out of Scope

- Adding new data sources (u53).
- Rewriting layout/TL;DR (u51).
- Numeric claim verification (u55).
- Compliance/advisory language filtering (u56).


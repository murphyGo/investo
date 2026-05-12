# Code Generation Plan: `u57 segment-narrative-scope-and-time-reconciliation`

**Date**: 2026-05-13
**Unit**: u57 segment-narrative-scope-and-time-reconciliation
**Stage**: Code Generation
**Status**: 📋 Planned
**Source**: 2026-05-13 10-subagent evaluation of generated market briefings, deduplicated against u51/u52/u53.
**Estimated Effort**: ~3-5 h
**Dependencies**:
- u7 segmented-briefing (three-market split).
- u45 segment-routing-exclusivity (input routing already fixed at item level).
- u52 prior-briefing-context-and-carryover (separate prior-day event lifecycle).

---

## Deduplication Boundary

Excluded because already owned elsewhere:
- u45: source/item routing exclusivity.
- u51: reader layout and actionability formatting.
- u52: prior-day carryover.
- u53: data-source expansion.

This unit owns **same-bundle narrative scope and time-state reconciliation** after items are already routed.

---

## Goal

Prevent a segmented briefing bundle from telling internally inconsistent stories because one segment cites open-state news while another segment has final close data, or because a segment promotes non-native cross-market material as its core issue.

Observed failures from 2026-05-11 review:
- Domestic segment promoted US open-state weakness while US segment concluded the same date with a positive close.
- Domestic segment used broad overseas macro/geopolitical stories as core issues rather than background.
- AAPL/TSMC surfaced as domestic watchlist impact without explicit domestic linkage.
- Shared UST/macro material was duplicated across US and crypto without segment-specific reinterpretation.

---

## Definition of Done

- [ ] Segment prompts rank native market facts above cross-market background.
- [ ] Same-bundle `장중/출발/마감` states are labeled and reconciled when final close exists.
- [ ] Cross-market material is downgraded to background unless the link to the segment is explicit.
- [ ] Domestic watchlist impact does not show unrelated global tickers without a domestic linkage.
- [ ] Shared macro material is summarized once or clearly reinterpreted per segment.

---

## Steps

### Step 1 — Time-state vocabulary and detection

- [ ] Define state labels: `pre-market`, `open`, `intraday`, `close`, `post-close`, `scheduled`.
- [ ] Detect wording/source titles that indicate `하락 출발`, `상승 출발`, `마감`, `장후`, `예정`.
- [ ] Attach state metadata to prompt context where available; otherwise add wording constraints.

### Step 2 — Same-bundle reconciliation context

- [ ] Build a minimal same-run segment context containing each segment's target date, market timezone, and close/open status.
- [ ] Pass this context to Stage 2 so domestic can avoid treating US open-state items as final if US close is already available.
- [ ] Keep this independent from u52 prior-day carryover.

### Step 3 — Native-vs-background scope rules

- [ ] Add prompt rules: domestic native facts first, overseas macro as background; US native facts first, crypto-specific news as background; crypto price/on-chain/regulatory first.
- [ ] Add deterministic filters or score hints for non-native items when they appear in a segment.
- [ ] Require explicit linkage text when a global ticker appears in domestic watchlist impact.

### Step 4 — Shared macro handling

- [ ] Identify repeated shared macro facts such as UST curve, oil, Fed schedule.
- [ ] Render once as shared background or require segment-specific interpretation in one sentence.
- [ ] Add cross-segment links only when they reduce duplication or clarify scope.

### Step 5 — Tests and gates

- [ ] Unit tests for state wording reconciliation: US `하락 출발` plus US close data should not create contradictory domestic core issue.
- [ ] Unit tests for domestic global ticker linkage requirements.
- [ ] Integration fixture for a same-date three-segment bundle with shared macro material.
- [ ] Run `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy --strict src/`, `uv run pytest -q`, `uv run mkdocs build --strict`.

---

## Out of Scope

- Source routing bugs before segment generation (u45).
- Prior-day event carryover (u52).
- New source adapters (u53).
- Numeric truth/freshness gates (u55).


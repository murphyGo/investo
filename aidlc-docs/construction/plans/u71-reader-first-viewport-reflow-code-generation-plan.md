# Code Generation Plan: `u71 reader-first-viewport-reflow`

**Date**: 2026-05-24
**Unit**: u71 reader-first-viewport-reflow
**Stage**: Code Generation
**Status**: Complete (5/5, 2026-05-24)
**Source**: 2026-05-24 ten-subagent user-quality review of generated segmented briefings
**Estimated Effort**: ~3-5 h
**Dependencies**:
- u50 lightweight-charts-embed (coordination only: chart blocks may move below summary but chart semantics are unchanged)
- u51 tldr-block-and-number-bold-inversion
- u54 source-status-severity-and-quality-kpi
- u61 first-viewport-summary-gate-v2
- u62 quality-status-publish-reconciliation

---

## Problem Statement

The first viewport can feel like an operations log instead of a reader summary. Reviewers repeatedly saw:
- Raw source failures or API diagnostic detail before the useful summary.
- Long `주의할 점` lines that are hard to scan on mobile.
- Malformed/truncated caution snippets such as broken tokens or compressed date ranges.
- Charts/diagnostics competing with the summary before the reader sees what happened.

u61 already blocks malformed summary lines. u71 changes the layout priority so the first screen answers the reader's main question first: "What happened, how confident is this, and what should I monitor?"

---

## Goal

Reflow the generated briefing header/first viewport into a stable order:
1. Segment title and date.
2. `## 한눈에 보기` summary bullets.
3. Compact status/confidence chip derived from canonical quality values.
4. Up to three concise immediate watchpoints or caution lines.
5. Collapsible diagnostics/source details after the useful summary.

Fixed first-viewport contract:

| Element | Limit / rule |
|---------|--------------|
| Summary bullets | exactly 3 when u61 supplies 3; otherwise u61 fallback contract applies |
| Status chip | one line: `데이터 상태: {normal/partial/limited/failed} · 본문 사용 {n|미집계} · 실패 {n} · 0건 {n}` |
| Watch/caution snippets | max 3 lines, max 90 Korean-visible chars each, truncate only at whitespace/punctuation |
| Diagnostics | rendered after snippets inside static MkDocs-compatible `<details><summary>수집/품질 진단</summary>...</details>` |
| Default expanded | only when segment status is `failed` or u61 could not produce a usable summary |
| Charts | compact chart blocks may start only after the summary/status/snippet block |

---

## Existing Coverage / Deduplication

This unit is not a new summary-quality gate.

- u51 owns TL;DR, H3 conversion, number bolding, and reader layout foundations.
- u61 owns malformed first-viewport summary validation/repair.
- u54/u62 own status values and public quality truth.
- u56 owns compliance language.

u71 only controls ordering, compactness, and diagnostic collapse.

---

## Scope Boundary

In scope:
- Header/first-viewport assembly order.
- Length bounding for caution/watchpoint summary lines.
- Diagnostic block placement/collapse behavior.
- Mobile-safe CSS for collapsed details if needed.
- Telegram alignment only if it uses the same first-viewport summary lines.

Out of scope:
- New LLM summary generation algorithm.
- New severity/KPI semantics.
- Chart redesign beyond making sure charts do not displace the first useful summary.
- Historical archive rewrite.

---

## Stage Decision

- **Functional Design — SKIP**. This is a presentation contract over existing summary/status values.
- **NFR Requirements — SKIP**. No new dependency, source, secret, or material runtime cost. CSS/Markdown rendering must stay static-site compatible.

---

## Implementation Steps

### Step 1 — Define first-viewport contract `[x]`
- [x] Write the exact order and maximum line counts for header, summary, status chip, watchpoints, and diagnostics.
- [x] Use the fixed compact chip fields from the table above: status tier, body-used count, failed-source count, and zero-item-source count.
- [x] Define when diagnostics must be expanded by default (only fully failed segment or no summary).
- **Acceptance**: contract is represented in tests and comments/docs near the renderer.

### Step 2 — Reorder reader-format output `[x]`
- [x] Move useful summary before raw source diagnostics.
- [x] Render diagnostics below the summary in `<details><summary>수집/품질 진단</summary>...</details>`.
- [x] Raw diagnostics are source outcome tables, API error details, zero-item per-source rows, trace/debug blocks, and quality KPI explanations; compact status chip is not considered raw diagnostics.
- [x] Preserve existing u61 summary validation path.
- [x] Preserve segment navigation and disclaimer placement.
- **Acceptance**: generated markdown fixture starts with title/date, summary, compact status, then diagnostics.

### Step 3 — Bound caution and watchpoint snippets `[x]`
- [x] Limit first-viewport caution/watchpoint lines to a small number and maximum character length.
- [x] u71 may only reflow/truncate u61-cleaned values. If a summary/caution value is malformed, delegate to the existing u61 API/fallback; do not add a parallel malformed-summary validator.
- [x] Too-long but valid snippets use fallback suffix `...` only after a word boundary; if no boundary exists before 90 chars, omit the snippet.
- [x] Prevent mid-token truncation and malformed date concatenation.
- **Acceptance**: fixtures with long/broken caution text render clean, bounded fallback lines.

### Step 4 — Mobile/static presentation `[x]`
- [x] Add or adjust CSS so collapsed diagnostics and compact status do not overlap charts or summary text.
- [x] Ensure compact market chart cards remain below the first useful text unless section placement explicitly calls for charts.
- [x] Avoid JavaScript-only access to critical summary/status text.
- [x] Required validation when CSS changes: render one fixture at 390x844 and 1280x720; verify summary/status text is visible above diagnostics/charts and no element overlaps. If Browser/Playwright is unavailable, record static CSS/HTML checks and a manual verification gap.
- **Acceptance**: static HTML/Markdown still carries all critical first-viewport content.

### Step 5 — Tests and gate `[x]`
- [x] Add unit tests for ordering.
- [x] Add unit tests for long diagnostics and malformed caution fallback.
- [x] Add CSS/asset regression checks if CSS changes.
- [x] Run targeted publisher/briefing/notifier tests and mkdocs strict if site assets change.

---

## Acceptance Criteria

- **AC-71.1** — Reader summary appears before diagnostics/source errors for non-failed segments.
- **AC-71.2** — Diagnostics are still available but visually/structurally secondary.
- **AC-71.3** — First-viewport caution/watchpoint snippets are bounded and not truncated mid-token.
- **AC-71.4** — Mobile layout keeps the first useful summary visible without chart/diagnostic overlap.
- **AC-71.5** — u61 summary validation and u56 compliance gates remain the single source of truth for their concerns.

---

## Tests / Validation

Expected test areas:
- `tests/unit/publisher/test_reader_format*.py`
- `tests/unit/briefing/test_pipeline_*summary*.py`
- `tests/unit/notifier/test_summary.py` if Telegram shares the compact lines
- `tests/unit/publisher/test_chart_assets.py` if CSS placement changes

Minimum local gate:
- Targeted pytest for changed tests.
- `uv run ruff check` on changed source/tests.
- `uv run mkdocs build --strict` if site CSS or generated pages are touched.

---

## Non-Goals

- New dashboard page.
- New user settings.
- Rewriting all briefing sections.
- Hiding source limitations entirely; the point is prioritization, not concealment.

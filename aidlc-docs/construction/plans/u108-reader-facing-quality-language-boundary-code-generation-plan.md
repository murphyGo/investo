# Code Generation Plan: `u108 reader-facing-quality-language-boundary`

**Date**: 2026-06-23
**Unit**: u108 reader-facing-quality-language-boundary
**Stage**: Code Generation
**Status**: Complete (2026-06-24)
**Source**: 2026-06-23 generated-briefing quality review with six read-only subagent lanes and parent deduplication
**Estimated Effort**: ~4-6 h
**Dependencies**:
- u54, u62, u65, u69, and u96 quality surfaces are complete.
- u71 first-viewport reflow is complete.
- u100 surface-quality gate is complete.

---

## Problem Statement

Recent generated segment archives show operator-facing quality language in the public reader path. Examples from June 2026 include first-viewport or card text containing `데이터 부족`, `[데이터부족]`, `본문 사용 미집계`, and watchpoint cards containing `출처: 확인 소스 미상`. These phrases are useful as internal diagnostics, but they make the public briefing feel machine-generated and do not help a reader understand the market.

The defect is not a new KPI problem. The issue is that diagnostic states are projected directly into reader prose, site cards, visual cards, and Telegram summaries instead of being converted to reader-safe wording or moved into collapsed diagnostics.

## Goal

Create a single public-language projection boundary for quality and coverage states. Public prose must explain limitations in human language, while raw diagnostic labels remain available only in logs, structured history, collapsed diagnostics, and quality dashboards.

## Existing Coverage / Deduplication

- u54/u62/u65/u69/u96 own quality severity, snapshots, replay, consistency, and current-run accounting.
- u71 owns first-viewport ordering and diagnostics collapse.
- u100 owns deterministic surface-quality issue scanning.
- This unit does not add a KPI, severity enum, source status enum, or first-viewport layout.
- This unit adds public-language boundary enforcement and shared projection text.

## Scope Boundary

In scope:
- Ban raw operator labels from reader prose, first viewport, site index cards, visual cards, and Telegram summaries.
- Provide a fixed mapping from diagnostic state to reader-safe Korean wording.
- Preserve raw values inside structured metadata, logs, and collapsed diagnostics.
- Add surface-quality issue codes for raw diagnostic leakage.

Out of scope:
- Changing source collection or coverage calculation.
- Redesigning `site_docs/quality.md`.
- Backfilling historical archive files.
- Rewriting market analysis content with an LLM.
- Changing watchpoint card structure beyond diagnostic-language removal.

## Stage Decision

Functional Design: skip. This is a public rendering boundary over existing quality and reader-format surfaces.

NFR Requirements: skip. The implementation is deterministic text projection with no new dependency, source, secret, network call, or material runtime cost.

## Fixed Contracts

### Region Model

Use these public region IDs in issue reports:

| Region ID | Surface | Block raw diagnostic labels |
|-----------|---------|-----------------------------|
| `segment_first_viewport` | Segment markdown before `## ①` excluding collapsed diagnostics | yes |
| `segment_body` | Segment markdown body excluding protected spans | yes |
| `site_index_card` | `site_docs/index.md` latest/archive cards | yes |
| `visual_card_text` | SVG/PNG/OG card visible text fields | yes |
| `telegram_summary` | notifier segment summaries | yes |
| `quality_dashboard_visible` | visible reader labels in `site_docs/quality.md` | yes |
| `collapsed_diagnostics` | `<details><summary>수집/품질 진단</summary>...</details>` | no |
| `structured_metadata` | JSONL, logs, internal dataclasses, raw dashboard inputs | no |

`site_docs/quality.md` is public. Its visible headings and prose must use reader-safe Korean labels. Raw internal metric keys may appear only in machine-readable code spans/tables that already represent operator metrics, and the unit must not introduce new raw leakage there.

Protected spans for segment markdown are fenced code blocks, markdown tables inside collapsed diagnostics, footers/disclaimers, and the complete collapsed diagnostics details block. Public prose outside those spans is scanned.

### Forbidden Public Phrases

The following exact raw phrases are forbidden in public prose regions:

- `[데이터부족]`
- `데이터부족`
- `데이터 부족`
- `본문 사용 미집계`
- `확인 소스 미상`
- `source missing`
- `price missing`
- `fallback_ratio`
- `figures_presence`

The following contextual patterns are forbidden in public prose regions:

- `본문 사용\s*(?:\d+|미집계)`
- `실패\s*\d+`
- `0건\s*\d+`
- `fallback[_ ]?ratio`
- `figures[_ ]?presence`

Do not ban bare `미집계` globally. It is banned only in the exact phrase `본문 사용 미집계` or inside the contextual body-use pattern above.

Allowed regions:

- JSONL metadata
- Python logs
- GitHub step summary diagnostics
- collapsed `<details><summary>수집/품질 진단</summary>`
- `site_docs/quality.md` raw metric code spans that are clearly operator metrics

### Public Wording Map

Use these fixed public strings:

| Diagnostic condition | Public wording |
|----------------------|----------------|
| low or limited coverage | `이번 문서는 수집 근거가 제한적입니다.` |
| core price missing | `핵심 가격 근거가 확인되지 않아 정확한 가격 서술은 줄였습니다.` |
| source count unavailable | `수집 상세는 진단 섹션에서 확인할 수 있습니다.` |
| watchpoint source missing | `확인 가능한 출처가 있는 신호만 표시했습니다.` |
| all watchpoints unusable | `오늘은 공개 근거가 충분한 관전 신호만 본문에 남겼습니다.` |

### Input and Precedence Rules

Create `src/investo/_internal/public_quality_language.py` as the neutral owner. `publisher`, `visuals`, and `notifier` consume this module; do not place the shared projection under `publisher`.

Projection input fields come from existing quality/status objects only:

1. `core_price_missing` or source outcome category failure for a segment price source.
2. `coverage.status` / segment severity from u54/u62.
3. u96 current-run fields such as fallback/data-limited counts.
4. source count missing or unavailable.
5. watchpoint collapse state from u110/u98.

Precedence is fixed:

1. core price missing
2. low or limited coverage
3. source count unavailable
4. watchpoint collapse

Render at most two public limitation sentences per public surface. When more than two conditions apply, keep the first two by precedence and leave details to collapsed diagnostics.

## Implementation Steps

- Extend the existing u100 issue set in `src/investo/_internal/surface_quality.py`; do not add a second independent scanner.
- Add `src/investo/_internal/public_quality_language.py` with a narrow public projection helper and the fixed precedence rules above.
- Update the existing `src/investo/publisher/segment_reader_format.py` publish hook so final public markdown is scanned after u71 reflow and u100 repair using the expanded issue set.
- Update site index summary/card renderers under `src/investo/publisher/site_index/` to use public wording rather than raw conclusion suffixes.
- Update visual-card text builders under `src/investo/visuals/` to strip Markdown and raw diagnostic labels before SVG/PNG text placement.
- Update Telegram summary construction under `src/investo/notifier/` so segment summaries never contain raw diagnostic labels.
- Keep collapsed diagnostics unchanged except for label text that is visibly public-facing.
- Add regression fixtures using 2026-06-17 domestic, US, and crypto snippets.
- Do not change watchpoint card structure, source extraction, matcher reasons, or actionability semantics. u110 owns watchpoint field readability; u111 owns watchlist matcher-language cleanup.

## Acceptance Criteria

1. Published segment body prose does not contain any forbidden public phrase.
2. First-viewport callouts do not contain `[데이터부족]`, `본문 사용 미집계`, or `미집계`.
3. Site index cards and OG/visual-card text do not contain raw diagnostic labels or Markdown residue from diagnostic strings.
4. Telegram segmented summaries do not contain raw diagnostic labels.
5. Collapsed diagnostics and structured metadata still preserve operator evidence.
6. Surface-quality failures identify the exact forbidden phrase and public region.
7. Regression fixtures prove that 2026-06-17 snippets render reader-safe limitation wording.
8. `site_docs/quality.md` visible labels are reader-safe while raw metric keys are confined to explicit operator metric contexts.
9. Tests cover the surface matrix: segment first viewport, segment body, site index card, visual card text, Telegram summary, visible quality dashboard, collapsed diagnostics, and structured metadata.

## Tests / Validation

```bash
uv run --extra dev pytest tests/unit/internal/test_surface_quality.py tests/unit/publisher/test_segment_reader_surface_quality.py tests/unit/publisher tests/unit/visuals tests/unit/notifier -k "quality or diagnostic or surface or watchlist or summary"
uv run --extra dev ruff check src/investo/_internal src/investo/publisher src/investo/visuals src/investo/notifier tests/unit/internal tests/unit/publisher tests/unit/visuals tests/unit/notifier
uv run --extra dev mypy src
```

## Non-Goals

- No source adapter changes.
- No quality KPI redesign.
- No archive backfill.
- No broad Korean copy rewrite.
- No LLM paraphrasing pass.

## Completion Summary

Completed 2026-06-24.

- Added `src/investo/_internal/public_quality_language.py` as the shared reader-safe projection boundary.
- Extended `src/investo/_internal/surface_quality.py` to block raw public diagnostic labels in segment first-viewport and body regions while preserving collapsed diagnostics.
- Updated reader-format, site index hero, Telegram summary extraction, visual-card text cleaning, and quality sparkline empty-state copy to use reader-safe language.
- Kept raw operational diagnostics available in collapsed `<details>` blocks, structured history, logs, and tests.
- Validation: 167 focused tests passed, scoped ruff passed, `mypy src` passed.

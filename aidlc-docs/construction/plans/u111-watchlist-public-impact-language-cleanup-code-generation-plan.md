# Code Generation Plan: `u111 watchlist-public-impact-language-cleanup`

**Date**: 2026-06-23
**Unit**: u111 watchlist-public-impact-language-cleanup
**Stage**: Code Generation
**Status**: Backlog / Planned
**Source**: 2026-06-23 generated-briefing quality review with watchlist/public-language findings
**Estimated Effort**: ~3-5 h
**Dependencies**:
- u108 reader-facing-quality-language-boundary is complete or u111 restates the public/diagnostic boundary locally.
- u64 watchlist entity matching and actionability is complete.
- u73 watchlist impact center v2 is complete.
- u100 surface-quality gate is complete.

---

## Problem Statement

The public "내 관심 자산 영향" callout can expose internal matcher reasons such as `[boundary-term]`, `[structured-symbol]`, and `[alias:Bitcoin]`. These are useful for debugging match provenance but read like implementation metadata to a public reader. Related watchlist daily pages and visual cards also carry raw or semi-raw matcher context.

This is a projection problem, not a matching problem. Matching semantics and u73 grouping should stay intact.

## Goal

Create a public watchlist impact projection that renders reader-safe Korean labels and keeps raw matcher reasons only in diagnostic surfaces.

## Existing Coverage / Deduplication

- u64 owns matching confidence and reason production.
- u73 owns Direct/Related/Uncertain/Rejected grouping and public projection boundaries.
- DEBT-075 documents diagnostics noise, but public leakage is a separate reader-facing defect.
- This unit does not change accepted matches, confidence calculation, aliases, or grouping precedence.

## Scope Boundary

In scope:
- Replace raw reason rendering in site and Telegram callouts.
- Apply the same public projection to watchlist daily pages and visual-card text.
- Keep raw reason codes in collapsed diagnostics only.
- Add a surface-quality guard that blocks bracketed matcher reason codes in public prose.

Out of scope:
- Reclassifying Direct/Related/Uncertain/Rejected.
- Changing alias matching.
- Changing rejected-candidate diagnostics.
- Adding watchlist settings UI.
- Backfilling public pages.

## Stage Decision

Functional Design: skip. This is a public projection refinement over existing watchlist data.

NFR Requirements: skip. The work is deterministic label mapping and adds no dependency, source, secret, or runtime cost.

## Fixed Contracts

### Public Label Map

| Internal status or confidence | Public label |
|-------------------------------|--------------|
| Direct match | `직접 관련` |
| Related match | `관련 맥락` |
| Uncertain | `관심 목록 보류` |
| Rejected | diagnostics only |
| `coverage_hold` | `수집 제한` |
| `structured`, `strict`, `alias`, `text` | not rendered directly |

### Canonical Public Projection API

Add one canonical public projection helper in `src/investo/briefing/watchlist.py` or a small sibling module that `briefing`, `publisher`, `visuals`, and `notifier` can consume without crossing module boundaries:

```python
def public_watchlist_match_label(match: WatchlistMatch, *, group: str) -> str: ...
def public_watchlist_match_summary(match: WatchlistMatch, *, group: str) -> str: ...
```

Required behavior:

- Use only existing u64/u73 data: term, group, item source name, and sanitized title.
- Do not use raw `match.reason` or `matched_alias` in public text.
- Preserve useful context through reason-family labels:
  - Direct high-confidence match -> `직접 관련`
  - Related context match -> `관련 맥락`
  - coverage hold -> `수집 제한`
  - Uncertain/Rejected -> diagnostics only for segment first viewport, Telegram, and visual cards.
- Site first viewport, Telegram, watchlist daily public sections, and `build_watchlist_relevance_card()` must all consume this helper or an object produced by it.

### Public Forbidden Pattern

Public prose must not contain:

- `[boundary-term]`
- `[structured-symbol]`
- `[alias:`
- `[text-match]`
- raw `match.reason`
- `matched_alias` wording
- visible alias-display text introduced only to explain the match path

Diagnostics may contain reason codes only inside collapsed R13-safe sections.

### Diagnostic Contract

Collapsed diagnostic sections may include only:

- reason code
- matched public term
- source name
- offending token when already R13-safe
- 6-character title hash

Diagnostics must not include raw item title, summary, URL, `matched_alias`, unredacted alias text, or the full matcher payload.

### Public Surface Scope

The matcher-reason guard applies to:

- segment first viewport and body
- Telegram summary from `src/investo/notifier/summary.py`
- watchlist daily page public sections
- generated SVG/PNG/OG-card visible text from `build_watchlist_relevance_card()` and the SVG render path

Only collapsed diagnostics are excluded.

## Implementation Steps

- Add the canonical public projection helper above and update `src/investo/briefing/watchlist.py::render_watchlist_impact()` so site and Telegram channels render public labels through it.
- Keep `render_watchlist_prompt_context()` free to use concise internal context for LLM grounding, but do not copy bracketed reason codes into public markdown.
- Update `src/investo/briefing/watchlist_impact.py` only when the public projection object needs a label field; do not change grouping logic.
- Update `src/investo/publisher/watchlist_pages.py` so public sections use label map and diagnostics remain collapsed.
- Update visual-card builders that render watchlist relevance or impact text, specifically `src/investo/visuals/cards.py::build_watchlist_relevance_card()` and the SVG render path in `src/investo/visuals/render.py`.
- Ensure visual cards receive only `public_impact(center)` or the canonical public projection; they must not render Uncertain/Rejected matches in public card rows.
- Update `src/investo/notifier/summary.py` so Telegram consumes the same sanitized projection.
- Add public-surface checks to `_internal.surface_quality` for bracketed matcher reason codes across all public surfaces, not only first viewport.
- Add fixtures for BTC/NVDA alias and structured-symbol cases.

## Acceptance Criteria

1. Site first-viewport callout contains no bracketed matcher reason codes.
2. Telegram summaries contain no raw matcher reason codes.
3. Watchlist daily page public sections contain reader-safe labels only.
4. Collapsed diagnostics still include enough R13-safe reason data for operators.
5. `match_watchlist_items()` outputs are unchanged for existing fixtures.
6. `build_impact_center()` group membership is unchanged for existing fixtures.
7. Raw `reason` and `matched_alias` remain available only in diagnostic data.
8. Public render snapshots contain none of `[boundary-term]`, `[structured-symbol]`, `[alias:`, `matched_alias`, or alias-explanation text.
9. Surface-quality scan blocks bracketed matcher reason codes outside diagnostics.
10. Visual-card text contains no raw reason or alias metadata and renders only Direct/Related public impacts.

## Tests / Validation

```bash
uv run --extra dev pytest tests/unit/briefing/test_watchlist.py tests/unit/briefing/test_watchlist_impact.py tests/unit/publisher/test_watchlist_daily_page.py tests/unit/visuals tests/unit/notifier/test_summary.py
uv run --extra dev ruff check src/investo/briefing/watchlist.py src/investo/briefing/watchlist_impact.py src/investo/publisher/watchlist_pages.py src/investo/visuals src/investo/notifier tests/unit/briefing tests/unit/publisher tests/unit/visuals tests/unit/notifier
uv run --extra dev mypy src
```

## Non-Goals

- No matcher rewrite.
- No alias behavior change.
- No portfolio workflow redesign.
- No archive backfill.
- No new watchlist UI.

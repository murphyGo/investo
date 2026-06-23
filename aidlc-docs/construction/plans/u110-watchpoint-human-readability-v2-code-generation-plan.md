# Code Generation Plan: `u110 watchpoint-human-readability-v2`

**Date**: 2026-06-23
**Unit**: u110 watchpoint-human-readability-v2
**Stage**: Code Generation
**Status**: Backlog / Planned
**Source**: 2026-06-23 generated-briefing quality review with domestic, US, crypto, and mobile watchpoint findings
**Estimated Effort**: ~4-6 h
**Dependencies**:
- u108 reader-facing-quality-language-boundary is complete or implemented in the same product slice.
- u64 watchlist/actionability structure is complete.
- u72 watchpoint action matrix is complete.
- u87 watchpoint matrix rehabilitation is complete.
- u98 watchpoint card list redesign is complete.
- u100 surface-quality gate is complete.

---

## Problem Statement

The current §⑥ card format is better than the old six-column table, but June 2026 archives still show mechanical residue: `출처: 확인 소스 미상` even when `현재:` embeds a source, `관심 영향: 관심 영향`, `상방 상방 데이터 부족`, `하방 하방 데이터 부족`, identical up/down triggers, and cards that treat low-value placeholders as reader-facing signals.

The card renderer must normalize field values before templating and collapse rows that cannot become human-readable watchpoints.

## Goal

Keep the u98 canonical card shape while making every rendered card read like a concise observation with a source, current signal, distinct confirmation conditions, confidence, and plain implication.

## Existing Coverage / Deduplication

- u72 owns the source/trigger/implication matrix contract.
- u87 filters trace fragments, bare links, and broken observation bullets.
- u98 owns the card shape.
- u100 owns broad surface-quality scanning.
- This unit improves field normalization and row eligibility inside the existing card renderer.

## Scope Boundary

In scope:
- Strip duplicated field labels before templating.
- Promote source names from `현재:` text when `출처` is missing.
- Require distinct up/down trigger text for a rendered card.
- Collapse rows with only generic data-limited placeholders.
- Tighten Stage 2 prompt examples to avoid duplicate labels.

Out of scope:
- Changing the u98 card format.
- Changing watchlist matching or watchlist impact grouping.
- Adding typed evidence models.
- Adding source adapters.
- Backfilling old archives.

## Stage Decision

Functional Design: skip. This is a renderer/prompt-contract refinement over existing watchpoint behavior.

NFR Requirements: skip. The work is deterministic string parsing and prompt text with no new dependency, source, secret, or cost.

## Fixed Contracts

### Normalized Field Rules

Before rendering a card:

- Strip leading labels only when they appear as field prefixes: `현재:`, `출처:`, `확인 소스:`, `상방:`, `상방 -`, `하방:`, `하방 -`, `관심 영향:`, `섹션 내 관심 영향:`.
- Preserve semantic text such as `상방 압력`, `하방 위험`, and `상방 확인 후 변동성 확대` when `상방`/`하방` are not followed by `:` or ` -`.
- Collapse repeated labels caused by template concatenation.
- Extract source candidates using the search order `source field` -> `current field` -> `upside trigger` -> `downside trigger` -> `implication`.
- Source extraction accepts `확인 소스: {name}`, `출처: {name}`, or `source: {name}` and stops at `·`, `;`, newline, `상방`, `하방`, `관심 영향`, or sentence end.
- Reject source candidates equal to `확인 소스 미상`, `source missing`, `데이터 부족`, or empty text.
- If multiple valid sources are found, use the first by search order after trimming Markdown links and punctuation.
- A public card requires a valid source. Rows without a promoted source are omitted; if all rows are omitted, the section collapses to the existing bounded note and u108 projects it into reader-safe wording.
- Treat identical normalized up/down trigger text as invalid.

### Invalid Row Decision Table

Hard-fail conditions always omit the row:

- missing valid source after extraction
- missing up/down trigger
- identical normalized up/down trigger text
- diagnostic/hash/link-only row

Soft invalid factors:

- confidence is `데이터부족`
- current field is only a configured symbol or generic topic after label stripping
- implication is missing or only `관심 영향 데이터 부족`

Decision table:

| Condition | Public behavior |
|-----------|-----------------|
| any hard-fail condition | omit row |
| no hard-fail and 0 soft factors | render card |
| no hard-fail and 1 soft factor | render card with available fields |
| no hard-fail and 2+ soft factors | omit row |
| all rows omitted | collapse section to bounded note |

Invalid-only sections collapse to the existing `DATA_LIMITED_NOTE`, and u108 must project that note into reader-safe public wording before publication. If u108 is not complete in the target branch, u110 implementation must add a local assertion that the collapsed note is public-safe.

## Implementation Steps

- Update `src/investo/publisher/watchpoint_matrix.py`.
- Add helper functions for label stripping, source promotion, trigger distinctness, and invalid-row scoring.
- Apply helpers before `_render_cards()` or the equivalent card-rendering point.
- Keep `render_watchpoint_matrix()` signature unchanged.
- Update `src/investo/briefing/prompts.py` §⑥ examples so the model emits source/current/up/down/impact text without repeating template labels.
- Add regression fixtures from 2026-06-17 domestic, US, and crypto snippets.
- Add one mobile-render-oriented fixture that uses the 2026-06-17 card shape and verifies no six-column table or repeated labels are needed for scanning.
- Ensure idempotence: running the renderer over already-rendered cards returns the same text.

## Acceptance Criteria

1. No rendered card contains `관심 영향: 관심 영향`.
2. No rendered card contains `상방 상방` or `하방 하방`.
3. No rendered card shows `출처: 확인 소스 미상` when a source name is present elsewhere in the same bullet.
4. Cards with identical up/down triggers are collapsed or omitted.
5. All-invalid sections collapse to one bounded note instead of multiple placeholder cards.
6. `render_watchpoint_matrix()` signature and markdown-in/markdown-out behavior stay unchanged.
7. Text outside §⑥ is byte-preserved in reader-format integration tests.
8. Mixed sections preserve valid cards while omitting rows with hard-fail conditions.
9. One soft invalid factor may render; two or more soft invalid factors omit the row.
10. Tests prove prefix stripping preserves semantic `상방 압력` and `하방 위험` text.

## Tests / Validation

```bash
uv run --extra dev pytest tests/unit/publisher/test_watchpoint_matrix.py tests/unit/briefing/test_prompts.py tests/unit/publisher/test_segment_reader_format.py
uv run --extra dev ruff check src/investo/publisher/watchpoint_matrix.py src/investo/briefing/prompts.py tests/unit/publisher/test_watchpoint_matrix.py tests/unit/briefing/test_prompts.py
uv run --extra dev mypy src
```

## Non-Goals

- No card redesign.
- No watchlist matcher change.
- No source adapter work.
- No archive backfill.
- No LLM rewrite after render.

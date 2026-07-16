# Code Generation Plan: `u131 bounded-line-sentence-boundary-truncation`

**Date**: 2026-07-17
**Unit**: u131 bounded-line-sentence-boundary-truncation
**Stage**: Code Generation
**Status**: Backlog (Ready)
**Source**: 2026-06-29/2026-06-30 production bundle review (briefing-unit-planner, 2026-07-17)
**Estimated Effort**: ~3-4 h
**Dependencies**:
- u71 reader-first-viewport-reflow (Complete) — 주의할 점 snippet bounding in `reader_format/reflow.py`.
- u76 plain-language-reader-aids (Complete) — meaning-line bounding in `reader_format/meaning.py`.
- u98/u110 watchpoint cards (Complete) — card title rendering in `publisher/watchpoint_matrix.py`.
- u112 reader-markdown-polish-gate-v2 (Complete) — `_looks_truncated_mid_token` in `_internal/surface_quality.py`.

---

## Problem Statement

Three bounded reader-facing line types in production briefings end mid-clause, producing broken Korean:

1. **u76 meaning lines** (`> **그래서 의미는?**`): `archive/crypto/2026/06/2026-06-29.md` lines 69/85/111 end `…이상 급등은 특정 지역의...`, `…출현 여부를...`, `…Extreme Fear 수준에서 반등의...`. Cause: `src/investo/publisher/reader_format/meaning.py` `_bound...` helper cuts at a *word* boundary within `MEANING_MAX_CHARS` and suffixes `...` — a Korean word boundary is routinely mid-clause.
2. **u71 주의할 점 snippets**: `archive/us-equity/2026/06/2026-06-30.md` line 18 ends `…포럼 발언이 매파적 본문 참고.` and `archive/domestic-equity/2026/06/2026-06-30.md` line 12 ends `…수급 부담이 본문 참고.`. Cause: `reader_format/reflow.py` cuts the snippet at `SNIPPET_MAX_CHARS` (word boundary) and appends the `_SNIPPET_CONTINUATION` (" 본문 참고.") directly onto the truncated clause.
3. **u98 card titles**: `archive/crypto/2026/06/2026-06-29.md` line 123 renders `#### 관찰 신호: CoinGecko BTC · UTC 24h…`. Cause: title bounding in `publisher/watchpoint_matrix.py` hard-cuts with `…`.

u112 shipped a truncation-residue issue code (`_looks_truncated_mid_token`, `_TRUNCATED_KOREAN_ELLIPSIS_RE`) that did not fire on any of these production shapes — its region coverage / patterns miss meaning lines, caution callouts, and §⑥ headings.

## Goal

Every bounded public line ends at a complete Korean sentence or clause boundary; when the first sentence does not fit the cap, the surface's existing deterministic fallback is used instead of a cut; and the u112 gate blocks the residue shapes so a regression cannot publish.

## Existing Coverage / Deduplication

- **u71/u76/u98/u110** own the line types, caps, and fallback texts — all unchanged. Only the bounding *algorithm* they call changes.
- **u112** owns the truncation-residue issue-code family — extended (patterns + regions), not forked.
- **u127** summary reject predicate is untouched (these lines are not first-viewport summary candidates).
- Not a new validator, not a prompt change, not a cap change.

## Scope Boundary

In scope: one shared sentence-boundary bounding helper; three call-site swaps; u112 detector alignment; regression fixtures.
Out of scope: 오늘의 결론/핵심 동인 composition defects (u134), watchpoint field/value semantics (u135), cap values, prompt-side length instructions.

## Stage Decision

Functional Design: SKIP — algorithm replacement inside existing rendering contracts; no new entity.
NFR Requirements: SKIP — pure string logic; no new dependency, source, secret, or cost.

## Fixed Contracts

1. **Shared helper** `bound_at_sentence(text: str, max_chars: int) -> str | None` in `src/investo/_internal/text.py`:
   - If `len(text) <= max_chars`: return `text` unchanged.
   - Else find the last Korean sentence terminator at or before `max_chars`. Terminator set (pinned): a `.` `!` `?` `。` that is preceded by a non-digit (so `150.00` never splits) — equivalently the regex `(?<=[^\d\s])[.!?。](?=\s|$)`.
   - If a terminator exists: return the text up to and including it (rstripped). No ellipsis is ever appended.
   - If none exists: return `None` (caller must use its fallback).
2. **Call-site behavior on `None`**:
   - meaning lines → existing `MEANING_FALLBACK` (u76 contract; already defined in `reader_format/_constants.py`).
   - 주의할 점 snippet → the fixed line `본문 §②·§④ 참조` (this literal already exists in the watchpoint bounded-note family; reuse the existing constant if one matches, otherwise pin this literal as a new module constant — do not invent new wording).
   - card title → drop trailing ` · `-separated segments right-to-left until the title fits; if even the first segment exceeds the cap, keep the first segment whole (titles are short labels; no ellipsis).
3. **`_SNIPPET_CONTINUATION` handling**: the continuation is appended **only** when the snippet was bounded at a sentence boundary AND the omitted remainder is non-empty; it is rendered as its own sentence (`… 확대되면 수급 부담. 본문 참고.` style is wrong — the continuation follows a completed sentence, e.g. `…확인 필요. 본문 참고.`).
4. **u112 detector**: `_looks_truncated_mid_token` (or its region router) must scan meaning-marker lines, 주의할 점 callout lines, and `#### 관찰 신호:` headings; `...`/`…` line-endings on those regions are blocking issues.
5. Idempotency: bounding an already-bounded line is a no-op.

## Implementation Steps

- [ ] Step 1 — Add `bound_at_sentence` to `src/investo/_internal/text.py` with the pinned terminator regex; unit tests including the digit guard (`7,499.36` unsplit), no-terminator → `None`, exact-cap boundary.
- [ ] Step 2 — Swap `src/investo/publisher/reader_format/meaning.py` `_bound…` internals to the helper + `MEANING_FALLBACK` on `None`; delete the `...` suffix path; keep `MEANING_MAX_CHARS` and `_MEANING_BOUNDARY_CHARS` removal if now dead.
- [ ] Step 3 — Swap the 주의할 점 snippet bounding in `src/investo/publisher/reader_format/reflow.py` to the helper; apply Fixed Contract 3 for `_SNIPPET_CONTINUATION`; fallback per Fixed Contract 2.
- [ ] Step 4 — Swap card-title bounding in `src/investo/publisher/watchpoint_matrix.py` to the `·`-segment-drop rule; remove the `…` suffix.
- [ ] Step 5 — Extend `src/investo/_internal/surface_quality.py` truncation detection per Fixed Contract 4; add the three production lines from 2026-06-29/30 archives verbatim as blocking-case tests.
- [ ] Step 6 — Rendered regression: run `apply_reader_format` (u81 chain) over trimmed fixtures reproducing the three shapes; assert outputs end at sentence boundaries and reruns are byte-stable.
- [ ] Step 7 — Quality gate: scoped ruff/format, `mypy src`, `pytest tests/unit/publisher tests/unit/internal`.

## Acceptance Criteria

1. AC-131.1: No public meaning line, 주의할 점 callout, or §⑥ card title ends with `...` or `…` after reader-format runs.
2. AC-131.2: The three verbatim 2026-06-29/30 production lines are blocked by the u112 gate and re-bounded correctly by the new algorithm.
3. AC-131.3: A first sentence longer than the cap yields the surface's deterministic fallback, never a cut fragment.
4. AC-131.4: `본문 참고.` follows only a completed sentence.
5. AC-131.5: Numbers with decimals never split at their period.
6. AC-131.6: Caps are unchanged and double application is byte-stable.

## Tests / Validation

- `tests/unit/internal/test_text.py` (or existing `_internal` text test module) — helper cases.
- `tests/unit/publisher/test_reader_format_meaning_u76.py` — meaning-line swap cases.
- `tests/unit/publisher/test_reader_format.py` — 주의할 점 snippet cases.
- `tests/unit/publisher/test_watchpoint_matrix.py` — title segment-drop cases.
- `tests/unit/internal/test_surface_quality.py` — blocking residue shapes.
- Local gate: scoped ruff/format, `mypy src`, focused pytest above.

## Non-Goals

- No cap changes, no new fallback wording beyond the pinned literal, no prompt changes.
- No 결론/동인 composition work (u134).
- No watchpoint value semantics (u135).
- No archive backfill.

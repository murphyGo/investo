# Code Generation Plan: `u132 watermark-window-reader-render-and-gate-alignment`

**Date**: 2026-07-17
**Unit**: u132 watermark-window-reader-render-and-gate-alignment
**Stage**: Code Generation
**Status**: In Progress (1/7; Step 1 complete 2026-07-18)
**Source**: 2026-06-29/2026-06-30 production bundle review (briefing-unit-planner, 2026-07-17)
**Estimated Effort**: ~2 h
**Dependencies**:
- u112 reader-markdown-polish-gate-v2 (Complete) — `watermark.window_bracket` issue code in `_internal/surface_quality.py`.
- u8 market-aware source window (Complete) — window computation, unchanged.
- u81 reader-format subpackage (Complete) — the repair chain the line must survive.

---

## Problem Statement

Every published briefing's second line is malformed. Example (`archive/us-equity/2026/06/2026-06-30.md:3`):

```
**기준 시각**: 2026-06-30 NY · 2026-06-30T04:00Z, 2026-07-01T04:00Z)
```

There is a dangling `)` and no opening bracket. Root cause chain:

1. `src/investo/briefing/_reader_enhance/enhancement.py:114` renders the collection window in mathematical half-open notation: `**기준 시각**: {date} {tz} · [{start}, {end})`.
2. That notation contains one `[` and zero `]` — *inherently* bracket-unbalanced. A downstream repair pass that strips unbalanced brackets (the same defect family u112 polices; candidate strippers are the bracket-balance repairs in `_internal/surface_quality.py:350` and `_internal/summary_quality.py:154` — the implementer must trace which pass rewrites this specific line in the production chain) removes the `[`, leaving `… start, end)`.
3. The u112 check that should block this — `_bad_watermark_window` (`_internal/surface_quality.py:295`) — returns `False` unless the line contains the token `수집창`, which the production renderer never emits. The check has never fired on a real briefing. Its companion `_WATERMARK_LINE_RE` (line 37) likewise expects a `HH:MM` shape production does not produce.

Reader impact: the very first data-provenance line of every document looks broken, and the half-open math notation is unreadable for the target retail audience even when intact.

## Goal

The watermark line renders a reader-readable, bracket-free collection window that is byte-stable through the full reader-format/repair chain, and the surface-quality gate actually fires on malformed watermark shapes.

## Existing Coverage / Deduplication

- **u112** owns the `watermark.window_bracket` issue code — this unit re-aims that one code at reality; no new issue-code family.
- **u8** window computation (KST/NY/UTC market-aware windows) is unchanged; only presentation changes.
- **u81** reader-format chain order is unchanged.
- No archive backfill: legacy committed archives keep the old line (consistent with u69's no-backfill precedent, DEBT-073).

## Scope Boundary

In scope: renderer format change; `_WATERMARK_LINE_RE` + `_bad_watermark_window` alignment; blocking detection of the legacy dangling-paren shape; byte-stability proof through the chain.
Out of scope: window semantics, timezone labels, archive rewrites, other watermark metadata (생성 라인 etc.).

## Stage Decision

Functional Design: SKIP — presentation + gate-pattern alignment on an existing line contract.
NFR Requirements: SKIP — deterministic rendering; no new dependency, source, secret, or cost.

## Fixed Contracts

1. **New watermark shape** (pinned, single source of truth in `enhancement.py`):
   `**기준 시각**: {YYYY-MM-DD} {TZ_LABEL} · 수집창 {start-ISO} ~ {end-ISO} (종료 미포함)`
   Example: `**기준 시각**: 2026-06-30 NY · 수집창 2026-06-30T04:00Z ~ 2026-07-01T04:00Z (종료 미포함)`
   - `수집창` token restores the key the u112 check already gates on.
   - `~` range with `(종료 미포함)` preserves the half-open semantics in Korean without bracket notation.
   - No `[`, `]`, or dangling `)` other than the balanced `(종료 미포함)` pair.
2. **Gate alignment**: `_WATERMARK_LINE_RE` and `_bad_watermark_window` match the new shape exactly; additionally, any `**기준 시각**:` line that (a) contains an unbalanced `(`/`)` count, or (b) matches the legacy `…Z, …Z)` dangling shape, is a blocking `watermark.window_bracket` issue.
3. **Chain stability**: the new line passes the full `apply_reader_format` chain and the summary/surface repair passes byte-unchanged (regression test runs the actual chain, not a unit-level formatter).

## Implementation Steps

- [x] Step 1 — Trace the stripper: feed the current legacy line through the production reader-format/publish chain in a test to identify which repair pass removes the `[` (candidates listed in Problem Statement). Record the finding in the unit summary; do not "fix" the stripper — it is correct for genuine unbalanced brackets.
  - Finding: `apply_reader_format()`, `reflow_first_viewport()`, and `repair_first_viewport_summary()` preserve the legacy line. A spy on the actual `segment_reader_format.apply_reader_format_to_segments()` call captures the legacy line immediately before `repair_surface_artifacts()` and the stripped line immediately after it. Its first-viewport `_repair_unmatched_markdown_markers()` path treats the unmatched `[` as a recoverable Markdown marker and removes it.
- [ ] Step 2 — Change `src/investo/briefing/_reader_enhance/enhancement.py` (line ~114 and docstring example at ~96) to the pinned shape.
- [ ] Step 3 — Update `_WATERMARK_LINE_RE` and `_bad_watermark_window` in `src/investo/_internal/surface_quality.py` per Fixed Contract 2, including the legacy-shape blocker.
- [ ] Step 4 — Add the chain byte-stability regression (Fixed Contract 3) using a full segment fixture.
- [ ] Step 5 — Add gate tests: new shape passes; legacy 2026-06-30 line (verbatim) blocks; unbalanced-paren variant blocks.
- [ ] Step 6 — Sweep other consumers: `rg -n "기준 시각" src/ tests/` and update any test fixture or parser expecting the old shape (notably `_internal/briefing_extract.py` if it parses the line).
- [ ] Step 7 — Quality gate: scoped ruff/format, `mypy src`, `pytest tests/unit/internal tests/unit/briefing tests/unit/publisher`.

## Acceptance Criteria

1. AC-132.1: Newly rendered segment markdown contains the pinned `수집창 … ~ … (종료 미포함)` watermark with balanced brackets.
2. AC-132.2: The verbatim legacy 2026-06-30 watermark line is a blocking surface-quality issue.
3. AC-132.3: The watermark line is byte-identical before and after the full reader-format/repair chain.
4. AC-132.4: `_bad_watermark_window` returns `True` for at least: legacy dangling shape, missing `수집창`, unbalanced parens; `False` for the pinned shape.
5. AC-132.5: No committed archive file is modified.

## Tests / Validation

- `tests/unit/internal/test_surface_quality.py` — gate cases (AC-132.2/132.4).
- `tests/unit/briefing/` enhancement tests — renderer shape.
- Chain regression in `tests/unit/publisher/test_segment_reader_surface_quality.py` or the existing full-chain test module — AC-132.3.
- Local gate: scoped ruff/format, `mypy src`, focused pytest.

## Non-Goals

- No change to window computation, market timezone mapping, or the 생성 watermark caption line.
- No modification of bracket-repair passes for non-watermark lines.
- No archive backfill.

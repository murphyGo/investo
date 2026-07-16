# Code Generation Plan: `u134 callout-and-diagnostic-line-composition-repair`

**Date**: 2026-07-17
**Unit**: u134 callout-and-diagnostic-line-composition-repair
**Stage**: Code Generation
**Status**: Backlog (Ready)
**Source**: 2026-06-29/2026-06-30 production bundle review (briefing-unit-planner, 2026-07-17)
**Estimated Effort**: ~3 h
**Dependencies**:
- u61/u71 first-viewport summary/reflow (Complete) — callout rendering sites.
- u108 reader-facing-quality-language-boundary (Complete) — `_internal/public_quality_language.py` constants and the public/diagnostic region rules.
- u127 summary-quality-reject-contract-unification (Complete) — reject predicate unchanged.
- u66/u74 crypto indicator & channel baseline tables (Complete) — table structure unchanged.

---

## Problem Statement

Four deterministic composition defects appear in the 2026-06-29/30 production briefings (every segment):

**(a) 핵심 동인 heading+sentence splice.** `archive/us-equity/2026/06/2026-06-30.md:17`:
```
> **핵심 동인**: 칩메이커 강세에 나스닥100 **+1.68%** 마감 나스닥 기사에 따르면 화요일(목표일) S&P 500은 …
```
The driver value is a §② story heading concatenated directly with the story's first body sentence, no separator ("…마감 나스닥 기사에 따르면…"). Producer: `src/investo/briefing/_reader_enhance/enhancement.py:176` renders `summary_header.driver` as-is; the driver assembly upstream joins heading + sentence with a bare space.

**(b) 오늘의 결론 low-coverage suffix splice.** All three segments end the 결론 callout with `…괴리가 관찰된다. 수집 근거가 제한적입니다` — `PUBLIC_LOW_COVERAGE_INLINE_TEXT` (`_internal/public_quality_language.py:21`, no trailing period, no leading connector) is appended to prose, producing a period-less splice and a 평서체→존댓말 register break mid-callout.

**(c) 소스 카운트 placeholder repetition.** Inside the collapsed `<details>수집/품질 진단</details>` block, every briefing renders:
```
> **소스 카운트**: 수집 대상 25 / 성공 20 / 수집 상세는 진단 섹션에서 확인할 수 있습니다. / 수집 상세는 진단 섹션에서 확인할 수 있습니다. / 수집 상세는 진단 섹션에서 확인할 수 있습니다.
```
The three trailing slots (0건 / 실패 / 본문 사용 counters) are each replaced by the full `PUBLIC_SOURCE_DETAIL_TEXT` pointer sentence (`_internal/public_quality_language.py:16`) — the u108 public projection applied per-slot *inside the diagnostics block it points to*. Composer: the `소스 카운트` line assembly in `src/investo/publisher/reader_format/reflow.py` (see the regex consuming `실패 N / 본문 사용 N` in the same file).

**(d) Funding-rate decimal noise.** `archive/crypto/2026/06/2026-06-29.md` lines 28/40 render `BTC 펀딩비 | 0.0001000000000000` — a Decimal serialized without normalization in the ⓪-A indicator table and ⓪-B channel baseline (`src/investo/publisher/channel_anchor_block.py` and the u66 indicator-table renderer).

## Goal

First-viewport callouts and collapsed diagnostics are well-formed Korean: the driver has a visible separator, the low-coverage note is its own sentence, diagnostics show numeric counters (or one pointer, once), and rates render without trailing-zero noise.

## Existing Coverage / Deduplication

- **u61/u71/u127**: summary extraction, reflow ordering, and the reject predicate are unchanged — this repairs the *producers* feeding them; no new gate family.
- **u108**: the public-language boundary is preserved for first-viewport/public regions; the fix applies only inside the collapsed diagnostics region, which u108 already designates operator-visible.
- **u131** owns truncation/bounding; this unit owns composition (separators, punctuation, slot filling). No overlap: neither touches the other's code paths.
- **u66/u74**: table structure and row semantics unchanged; only Decimal-to-string normalization changes.

## Scope Boundary

In scope: the four defects above, their producers, and pinned formats.
Out of scope: truncation/bounding (u131), summary reject rules (u127), diagnostics block ordering (u71), new KPIs, prompt changes.

## Stage Decision

Functional Design: SKIP — deterministic string composition repair on existing render contracts.
NFR Requirements: SKIP — no new dependency, source, secret, network, or cost.

## Fixed Contracts

1. **Driver format**: `{heading} — {first sentence}` with a spaced em-dash separator; if the combined value exceeds the existing driver length budget, render `{heading}` alone. No other wording change.
2. **Low-coverage note**: appended as its own sentence using the full-sentence constant `PUBLIC_LOW_COVERAGE_TEXT` ("이번 문서는 수집 근거가 제한적입니다.") after the preceding sentence's terminator; never the inline fragment. If the preceding prose lacks a terminator, add `.` before appending. `PUBLIC_LOW_COVERAGE_INLINE_TEXT` remains for genuine mid-sentence uses elsewhere (audit each use site; only the 결론-append site changes).
3. **소스 카운트 line (inside `<details>` diagnostics only)**: `수집 대상 N / 성공 N / 0건 N / 실패 N / 본문 사용 N|미집계` — numeric counters restored. The pointer sentence never appears inside the diagnostics block. First-viewport/public projections of source counts are untouched (u108 rules apply there).
4. **Rate normalization**: Decimal values in indicator/baseline tables render via `Decimal.normalize()`-equivalent shortest exact form with no exponent notation (`0.0001`, not `0.0001000000000000`, not `1E-4`). Applies to the funding-rate row family in `channel_anchor_block.py` and the u66 indicator table; no rounding (exact value preserved).

## Implementation Steps

- [ ] Step 1 — Trace driver assembly upstream of `enhancement.py:176` (the `summary_header.driver` builder in `briefing/_assembly/` per u83 decomposition); apply Fixed Contract 1 at the assembly point, not the render point. Tests with the verbatim 2026-06-30 heading+sentence pair.
- [ ] Step 2 — Locate the 결론-append site for `PUBLIC_LOW_COVERAGE_INLINE_TEXT` (rg the constant; the append happens in the summary/first-viewport pipeline); apply Fixed Contract 2. Test both terminator-present and terminator-absent preceding prose.
- [ ] Step 3 — Fix the `소스 카운트` composer in `src/investo/publisher/reader_format/reflow.py` per Fixed Contract 3; confirm the consuming regexes in `publisher/quality_consistency.py` and `publisher/evidence_accounting.py` (both parse `실패 N / 본문 사용 N`) still match, and update their tests if the restored counters change matches from `미집계` paths.
- [ ] Step 4 — Add Decimal normalization per Fixed Contract 4 in `src/investo/publisher/channel_anchor_block.py` and the u66 indicator table renderer; test `0.0001000000000000 → 0.0001`, `0.0100 → 0.01`, integer-valued Decimals keep no trailing dot.
- [ ] Step 5 — Rendered regression fixtures reproducing all four 2026-06-29/30 shapes; assert repaired output and idempotent reruns.
- [ ] Step 6 — Quality gate: scoped ruff/format, `mypy src`, `pytest tests/unit/publisher tests/unit/briefing tests/unit/internal`.

## Acceptance Criteria

1. AC-134.1: 핵심 동인 renders `{heading} — {sentence}` (verbatim 2026-06-30 input produces the separator) or heading-only past the length budget.
2. AC-134.2: The low-coverage note renders as its own terminated sentence; no `…관찰된다. 수집 근거가 제한적입니다` splice shape survives.
3. AC-134.3: The diagnostics 소스 카운트 line shows five numeric-or-미집계 slots and zero pointer sentences; `quality_consistency`/`evidence_accounting` parsers still reconcile.
4. AC-134.4: Funding-rate rows render shortest exact form; ⓪-A and ⓪-B show identical values.
5. AC-134.5: First-viewport/public source-count projections are byte-unchanged (u108 boundary intact).
6. AC-134.6: Reruns over repaired output are byte-stable.

## Tests / Validation

- `tests/unit/briefing/` assembly tests — driver format.
- `tests/unit/publisher/test_reader_format.py` — low-coverage append, 소스 카운트 slots.
- `tests/unit/publisher/test_quality_consistency.py`, `tests/unit/publisher/test_evidence_accounting.py` — parser agreement.
- `tests/unit/publisher/test_channel_anchor_block.py` — rate normalization.
- Rendered regression fixtures from the 2026-06-29/30 shapes.
- Local gate: scoped ruff/format, `mypy src`, focused pytest above.

## Non-Goals

- No truncation/bounding changes (u131), no reject-predicate changes (u127), no diagnostics reordering (u71).
- No public first-viewport source-count exposure (u108 boundary stays).
- No rounding of rates — normalization only.
- No archive backfill.

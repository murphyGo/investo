# Code Generation Plan: `u130 domestic-anchor-level-claim-quarantine-v2`

**Date**: 2026-07-17
**Unit**: u130 domestic-anchor-level-claim-quarantine-v2
**Stage**: Code Generation
**Status**: Backlog (Ready)
**Source**: 2026-06-29/2026-06-30 production bundle review (briefing-unit-planner, 2026-07-17)
**Estimated Effort**: ~4-5 h
**Dependencies**:
- u109 domestic-anchor-sanity-quarantine (Complete) — trust classification, plausibility bands, withheld metadata.
- u70 cross-surface-numeric-anchor-reconciliation (Complete) — `anchor_assertion_gate.py` move-claim gate.
- Commit `d4d32d1` (2026-07-02) — blockquote callouts are already prose-gated; preserve.
- u55 numeric verification (Complete) — unchanged; this unit does not verify numeric truth.

---

## Problem Statement

The published 2026-06-30 domestic briefing (`archive/domestic-equity/2026/06/2026-06-30.md`) asserts **"코스피는 150.00을 나타냈다"** in 오늘의 결론, 핵심 동인, §① 요약, and §② — four public claims of an index level that is off by ~50x (the 06-29 briefing states KOSPI traded around 8,390; the 06-25 anchor table shows 8,800.00). On the same date:

- The u109 quarantine worked as designed for the anchor surfaces: the top table has no 코스피 row and ⓪-B shows `코스피 | 미수집`. The **body prose kept the bad number anyway** because the u70 gate only detects *move claims* (movement verb such as 급락/상승 plus signed number, see `_MOVE_VERBS` in `src/investo/publisher/anchor_assertion_gate.py`). "코스피는 150.00을 나타냈다" contains no move verb and no signed percent, so it passes.
- The anchor table published `^KOSDAQ | 344.00` although the 2026-06-26 briefing's anchor surfaces carried 477.00 — a -28% four-day jump. The u109 static band for `^KOSDAQ` is `(300, 3000)` (`src/investo/orchestrator/domestic_anchor_quarantine.py:34`), so 344.00 passes; there is no continuity check against the segment's own recent published anchors.
- The TL;DR (한눈에 보기) says "SK하이닉스 관련 정밀 수치는 … 확정할 수 없습니다" (gate rewrite) while §③ in the same document asserts "SK하이닉스[000660]는 2,628,000원" and "삼성전자[005930]는 323,000원(-4.86%)" — the same symbol is gated in one section and asserted in another within a single run.

A reader who knows the market sees fabricated-looking numbers; a reader who does not is directly misinformed. This is the highest-severity reader-trust defect in the reviewed bundle.

## Goal

A domestic briefing can never publish a precise index/FX/large-cap **level** for a symbol whose anchor is quarantined or absent, an anchor value discontinuous with the segment's own recent published values is quarantined before any surface sees it, and gate decisions for a symbol are consistent across every section of one document.

## Existing Coverage / Deduplication

- **u109** owns trust classification, static plausibility bands, orchestrator-level filtering, and withheld-count quality metadata. This unit adds one quarantine *reason* (`discontinuous`) inside u109's classifier; bands and existing reasons are unchanged.
- **u70** owns the assertion gate and its move-claim detection. This unit adds *level-claim* detection beside it; `_MOVE_VERBS`, the signed-number guard, and the d4d32d1 blockquote handling are unchanged.
- **u55** numeric freshness/fact verification is untouched.
- **u74** `channel_anchor_block` missing reasons are untouched.
- Not in scope: US/crypto claim gating changes, new source adapters, LLM prompt changes.

## Scope Boundary

In scope:
- Level-claim detection for domestic core symbols (`^KOSPI`, `^KOSDAQ`, `KRW=X`, `005930.KS`, `000660.KS` — the existing `_SEGMENT_CORE_SYMBOLS[DOMESTIC_EQUITY]`).
- `discontinuous` quarantine reason with a last-published-anchor lookback.
- Same-run same-symbol gate-decision consistency sweep.
- Quality-history metadata for the new reason.

Out of scope:
- US/crypto level-claim gating (follow-up only if production shows the same defect there).
- Changing static plausibility bands.
- Re-verifying numbers against sources (u55).
- Rewriting historical archives.

## Stage Decision

Functional Design: SKIP — extends two existing gate/quarantine mechanisms with pinned contracts below; no new domain entity.
NFR Requirements: SKIP — deterministic string/decimal logic; no new dependency, source, secret, network call, or runtime budget.

## Fixed Contracts

1. **Level claim** = a sentence containing (a) a core-symbol Korean/English label (resolve via the existing `anchor_label` registry plus the alias sets already used by move-claim detection) AND (b) a decimal number ≥ 2 digits (with optional thousands separators, optional decimals, optional trailing unit 원/포인트/pt) within the same sentence, AND (c) no movement verb from `_MOVE_VERBS`. Sentences already matched as move claims stay on the move-claim path.
2. **Gate action for level claims** = identical to move claims: rewrite the offending sentence to the existing deterministic data-limited callout, preserving neighboring supported sentences (reuse `_gate_line` machinery).
3. **Discontinuity rule** = when classifying a candidate domestic anchor value, look up the most recent published value for the same symbol within the prior **7 calendar days** from the quality/anchor history the orchestrator already loads (u52-style archive walk is the fallback if no structured store exists — the implementer must reuse the existing archive-walk helper, not write a new scanner). If `abs(candidate/previous - 1) > 0.15` for `^KOSPI`/`^KOSDAQ`/`KRW=X` or `> 0.30` for `005930.KS`/`000660.KS`, classify as `discontinuous` (a new reason string alongside `implausible`/`stale`). No previous value within 7 days → skip the check.
4. **Consistency sweep** = after per-line gating, collect the set of symbols for which any rewrite occurred; run a second pass over the document gating *all* remaining precise claims (level or move) about those symbols. Idempotent: a second application produces byte-identical output.
5. `discontinuous` counts into the existing `domestic_anchor_withheld_count` and appends to `domestic_anchor_withheld_reasons`.

## Implementation Steps

- [ ] Step 1 — Read `src/investo/publisher/anchor_assertion_gate.py` end to end; extend claim detection with the level-claim pattern (Fixed Contract 1), reusing `_SEGMENT_CORE_SYMBOLS` and the existing sentence splitter. Add unit tests for the exact 2026-06-30 sentences ("코스피는 150.00, 코스닥은 344.00을 나타냈다", "SK하이닉스[000660]는 2,628,000원으로 동반 하락했다").
- [ ] Step 2 — Add the consistency sweep (Fixed Contract 4) as a post-pass in the gate's public entry point; pin idempotency with a double-application test.
- [ ] Step 3 — In `src/investo/orchestrator/domestic_anchor_quarantine.py`, add the `discontinuous` reason (Fixed Contract 3). Locate the previous-published-value lookup: first inspect what u109 already loads for `stale` detection; reuse that data path. Add tests for 477→344 (quarantined), 477→460 (passes), no-history (skipped).
- [ ] Step 4 — Wire `discontinuous` into withheld-count/reasons metadata (`src/investo/orchestrator/pipeline.py` quality assembly; follow the existing reason plumbing added by u109).
- [ ] Step 5 — Record a rendered regression fixture: run the reader-format + gate chain over a stored copy of the raw 2026-06-30 domestic Stage-2 output (or a trimmed snippet fixture reproducing the four "150.00" claims) and assert no precise 코스피 level survives.
- [ ] Step 6 — Prove US/crypto fixtures byte-unchanged (existing `test_anchor_assertion_gate.py` US/crypto cases must not need edits).
- [ ] Step 7 — Quality gate: scoped ruff + format, `mypy src`, focused pytest for the two modules, full `pytest tests/unit/publisher tests/unit/orchestrator`.

## Acceptance Criteria

1. AC-130.1: A bare level claim about a domestic core symbol with a quarantined/absent anchor is rewritten to the data-limited callout in body prose, list bullets, and reader-format blockquote callouts.
2. AC-130.2: The exact 2026-06-30 "코스피는 150.00" sentences (all four section variants) are gated in the regression fixture.
3. AC-130.3: A domestic anchor value >15% (index/FX) or >30% (large-cap) away from the most recent published value ≤7 days old is withheld with reason `discontinuous`, and the reason appears in quality-history metadata.
4. AC-130.4: When any claim about symbol X is gated, no precise level or move claim about X survives anywhere in the same document (SK하이닉스 TL;DR-vs-§③ shape).
5. AC-130.5: Gate application is idempotent (double-run byte-equal).
6. AC-130.6: US and crypto gating behavior is byte-unchanged on existing fixtures.

## Tests / Validation

- `tests/unit/publisher/test_anchor_assertion_gate.py` — new level-claim cases, consistency-sweep cases, idempotency, US/crypto unchanged.
- `tests/unit/orchestrator/test_domestic_anchor_quarantine.py` — `discontinuous` boundary cases (exactly 15%, >15%, no history, 8-day-old history skipped).
- New rendered regression fixture under `tests/fixtures/` reproducing the 2026-06-30 domestic claim shapes.
- Local gate: `ruff check` (changed files), `ruff format --check` (changed files), `mypy src`, `pytest tests/unit/publisher tests/unit/orchestrator`.

## Non-Goals

- No change to static plausibility bands or existing quarantine reasons.
- No numeric re-verification against source payloads (u55 owns that).
- No US/crypto claim-detection changes.
- No backfill of already-committed archives (the 2026-06-30 file stays as-is; the fixture is test-side).

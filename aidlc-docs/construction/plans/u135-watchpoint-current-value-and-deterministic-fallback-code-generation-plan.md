# Code Generation Plan: `u135 watchpoint-current-value-and-deterministic-fallback`

**Date**: 2026-07-17
**Unit**: u135 watchpoint-current-value-and-deterministic-fallback
**Stage**: Code Generation
**Status**: Backlog (Ready) — implement after u131 (card-title bounding lands first so title tests don't churn)
**Source**: 2026-06-29/2026-06-30 production bundle review (briefing-unit-planner, 2026-07-17)
**Estimated Effort**: ~4-5 h
**Dependencies**:
- u72 watchpoint-action-matrix (Complete) — §⑥ observational contract + `scan_compliance` double-pass.
- u87/u98 watchpoint rehabilitation/card redesign (Complete) — card shape.
- u110 watchpoint-human-readability-v2 (Complete) — field cleanup and hard-fail filters.
- u70 anchor reconciliation + u66 crypto indicators + u107 CFTC positioning (Complete) — the deterministic payloads this unit reads.
- u131 bounded-line-sentence-boundary-truncation (Backlog) — card-title bounding.
- DEBT-074 — graceful `데이터부족` collapse stays for genuinely empty payloads.

---

## Problem Statement

Two production failures in §⑥ 오늘의 관전 포인트:

1. **Source label in the value slot.** `archive/crypto/2026/06/2026-06-29.md` lines 123-129 render a card whose `현재:` field is `CoinGecko BTC` — the *source name*, not a value — while the real values ($60,284 close, $58,935–$60,644 24h range) sit in the same briefing's reconciled payload. u110's DoD included promoting embedded source names out of text fields, and its gate is green, yet this shape published five days after u110 completed: the promotion leaves the vacated `현재:` slot empty-or-source-filled instead of resolving an actual value.
2. **Rich runs collapse to the bounded note.** `archive/us-equity/2026/06/2026-06-30.md:102` and `archive/domestic-equity/2026/06/2026-06-30.md:85` both render only `관전 포인트: 구조화 가능한 관찰 신호가 부족합니다` — although the us-equity briefing's own §③ carries CFTC leveraged-money net-short divergence (E-mini -18.9% OI, NQ -19.3% OI vs. indices up) and reconciled anchor closes with 52w ranges: exactly the observational up/down material §⑥ exists for. When Stage-2 emits no well-formed signals (or u110 filters kill them all), there is no deterministic path from already-collected data to a card.

## Goal

Public cards always carry a real snapshot value in `현재:`, and a segment whose reconciled payload contains concrete signals renders 1-2 bounded observational cards instead of the empty note — without any new LLM call and within the u72 compliance contract.

## Existing Coverage / Deduplication

- **u72** observational contract, banned-advice rules, and the post-conversion `scan_compliance` re-run: unchanged and reused for synthesized cards.
- **u87/u98**: card shape and rehabilitation logic unchanged.
- **u110**: field-prefix stripping, source promotion, duplicate-trigger and hard-fail filters unchanged for LLM cards; this unit adds value *resolution* after promotion and a fallback *after* u110 filtering.
- **DEBT-074**: the graceful `데이터부족` collapse remains the terminal state for payloads with no resolvable signals.
- **u64** structure regexes remain the validation contract for card text.
- Not in scope: matrix redesign, new sources, prompt rewrites beyond one clarifying example, watchlist matching.

## Scope Boundary

In scope: `현재:` value resolution from the reconciled payload; deterministic fallback synthesis (≤2 cards, closed templates); compliance re-scan of synthesized cards; regression fixtures.
Out of scope: card shape/신뢰도 enum changes, LLM prompting overhaul, new indicator collection, title bounding (u131).

## Stage Decision

Functional Design: SKIP — extends the existing §⑥ conversion contract with pinned templates and resolution keys; no new domain entity.
NFR Requirements: SKIP — deterministic synthesis from already-collected data; no new dependency, source, secret, LLM call, or cost.

## Fixed Contracts

1. **Value resolution keys** (segment → resolvable snapshot values, all read from payloads the orchestrator already passes to publish/reader-format):
   - Any segment: reconciled `MarketAnchor` close + pct for a core symbol (u70 `anchor_table_input`).
   - Crypto: 24h high/low from the price payload; F&G value; funding/OI from u66 indicator `raw_metadata`.
   - US: CFTC net-position % of OI per contract row (u107).
   - Domestic: reconciled KR anchors only (quarantined anchors are never resolvable — u109/u130).
2. **`현재:` rule**: after u110 source-promotion, the `현재:` slot must contain at least one digit or a value token from the resolution keys. A card whose `현재:` cannot resolve hard-fails into u110's existing invalid-row handling. Resolution matches card signal text to keys by ticker/label token (reuse `anchor_label` registry tokens; no fuzzy matching).
3. **Fallback trigger**: zero cards survive u110 filtering AND the segment payload resolves ≥1 key from contract 1. Then synthesize `min(2, resolvable signals)` cards in this fixed priority: (1) core anchor 52w/24h range card, (2) CFTC positioning divergence card (US/crypto), (3) F&G extreme card (crypto only, value ≤20 or ≥80).
4. **Closed Korean templates** (pinned; placeholders resolved from payload values, no free text):
   - Range: `관찰 신호: {label} 가격 구간 · 현재: {close} ({pct}) · 확인 조건: 상방 {upper} 상회 시 단기 회복 흐름 관찰; 하방 {lower} 이탈 시 방어적 수급 관찰 · 신뢰도: {conf} · 관심 영향: 본문 §⑤ 가격 동향과 연계 점검.`
     - Crypto `{upper}/{lower}` = 24h high/low; US/domestic = 52w high/low from the reconciled anchor.
   - CFTC: `관찰 신호: {contract} 포지셔닝 · 현재: 순포지션 {net}계약 ({oi_pct} OI, 주간 지연) · 확인 조건: 상방 순매도 축소 전환 관찰; 하방 순매도 확대 지속 관찰 · 신뢰도: 보통 · 관심 영향: 가격과 포지셔닝 괴리 지속 여부 점검.`
   - F&G: `관찰 신호: 공포·탐욕 지수 · 현재: {value} ({band}) · 확인 조건: 상방 20 상회 시 심리 회복 관찰; 하방 10 이탈 시 극단 공포 심화 관찰 · 신뢰도: 높음 · 관심 영향: 반등 지속성 판단 보조 지표.`
   (Rendered through the existing u98 card renderer — the templates define field payloads, not raw markdown.)
5. **신뢰도** from data freshness: same-run reconciled data → `높음`; weekly-delayed (CFTC) → `보통`. Never `데이터부족` on a synthesized card (contradiction by construction).
6. **Compliance**: synthesized cards pass the u64 structure regexes and the second `scan_compliance` pass (u72 orchestration); a compliance failure on a synthesized card drops that card (falls back toward the bounded note), never blocks publish.
7. Synthesized cards carry a non-public marker in diagnostics metadata (`watchpoint_synthesized: N` in the quality snapshot) so operators can observe fallback frequency; no public visual difference.

## Implementation Steps

- [ ] Step 1 — Read `src/investo/publisher/watchpoint_matrix.py` (u72/u87/u98/u110 layers) and the orchestrator conversion call in `src/investo/orchestrator/pipeline.py`; document (in the unit summary) where u110 promotion vacates `현재:`.
- [ ] Step 2 — Implement value resolution (Fixed Contracts 1-2) in `watchpoint_matrix.py`; the reconciled payload arrives via a new explicit parameter from the orchestrator (no publisher→orchestrator import; payload is plain data).
- [ ] Step 3 — Implement fallback synthesis (Fixed Contracts 3-5) in a new sibling `src/investo/publisher/watchpoint_fallback.py`; templates as module constants.
- [ ] Step 4 — Wire the orchestrator: pass the payload, run synthesis when the trigger fires, re-run `scan_compliance` over the final §⑥ (existing u72 double-pass extended to cover synthesized output), stamp `watchpoint_synthesized` into the quality snapshot.
- [ ] Step 5 — Regressions: (a) 2026-06-29 crypto fixture — `현재: CoinGecko BTC` resolves to `$60,284.00 (+2.23%)` or the row fails; (b) 2026-06-30 us-equity fixture — CFTC + anchor payload synthesizes 2 cards where production rendered the bounded note; (c) empty-payload fixture — bounded note preserved (DEBT-074).
- [ ] Step 6 — Compliance tests: synthesized templates pass u64 structure regexes and contain no banned-advice tokens; forced-failure path drops the card.
- [ ] Step 7 — Quality gate: scoped ruff/format, `mypy src`, `pytest tests/unit/publisher tests/unit/orchestrator`, `mkdocs build --strict` if site_docs touched (expected: not touched).

## Acceptance Criteria

1. AC-135.1: No public card renders a `현재:` slot without a digit/value token; the 2026-06-29 `현재: CoinGecko BTC` shape either resolves to the payload value or the row is filtered.
2. AC-135.2: A run with zero surviving LLM cards and a resolvable payload renders 1-2 synthesized cards in the pinned priority order; the 2026-06-30 us-equity fixture renders the CFTC + range cards.
3. AC-135.3: A run with no resolvable keys renders the existing bounded note byte-identically.
4. AC-135.4: Synthesized cards pass `scan_compliance` and u64 structure regexes; a failing synthesized card is dropped without blocking publish.
5. AC-135.5: `watchpoint_synthesized` count lands in quality-snapshot metadata; public rendering shows no synthesized/LLM distinction.
6. AC-135.6: u110 filter behavior for LLM cards is unchanged on existing fixtures.

## Tests / Validation

- `tests/unit/publisher/test_watchpoint_matrix.py` — value resolution, hard-fail path.
- New `tests/unit/publisher/test_watchpoint_fallback.py` — trigger, priority, templates, compliance, empty payload.
- `tests/unit/orchestrator/` stage tests — wiring, quality-snapshot stamp, double `scan_compliance`.
- Rendered regressions from 2026-06-29 crypto and 2026-06-30 us-equity/domestic shapes.
- Local gate: scoped ruff/format, `mypy src`, focused pytest above.

## Non-Goals

- No card-shape/신뢰도-enum change, no matrix redesign (u72/u98 stay).
- No new LLM call or prompt overhaul.
- No new indicator collection; only already-reconciled payloads are read.
- No liquidation/netflow signals (DEBT-071/072 boundaries stay).
- No archive backfill.

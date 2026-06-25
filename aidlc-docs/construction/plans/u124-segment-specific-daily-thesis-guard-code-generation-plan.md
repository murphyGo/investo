# Code Generation Plan: `u124 segment-specific-daily-thesis-guard`

**Date**: 2026-06-25
**Unit**: u124 segment-specific-daily-thesis-guard
**Stage**: Code Generation
**Status**: Backlog / Planned
**Source**: 2026-06-23 generated-briefing review, focused on repeated `> **오늘의 큰 그림:**` lines across domestic, US, and crypto archive pages.
**Estimated Effort**: ~3-5 h
**Dependencies**:
- u57 segment-narrative-scope-and-time-reconciliation is complete; keep segment scope and time-state rules.
- u60 shared-macro-evidence-hardening is complete; reuse shared macro evidence validation.
- u99 daily-thesis-layer is complete; extend its thesis rendering instead of adding a second thesis surface.
- u112 reader-markdown-polish-gate-v2 is complete; keep existing bounded grammar/polish checks.

---

## Problem Statement

The 2026-06-23 domestic, US, and crypto briefings all render the same first-viewport daily thesis:

`> **오늘의 큰 그림:** 금리와 달러 변수가 국내·미국에 동시에 걸리며, 오늘 독자는 금리·달러 민감도을 먼저 확인해야 합니다.`

The grammar issue is already covered by u112, but the semantic defect remains: three different segment pages present one generic cross-market consequence. A domestic reader needs the thesis to connect rates/dollar to KOSPI flows, USD/KRW, and local sectors. A US reader needs sector/rates/earnings framing. A crypto reader needs liquidity, risk appetite, funding/OI, or policy framing.

## Goal

Make the daily thesis segment-native while preserving the shared macro bridge. The same macro fact may appear in multiple segments, but the consequence sentence must be distinct and anchored to each segment's evidence context.

## Existing Coverage / Deduplication

- u57 owns time-state and segment narrative scope.
- u60 owns shared macro evidence matching.
- u99 owns the daily thesis surface.
- u112 owns bounded polish defects such as `민감도을`.

This unit extends u99 with bundle-level duplication and segment-consequence gates. It does not redesign the first viewport, add macro sources, or change u57 shared macro block rendering.

## Scope Boundary

In scope:
- Add a segment consequence field to the existing daily thesis input contract.
- Block identical thesis text across all three segments in one bundle.
- Require segment-native nouns in the consequence clause.
- Add a bounded fallback line for segments without enough evidence.

Out of scope:
- No new macro source adapter.
- No bundle-context entity replacement.
- No chart or watchpoint rendering change.
- No broad style checker.
- No archive backfill.

## Stage Decision

Functional Design: skip. This is a prompt/context and deterministic gate refinement over u99.

NFR Requirements: skip. No new dependency, source, secret, network call, workflow, runtime budget, or deploy surface.

## Fixed Contracts

### Thesis Input Contract

Extend the current thesis input with a segment consequence value:

```python
@dataclass(frozen=True, slots=True)
class SegmentDailyThesisInput:
    segment: MarketSegment
    shared_driver: str
    segment_consequence: str
    evidence_labels: tuple[str, ...]
```

Rules:
- `shared_driver` may repeat across segments.
- `segment_consequence` must not repeat across all three segments.
- `evidence_labels` must reference labels already present in segment context or channel baseline rows.
- Empty evidence collapses to the fixed fallback:
  `> **오늘의 큰 그림:** 이 세그먼트의 공통 신호는 제한적입니다. 본문 수급·지표 항목을 먼저 확인하세요.`

### Segment Consequence Lexicon

Use a deterministic minimum term set:

- domestic-equity: one of `KOSPI`, `KOSDAQ`, `원/달러`, `외국인`, `기관`, `반도체`, `국내 수급`
- us-equity: one of `S&P 500`, `Nasdaq`, `Dow`, `섹터`, `실적`, `CFTC`, `변동성`, `미국 금리`
- crypto: one of `BTC`, `ETH`, `도미넌스`, `펀딩`, `OI`, `CFTC`, `정책`, `유동성`

## Implementation Steps

- [ ] Inspect `src/investo/orchestrator/bundle_context.py` where `> **오늘의 큰 그림:**` is composed.
- [ ] Inspect `src/investo/publisher/daily_thesis.py` and current `tests/unit/publisher/test_daily_thesis.py` to preserve the u99 marker contract.
- [ ] Add `SegmentDailyThesisInput` in the existing daily-thesis or bundle-context module that already owns thesis rendering.
- [ ] Build segment consequence strings from existing segment anchors, channel baseline rows, source outcomes, and bundle context; do not read new files or call network sources.
- [ ] Add a bundle-level assertion function that receives `{segment: thesis_text}` and rejects identical text across all three published segments.
- [ ] Wire the assertion into the segmented publish path before archive write and into replay/surface-quality checks.
- [ ] Update `src/investo/briefing/prompts.py` so Stage 2 recent-context instructions never ask for a raw repeated daily thesis line.
- [ ] Add tests for domestic/US/crypto distinct thesis text, insufficient-evidence fallback, and the 2026-06-23 repeated-line regression.
- [ ] Write `aidlc-docs/construction/u124-segment-specific-daily-thesis-guard/code/summary.md`.

## Acceptance Criteria

1. A same-date bundle cannot publish identical `오늘의 큰 그림` lines across domestic, US, and crypto.
2. Each published thesis line includes at least one segment-native term from the fixed lexicon.
3. The shared macro driver may repeat, but the consequence clause differs by segment.
4. The insufficient-evidence fallback is reader-safe and does not mention operator diagnostics.
5. Existing u99 daily thesis marker and placement remain unchanged.
6. Existing u57 shared macro block output remains unchanged outside the daily thesis line.
7. The 2026-06-23 repeated "금리와 달러 변수" fixture fails before the fix and passes after distinct consequence generation.

## Tests / Validation

```bash
uv run --extra dev pytest tests/unit/orchestrator/test_bundle_context.py tests/unit/publisher/test_daily_thesis.py tests/unit/briefing/test_prompts.py tests/integration/test_bundle_reconciliation.py tests/unit/internal/test_surface_quality.py
uv run --extra dev ruff check src/investo/orchestrator/bundle_context.py src/investo/publisher/daily_thesis.py src/investo/briefing/prompts.py tests/unit/orchestrator/test_bundle_context.py tests/unit/publisher/test_daily_thesis.py
uv run --extra dev ruff format --check src/investo/orchestrator/bundle_context.py src/investo/publisher/daily_thesis.py src/investo/briefing/prompts.py tests/unit/orchestrator/test_bundle_context.py tests/unit/publisher/test_daily_thesis.py
uv run --extra dev mypy src
```

## Non-Goals

- No macro source expansion.
- No rewrite of bundle context.
- No first-viewport reflow redesign.
- No grammar checker.
- No archive backfill.

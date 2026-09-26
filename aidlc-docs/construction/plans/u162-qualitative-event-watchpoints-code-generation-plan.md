# Code Generation Plan: `u162 qualitative-event-watchpoints`

**Date**: 2026-09-26
**Unit**: u162 qualitative-event-watchpoints
**Stage**: Code Generation (planned)
**Status**: Queued — design approved; follows u161; retains u152 numeric boundary.
**Source**: `../news-event-briefing/evidence/review-20260922.md`; user planning request 2026-09-26.
**Estimated Effort**: ~10–16 h
**Dependencies**: u157 typed 사건, u158 terminal event, 기존u152 current-observation계약 구현/통합.

## Problem Statement
정성현재상태에숫자/지표candidate가없으면기존watchpointresolver에서탈락한다. source-backed협상·법안·서비스후속관찰이정량카드로대체될수있다.

## Goal
정성 사건 상태를 추적하는 관전 포인트을 통해 전일 중요한 사건을 독자가 이해하고 신뢰 수준을 구분하게 한다. 자세한 동작은 [설계](../u162-qualitative-event-watchpoints/design-brief.md)의 Fixed contracts로 고정한다.

## Existing Coverage / Deduplication
Extend u152 numericresolver, u98/u110 card, u135 fallback, u144 typed outcomes, u153 bounding. Add only the named event/window extension; no replacement pipeline/finalizer, generic new quality dashboard, generic numeric engine, or parallel source registry.

## Scope Boundary
In scope: `models/events.py (u157 DTO extension), publisher/event_watchpoints.py, publisher/segment_reader_format.py, publisher/watchpoint_matrix.py (composition/result only), publisher/public_document.py`; new files `publisher/event_watchpoints.py`.
No production activation, historical archive rewrite, paid API, independent LLM evaluation stage, credentials change, or unrelated unit completion.

## Stage Decision
Functional Design: REQUIRED; design draft and common event contracts are written, approved 2026-09-27.
NFR Requirements: SKIP separate stage — 기존NF6/7/9/10과NFR-003/004/005/006/007 재사용. 새I/O/LLM/비용없음.
Use the shared NFR/validation document; no boilerplate infrastructure stage. This code plan does not bypass design/source/operational gates.

## Fixed Implementation Contracts
Normative: [design-brief](../u162-qualitative-event-watchpoints/design-brief.md), [event-contract](../news-event-briefing/event-contract.md), [business-rules](../news-event-briefing/business-rules.md), [NFR](../news-event-briefing/nfr-and-validation.md). The numbered rules and exact defaults there are part of this plan. Changes require synchronized design/AC updates.

## Implementation Steps
- [ ] Step 1: u152통합SHA와numericcurrentcontract를확인하고typedeventwatchpoint/CompanionOutcome를정의한다.
- [ ] Step 2: eventfact→observedstate/source/time/nextcheck검증및renderer를추가한다.
- [ ] Step 3: segment_reader_format에 event-present 총 2개 composition을 추가하고 event-absent numeric 최대 6/fallback 2를 보존한다.
- [ ] Step 4: B8 bounded repair에서 provisional survivor → 카드 reconciliation → reindex를 연결한다. read-only terminal 검증과 finalize idempotence를 확인한다.
- [ ] Step 5: numeric우회/partial사건제거/compliance/noeventnegative및real-finalizerreplay를통과한다.
- [ ] Step 6: kind별 CompanionOutcome와 자체 회귀·독립 리뷰를 완료한다. u159 소비자 확장은 선택적 후속 통합이며 이 유닛의 완료 조건이나 hard dependency가 아니다.

## Acceptance Criteria
1. AC-162.1: source-backed숫자없는협상/법안/서비스상태카드가유효하게남는다.
2. AC-162.2: 미래조건을current로복사하거나numericrow를event로바꿔검증을회피할수없다.
3. AC-162.3: mixed/event-only는 최대 2개, numeric-only는 기존 최대 6개/zero-row fallback 2개이며 typed aggregate 제약이 유지된다.
4. AC-162.4: 후처리삭제event가카드/summary에재등장하지않고두번finalizebyte동일이다.
5. AC-162.5: 기존numeric/fallbackfixture는event0일때동일하고source미상/금지표현은기존정책대로처리된다.

## Tests / Validation
Planned test targets (new paths are to be created): `tests/unit/publisher/test_event_watchpoints.py tests/unit/publisher/test_watchpoint_matrix.py tests/integration/test_mixed_event_watchpoints.py`.

```sh
uv sync --extra dev --extra docs
uv run python -m pytest -q tests/unit/publisher/test_event_watchpoints.py tests/unit/publisher/test_watchpoint_matrix.py tests/integration/test_mixed_event_watchpoints.py
uv run ruff check src tests
uv run mypy src
python scripts/check_no_paid_apis.py
git diff --check
```

Before the final integration, run the repository's current full gate and the shared golden matrix. Do not claim scheduled shadow, source qualification, notification or Pages checks from offline tests. Each fixture asserts final reader-visible output/typed outcome, not only helper internals. The exact test module names must be created or mapped to a verified existing module before running; this planning task does not execute future tests.

## Non-Goals
No promise of worldwide event completeness, no fabricated importance/market causality, no copying of unqualified full articles, no increasing LLM stages or removing data-trust gates. u154 layout, u156 Telegram formatting, unrelated sector dashboard/activation gates remain with their owners.

## Completion and handoff
Deliver code/test diff, focused/full gate evidence, per-AC results, cumulative read-only review, cross-check and public-surface compatibility proof. State remains Backlog until work actually starts. Code completion, remote delivery and operational activation are distinct statuses. The user authorized a commit and push after each completed unit on 2026-09-27.

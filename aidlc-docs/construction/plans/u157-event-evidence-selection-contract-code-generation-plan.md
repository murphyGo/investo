# Code Generation Plan: `u157 event-evidence-selection-contract`

**Date**: 2026-09-26
**Unit**: u157 event-evidence-selection-contract
**Stage**: Code Generation (complete)
**Status**: Code complete — 8/8 steps, full regression 5415 passed; final focused boundary suite 61 passed. Default off; v2 delivery waits for u158/u159.
**Source**: `../news-event-briefing/evidence/review-20260922.md`; user planning request 2026-09-26.
**Estimated Effort**: ~24–32 h
**Dependencies**: 기존 u58/u59/u93/u97 완료. u160/u161은 hard dependency가 아니다.

## Problem Statement
9/22 검토에서 국내·미국12편의 첫 이슈가 가격 등락이었다. 기존 price/macro core300과 일반 뉴스context100, Stage2 cap 때문에 중요한 비수치 사건이 밀릴 수 있다.

## Goal
중요 사건 선정과 입력 보존을 통해 전일 중요한 사건을 독자가 이해하고 신뢰 수준을 구분하게 한다. 자세한 동작은 [설계](../u157-event-evidence-selection-contract/design-brief.md)의 Fixed contracts로 고정한다.

## Existing Coverage / Deduplication
Extend u97 hierarchy, u93 budget, u58 policy lane, u59 required macro, u45/u57/u74 routing. Add only the named event/window extension; no replacement pipeline/finalizer, generic new quality dashboard, generic numeric engine, or parallel source registry.

## Scope Boundary
In scope: `models/events.py, briefing/_core/classification.py, _core/orchestration.py, _core/section_planning.py, _assembly/markdown_render.py, briefing/segments.py, briefing/generation_contract.py, orchestrator/pipeline.py, models/items.py (optional evidence field), publisher/git_ops.py (shared publication receipt), models/publication.py`; new files `models/events.py; briefing/event_selection.py; briefing/event_evidence.py; models/publication.py; orchestrator/event_receipts.py`.
No production activation, historical archive rewrite, paid API, independent LLM evaluation stage, credentials change, or unrelated unit completion.

## Stage Decision
Functional Design: REQUIRED; design draft and common event contracts are written, approved 2026-09-27.
NFR Requirements: REQUIRED — 공통 데이터와 Stage1 schema, input budget, routing 및 runtime failure 의미가 바뀐다. 공통 NF1/2/3/6/7/9/10 적용.
Use the shared NFR/validation document; no boilerplate infrastructure stage. This code plan does not bypass design/source/operational gates.

## Fixed Implementation Contracts
Normative: [design-brief](../u157-event-evidence-selection-contract/design-brief.md), [event-contract](../news-event-briefing/event-contract.md), [business-rules](../news-event-briefing/business-rules.md), [NFR](../news-event-briefing/nfr-and-validation.md). The numbered rules and exact defaults there are part of this plan. Changes require synchronized design/AC updates.

## Implementation Steps
- [x] Step 1: E1~E5 타입과 optional NormalizedItem.event_evidence, stable identity/span/serialization을 구현한다. 단일 문서의 두 제품과 새 공식 근거 추가를 검증한다.
- [x] Step 2: E11의 PublishReceipt, 원격 ancestry/CAS 확인, 7일 event receipt를 기존 publisher transaction에 연결한다. pre/post-commit 실패를 분리하고 preview/shadow는 기록하지 않는다.
- [x] Step 3: _select_llm_candidate_items의 모든 active lane을 stable key로 정렬하고 news reservation과 실제 evidence-row accounting을 통합한다. 기존 정책 우선권을 보존한다.
- [x] Step 4: ClassificationResult v2와 prompt/parse/error code를 추가한다. v1 replay는 명시적 legacy 경로로 유지한다.
- [x] Step 5: EventSelectionPlan과 점수·중복·불확실성 규칙을 구현하고 section_plan을 확장한다.
- [x] Step 6: Stage2 protected event renderer와 실제 선택목록을 공통 함수로 만들어 전송과 trace가 어긋나지 않게 한다.
- [x] Step 7: B2 공유 후보와 GenerationResult handoff를 연결한다. E9 shadow는 v1 프롬프트·입력·응답을 그대로 소비하고 preview는 별도 비게시 경로다.
- [x] Step 8: 회귀·정적 검사·독립 리뷰를 수행한다. 실제 v2 preview는 u158 parser 통합 후 검증하고 active는 u158/u159 완료까지 차단한다.

## Acceptance Criteria
1. AC-157.1: 숫자 없는 사건의 선정과 오래된 월간값 제외가 고정 fixture에서 통과한다. active/preview의 결정론적 후보·선정은 입력 permutation에 불변이며 live LLM 출력 불변을 주장하지 않는다.
2. AC-157.2: 1000건·대량단일source fixture에서도 모든 기존상한과 reservation accounting을 만족한다. 보호 actual 손실은0 또는 명시적 오류다.
3. AC-157.3: 가격14개+중요뉴스2개 사례에서 eligible 사건2개가 Stage2에 남는다. 월간값만 있는 날 사건을 꾸미지 않는다.
4. AC-157.4: invalid item ID/span/future-state/conflict가 supported로 통과하지 않는다. v2누락은classification_unavailable다.
5. AC-157.5: source-backed 글로벌사건만 허용된시장으로 공유되고 세그먼트 반응은 독립적이다.
6. AC-157.6: off/shadow는 동일 v1 기록 응답에서 공개 bytes/알림/cursor가 동일하다. preview는 archive/git/알림 쓰기 0회이며 active는 MVP 통합 전 거부된다.
7. AC-157.7: 하나의 문서 내 두 제품은 서로 다른 사건이며 후속 공식 문서 추가에도 기존 canonical event ID가 유지된다. pre/post-commit 실패, push 응답 유실과 remote cursor CAS를 E11대로 처리한다.

## Tests / Validation
Implemented test targets: `tests/unit/briefing/test_event_selection.py tests/unit/briefing/test_event_classification.py tests/unit/briefing/test_section_planning_story_hierarchy.py tests/integration/test_event_prompt_budget.py tests/unit/publisher/test_git_ops.py tests/integration/test_event_publication_boundary.py`.

```sh
uv sync --extra dev --extra docs
uv run python -m pytest -q tests/unit/briefing/test_event_selection.py tests/unit/briefing/test_event_classification.py tests/unit/briefing/test_section_planning_story_hierarchy.py tests/integration/test_event_prompt_budget.py tests/unit/publisher/test_git_ops.py tests/integration/test_event_publication_boundary.py
uv run ruff check src tests
uv run mypy src
python scripts/check_no_paid_apis.py
git diff --check
```

Before the final integration, run the repository's current full gate and the shared golden matrix. Do not claim scheduled shadow, source qualification, notification or Pages checks from offline tests. Each fixture asserts final reader-visible output/typed outcome, not only helper internals. Actual test commands and results are recorded in ../u157-event-evidence-selection-contract/code/validation.json.

## Non-Goals
No promise of worldwide event completeness, no fabricated importance/market causality, no copying of unqualified full articles, no increasing LLM stages or removing data-trust gates. u154 layout, u156 Telegram formatting, unrelated sector dashboard/activation gates remain with their owners.

## Completion and handoff
Deliver code/test diff, focused/full gate evidence, per-AC results, cumulative read-only review, cross-check and public-surface compatibility proof. State remains Backlog until work actually starts. Code completion, remote delivery and operational activation are distinct statuses. The user authorized a commit and push after each completed unit on 2026-09-27.

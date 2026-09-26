# Functional Design: u157 중요 사건 선정과 입력 보존

**Date**: 2026-09-26
**Status**: Design approved by the 2026-09-27 sequential-development request. Code complete — 8/8 steps, full regression 5415 passed; final focused boundary suite 61 passed. Default off; v2 delivery waits for u158/u159.
**Priority / effort**: P0 / 24–32 h (rough engineering estimate, not commitment).
**Dependencies**: 기존 u58/u59/u93/u97 완료. u160/u161은 hard dependency가 아니다.

## Reader problem
9/22 검토에서 국내·미국12편의 첫 이슈가 가격 등락이었다. 기존 price/macro core300과 일반 뉴스context100, Stage2 cap 때문에 중요한 비수치 사건이 밀릴 수 있다.

## Ownership and deduplication
Existing owners: u113 publication transaction, u97 hierarchy, u93 budget, u58 policy lane, u59 required macro, u45/u57/u74 routing.
Existing code touch points: `models/events.py, briefing/_core/classification.py, _core/orchestration.py, _core/section_planning.py, _assembly/markdown_render.py, briefing/segments.py, briefing/generation_contract.py, orchestrator/pipeline.py, models/items.py (optional evidence field), publisher/git_ops.py (shared publication receipt), models/publication.py`.
Proposed new modules: `models/events.py; briefing/event_selection.py; briefing/event_evidence.py; models/publication.py; orchestrator/event_receipts.py`. These paths do not imply implementation exists.

## Shared contracts
[Program overview](../news-event-briefing/README.md), [entities and schema](../news-event-briefing/event-contract.md), [business rules](../news-event-briefing/business-rules.md), [NFR and evaluation](../news-event-briefing/nfr-and-validation.md).
The unit-specific rules below bind the shared contract. Inconsistency must be resolved in design before code; implementations cannot silently override common identity/budgets/trust semantics.

## Fixed contracts
1. 공통 E1~E5와 E9~E11을 구현한다. 사건 ID·revision·span·timing·novelty와 7일 committed event receipt를 소유한다. 문서 identity와 사건 identity를 구분하고 기존 Category와 macro_event_key를 유지한다. E11의 공통 PublishReceipt/원격 확인 기반을 이 유닛에서 먼저 구현하며 u160이 재사용한다.
2. Stage1 news reservation은 최대 24개이며 기존 macro/공식 정책 우선권 뒤의 남은 공간에서 적용한다. 96-total/24-source/12-lookahead와 64KiB stdout을 유지한다. 공식 crypto-policy의 새로운 global cap은 만들지 않는다. active/preview의 모든 lane은 stable key로 정렬하고 off/shadow는 기존 순서를 유지한다.
3. Stage1 v2는 최대12개의 사건 draft를 반환한다. v2 요청에 event 정보가 없으면 정상0건으로 숨기지 않는다. classification 실패와 중요사건 미선정을 구분한다.
4. E5 점수/eligibility로0~5개를 선정한다. 숫자 없는 휴전/출시/발언 양성 사례, 정확하지만 변화 없는 월간값 음성 사례를 모두 고정한다. 인물의 유명세나 숫자 포함 여부는 점수항목이 아니다.
5. 선정 전에 필수 fact를 담은 모든 evidence rows를 먼저 배정한다. total/section 상한은 모두 실제 rows로 계산한다. optional 근거를 줄여도 예산이 부족하면 budget_deferred로 제외한다. selected plan과 Stage2 protected block은 정확히 일치해야 한다.
6. 공유후보는 B2의 닫힌 source/approved-cause 집합만 허용한다. 국내·미국·crypto로 실제 근거 없는 중요도를 복제하지 않는다. cross-market 후에도 segment별 선택과 source refs를 유지한다.
7. E9의 off/shadow/preview/active를 단일 GenerationPolicy로 전달한다. shadow는 기존 v1 입출력을 읽는 결정론적 계측만 한다. v2 생성은 비게시 preview에서 검증하며 u157 단독 active는 거부한다. shadow on/off 비교는 동일 기록 v1 응답을 사용한다.

## Stage decision
Functional Design: REQUIRED — new cross-module/event behavior; this document and shared contracts were approved by the 2026-09-27 implementation request.
NFR Requirements: REQUIRED — 공통 데이터와 Stage1 schema, input budget, routing 및 runtime failure 의미가 바뀐다. 공통 NF1/2/3/6/7/9/10 적용.
Separate NFR Design/Infrastructure Design: no separate artifact for pure code; focused runtime/storage rules are fully specified here. u157/u160/u161 public I/O and transaction rules require their NFR review before implementation. No new deployment platform.

## Failure and compatibility
Apply B4/B5/B8/B11 and unit-specific states. Off mode preserves current producer/consumer behavior. Existing numeric/entity/compliance hard gates and sibling availability remain authoritative. Code-ready status requires hard dependencies and design approval; source qualification stays separate from code readiness.

## Acceptance criteria
- AC-157.1: 숫자 없는 사건의 선정과 오래된 월간값 제외가 고정 fixture에서 통과한다. active/preview의 결정론적 후보·선정은 입력 permutation에 불변이며 live LLM 출력 불변을 주장하지 않는다.
- AC-157.2: 1000건·대량단일source fixture에서도 모든 기존상한과 reservation accounting을 만족한다. 보호 actual 손실은0 또는 명시적 오류다.
- AC-157.3: 가격14개+중요뉴스2개 사례에서 eligible 사건2개가 Stage2에 남는다. 월간값만 있는 날 사건을 꾸미지 않는다.
- AC-157.4: invalid item ID/span/future-state/conflict가 supported로 통과하지 않는다. v2누락은classification_unavailable다.
- AC-157.5: source-backed 글로벌사건만 허용된시장으로 공유되고 세그먼트 반응은 독립적이다.
- AC-157.6: off/shadow는 동일 v1 기록 응답에서 공개 bytes/알림/cursor가 동일하다. preview는 archive/git/알림 쓰기 0회이며 active는 MVP 통합 전 거부된다.
- AC-157.7: 하나의 문서 내 두 제품은 서로 다른 사건이며 후속 공식 문서 추가에도 기존 canonical event ID가 유지된다. pre/post-commit 실패, push 응답 유실과 remote cursor CAS를 E11대로 처리한다.

## Development sequence
See [code-generation plan](../plans/u157-event-evidence-selection-contract-code-generation-plan.md). Implementation follows the 2026-09-27 user-authorized sequential queue.

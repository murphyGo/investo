# Functional Design: u162 정성 사건 상태를 추적하는 관전 포인트

**Date**: 2026-09-26
**Status**: Design approved by the 2026-09-27 sequential-development request. Queued — design approved; follows u161; retains u152 numeric boundary.
**Priority / effort**: P2 / 10–16 h (rough engineering estimate, not commitment).
**Dependencies**: u157 typed 사건, u158 terminal event, 기존u152 current-observation계약 구현/통합.

## Reader problem
정성현재상태에숫자/지표candidate가없으면기존watchpointresolver에서탈락한다. source-backed협상·법안·서비스후속관찰이정량카드로대체될수있다.

## Ownership and deduplication
Existing owners: u152 numericresolver, u98/u110 card, u135 fallback, u144 typed outcomes, u153 bounding.
Existing code touch points: `models/events.py (u157 DTO extension), publisher/event_watchpoints.py, publisher/segment_reader_format.py, publisher/watchpoint_matrix.py (composition/result only), publisher/public_document.py`.
Proposed new modules: `publisher/event_watchpoints.py`. These paths do not imply implementation exists.

## Shared contracts
[Program overview](../news-event-briefing/README.md), [entities and schema](../news-event-briefing/event-contract.md), [business rules](../news-event-briefing/business-rules.md), [NFR and evaluation](../news-event-briefing/nfr-and-validation.md).
The unit-specific rules below bind the shared contract. Inconsistency must be resolved in design before code; implementations cannot silently override common identity/budgets/trust semantics.

## Fixed contracts
1. EventWatchpoint(kind="event",event_id,observed_state,observed_at/time_basis,source_refs,next_check,implication)와NumericWatchpoint를명시적taggedunion으로구분한다. 숫자가없다는문자열휴리스틱으로event분기하지않는다.
2. observed_state는 repair 단계의 provisional survivor EventFact에서 구성하고 seal 전에 validated terminal survivor와 대조한다. 생성 자유문장·미래 조건을 current로 복사하지 않는다. source/time basis를 표시하고 scheduled 상태는 예정으로 보존한다.
3. next_check는 같은 event의 source-backed scheduled fact가 있으면 그것을 사용한다. 없으면 kind별 닫힌 일반 관찰 템플릿(공식 결정/실적 공개/서비스 제공 상태/후속 발언 확인)을 쓰고 kind=observation_template로 구분한다. implication은 검증된 meaning을 재사용한다. 적합한 입력이 없으면 제외한다. standalone scheduled event는 u35에 남기며 추가 LLM/자유 today_watch 재파싱은 없다.
4. event문장에가격/금리/실적숫자가있으면기존numericgate를그대로적용한다. numericrow가unresolved일때kind=event로재시도하는경로는없다. u152 resolve_watchpoint_currents를수정하여예외를추가하지않는다.
5. 유효 event가 있는 active mixed/event-only 경로만 최대 2개다. event 1개+유효 numeric 1개, numeric 없으면 event 최대 2개다. event 0이면 기존 numeric 최대 6개와 zero-row fallback 최대 2개 계약을 유지한다. invalid event는 제외하고 실패 이유를 기록한다.
6. WatchpointRenderResult 기존rendered/limited제약은유지한다. public aggregate는유효카드1개이상이면rendered,0개면기존canonical limitation. kind별attempt/rendered/limited사유는새private CompanionOutcome에보관해rendered에limitation을섞지않는다. 기존hardgate는별도로우선한다.
7. B8 repair reconciliation 안에서 제거된 사건의 카드와 summary를 제거한다. event가 모두 제거되면 같은 frozen numeric payload로 legacy branch를 다시 계산한다. seal 이후 변경하지 않는다. no-source/unknown과 특이사항 없음을 구분한다.

## Stage decision
Functional Design: REQUIRED — new cross-module/event behavior; this document and shared contracts were approved by the 2026-09-27 implementation request.
NFR Requirements: SKIP separate stage — 기존NF6/7/9/10과NFR-003/004/005/006/007 재사용. 새I/O/LLM/비용없음.
Separate NFR Design/Infrastructure Design: no separate artifact for pure code; focused runtime/storage rules are fully specified here. u160/u161 public I/O and transaction rules require their NFR review before implementation. No new deployment platform.

## Failure and compatibility
Apply B4/B5/B8/B11 and unit-specific states. Off mode preserves current producer/consumer behavior. Existing numeric/entity/compliance hard gates and sibling availability remain authoritative. Code-ready status requires hard dependencies and design approval; source qualification stays separate from code readiness.

## Acceptance criteria
- AC-162.1: source-backed숫자없는협상/법안/서비스상태카드가유효하게남는다.
- AC-162.2: 미래조건을current로복사하거나numericrow를event로바꿔검증을회피할수없다.
- AC-162.3: mixed/event-only는 최대 2개, numeric-only는 기존 최대 6개/zero-row fallback 2개이며 typed aggregate 제약이 유지된다.
- AC-162.4: 후처리삭제event가카드/summary에재등장하지않고두번finalizebyte동일이다.
- AC-162.5: 기존numeric/fallbackfixture는event0일때동일하고source미상/금지표현은기존정책대로처리된다.

## Development sequence
See [code-generation plan](../plans/u162-qualitative-event-watchpoints-code-generation-plan.md). Implementation follows the 2026-09-27 user-authorized sequential queue.

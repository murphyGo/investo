# u167 Functional / NFR Design: 설명 근거와 품질 축

**Date**: 2026-10-10. **Status**: 설계 작성; 구현 미착수. **Purpose**: 원문에 있는 배경·의미·반응·후속 근거를 모델 입력까지 전달하고, 내용·시점·이력 부족을 분리한다.

## 현재 문제와 중복 제거

`briefing/event_evidence.py::_refs`는 actor/action/object/relation/impact/fact만 모은다. `_internal/event_rendering.py::_validate_narrative`는 그 집합 안의 refs만 의미/반응에서 사용하게 한다. 원문에 유용한 설명이 있어도 선택되지 않으면 Stage2가 사용할 수 없다. 같은 파일의419-427행은 서로 다른 부족 조건을 detail_limited 하나로 묶는다.

u157의 source/span/선정, u158의 본문, u161의 typed excerpt/자격검증된 HTTP, u159의 카운트를 재사용한다. 새 source registry, 원문 우회 수집, 별도 quality dashboard를 만들지 않는다.

## Canonical owners와 functional contract

- `models/event_context.py`: `EventContextDocument`, `EvidenceChunk`, `ContextRef`, `EventTimeContext`, `MeaningContext`, `ReactionContext`, `EventSupportVector`, `ContextEventDraft`.
- `models/event_config.py`: 공통 `EventGenerationPolicy`와 schema별 capability. 환경변수 해석은 entrypoint 한 곳에서 한다.
- `models/event_evidence.py`: source-owned evidence factory의 기존 소유권. source 입력→v3 chunk 변환은 여기의 pure factory로 확장한다.
- `briefing/event_evidence.py`, `event_input.py`, `event_prompt.py`, `event_selection.py`: transmitted buffer 검증·Stage1 schema·actual byte 보호.
- `publisher/event_quality.py`와 `models/event_quality.py`: 기존카운트에 versioned quality vector projection을 연결한다. 구조상 qualified의 기존 의미를 변경하지 않는다.

shared 필드·enum·precision·상한은 [C1/C2/C7](../event-news-v3/contracts.md)에 고정한다. Stage1 `ContextEventDraft`는 actor/action/object refs, fact drafts, relation/impact refs와 독립된 background/comparison/meaning/reaction/follow_up refs를 가진다. occurrence ID와 normalized novelty는 u168이 계산하며 이 유닛이 임의 identity를 확정하지 않는다.

`ContextFactDraft(subject_refs,predicate_refs,object_refs,metric_refs,value_refs,unit_refs,period_refs,status_refs,value_kind)`의 각 성분은 source-owned ContextRef tuple이다. value_kind는 numeric/text다. 숫자 fact는 subject·metric·value·unit·period·status를 확인할 수 있어야 한다. 원문에 unit/period가 없는 경우 null과 facts limitation을 유지하고 필수 actual을 완전하다고 판정하지 않는다. source가 미리 제공한 typed metadata도 pure factory가 field label과 값을 deterministic source-owned chunk로 직렬화해 동일 ref 검증을 적용한다. LLM의 key/value 선언만으로 metadata authority를 부여하지 않는다. u168 parent가 이 성분별 binding에서 canonical entity/metric/fact를 계산한다.

같은 사건에 속한 transmitted document/chunk 안의 refs만 사용할 수 있다. source가 확인하지 않은 시각·예상치·단위는 null/unknown으로 남긴다. chunk에1,200자 이후의 정보가 실제 확보된 경우에도 role별 정확한 locator와 budget으로 전달한다. 추가 원문을 얻을 권한은 u161/u173이 소유한다.

## NFR contract

Stage1 total24KiB와candidate96/source24/lookahead12를 유지하고 v3 Stage2 보호블록만16KiB로 둔다. v2는8KiB와기존serialization을유지한다. raw chunk/error/model text는 public Git/log/history에 기록하지 않는다. 진단은 field/rule_code/event hash/attempt의 bounded record다. 신규HTTP/LLM단계/secret/유료API는없다. 실제inputbytes와runtime를측정하고DEBT-090을자동완료시키지않는다.

## 실패 정책과 handoff

invalid ref/span/source ownership은 hard error다. fact/time/history/locator/meaning/reaction의 이용 가능성은 각각 유지한다. quiet와source_limited를구별한다. 정상0건으로classification실패를숨기지않는다. u168은 검증된 context draft와quality vector를, u169는새 역할별 보호블록과시간precision을소비한다.

## 설계 수용 조건

원문에 존재하지만 기존 identity/fact refs 밖에 있던 의미·반응이 v3 protected block에 남는 양성 사례, 다른 사건 refs를 붙이는 음성 사례, 날짜만 불명확한 충분한 기사, history만 없는 기사, 사실 자체가 없는 기사, 실제 future를occurred로승격하려는 사례를 각각 확인한다. 상세한 구현 AC와 명령은 [계획](../plans/u167-event-context-evidence-and-quality-code-generation-plan.md)에 있다.

# Functional Design Brief: u168 canonical-event-identity-and-fact-delta

**Date**: 2026-10-10
**Status**: 사용자 개발 지시로 Functional Design/NFR 실행 승인, 2026-10-10; foundation 5/8; native E5/CAS/운영 미적용.
**Dependency**: u167 event-context-evidence-and-quality.
**Normative contracts**: [event-news-v3/contracts.md C2/C3/C7](../event-news-v3/contracts.md). 공통 정책·예산의 정의와 변경은 해당 문서가 소유한다.

## 1. 목적과 확인한 현재 문제

같은 사건을 여러 매체가 다르게 표현하거나 공식 후속 문서가 추가될 때 사건의 정체성을 유지하고, 실적·정책의 새로운 사실과 단순 재보도를 구별한다. document, 단일 occurrence event, 장기 story를 분리한다. 사건 설명의 참·거짓을 identity hash로 판정하지 않는다.

현재 `src/investo/briefing/event_evidence.py:191-194,364-395`는 원문 actor/action/object 문자열에 날짜 또는 document alias를 결합한다. 사건 날짜가 없으면 같은 사실을 보도한 서로 다른 문서가 별도 ID가 될 수 있다. `:398-434`는 fact 원문 문자열 hash로 novelty를 계산한다. `:256-270`의 집합 포함 비교에는 문장 표현과 경제적 사실값의 구분이 없다. `src/investo/orchestrator/event_receipts.py:96-133`은 7일과 ID별 마지막 receipt를 유지한다. 정확한 원문 span·remote baseline·terminal survivor라는 기존 강점은 보존한다.

v3에서는 원문 alias 근거가 있는 엔티티, 단위·기간·상태를 포함한 사실, 명시적인 occurrence 근거를 parent가 정규화한다. LLM이 entity/event/story ID나 canonical alias를 발급하지 않는다. 같은 이름·날짜·주제만으로 같다고 판단하지 않는다.

## 2. Canonical owners와 입력/출력

| 경로 | 소유 책임 | 허용 import 방향 |
|---|---|---|
| `src/investo/models/event_identity.py` (신규) | frozen identity/fact/delta/receipt DTO, 닫힌 literal·bounds | models와 표준 라이브러리만 |
| `src/investo/models/event_story.py` (신규 foundation) | C6 전체 공유 frozen story DTO 선언; u169가 독립적으로 reader/receipt를 검증하도록 모델만 제공 | models와 표준 라이브러리만; reducer/I/O/render 없음 |
| `src/investo/briefing/event_identity.py` (신규) | source refs 해석을 통한 순수 normalization·match·delta | models, briefing, 이미 허용된 neutral `_internal` |
| `src/investo/orchestrator/event_receipts.py` (확장) | schema별 remote read, v3 serialization, 30일 보존 | models와 기존 Git/receipt owner |
| `src/investo/orchestrator/event_publication.py` (확장) | 확정 baseline과 sealed v3 receipts를 기존 transaction에 결합 | 기존 orchestrator 경계 |
| `src/investo/briefing/event_evidence.py` (호환) | schema2의 기존 함수·import·7일 semantics 유지 | v3 호출에서는 새 owner로 명시 분기 |
| `src/investo/briefing/generation_contract.py`, `briefing/event_prompt.py`, `orchestrator/pipeline.py` | v3 typed handoff만 추가 | 각 경계의 models DTO |

기존 `models/events.py.EventCandidate/EventIdentityReceipt`를 v3 의미로 조용히 바꾸지 않는다. 기존 `_span_key`, `_novelty`, `_match_receipt`를 새 도메인의 재사용 API로 만들지 않는다. u169가 sealed document를 변경할 때 `CanonicalEventReceipt`를 공유 models에서 가져오며 publisher→briefing import를 추가하지 않는다. `event_digest`는 기존 neutral 모델 utility를 재사용한다.

의존 cycle 방지를 위해 `models/event_story.py`의 전체 공유 DTO 선언은 u168 foundation에 포함한다. `StoryState`, `SealedStorySourceRef`, `NextCheck`, `StoryRecord`, `StoryStateProposal`, `StoryPublicationDelta`와 이에 직접 필요한 frozen support DTO를 C6 및 [u170의 S170-1~3](../u170-story-state-and-follow-up-ledger/design-brief.md)에 고정한 shape로 정의한다. typed `StoryPublicationDelta.next_record: StoryRecord`와 canonical next_record_hash/prior_record_hash를 함께 둔다. u169는 이 선언만으로 actual reader fields를 검증할 수 있고 u170 reducer/ledger를 import하지 않는다. u170은 모델을 재선언하지 않고 전이 의미·ledger·u162 integration을 구현한다. u168은 story state를 advance/선정/게시하지 않으며 delta tuple은 u170 통합 전 empty다.

아래 타입은 구현할 계약이다. 현재 파일에 존재한다는 뜻이 아니다. 모든 models DTO는 frozen/extra-forbid이며 ID·digest는 현재 `EventId` 24hex와 `Digest` 64hex를 재사용한다. 문자열의 Unicode codepoint 상한과 ledger UTF-8 byte 상한은 별도로 검증한다.

### E168-1. 엔티티와 alias

`EntityIdentity(entity_id: Digest, source_labels: tuple[str,...], display_label: str, alias_refs: tuple[ContextRef,...])`는 C3의 공유 타입이다. `source_labels`는 중복 없는 최대 8개·각 1..240자, `display_label`은 1..240자다. 원문 label과 refs를 보존한다. 승인된 짧은 alias가 없으면 긴 원문 label을 본문에서 사용한다. headline 120자와 digest 140자의 표시 제한 때문에 이 label이나 유효 본문을 삭제하지 않는다. 240자를 초과한 원문은 field limitation으로 기록하며 임의 약칭·중간 절단으로 우회하지 않는다.

`EntityIdentityBasis = approved_registry | explicit_source_alias | raw_label`을 추가한다. parent-owned `EntityBinding(entity, basis, registry_key: str|None, identity_refs: tuple[ContextRef,...])`는 private generation 입력이다. approved registry는 코드 리뷰된 기존 기업/티커 registry의 정확한 identifier와 등록된 label만 쓴다. registry-only row는 사건 발생 근거가 될 수 없다. 같은 원문에 명시된 동의 표기 또는 검수 registry의 동일 ID가 있어야 서로 다른 label을 같은 entity에 결속한다.

raw label은 NFKC/공백 정규화까지만 허용한다. 대소문자·법인 suffix·직함·언어를 임의로 없애지 않는다. 예: `Apple`과 `Apple Bank`, `Fed chair`와 특정 인물, 제품명 suffix가 다른 두 상품은 자동 병합하지 않는다. alias source ref는 u167의 정확한 transmitted chunk에 속해야 하며 original label과 원문 refs를 결과에 보존한다. 표시 alias가 승인되어도 원문에서 말하지 않은 인물의 현재 직함을 발급하지 않는다.

### E168-2. 사실과 delta

`CanonicalFact(subject_id: Digest, predicate: FactPredicate, object_id: Digest|None, metric_key_hash: Digest|None, value: str, unit: str|None, period: str|None, status: FactStatus)`는 C3 필드이며 기존 `FactPredicate/FactStatus`의 닫힌 값들을 재사용한다. `FactBinding(fact_id: Digest, canonical: CanonicalFact, original_value: str, source_refs: tuple[ContextRef,...], normalization: normalized|raw)`가 private 원문 결속을 소유한다. event당 최대8fact이며 fact별 refs 최대16개다. bound는 C4/C7와 함께 검증한다.

숫자 fact의 metric_key_hash는 필수다. source의 지표 명칭·공식 metric code를 u167 ContextFactDraft.metric_refs에서 결속하고 허용된 NFKC/공백 정규화 hash로 만든다. 검수 registry 또는 source의 explicit alias가 없는 metric synonym은 합치지 않는다. result/guidance 같은 predicate만으로 metric을 대신하지 않는다. text fact의 metric 부재는 null이다. 같은 issuer·period·unit·value여도 revenue와 net_income은 다른 fact라는 negative fixture를 고정한다. subject/object/value/unit/period/status도 ContextFactDraft의 성분별 refs에서 parent가 검증한다.

value는 최대240자, unit/period는 각 최대80자다. 허용 정규화는 NFKC·공백·숫자에 붙은 천 단위 separator 제거뿐이다. `1,200`과 `1200`은 합쳐도 `1.20`과 `1.2`, `5%`와 `0.05`, 달러와 원화, FY2026과 Q4, actual과 forecast는 합치지 않는다. 숫자 이외 comma·sign·소수·unit을 지우지 않는다. currency/scale 환산, 의미 synonym, 집계, 계산은 금지한다. predicate/unit/period/status는 source 또는 source-owned typed metadata로 확인되어야 한다. source-backed 여부가 불명확하면 원문 결속을 보존하고 `normalization=raw`를 쓴다.

fact identity = versioned digest of `(subject_id,predicate,object_id,metric_key_hash,normalized_or_raw_value,unit,period,status)`. source wording/ref offset/doc arrival은 canonical identity의 구성요소가 아니다. 원문 refs는 identity와 별도로 항상 보존한다. 동일 fact를 여러 문서가 뒷받침하면 refs를 합치되 한 문서의 상충 interpretation을 선택하지 않는다.

`EventFactDelta(added_fact_ids, superseded_fact_ids, unchanged_fact_ids, correction_pairs, unresolved_conflict_ids, evidence_refs)`는 parent-owned다. tuple은 stable sort/unique이며 membership은 baseline과 current fact set에 한정한다. 단순 현재 입력에서 사라진 fact는 superseded가 아니다. source가 수정·취소·대체 사실을 명시한 경우에만 `correction_pairs=(old_id,new_id)`를 발급하고 해당 refs를 요구한다. conflicting actual values는 모두 남기고 conflict를 기록한다. 새로운 독립적인 forecast/quoted opinion을 실제 결과로 승격하지 않는다.

novelty는 `new|material_update|repeat|unknown`이다. remote baseline을 못 읽으면 unknown, 확정 history에 occurrence가 없으면 new, occurrence가 있고 실제 추가/명시적 correction delta가 있으면 material_update, 모두 이미 알려진 사실이면 repeat다. revision 변화만으로 material_update를 발급하지 않는다. unknown은 repeat가 아니다. 이 판정은 source claims의 semantic truth를 대신하지 않는다.

### E168-3. occurrence와 안전한 duplicate

`OccurrenceStage = announcement|decision|result|implementation|correction|statement|unknown`은 source가 직접 확인한 발표 단계다. `CanonicalEventIdentity(event_id: EventId, event_key_hash: Digest, event_kind: EventKind, actor_ids: tuple[Digest,...], action_key_hash: Digest, object_ids: tuple[Digest,...], occurrence_key_hash: Digest, document_aliases: tuple[Digest,...], occurrence_basis: official_key|explicit_cross_reference|raw_document, occurrence_stage: OccurrenceStage, stage_refs: tuple[ContextRef,...])`는 private generation의 고정 identity다. `action_key_hash`는 source-backed action text의 허용 정규화 hash이며 임의 taxonomy synonym으로 통합하지 않는다. stage 미확인은 unknown/ref 없음이며 다른 source의 알려진 stage와 자동 결속하지 않는다.

동일 occurrence 판정 우선순위는 다음과 같다.

1. 명시된 공식 release/공시/결정 ID 또는 macro event key가 같고 event kind, actor/action/object, 발표 단계가 양립하면 공식 occurrence를 공유한다. 동일 공식 key에 상충 tuples가 있으면 `identity_conflict`다.
2. 동일 원문의 명시적 reference 또는 검수 adapter가 확인한 원발표 URL/ID가 같고 tuples·발표 단계가 양립하면 explicit cross-reference match다. LLM이 외부 locator를 발명하지 못한다.
3. 위 근거가 없으면 `(document_id, actor_ids, action_key_hash, object_ids, event_kind, stage)`의 보수적인 raw occurrence를 유지한다. 동일한 normalized tuples·날짜가 다른 문서에 등장하면 `uncertain_duplicate` pair로 계측하며 자동 병합하지 않는다.

같은 문서 속 다른 제품/결정/행동은 별도 occurrence다. 날짜만 같은 반복 연설·회사 같은 다른 실적 기간·scheduled 발표와 actual 결과는 별도 event다. 날짜·기간은 u167 `EventTimeContext`의 source refs를 사용하고 publication/received time을 event time으로 대입하지 않는다. 날짜는 matching contradiction check로 쓰되 날짜가 같다는 사실만으로 merge하지 않는다.

event_id는 최초 안정 occurrence key의24hex다. 이미 remote-confirmed ID가 있으면 공식 근거가 뒤늦게 추가되어도 ID를 유지하고 alias만 추가한다. 여러 기존 remote IDs를 하나로 합칠 근거가 모호하면 자동 선택하지 않는다. 기존 ID를 재작성하는 bulk merge·redirect migration은 이 유닛에 없다.

`IdentityMatchResult(identity, outcome: matched|new|uncertain_duplicate|conflict, matched_receipt_ids, duplicate_pairs)`는 closed 결과다. conflict는 기존 trust/quality owner에 넘기며 valid라고 흡수하지 않는다. `uncertain_duplicate`의 두 occurrence를 별도 record로 남기고 u169 editorial selector에 제공한다. u168이 두 사건을 숨기거나 중요도를 결정하지 않는다.

story_id는 occurrence ID와 다르다. `StoryIdentityHint(story_key_hash, entity_ids, event_kind, explicit_thread_refs, confidence: explicit|unlinked)`만 u170에 전달한다. 동일 회사·같은 뉴스 주제만으로 story key를 발급하지 않는다. 단일 standalone occurrence의 보수적 story key는 event_id에서 결정한다. 장기 story의 lifecycle/retention은 u170 소유다.

### E168-4. remote hash-only ledger

v3 path는 `archive/_meta/event_identity_v3/{segment}.json`이다. legacy `archive/_meta/event_receipts.json`과 다르다. canonical type `CanonicalEventLedger(schema_version=3, segment, records)`와 `CanonicalEventReceipt`는 models에 둔다. receipt 필드: event_id, event_key_hash, occurrence_key_hash, canonical_tuple_hash, occurrence_aliases, entity_ids, event_kind, document_aliases, revision_hashes, cumulative_fact_hashes, fact_slots, supersession_pairs, first_published_at, last_evidence_at. source text/value/display_label/URL/private chunk/secret은 저장하지 않는다.

`OccurrenceAlias(key_hash: Digest, basis: official_key|explicit_cross_reference|raw_document, stage: OccurrenceStage)`는 같은 models 파일의 frozen hash-only DTO다. receipt의 canonical_tuple_hash는 `(kind,ordered actor IDs,action_key_hash,ordered object IDs,stage)`의 versioned digest다. alias match 후 이 tuple과의 양립성을 검증하고 같은 공식 key의 상충 action/actor/object/stage를 conflict로 반환한다. 역할을 합친 entity_ids만으로 판정하지 않는다. receipt의 occurrence_aliases는 최대 32개이며 stable sort/unique로 보존한다. 새 공식/cross-reference key가 같은 occurrence임을 source가 확인하면 최초 event_id를 유지하고 alias를 추가한다. 다음 run은 현재 key를 모든 retained aliases와 대조한다. alias 충돌·다중 remote ID match는 conflict이며 임의 ID를 선택하지 않는다. alias-only provenance 변화는 material_update·fact delta·last_evidence_at 갱신이 아니며 실제 terminal occurrence가 발행된 transaction 안에서만 저장한다. 상한 초과를 조용히 잘라내지 않는다.

2026-10-10 구현 검토에서 hash-only `FactSlotReceipt(slot_key_hash,fact_hash,status)`를 추가했다. slot은 CanonicalFact에서 value만 제외한 tuple의 digest이며 모든 cumulative fact hash의 slot membership을 보존한다. 이전 actual과 같은 slot의 다른 값은 명시적 correction 없이 conflict/novelty unknown이다. occurrence의 period discriminator는 source-owned EventTimeContext.reference_period를 사용하여 선택된 fact 부분집합 변화가 ID를 바꾸지 않는다.

30일 rolling·segment당 최대5000records·serialized1MiB는 C3 기본값이다. 단순 입력 재등장·preview·shadow로 last_evidence_at을 연장하지 않는다. last_evidence_at은 terminal surviving occurrence가 source-backed 새 delta로 실제 봉인·remote confirmed된 시각이다. first publication의 new도 최초 evidence로 기록한다. 사실 집합은 retained occurrence 안에서 누적하며 명시적 supersession은 삭제 대신 hash pair로 보존한다. 오래된 사실이 다시 등장해도 new delta가 되지 않는다.

전용 `EventIdentityBaseline(baseline_sha, metadata_hash, metadata_paths, availability: available|unavailable, segment_receipts)`를 동일 run의 fixed remote SHA에서 읽는다. read/fetch deadline은 기존 remote owner의20초 총량을 공유하며 segment당 새 fetch를 만들지 않는다. missing file in a valid remote tree는 available empty bootstrap, unreadable/malformed/over-budget ledger는 unavailable다. local dirty 파일/private pending receipt를 baseline으로 읽지 않는다.

serialization은 exact UTF-8 bytes·stable ordering이다. TTL 이후에도 overflow면 새 publication metadata를 잘라내거나 oldest를 무조건 제거하지 않고 `identity.ledger_budget_exhausted`로 publication preparation을 명시 실패시킨다. bound 초과 진단은 raw content를 포함하지 않는다. lookup/comparison에서 cap 때문에 이력을 완전히 확인하지 못한 경우 u167 support를 limited/history-unavailable, novelty를 unknown으로 표시하고 완전 history로 취급하지 않는다. sealed survivors만 receipt를 제안하며 omitted/trust-blocked event는 delta/history refresh0이다.

기존 `PublicationRequest`/`PublishReceipt`/CAS는 재사용한다. u168 metadata paths는 schema3가 실제 생성되는 segment paths만 포함한다. u170 story/news cursor와 같은 publication에 결합될 때 orchestrator가 전체 metadata path 집합의 hash를 **같은 baseline SHA**로 계산하고 한 request/한 transaction에 전달한다. commit/push 이후 response 유실은 remote ancestry/content 확인으로 판단한다. outcome_unknown을 available 새 baseline으로 승격하지 않는다.

## 3. 순수 API와 실행 순서

`normalize_entity_bindings(context_documents, alias_proposals, approved_registry) -> tuple[EntityBinding,...]`, `normalize_fact_bindings(context_documents, proposals, entities) -> tuple[FactBinding,...]`, `resolve_event_identity(proposal, entities, facts, baseline, clock) -> IdentityMatchResult`, `compare_event_facts(identity, current_facts, baseline, *, corrections=(), documents=(), prior_fact_bindings=()) -> EventFactDelta`를 `briefing/event_identity.py`가 소유한다. clock/registry/context/baseline을 인자로 받으며 I/O, network, env, LLM 호출이 없다.

orchestrator는 fixed baseline → u167 evidence preparation → Stage1 source-linked proposals → 순수 정규화/identity/delta → u169 editorial plan 순서로 연결한다. Stage2가 고정 ID/fact/ref를 설명한다. finalizer E5 survivor receipt → combined transaction → remote-confirmed publication 이후에만 다음 실행의 history가 된다. budget·source quality·rendering·사람 semantic scoring은 각 공통 owner에 남긴다.

## 4. NFR와 폐기/호환

Functional Design REQUIRED: 이름/발표 단계/중복/수정/novelty의 도메인 semantics가 바뀐다. NFR Requirements REQUIRED: 7→30일 remote history, per-segment ledger, CAS composition, bounds 및 privacy를 변경한다. 기존 NFR-001/002/003/004/005/006/007와 R13, DEBT-090을 적용한다. 추가 LLM 단계/HTTP/API/DB/secret0이다. 성능은 5000records/1MiB/96candidate fixture를 실제 측정해야 하며 측정 없이 통과로 쓰지 않는다.

schema2 원문 tuple hash·문자열 novelty·7일 receipt는 legacy owner에만 남긴다. schema3에서는 호출하지 않는다. migration은 기존7일 ledger를 명시적 replay input adapter로만 읽어 old IDs/hashes/provenance를 점검한다. v2 해시에서 canonical facts, display alias, source body, 사건 날짜, story state를 복원하지 않는다. schema3 initial live baseline은 v3 missing ledger의 empty available bootstrap이다. 기존 archive/URLs/legacy receipt 파일은 고치지 않는다.

alias·duplicate·fact-delta·ledger negative matrix와 AC는 [code-generation plan](../plans/u168-canonical-event-identity-and-fact-delta-code-generation-plan.md)에 있다. 이 문서 작성은 구현 시작·migration 실행·production activation을 뜻하지 않는다.

구현의 explicit correction은 current source에서 다시 결속한 before/after fact bindings, 같은 occurrence의 refs, 주체·지표·이전/새 값을 함께 말하는 명시 정정 claim을 요구한다. hash-only prior receipt에서 원문 값을 복원하지 않는다. 승인 registry 주체의 correction 등 아직 제공하지 못하는 binding은 conservative rejection이며 native integration 이전 미완료 범위로 남긴다.

최종 foundation 검증: numeric metadata metric/unit/period 성분은 각각의 source-owned 필드와 값에 결속한다. correction은 before/after의 동일 canonical slot과 source의 긍정적인 정정 문장 fullmatch를 요구하며 부정문과 다른 metric 대체를 거절한다. 여러 actor/object는 개별 entity binding 후 동일 ID의 provenance를 합친다. 위 수정은 독립 검토의 이전 재현을 모두 거절/보존하는 것으로 확인했다.

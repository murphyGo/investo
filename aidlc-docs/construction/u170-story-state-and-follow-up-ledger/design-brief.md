# Functional Design Brief: u170 story-state-and-follow-up-ledger

**Date**: 2026-10-10
**Status**: 문서 초안 작성; Functional Design/NFR 승인 미기록; 구현 0/8; 운영 미적용.
**Dependencies**: u168 canonical-event-identity-and-fact-delta, u169 event-first-document-and-finalization.
**Normative contracts**: [event-news-v3/contracts.md C3/C4/C5/C6/C7](../event-news-v3/contracts.md). 공통 policy·renderer·finalizer·budget 정의는 해당 owner를 따른다.

## 1. 목적과 실제 현재 경로

사건의 재등장과 사건의 해결을 구별한다. 독자는 이전 확인 상태, 오늘 검증된 변화, 남은 질문, 다음 확인 근거를 읽을 수 있어야 한다. 시간 경과·회사명 재등장으로 완료를 선언하지 않는다. 숫자가 없는 정책·협상·서비스 사건도 출처 있는 상태 변화를 추적한다.

현재 `src/investo/briefing/carryover_parser.py:412-449`는 title/summary/metadata의 topic substring 또는 ticker 재등장만으로 resolved를 표시할 수 있다. `src/investo/models/carryover.py:78-102`의 topic/date 상태는 canonical event ID와 연결되지 않는다. `src/investo/orchestrator/pipeline.py:3315-3339`는 archive 기반 carryover를 native candidates에서 구성한다. 신규 event watchpoint는 facts/meaning/source를 검증하지만 source-backed scheduled fact가 없으면 event-kind별 일반 다음 확인 문장을 사용한다. `src/investo/publisher/event_watchpoints.py:38-48,94-168`.

u170은 v3에서 이 추론을 폐기한다. u168의 occurrence/fact delta와 u167의 follow-up chunks를 소비하여 source-backed state proposal을 만든다. u169가 독자 문서의 FollowUpEntry를 소유하고 u144 finalizer가 실제 survivor를 봉인한다. 공개 story ledger는 봉인된 reader state만 갱신한다.

## 2. Canonical owners

| 경로 | 책임 |
|---|---|
| `src/investo/models/event_story.py` (u168 foundation 재사용) | u168이 먼저 전체 shared frozen DTO 선언; u170은 이 타입으로 전이 규칙을 구현하며 타입을 재선언하지 않음 |
| `src/investo/briefing/event_story.py` (신규) | pure linking·transition table·state reducer·follow-up proposal selection |
| `src/investo/orchestrator/event_story.py` (신규) | same fixed remote baseline에서 read, exact-byte preparation·retention, publication receipt 연계 |
| `src/investo/briefing/generation_contract.py`, `src/investo/orchestrator/pipeline.py` | 기존 Stage1/Stage2와 draft/sealed/transaction에 typed input/output 연결 |
| `src/investo/publisher/event_watchpoints.py` (기존 확장) | u162 tagged event family의 v3 NextCheck input adapter; 기존 numeric family 보존 |
| `src/investo/models/event_document.py`, `src/investo/publisher/public_document.py` 및 u169 renderer | u169 소유; FollowUpEntry 소비·pre-seal survivor reconciliation·StoryPublicationDelta 생성/봉인 hook만 통합 |

models는 publisher/briefing/orchestrator를 import하지 않는다. briefing은 publisher를 호출하지 않는다. publisher는 event_story models와 기존 neutral validator만 사용한다. reducer를 publisher에서 import해 두 번째 state owner를 만들지 않는다. 현재 u144의 finalizer·PublishReceipt·CAS·Git writer를 재사용한다.

## 3. 고정 모델 계약

모든 DTO는 frozen/extra-forbid이며 null과 unknown을 구분한다. ID/digest는 u168의 source-backed IDs와 기존 Digest/EventId를 쓴다. 아래는 미래 구현 계약으로 현재 존재하는 타입을 주장하지 않는다. 의존 순서는 u168→u169→u170이다. `models/event_story.py`의 아래 shared frozen DTO 선언 전체는 u168 foundation scope이며 state reducer/ledger/render는 없다. u169는 typed StoryRecord/StoryStateProposal/StoryPublicationDelta를 독립적으로 검증한다. 실제 delta tuple은 u170 통합 전까지 empty다. u170은 타입을 재선언하지 않고 semantics/reducer/I/O를 구현한다.

### S170-1. Public StoryRecord와 private proposal

`StoryState = announced|pending|confirmed|implemented|resolved|cancelled|unknown`. `StoryDisposition = active|archived_unknown|closed`다. archived_unknown은 state에 새 성공 상태를 추가하는 것이 아니다.

`StoryRecord(story_id: Digest, segment: MarketSegment, event_ids: tuple[EventId,...], latest_state: StoryState, verified_delta: VerifiedStoryDelta|None, open_question: ObservationQuestion|None, next_check: NextCheck|None, resolution_evidence: tuple[SealedStorySourceRef,...], updated_at: datetime, source_refs: tuple[SealedStorySourceRef,...], kind: EventKind, disposition: StoryDisposition, closed_at: datetime|None, last_evidence_at: datetime, state_time: StoryTransitionTime, related_story_ids: tuple[Digest,...])`가 canonical reader state다. related_story_ids는 source-backed 명시 관계만 최대4개로 보존한다. event_ids는 stable order/unique 최대128개, source_refs 최대64개, 각 source receipt의 verified href 최대2000자다. 상한 때문에 새 occurrence가 조용히 유실되면 안 되며 publication preparation은 `story.record_budget_exhausted`로 명시 실패한다.

`VerifiedStoryDelta(fact_ids: tuple[Digest,...], delta_hash: Digest, reader_text: str, source_refs)`는 이미 봉인된 독자용 사실 delta다. reader_text 최대240자, fact IDs 최대8개, 원문 chunk text는 넣지 않는다. 단순 “새 기사 등장”을 verified_delta로 만들지 않는다. 원문 refs의 결과 설명·status/period/unit은 u168의 사실 binding에 결속한다.

`ObservationQuestion(question_id: Digest, kind: release_result|decision_outcome|implementation_status|agreement_outcome|service_status|correction_resolution|source_confirmation, text: str, subject_ids: tuple[Digest,...], resolution_target: ResolutionTarget, source_refs)`는 최대180자의 구체적인 미해결 확인 질문이다. refs는 현재 source-backed open issue/기대 조건에 연결한다. 일반 `후속 발표를 확인`만으로 새 질문·예정일을 발급하지 않는다. 명시된 해결 조건을 못 확인하면 state와 question을 유지한다.

`ResolutionTarget(kind: same_occurrence|linked_release_result, occurrence_id: EventId|None, thread_key_hash: Digest|None, subject_ids: tuple[Digest,...], period: str|None, required_metric_keys: tuple[Digest,...], expected_status: actual|scheduled|quoted_opinion, source_refs)`는 u168 foundation의 frozen 공유 DTO다. 일반 질문은 동일 occurrence를 대상으로 한다. release_result는 source-backed release/thread key·issuer·period·필수 metric과 actual status를 대상으로 하며 scheduled와 actual의 서로 다른 occurrence IDs를 명시적으로 같은 story에 연결한다. source가 그 관계를 확인하지 못하면 resolved하지 않는다. 날짜·회사명·주제만의 일치는 resolution evidence가 아니다.

u168 foundation이 선행 정의한 `SealedStorySourceRef(document_id, revision_id, chunk_id, start, end, ref_sha256, source_href)`를 재사용한다. public ledger에서는 **봉인된 독자 state/claim에 이미 쓰인** ContextRef의 hash/offset·검증 locator projection이다. pre-seal proposal에는 same-run validated context에서 이 shape를 임시로 만들 수 있지만 type 이름만으로 sealed authority를 갖지 않으며 E5가 원문 결속·survivor 사용·locator를 검증해야 한다. source_href와 IDs/hash/span만 보존하고 raw EvidenceChunk.text, 원문 quote/private fixture/secret은 저장하지 않는다. 모델이 생성한 source URL은 사용할 수 없다. receipts는 공개 archive의 immutable provenance와 함께 해석되며 과거 raw buffer를 ledger만으로 재구성하지 않는다.

`StoryObservation(story_hint, event_id, event_kind, fact_delta, transition_proposal, question_proposal, next_check_proposal, context_refs, observation_clock)`는 private same-run 입력이다. `StoryTransitionProposal(signal, proposed_state, evidence_refs, occurrence_ids, resolution_fact_ids, transition_time)`의 IDs/refs/time은 parent가 검증한다. LLM은 evidence spans와 source claim을 제안할 수 있지만 state/story ID를 승인하지 못한다.

`StoryStateProposal(story_id, segment, prior_record_hash: Digest|None, next_record: StoryRecord, next_record_hash: Digest, event_ids, fact_ids, evidence_refs: tuple[ContextRef,...], observed_clock)`는 reducer가 parent-owned로 만든 pre-seal frozen proposal이다. generation의 source spans·next_record의 reader text·hash를 결속한다. LLM Stage2는 이 record의 자유 사본을 발급하지 않는다. u169 finalizer는 이 타입을 입력받아 실제 survivor의 reader fields·facts·refs·source locator를 검증하고 matching StoryPublicationDelta를 봉인한다.

### S170-2. 시각과 next check

`StoryTransitionTime(value: datetime|date|None, precision: exact|date|unknown, evidence_refs: tuple[SealedStorySourceRef,...])`는 public source 상태 시점이다. private proposal은 같은 value/precision과 `tuple[ContextRef,...]`를 갖는 `StoryTransitionTimeDraft`를 사용한다. 두 타입은 같은 canonical models 파일에 고정하고 finalizer가 source refs를 검증해 public projection한다. exact는 timezone-aware UTC datetime, date는 source date 그대로, unknown은 null/ref 없음이다. source가 date-only면 UTC midnight datetime으로 바꾸지 않는다. `StoryTransitionProposal.transition_time`은 Draft, `StoryRecord.state_time/NextCheck.scheduled_time`은 public 타입이다.

updated_at/last_evidence_at/closed_at과 publication delta의 observed_clock는 run/proposal/봉인에 사용한 고정 timezone-aware UTC clock이다. 이 운영 시각을 source 사건 시각으로 표시하지 않는다. ledger retention은 운영 clock 기준으로 계산하고 reader의 `기준 시점`은 StoryTransitionTime precision을 따른다.

`NextCheck(kind: scheduled_fact|observation_question, text: str, fact_id: Digest|None, question_id: Digest|None, scheduled_time: StoryTransitionTime|None, source_refs)`는 최대240자다. scheduled_fact는 scheduled 상태의 source-backed fact ID, exact/date source time, 해당 refs가 필수다. 시간 미상으로 scheduled_fact를 만들지 않는다. observation_question은 구체적인 question ID/text와 근거를 갖지만 예정일·numeric threshold를 발명하지 않는다. company/ticker/price reference만으로 next check의 현재 상태를 만들지 않는다.

기존 `NumericWatchpoint`는 u152 numeric owner에서 유지한다. 기존 `EventWatchpoint`의 tagged kind도 그대로이며 v3는 NextCheck를 입력 adapter로 소비한다. numeric row를 event kind로 바꾸어 검증을 우회하지 않는다. u169의 전체 문서에서 FollowUpEntry는 최대3개다. v2 u162의 mixed 최대2/numeric-only 최대6/fallback2 contract는 별도 legacy 경로에서 그대로 유지한다. v3는 같은 next check를 별도 §⑥ 카드와 FollowUpEntry로 두 번 렌더링하지 않는다.

### S170-3. Story identity와 linking

u168의 explicit story hint, source가 확인한 공식 thread/case/release/계약 ID 또는 exact source cross-reference만 기존 story와 결속한다. actor/company/ticker/topic/date의 일치만으로 서로 다른 정책·제품·기간을 같은 story에 넣지 않는다. explicit link가 없으면 event_id에서 standalone story_id를 결정하고 `unlinked`로 계측한다. uncertain_duplicate event를 강제로 같은 story에 넣지 않는다.

resolved/cancelled closed story를 회사명 재등장으로 재개하지 않는다. source가 새 결정/새 협상/재개를 명시해도 원래 closed 기록은 immutable하게 보존하고 별도 story_id+`related_story_id` hash relationship을 만든다. 동일 source가 기존 closure를 명시적으로 정정한 경우는 correction evidence를 갖춘 conflict/correction review 결과로 다루며 조용한 state 회귀를 금지한다.

## 4. transition table과 도메인 규칙

`StoryTransitionSignal = announcement|pending_confirmation|outcome_confirmed|implementation_verified|resolution_verified|cancellation_verified|evidence_conflict|no_new_evidence`의 닫힌 집합이다. 각 signal은 source의 현재 claim/fact/ref를 요구한다. pending_confirmation은 단지 날짜가 미래라는 이유가 아니라 source가 미결/대기/조건부 상태를 명시할 때만 가능하다.

| Event family | 허용 evidence와 주 흐름 | 금지하는 shortcut |
|---|---|---|
| monetary_policy / regulation | 결정·법안·규정의 source announcement → source 미결 pending → 공식 의결/결정 confirmed → source 시행 implemented → 명시적 완료/정해진 question 해소 resolved; 철회 cancelled | 연설에서 결정 추정, 유효일 도래만으로 시행, 의회·기관 이름만으로 법안 통과 |
| geopolitical / corporate_action | source 발표/협상 announced 또는 pending → 합의/결정 confirmed → 실제 이행 implemented → 명시적 종료·해소 resolved; 결렬/철회 cancelled | 당사자 재등장/주가반응/기사수로 합의·종전·M&A 완료 |
| product_service / market_structure | 발표 announced → 출시/복구 준비 pending → 공식 제공/운영 확인 confirmed → 실제 개시/복구 implemented → 기존 장애/개시 question 해소 resolved; 취소 cancelled | 출시 예정일 경과/앱 이름 재등장으로 service live, 신규 제품을 기존 제품에 병합 |
| earnings_result / macro_release | source 일정 announced/pending → 해당 기간 actual 결과 confirmed → 기존 release-result question에 source-backed linked release/thread·issuer·period·필수 actual 답이 확인되면 resolved; 취소/연기 철회 cancelled | forecast를 actual로 전환, 지표 이름/회사명만 보고 실적 공개 완료 |
| public_statement | source quoted statement announced/confirmed; 별도의 후속 결정 질문이 있으면 pending → 그 결정의 명시 근거로 confirmed/resolved | 발언을 실제 정책/행동 implemented로 승격 |

허용 edge는 same state 유지, unknown→source가 확인한 비terminal 상태, announced→pending/confirmed/implemented/resolved/cancelled, pending→confirmed/implemented/resolved/cancelled, confirmed→implemented/resolved/cancelled, implemented→resolved/cancelled다. skip-stage edge는 **건너뛴 상태를 발명한다는 뜻이 아니며**, 도착 상태를 source가 직접 확인하고 family table 조건을 충족할 때만 허용한다. announced 상태에서 actual result가 source로 확인되면 confirmed로 직접 갈 수 있다. closed 상태는 immutable하다.

새 근거가 없으면 최신 state/question/last_evidence_at을 유지한다. 문서 revision·같은 알려진 fact의 paraphrase·같은 회사명은 no_new_evidence다. fact delta가0인 동일 event 재보도는 headline promotion0이다. 새로운 source가 명시 상태 claim을 처음 검증하는 경우 해당 transition의 evidence hash/ref가 새로워야 한다. 이때 headline이 아닌 follow-up state로 설명할 수 있으며 source 대체만으로 confidence/state를 올리지 않는다.

state 충돌에서는 기존 확인 상태를 unknown으로 덮어쓰지 않는다. `StoryTransitionResult(record, disposition: applied|unchanged|limited|conflict, reason_code, proposed_delta)`를 반환하고 conflict/불확실성은 reader support vector에 별도 표시한다. current state를 조용히 낮추거나 해당 hard finding을 구조 변경으로 없애지 않는다. explicit source correction도 established history를 지우지 않고 correction fact/ref를 보존한다.

resolved는 source가 완결/종료/취소 아님을 직접 확인하거나, 미리 명시한 open question의 해결 조건을 ResolutionTarget의 occurrence 또는 explicit linked release/thread·issuer·period·status·metric 조건을 필수 facts가 충족할 때만 발급한다. resolution_fact_ids·resolution_evidence가 필수다. cancelled는 source의 철회/취소/결렬 claim이 필수다. TTL·주말·예정일경과·조회실패는 둘 다 아니다.

## 5. sealed survivor 업데이트와 remote ledger

경로 `archive/_meta/event_stories_v3.json`, type `StoryLedger(schema_version=3, records: tuple[StoryRecord,...])`. 진행 story는 segment당 최대200개, 전체 serialized UTF-8는5MiB, 본문 follow-up은3개다. active overflow 시 마지막 업데이트 순으로 unseen story를 잘라내지 않고 `story.ledger_budget_exhausted`로 publication preparation을 명시 실패시킨다. record/event/ref bound도 동일 원칙이다.

180일간 마지막 새 근거가 없는 active record는 `disposition=archived_unknown`으로 active view에서 제외한다. latest_state는 유지하며 resolved로 세지 않는다. archived record를 포함한 ledger가5MiB를 넘으면 명시 실패하며 별도 영구 archive backfill을 만들지 않는다. closed는 resolved/cancelled다. closed_at은 terminal proposal/seal에 사용한 고정 observed_clock이며 remote confirmation 후에만 retention authority를 갖는다. 실제 push confirmation 시각은 기존 PublishReceipt에 별도로 기록한다. 확정된 closed_at 이후 90일이 지나면 active ledger에서 제거할 수 있다. 이미 발행된 immutable archive는 영구 이력이다. no-new-evidence로 TTL/closed retention을 연장하지 않는다.

`StoryBaseline(baseline_sha, metadata_hash, metadata_paths, records, availability: available|unavailable)`는 u168/news의 **동일 fixed remote SHA**로 읽는다. 별도 git fetch를 만들지 않는다. missing file은 available empty, invalid/read failure/5MiB 초과는 unavailable다. 불확실한 baseline으로 old story를 새 story처럼 확정하지 않는다. pure proposals는 limitation으로 생성 가능하지만 active publication preparation은 기존 CAS owner의 known-baseline 조건을 충족해야 한다.

u168 foundation이 정의한 `StoryPublicationDelta(story_id, segment, prior_state: StoryState|None, next_state: StoryState, event_ids: tuple[EventId,...], fact_ids: tuple[Digest,...], prior_record_hash: Digest|None, next_record: StoryRecord, next_record_hash: Digest, source_receipts: tuple[SealedStorySourceRef,...], observed_clock: datetime, disposition: active|archived_unknown|closed)`를 재사용한다. **u169/u144가 E5 seal 과정에서 생성하는 survivor update DTO**이며 typed next_record로 reader fields를 직접 검증한다. 전체 타입이 u168 foundation에 있으므로 u169의 컴파일이 u170 reducer/ledger에 의존하지 않는다. 모델 owner는 `models/event_story.py`, 생성/terminal검증/seal owner는 기존 finalizer다. 다른 finalizer나 orchestrator의 post-seal rewrite를 만들지 않는다. observed_clock는 UTC exact 운영 시각, next_record.state_time은 source exact/date/unknown을 별도로 보존한다.

E5 결과가 `tuple[StoryPublicationDelta,...]`를 직접 제공한다. pre-seal StoryStateProposal의 typed next_record와 deterministic canonical JSON hash를 next_record_hash에 결속한다. 이 record의 reader fields는 실제 article/FollowUpEntry의 살아남은 claim·fact/ref·region과 일치해야 한다. prior_record_hash는 fixed baseline record의 hash다. u169 finalizer가 typed record를 검증하는 기존 hook에 u170 proposal을 연결하며 별도 finalize owner가 되지 않는다. omitted/trust-blocked event에 의존한 transition은 delta에 포함하지 않는다. **문서에서 보이지 않은 수집/LLM state proposal은 ledger update0**이다. 최대3개 follow-up 밖에서 아직 발행되지 않은 transition은 pending private observation에 머물며 next run의 committed baseline이 아니다. fresh article의 reader state가 transition을 명시·검증한 경우 그 article에서도 sealed delta를 파생할 수 있다.

orchestrator는 sealed delta와 baseline의 prior hash/state membership을 확인한다. delta의 typed next_record가 same-run proposal/hash와 exact match하는 경우만 해당 frozen record에서 exact bytes를 준비하고 u168 identity receipts/news cursor와 같은 metadata path 집합·baseline hash·한 PublicationRequest로 기존 transaction에 전달한다. record를 ledger write 직전에 다시 생성하거나 수정하지 않는다. remote-confirmed 이후에만 다음 run의 history가 된다. concurrent writer 충돌 시 최신 branch의 story를 보지 않은 reducer 결과를 덮어쓰거나 임의 rebase하지 않는다. pre-commit rollback·post-commit/push-response loss·outcome_unknown은 기존 publish owner의 receipt 정책을 따른다.

TTL/90일 retention-only housekeeping은 same remote baseline과 실제 active-schema3 publication의 metadata transaction 안에서만 수행한다. invisible **semantic transition**을 쓰지 않으며 housekeeping으로 latest_state/last_evidence_at을 바꾸지 않는다. preview/shadow/off는 remote ledger/production file write0이다.

## 6. 함수·순서·폐기

`link_story(observation, baseline) -> StoryLinkResult`, `advance_story(prior, observation, clock) -> StoryTransitionResult`, `select_follow_up_proposals(results, editorial_event_ids, cap=3) -> tuple[StoryRecord,...]`를 `briefing/event_story.py`가 소유한다. 결과는 models DTO다. network/LLM/env/파일/현재시각 읽기0, 모든 clock은 explicit 인자다. 선택은 explicit material update/해결 evidence→source-backed 임박 scheduled check→최근 verified state의 순서와 story_id tie-break로 deterministic하게 처리한다. 새로운 editorial scoring engine을 만들지 않고 u169의 selected event IDs·priority를 소비한다.

실행 순서: fixed baseline → u168 identity/delta → source-backed transition proposals → u169 EditorialPlan/Stage2 → pre-seal follow-up와 article survivor reconciliation → u144 read-only gates/E5 deltas → combined metadata transaction → remote confirmation. summary/surface/meaning/reaction/source qualification/semantic 점수는 각 기존 owner를 재사용한다.

schema3에서 archive §⑥ substring parser·ticker resolution·`_NEXT_CHECK` generic template 기반 성공 state 추론을 호출하지 않는다. schema2의 기존 parser/watchpoints는 rollback/read-only historic parsing에 남긴다. 기존 carryover archive를 scan하여 new story 상태를 자동 채우지 않는다. 과거 근거를 사용할 때는 source-addressed frozen replay 입력으로만 제공한다. legacy strings에서 사실·해결 상태·예정일을 발명하는 migration은 없다.

## 7. Stage/NFR 결정과 완료 증거

Functional Design REQUIRED: 종류별 state table, closure 조건, 구체적 next check, archived disposition과 publication-visible state라는 신규 제품 도메인이다. NFR Requirements REQUIRED:180일/90일/200records/5MiB remote reader-state ledger·CAS composition·public/private provenance·retention이 바뀐다. 기존 NFR-001/002/003/004/005/006/007, R13, DEBT-090 적용. 추가 LLM/HTTP/DB/secret0이다.

상한/복잡도는 실제200active/5MiB·private96candidate·본문3followup fixture에서 bytes/time을 측정한다. 성능·semantic acceptance·live activation을 문서나 regression green으로 선언하지 않는다. AC·negative cases·정확한 명령은 [code-generation plan](../plans/u170-story-state-and-follow-up-ledger-code-generation-plan.md)에 있다. 이 문서는 implementation0의 draft이며 activation을 승인하지 않는다.

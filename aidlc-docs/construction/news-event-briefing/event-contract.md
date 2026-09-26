# 공통 사건 데이터 계약 (Proposed)

Owner: u157. Consumer: u158/u159/u161/u162; u160은 별도 NewsObservationWindow를 제공하고 E11의 발행 확인 기반을 재사용한다. 공통 DTO는 `src/investo/models/events.py`에 두고 형제 unit 직접 import를 추가하지 않는다. `NormalizedItem.category`의 기존5값을 유지한다.

## E1 EvidenceDocument / EvidenceRef

- `document_id`: SHA256(source_name + canonical_url 또는 원본title+published_at); URL은 fragment/추적용 utm_*만 제거하고 의미있는 query는 유지한다.
- `revision_id`: SHA256(normalized title+summary+approved detail excerpt). 실제 전송 buffer를 절단하면 revision을 다시 계산하고 `origin_revision_id`에 source revision을 보존한다. refs는 전송 revision, novelty/receipt는 source revision을 사용하여 입력 예산 변화가 새 사건을 만들지 않게 한다. URL이 같은 수정기사는 같은document_id의 다른 revision이다.
- `source_name`, `url|null`, `published_at`(tz-aware UTC), `received_at`(run 고정 시각), `event_time|null`, `event_time_basis=source_exact|source_date|unknown`, `source_tier`, `source_status`.
- `title`, `summary`, `detail_excerpt`는 Stage1에 실제 전달한 정규화된 문자열 buffer다. `EvidenceRef(document_id,revision_id,field,start,end)`는 해당buffer의 Python code-point offsets를 참조한다. 원문과 일치하는 비공백 span, 1~240자만 허용한다. 파싱 후 parent가 quote를 재구성하며 모델이 URL/quote를 새로 만들지 않는다.
- 출처에서 사건시각을 주지 않으면 null이다. 보도시각을 사건시각으로 복사하지 않는다. 날짜만 있으면 날짜정밀도이며 임의00시를 실제 사건시각으로 보이지 않는다.
- old monthly data의 source observation period와 fresh release time을 분리한다. 다시 수집한 시각은 새 발표 근거가 아니다. full evidence buffers는 공개 ledger에 저장하지 않는다.

## E2 EventCandidate / identity

`event_id`, `event_kind`, `evidence_refs`(1~3 documents), `actor_refs`, `action_refs`, `object_refs`, `change_facts`(최대4), `timing`, `relation`, `impact`, `novelty`, `evidence_state`, `required_fact_ids`, `selection_reason`.

| 필드 | 닫힌 값과 규칙 |
|---|---|
| event_kind | geopolitical, monetary_policy, macro_release, earnings_result, product_service, public_statement, corporate_action, regulation, market_structure |
| timing | occurred, announced, scheduled, background, unknown |
| relation | direct, linked, background, unrelated; direct/linked는 source span 또는 기존 승인 cause key 필수 |
| impact | systemic, sector, company, context; source span으로 변화·대상 범위를 뒷받침 |
| novelty | new, material_update, repeat, unknown; 과거7일 committed receipt 비교로 보수적으로 판정 |
| evidence_state | supported, detail_limited, conflicting, unsupported |

사건 identity는 문서 identity와 다르다. `event_key=(actor_key, action_predicate, object_key, effective_date_or_official_key)`를 근거 span에서 만든다. actor/object는 검증된 entity ID 또는 exact NFKC/casefold span이다. 한 문서에서 발표한 서로 다른 두 제품은 object가 달라 서로 다른 사건이다. 같은 회사·URL·주제만으로 병합하지 않는다.

부모가 actor/action/object/time 일치를 확인한 경우에만 병합한다. 시점 미상은 동일 문서 안의 동일 사건 tuple 또는 같은 공식 event key 외에는 병합하지 않는다. 판별이 불확실하면 별개 후보와 duplicate-risk로 남긴다. 새로운 사건의 ID는 정규화된 event_key의 SHA256 앞 24자리이며, 시점/공식 key가 없으면 최초 문서 ID를 seed에 추가한다. 충돌한 tuple은 병합하지 않고 identity_conflict로 제외한다.

과거 7일 remote-committed receipt의 canonical event ID와 document aliases를 먼저 조회한다. 근거를 추가하거나 기사 revision이 달라져도 기존 tuple/검증된 공식 key와 일치하면 ID를 유지한다. 공식 자료가 뒤늦게 들어왔다는 이유로 anchor를 바꿔 ID를 다시 만들지 않는다. 같은 URL의 수정 중 action/object/time이 바뀌면 새 사건이다. 기존 macro_event_key는 u59 소유 alias이며 덮어쓰지 않는다.

## E3 EventFact

`fact_id`는 event_id+predicate+span hash. `predicate=decision|result|guidance|launch|statement|agreement|status_change`, `value_text`는 EvidenceRef의 원문에서 추출, `period|null`, `unit|null`, `status=actual|forecast|scheduled|quoted_opinion`.

- 최소한 actor와 action을 근거로 확인해야 supported이다. 미래 일정은 occurred로 바꿀 수 없다.
- required_fact_ids: 정책결정의 결정방향/규모, 실적 실제치와 가이던스, 제품 발표의 출시상태, 발언의 주체/핵심주장처럼 소스에 존재하는 핵심 fact를 지정한다. 소스에 없는 예상치·변화폭은 생성하지 않는다.
- headline-only 기사도 후보가 될 수 있지만 detail_limited로 분류하고 설명완료율 분자에서 제외한다.
- 실제/예상/전기, 발언/사실, 관련성/실제 인과관계를 다른 fact로 보존한다. 충돌한값은 임의 선택하지 않고 conflicting 처리한다.

## E4 Stage1 schema v2 / compatibility

기존 `assignments`, `unassigned`를 유지하고 `schema_version:2`, `events:[EventCandidateDraft]`를 추가한다. segment당 최대12 drafts, 사건당3 documents/4 facts. 기존 item_id는 candidate selection 뒤1..N의 same-run lookup만 허용한다. 잘못된ID·출처span·상태는 거부하고 기존 retry budget 안에서 처리한다. Stage1 stdout 64KiB 상한은 유지한다. Stage1의 추가 detail_excerpt block은 segment당 UTF-8 24KiB로 제한한다. E5의 결정론적 후보 순서로 최대 1200 codepoints씩 배정하고 남은 byte 예산에서 codepoint 경계를 지켜 자른다. 전달하지 못한 detail은 evidence_budget_limited로 계측한다. EvidenceRef는 이렇게 실제 전달한 buffer만 참조한다. title/기존 summary의 현재 상한은 유지한다.

v1 parser는 off/shadow 및 명시적 legacy replay에서만 허용한다. `event_mode=preview|active`의 v2 응답에 events가 누락되면 정상 0건 대신 `event_classification_unavailable`로 기록한다. 기존 retry 한도 소진 시 해당 generation 실패/partial sibling 계약을 따른다. silent v1 downgrade는 금지한다. shadow는 E9대로 v1을 전혀 변경하지 않는다.

## E5 EventSelectionPlan / 예산

Stage1 총 96, 소스당 24, lookahead 12를 유지한다. 기존 macro 최대 12와 공식 crypto-policy 우선 lane을 유지하며 crypto-policy의 별도 global cap을 신설하지 않는다. 모든 lane은 같은 total/per-source/lookahead accounting을 소비한다.

그 다음 news 또는 actual-event metadata 항목에 남은 공간 안에서 최대 24개의 reservation을 적용한다. 이미 보호된 news도 reservation 수에 포함한다. source_name 오름차순 round-robin에서 source당 처음 4개를 배정하고 같은 순서로 반복한다. 소스 안 순서는 published_at 내림차순, document_id, revision_id다. 미래 일정만 있는 항목·registry·변화 없는 price/macro는 reservation을 소비하지 않는다. 보호 lane이 예산을 채우면 reservation이 0일 수 있으며 이를 `reservation_starved`로 계측한다.

active/preview의 모든 lane에서 기존 의미 우선순위 뒤의 tie는 `(-published_at, source_name, document_id, revision_id)`로 고정한다. macro의 기존 priority/date distance는 유지하되 input index tie를 stable key로 바꾼다. 나머지 공간도 stable key 순서다. off/shadow는 기존 ordering을 유지한다. permutation 불변 AC는 결정론적 단계에만 적용하고 LLM의 의미 판단까지 동일하다고 주장하지 않는다.

Stage1 후보 중 eligibility는 relation direct/linked, timing occurred/announced, novelty new/material_update, evidence supported/detail_limited. 발생시점 미상은 `보도 기준` 표시와 관측창 내 published_at이 있을 때만 제한 후보로 허용한다. 정상 baseline에 해당 receipt가 없으면 novelty=new다. baseline 조회 실패로 novelty=unknown이면 evidence_state=detail_limited로 낮추고 novelty 점수 0으로 제한 선정한다. repeat은 새 내용이 없는 한 제외한다.

점수표: impact systemic40/sector25/company15/context0 + novelty new20/update15/repeat0/unknown0 + supported15/limited5 + direct15/linked8 + source official10/other5. 최소45점, 최대5사건; tie는점수→published_at내림→event_id. conflicting/unsupported/unrelated는 제외. 시장 반응이 없어도 중요 정책/신제품/발언은 선정 가능하다. event_kind별 최소할당량 없음.

Stage2 전체 48(crypto 32), section 14(crypto 8)를 유지한다. protected와 grouped를 합한 **실제 evidence rows**를 전체·section에 같은 단위로 센다. 같은 item은 중복 전송하지 않는다. 사건은 최대 3개 documents를 참조할 수 있고 모든 required fact의 근거 rows를 먼저 배정한다. optional rows를 줄인 후에도 count/byte가 초과하면 그 사건을 selection 전에 `budget_deferred`로 제외하고 다음 순위 후보를 검토한다. 같은 근거 row를 공유하는 사건은 row를 한 번만 세되 각각의 fact refs는 보존한다.

선정 사건은 최대 5개이며 event block은 segment당 8KiB다. 전체 64KiB Stage1 응답 상한과 독립적으로 검사한다. required_macro 별도 block은 기존 계약을 유지하고 같은 event/key와 연결한다. selected로 기록한 사건이 prompt에서 탈락하는 것은 결함이다. crypto의 사건 5개×2 rows가 section 8을 초과하는 fixture를 반드시 포함한다.

## E6 Stage2OutputV2 / EventNarrative

출력은 JSON 한개: `schema_version:2`, `sections:{market_summary,sector_flow,indicators_events,notable_tickers,today_watch}`, `events:[EventNarrative]`. 모든기존6섹션은 코드가 조립하고②는 event renderer가 단독 소유한다. selected event_id 순서와 exact set 일치를 검증한다.

EventNarrative는 다음 구조다. 모든 길이는 Unicode codepoints 기준이다.

- `event_id`, `headline`(80), `what_happened`(전체 240), `fact_ids[]`, `source_refs[]`.
- what_happened의 첫 문장은 주체와 핵심 변화를 담은 **80자 이하 완전한 문장**이다. 이후 설명은 후속 문장이다. 이 첫 문장을 conclusion으로 재사용하고 publisher가 다시 요약하지 않는다.
- `meaning={text:str|null, mode:source_reported|conditional|unavailable, evidence_refs:[]}`. text는 최대 180자다. source_reported는 해당 주장 refs가 필수이며 conditional은 사건 근거를 연결하고 조건부 표현을 명시한다. unavailable은 text=null이다.
- `reaction={text:str|null,status:observed|source_reported_no_reaction|unavailable,evidence_refs:[]}`. text는 최대 180자다. observed와 source_reported_no_reaction은 각각 해당 반응 근거가 필수다. unavailable은 text=null이며 **“시장 반응은 확인하지 못했습니다.”**로 렌더한다. 자료가 없다고 실제 무반응을 단정하지 않는다.

u158의 사건 validator가 event별 허용 fact/entity/evidence 집합을 검사한다. factual numeric/entity slots는 허용 fact ID와 actor/object refs로 구성하며 actual/forecast/period 역할을 보존한다. URL은 모델 문자열로 받지 않고 EvidenceRef lookup으로만 렌더한다. `event.fact_unsupported`, `event.entity_unsupported`, `event.evidence_invalid`를 닫힌 hard finding으로 추가하며 B8에서 삭제 전 보존한다. 기존 hard gates도 그대로 적용한다. 자유 문장의 새로운 주장을 기존 gate가 전부 검증한다는 보장은 하지 않는다. 주석된 평가셋에서 별도로 검증한다.

renderer가 required_fact_ids의 근거값을 `결정/실적/발표 내용` 줄에 보존한다. 모델이 fact ID만 돌려주고 핵심 내용이 없는 문서는 qualified가 아니다. 공백·generic what은 거부한다. system/user/retry는 동일 schema version을 사용한다. `_stage2_retry_feedback`의 v2 분기는 JSON 객체를 요구하며 v1의 기존 Markdown feedback은 유지한다.

모든선정사건없음은 수집상태에따라 `수집된 근거에서 주요 사건을 선정하지 못했습니다` 또는 `뉴스 수집이 제한되어 중요 사건을 판단하기 어렵습니다` 한문장. 세계에중요뉴스가없다는단정금지. v1/v2는 명시적policy로선택하고형식추론fallback금지. 기존무료CLI provider2종·retry budget을공유하며세번째LLM단계를추가하지않는다.

## E7 EventPublicationReceipt / terminal DTO

GenerationResult의 optional `event_plan=None`과 frozen `event_payload=None`을 통해 orchestrator가 PublicDocumentContext로 전달한다. 구현된 payload는 `EventGenerationPayload(plan, narratives, collection_limited)`이며 plan/narratives를 한 경계로 운반한다. None은 해당 단계 미실행이며, 정상 완료한 0건은 빈 plan/narratives를 가진 payload로 구분한다. 기존 Briefing 필드문자열을최종사실소스로사용하지않는다.

u144 phase-one에서 `<!-- investo:block event:{event_id} -->` owned region을만들고 terminal validation이 실제살아남은block/fact/source를검사한다. ID는보이지않는기존marker관례이며공개설명텍스트/알림에노출하지않는다. generation receipt와 sealed receipt를구분한다.

PublicEventSummary(event_id,headline,fact_summary,coverage)와 PublicNotificationSummary의 `events=()` default를추가할수있다. terminal의 알림 적격 사건 중 기존 순서대로 최대 3개인 ordered subset이다. 각 문장은 최대 180 codepoints의 완전한 문장이고 줄바꿈은 금지한다. terminal 4~5건과 DTO 3건은 정상이다. 반드시 `_derive_public_notification_summary`가 terminal layout에서 유도한다. `conclusion`은 첫 유효 사건 what의 80자 이하 첫 문장이며기존소비자도개선효과를얻는다. notifier는generated evidence/narrative를읽지않으며u156 layout은독립이다.

## E8 trace와 coverage

상태순서: collected→routed→candidate→classified→selected→prompted→generated→finalized→published. 제외사유는 source_unavailable, outside_window, routing_rejected, candidate_cap, low_importance, duplicate, background, evidence_conflict, budget_deferred, classification_unavailable, llm_omitted, detail_limited, finalization_removed, published.

공개quality에는 개수/상태와뉴스관측기간만 저장한다. raw spans/본문/모델출력은 공개git에넣지않는다. private run trace는 hash IDs, stage, reason, source_name만. u159 golden corpus의실제원문은NFR-008/R10의private경계준수,공개테스트에는합성·허용된요약만포함한다.



### 단계별 count와 상태

| 필드 | 0이 가능한 조건 | null 조건 |
|---|---|---|
| collected_candidate_count | 수집 단계가 완료되고 관측 후보가 0 | 수집 미실행/전면 실패 |
| selected_count | 분류·선정이 정상 완료되고 0 | 분류 실패/미실행 |
| prompted_count | prompt 구성 완료, selected 0 | prompt 구성 실패/미실행 |
| terminal_event_count / qualified_event_count / details_limited_count | terminal 검증 완료, 해당 집합 0 | finalizer 미실행/실패 |
| summary_event_count | terminal DTO 유도 완료, 적격 사건 0 | DTO 유도 미실행/실패 |
| omitted_count | selected와 terminal이 모두 알려진 경우의 차이 | 둘 중 하나라도 미집계 |
| unsupported_count | 해당 구조 검사가 완료되고 관측 위반 0 | 검사 미실행/실패 |
| selection_coverage / qualified_coverage | 분모>0이고 분자=0 | selected가 0/null 또는 terminal 미집계 |

주 상태 우선순위는 hard_trust_blocked → classification_unavailable → finalization_unavailable → source_limited → detail_limited → no_qualifying_event → qualified다. 여러 원인은 reasons에 모두 유지한다. 내부 terminal 반영률과 published 집계를 분리한다. bundle published 집계는 remote_confirmed이며 분모가 알려진 segment만 합산하고 excluded_segments를 함께 기록한다. 완전 실패를 0/0=100%로 표시하지 않는다.

## E9 실행 설정과 버전 선택

`INVESTO_EVENT_BRIEFING_MODE=off|shadow|preview|active`, 기본 off다.

| 모드 | 실행 계약 | 공개 쓰기 |
|---|---|---|
| off | 기존 v1 Stage1/2 | 기존 동작 |
| shadow | v1 프롬프트·입력·응답을 그대로 두고 결정론적 source/candidate/window 진단만 관찰한다. v2 annotations를 요청하지 않는다 | 기존 결과 그대로; event receipt/cursor 쓰기 없음 |
| preview | 격리된 비게시 실행에서 v2 Stage1/2 또는 기록 응답을 사용한다. 추가 3번째 LLM 단계 없음 | `.tmp/event-preview/{run_id}`만; archive/git/notify/cursor 쓰기 없음 |
| active | u157/158/159가 함께 구현된 compatibility version 2만 허용 | 기존 공개 transaction 및 E11 |

shadow on/off의 byte 불변 검증은 동일한 기록 v1 응답으로 한다. 별도 live LLM 실행 두 건의 byte 동일성을 주장하지 않는다. shadow는 비간섭·입력 가시성 검증이며 사건 의미 품질은 v2 preview에서 검증한다. preview와 active에는 모든 v2 consumer가 필요하다. 준비되지 않은 조합이나 잘못된 값은 preflight에서 거부한다.

`INVESTO_NEWS_WINDOW_MODE=off|shadow|active`는 u160 소유, 기본 off다. shadow는 주입된/읽기 전용 baseline으로 새 창을 계산만 하고 기존 fetch/window/publication을 유지한다. 실제 새 창 fetch는 비게시 preview/replay 또는 별도 active 단계에서 검증한다. off/shadow/replay/dry-run은 production cursor를 수정하지 않는다.

`INVESTO_EVENT_ENRICHMENT=off|feed|official_body`는 u161 소유, 기본 off다. official_body는 qualification record가 없으면 해당 신규 fetch 0회와 unavailable이다. 설정은 공유 config에서 읽고 leaf module은 환경을 직접 읽지 않는다. watchpoint는 active와 u162 통합 후 사용한다.

## E10 Structured extract와 자유 해석의 경계

required_fact_ids는 모델이 임의로 비워서 통과시키지 못하도록 `event_kind`별로 parent가 재계산한다. monetary_policy는 모든supported decision fact, earnings_result는 모든supported actual/result/guidance fact, product_service는 모든supported launch/status_change fact, public_statement는 actor/action refs와 모든 supported statement fact, 나머지는 모든supported agreement/result/status_change fact를 필수로 한다. 해당종류의핵심fact가하나도없으면 detail_limited다. input source가 headline-only이면 완전설명 fixture의 정답으로 사용할 수 없다.

각 fact는 source span과 값/시점이 같은지 기계적으로 검사한다. 실제문장의 의미적 함의는 이 검사만으로 확정하지 않는다. 잘못된모델 event_kind/impact/required fact 추출은 annotated replay에서검출하고새fixture로남긴다. source-backed라고표현하는것은참조된근거가존재한다는뜻이며세계사실이확정됐다는뜻은아니다.

## E11 수집 근거 전달과 확정 기록

u157은 `NormalizedItem.event_evidence: EvidenceDocument | None = None`을 추가한다. DTO는 models/events 소유이며 items를 역으로 import하지 않는다. 기존 공개 serialization은 새 event_evidence=None 키만 제외하고 기존 nullable 키와 bytes를 유지한다. source는 parsing 시 summary 절단 전 typed evidence를 만들며 SourceCollectionReport.items → CollectStage → GenerationInput.items로 운반한다. 별도 mutable lookup이나 object identity join은 금지한다. document/source/revision을 검증하고 routing된 item과 근거를 함께 전달한다. 없으면 title/기존 summary에서 제한된 EvidenceDocument를 만든다. Stage1의 직렬화 helper만 bounded buffers를 소비하며 item 전체 dump로 본문을 공개하지 않는다.

u157이 `models/publication.py::PublishReceipt`와 기존 publisher/git_ops의 반환 seam을 소유한다. 필드는 run_id, local_sha, remote_ref, baseline_metadata_hash, status=pending|remote_confirmed|definitely_unpublished|outcome_unknown이다. E11은 기존 u113 transaction의 확장이며 별도 publisher를 만들지 않는다. u160은 window metadata만 추가한다.

1. pre-commit 실패: 이 transaction이 바꾼 files/index snapshot만 복원한다.
2. commit 이후 push 실패 또는 응답 불명: immutable pending receipt와 local commit을 보존한다. 파일만 rollback하거나 이미 remote에 없는 것으로 단정하지 않는다.
3. 기존 전체 deadline 안에서 원격 확인을 최대 2회 한다. local commit이 remote tip 또는 ancestor이면 remote_confirmed다. 원격을 성공적으로 읽었지만 commit이 없으면 definitely_unpublished이며 동일 transaction retry가 가능하다. 원격 tip만 전진하고 baseline metadata hash가 같아 허용된 rebase를 수행하면 새 local SHA를 가진 후속 immutable receipt를 만들고 같은 run_id/content hash로 연결한다. 이전 SHA만 검사하여 실패로 오인하지 않는다. 확인 자체가 실패하면 outcome_unknown이며 알림·cursor 성공 판정을 보류한다.
4. fetch/rebase 전후 baseline metadata hash를 비교한다. 원격 cursor/event receipt가 달라졌으면 clean rebase도 stale transaction을 허용하지 않는다. 최신 remote에서 다시 계산하고 force push/max merge는 금지한다. 내용이 같은 기존 transaction의 ancestry 확인이 우선이다.
5. 다음 실행은 remote의 확정 tree만 baseline으로 사용한다. pending 파일은 입력으로 쓰지 않는다. notifier-only 실패는 이미 확정된 publication을 되돌리지 않는다.

`archive/_meta/event_receipts.json`은 최근 7일의 canonical event IDs, actor/action/object/time의 hash key, document aliases/revision/fact hash, selected/published 상태만 보존한다. 원문/span은 저장하지 않는다. sealed survivor만 게시 receipt에 포함하고 같은 archive commit에 기록한다. alias 비교용 keys는 해시로 저장한다. run manifest에 자신의 commit SHA를 넣지 않는다. shadow/preview에는 production receipt를 쓰지 않는다. post-commit reconciliation과 pending receipt는 private 작업 상태에 둔다.

### 2026-09-27 구현 시 확인한 발행 경계

PublicationRequest는 기본 60초의 전체 Git 예산을 소유한다. metadata read/reconcile은 별도 호출당 10초 상한이며 rebase는 남은 총 예산 안에서 cleanup 시간을 예약한다. transaction 밖 staged 파일은 mutation 전에 거부한다. pre-commit 실패·취소는 index와 파일을 복원하며 commit 이후는 보존한다. remote-confirmed 이후 private receipt 저장 실패는 경고로 분리하고 이미 확정된 게시를 되돌리지 않는다. private receipt는 임시 파일의 fsync 후 원자적 exclusive 설치로 기록한다. 기존 모드의 Git 명령·반환값은 유지한다.

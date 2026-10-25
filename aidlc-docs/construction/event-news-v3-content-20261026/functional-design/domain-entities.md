# 근거·본문·평가 타입 계약

전부 frozen typed model로 구현한다. canonical event/fact/entity/time/ref/story 타입은 u167/u168/u170 것을 재사용한다. 자유 `dict[str, Any]`로 별도 진실 원본을 만들지 않는다. 아래는 설계 타입이며 신규 클래스의 존재나 검증 성공을 뜻하지 않는다.

## Private 타입 — models/event_article.py

| 타입 | 필수 필드와 불변조건 |
| --- | --- |
| `EvidencePassage` | passage_id, document_id/revision/hash, original start/end, text, ContextRef tuple, source_role, attribution; exact source substring·offset 검증. source당 6개/6,000자, passage당 1,200자. 240자 ContextRef 여러 개를 연결하되 문맥 passage 전체도 검증기에 전달 |
| `ArticleQuestion` | question_id, event_id, kind, required, applicability_rule_id, evidence_refs, status=answerable/missing/not_applicable; 모델이 required를 바꾸지 못함 |
| `EventEvidencePacket` | event_id, canonical event/facts, required_fact_ids, source documents 최대4, passages, questions 최대6, conflicts, input_manifest_hash, packet_hash; actor/topic만 같은 타 사건 evidence는 제외 |
| `ClaimAtom` | 기존 fact/entity IDs, action/status/polarity/modality, time/period/unit/value, attributed_actor_id; 해당 종류에 필요한 필드가 없으면 invalid. 새 값을 source registry에 자동 등록하지 않음 |
| `SentenceClaim` | claim_id, event_id, sentence_ids, kind=fact/attributed_explanation/conditional_analysis/observation, atoms, source_refs, mechanism/assumption refs; 모든 참조가 실제 transmitted packet 안에 존재 |
| `ArticleComposition` | event_id, narrative, claims 최대24, question_answer_map, packet_hash, policy_hash; headline/lead/digest 포함 모든 factual clause 소유. generation profile과 content version 일치 |
| `ClaimReview` | claim_id, verdict=supported/contradicted/insufficient, evidence refs, reason code; 빠진 claim 또는 추가 ID는 전체 response invalid |
| `ArticleReadiness` | event_id, state, core coverage, required question coverage, source/packet/composition/review gap codes, claim verdicts, draft_hash/packet_hash/policy_hash/review_hash; 인간 점수 field 없음 |
| `ArticleReviewBatch` | exact ordered event IDs, all claim reviews, required question results, reviewed draft hash, validator version, CLI model/version, call ordinal; 평가 대상 hash 불일치는 stale review |

`packet_hash`는 source revision·선택된 passage·facts·질문·직렬화 manifest를 포함한다. 공백 정규화로 원문 offset을 무효화하지 않는다. 문장 IDs는 draft 내부 로컬 ID이고 canonical event/fact ID를 대체하지 않는다. 수정 draft는 새 hash와 새 평가를 갖는다. 체인 오브 소트나 긴 자유 평가 원문은 산출물 요구사항이 아니다.

## Reader 타입 — models/event_document.py

`content_contract_version: Literal[1,2]`를 edition과 각 typed article의 일치 조건으로 추가한다. field 부재는 legacy v3의 version1이다. article_v2는 version2이며 섞인 edition은 invalid다. 문서 schema와 marker는 **3**을 유지한다. 이 private profile은 공개 marker로만 선택하지 않고 typed payload로 판별한다.

`ArticleNarrative(blocks,lead_sentence_id,headline_claim_ids,digest_claim_ids)`가 본문의 유일한 text owner다. `NarrativeBlock(kind=paragraph|bullets|fact_table, sentences|fact_ids)`는 닫힌 union이다. paragraph/bullets는 sentence IDs/text/claim IDs를 담고 fact_table은 검증된 fact IDs만 담는다. 문장 24개·block 8개·본문 3,200자 상한이다. 임의 HTML/Markdown/table string은 금지한다. caption도 sentence claim을 요구한다.

version2의 기존 `what_changed`는 narrative의 lead와 **동일한 text**이며 최대600자다. background/meaning/reaction은 optional typed facets로 필요한 기존 asset/story 검증을 지원하되 원천은 narrative claim이다. 버전1 `display_blocks`와 새 narrative를 동시에 주면 reject한다. version2 renderer는 narrative만 본문에 노출하고 같은 facet을 중복 렌더하지 않는다. headline120/digest140, facts8/event, article5/edition 상한은 유지한다.

`PublicEventView`에는 검증·봉인된 narrative의 reader text/claim IDs/fact IDs와 공개 가능한 source locator만 projection한다. `EvidencePassage.text`, 원문 quote, private model IO, review reason text는 공개하지 않는다. 문장 근거의 공개 locator는 기존 sealed locator DTO를 재사용하고 private ContextRef 전체를 직렬화하지 않는다.

## 영구 이력·compatibility

`PublishedEventEdition`/`PublicEditionView`의 version2는 content contract version과 narrative를 projection hash에 포함한다. **version1의 canonical hash 알고리즘/serialized shape는 그대로 보존**한다. 읽을 때 raw JSON의 version/hash를 먼저 검사하고, v1에 새 default field를 추가한 model_dump를 기존 hash와 대조하지 않는다. v1 serializer는 새 optional 필드를 출력하지 않는다. 실제 과거 sidecar fixtures로 byte/hash round-trip을 검증한다.

새 reader는 v1/v2를 지원한다. 미지원 content version은 `unsupported_schema`로 처리하고 archive 링크로 fallback하며 Markdown을 재파싱해 narrative를 발명하지 않는다. 구형 code rollback의 archive reader가 새 sidecar를 거부하는 상황도 검증하고 old reader에 새 sidecar를 강제 입력하지 않는다. 기존 archive/body/source bytes를 backfill하지 않는다.

알림/home/OG/회고는 같은 terminal event의 digest→headline→기존 availability 순서를 유지한다. 별도 LLM 요약 0회. story advance는 기존 typed proposal과 canonical 사실을 사용하고 기사 문장의 생김새로 새 state를 추론하지 않는다.

## Finalization 검증 증서

검증 결과는 exact draft/packet/policy hash에 결속된 private `ArticleReadiness`다. finalizer가 삭제한 sentence/claim은 terminal coverage에서 뺀다. 남은 문장을 바꾸지 않은 단순 삭제는 기존 sentence 검증 결과를 재사용하되 새 terminal assessment hash를 계산한다. 수정된 text에 이전 supported를 복사하지 않는다. source-supported required claim이 빠지면 readiness 재판정 및 기존 article/digest/asset/story reconciliation을 수행한다.

public seal은 최종 Markdown과 public projection에만 결속한다. private readiness hash/count는 운영 evidence에 보관하되 private raw가 public sidecar를 통해 유출되지 않도록 별도 allowlist serializer를 사용한다.

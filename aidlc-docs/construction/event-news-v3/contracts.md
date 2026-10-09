# Event/news v3 — 공통 계약

**Date**: 2026-10-10. **Status**: 설계 초안; 구현/운영 미적용. **Owner**: u167–u173 공통, 개별 canonical owner는 아래 표. 기존 v2 E1–E11은 기존 출력에서 유지한다.

이 문서는 shared contract의 단일 출처다. 각 유닛 계획은 이 계약을 재정의하지 않는다. 코드형 표기는 구현할 frozen Pydantic/dataclass의 논리 필드이며 현재 존재하는 타입이라는 뜻이 아니다.

## C1. Generation policy와 버전

`EventGenerationPolicy(mode: off|shadow|preview|active, document_schema: 2|3, active_segments: tuple[MarketSegment,...])`는 models에서 소유하고 orchestrator entrypoint에서 한 번 구성한다. 기존 `INVESTO_EVENT_BRIEFING_MODE`를 재사용하고 새 `INVESTO_EVENT_DOCUMENT_SCHEMA`의 기본값은 `2`다. 기존 기본 동작과 현재 reviewed pin은 문서 작성만으로 바뀌지 않는다.

- off/shadow: 기존 공개 bytes/알림/receipt/cursor를 유지한다. v3 shadow는 기존 입력/응답의 결정론적 분석만 하며 새 HTTP/LLM/production ledger 쓰기 0회다.
- preview+schema3: 비게시 entrypoint의 실제 두 단계 호출을 v3 schema로 대체한다. 생성 호출 단계 추가 0개. archive/git/알림/production ledger/cursor 쓰기 0회.
- active+schema3: u172 cutover acceptance를 통과한 market allowlist에만 적용한다. capability는 기본 false다. 실제 reviewed code/policy 판독을 gate로 삼고 사람 점수나 source qualification을 env 문자열만으로 통과시키지 않는다.
- 하나의 시장·한 실행은 한 schema로만 생성한다. 같은 문서에 v2 7섹션과 v3 본문을 동시에 생성/게시하지 않는다. rollback은 이전 reviewed schema2 코드/policy 전체로 복귀한다.

## C2. Evidence와 시간 — u167

기존 `EvidenceDocument`/`EvidenceRef`는 v2용으로 유지한다. v3 canonical owner는 `models/event_context.py`의 `EventContextDocument`, `EvidenceChunk`, `ContextRef`, `EventTimeContext`, `EventSupportVector`다. sources/briefing/publisher가 모델 경계를 공유하며 서로 sibling import하지 않는다.

`EvidenceChunk(chunk_id, role, text, source_locator, text_sha256)`는 private generation buffer다. role은 `identity|fact|background|comparison|meaning|reaction|follow_up`의 닫힌 집합이다. text는 1..1200 codepoints, 문서당 최대4chunk다. 같은 원문에 chunk가 여러 개여도 하나의 document identity다. 원문 parser가 확인한 소스 내 위치/문맥을 locator에 보존하며 생성 모델이 URL·chunk를 발급할 수 없다.

`ContextRef(document_id,revision_id,chunk_id,start,end)`의 span은1..240codepoints이며 정확한 transmitted buffer 범위를 가리킨다. title/summary/detail legacy 입력은 v3 chunk로 결정론적으로 변환한다. 새로운 의미/반응/후속 근거가 기존 actor/action/object/fact의 부분집합일 필요는 없지만 같은 사건의 검증된 문서 집합에 속해야 한다.

`EventTimeContext`는 `occurred_at`, `announced_at`, `published_at`, `received_at`, `reference_period`와 각 값의 `exact|date|unknown` precision 및 source ref를 갖는다. exact는timezone-aware UTC다. unknown은null이다. published/received를occurred/announced로자동복사하지않는다. 사건종류의시각은공식발표내용으로확인한경우에만날짜값으로승격한다.

`EventSupportVector`의 축:

| 필드 | 닫힌 값 | 해석 |
|---|---|---|
| facts | complete / limited / missing | 사건 종류의 필수 사실 충족 |
| time | exact / date / publication_only / unknown | 사건/발표 시각 확실성 |
| novelty | known / unknown | remote-confirmed 비교 이력 이용 가능 |
| locator | complete / missing | 공개 주장에 필요한 출처 locator |
| meaning | source_reported / conditional / unavailable | 의미의 종류와 근거 |
| reaction | observed / source_reported_no_reaction / unavailable | 반응 확인 상태 |

`MeaningContext(text,mode,mechanism,assumptions,refs)`의 mode는 source_reported/conditional/unavailable이다. unavailable은 text/refs가 없고, conditional은 전제와 해당 사실 refs를 가진다. 원문이 주장한 의미와 작성자의 조건부 분석을 분리한다.

`ReactionContext(asset_id,window_start,window_end,observed_at,baseline_ref,value_ref,text,status,attribution,refs)`의 attribution은 source_reported/coincidence_only/unavailable이다. observed는 비교 시각·근거가 있어야 하고 unavailable은 수치 필드가 null이다. 관측 사실만 있을 때 ‘사건 때문에’라는 원인 단정을 생성하지 않는다. date-only는 precision을 유지하고 임의의 장중 시각을 만들지 않는다.

축별 `reason_codes`는 `facts.required_missing|facts.content_shallow|time.event_unknown|history.unavailable|source.locator_missing|meaning.ref_missing|reaction.ref_missing`을 기록한다. 생성 validator 실패는 `field`, `rule_code`, `event_id_hash`, `attempt`만 private bounded diagnostic으로 남기고 공개 text/raw source/secret을 기록하지 않는다.

`ContextFactDraft(subject_refs,predicate_refs,object_refs,metric_refs,value_refs,unit_refs,period_refs,status_refs,value_kind)`의 각 성분은 source-owned ContextRef tuple이다. 숫자 fact는 source-backed metric이 필수다. typed source metadata도 deterministic chunk로 직렬화하여 같은 소유권 검증을 적용한다. 필수 성분 부재는 null과 facts limitation으로 남기고 LLM의 key/value 선언만으로 확인된 사실을 만들지 않는다.

기존 qualified 카운트는 기존 의미를 보존한다. v3는 축별 품질과 사람이 검수한 semantic score를 별도로 보고하며, 날짜 미확인을 설명이 허위인 상태로 바꾸지 않는다. source 제한도 ‘사건 없음’으로 정규화하지 않는다.

## C3. Canonical identity와 fact delta — u168

canonical owner는 `models/event_identity.py`, normalization은 `briefing/event_identity.py`, remote ledger orchestration은 `orchestrator/event_receipts.py`다. source-backed `EntityIdentity(entity_id,source_labels,display_label,alias_refs)`를 공유한다. 원문·display label은 각각 최대 240자이며 승인된 짧은 alias가 없으면 본문에서 긴 원문을 보존한다. headline/digest 상한은 본문 entity의 상한과 독립이다. 임의 번역/약칭은 approved registry 또는 같은 원문의 명시적 alias 근거가 없으면 발급하지 않는다.

`CanonicalFact(subject_id,predicate,object_id,metric_key_hash,value,unit,period,status)`의 status는 actual/forecast/scheduled/quoted_opinion을 유지한다. 단위/기간/상태와 source-backed metric_key_hash는 identity 구성요소다. 숫자 fact는 metric discriminator가 필수이며 매출과 순이익처럼 다른 지표의 같은 값을 합치지 않는다. nonnumeric fact에 metric이 없으면 null을 유지한다. 기계 정규화는UnicodeNFKC/공백과 숫자의 천 단위 separator 제거까지만 허용하며 의미·환산·추론 변환을 하지 않는다. 의미가 불명확하면 raw fact의 보수적 identity를 유지한다.

document identity, 단일 occurrence의 event_id, 장기 thread의 story_id를 구분한다. 서로 다른 결정/제품/발표 단계는 별도 event다. 같음을 확신하지 못하면 합치지 않고 uncertain_duplicate로 계측한다. novelty는 `new|material_update|repeat|unknown`이며 material_update에는 source-backed 사실 delta가 필요하다.

hash-only fact history는30일 rolling, segment당 최대5000 event records/1MiB를 기본 상한으로 한다. 경로는 `archive/_meta/event_identity_v3/{segment}.json`이다. 확정 remote baseline과 publication receipt를 사용하고 원격 확인 실패는 unknown이다. preview/shadow는 쓰지 않는다. 기존7일 ledger migration은 replay 입력으로만 사용하고 새로운 사실/상태를 발명하지 않는다. receipt의 `fact_slots: tuple[FactSlotReceipt,...]`는 `(slot_key_hash,fact_hash,status)`만 보존하며 cumulative_fact_hashes와 membership이 일치한다. slot hash는 CanonicalFact의 value를 제외한 tuple에 결속하여 이전 actual 값과의 충돌을 원문 없이 판별한다. receipt는 공식·cross-reference·raw occurrence key를 hash-only typed alias 집합으로 보존하여 늦게 발견한 공식 근거에도 기존 ID를 유지한다. alias-only 변화는 material delta나 freshness 갱신이 아니다. cap으로 history를 완전히 보유하지 못하면 coverage를 limited/novelty unknown으로 명시하고 조용한 완전 이력으로 취급하지 않는다.

## C4. 전체 문서 모델·생성·렌더링 — u169

canonical owner `models/event_document.py`: `EventEditionDraft`, `EditorialPlan`, `EventArticle`, `EventDigest`, `ContextPanel`, `MarketReferencePanel`, `FollowUpEntry`, `EditionAvailability`.

`EventEditionDraft(schema_version=3,segment,target_date,price_reference_date,price_time_basis,news_window,availability,editorial_plan,articles,digests,follow_ups,context_panels,reference_panels,asset_impacts,disclaimer)`가 유일한 생성 원본이다. ①~⑥ section string을 요구하거나 별도 자유 Markdown 사본을 생성하지 않는다. rendered Markdown은 publisher가 위 모델에서 결정론적으로 파생한다. `asset_impacts`는 생성 모델의 자유 출력이 아니라 u171의 결정론적 matcher가 봉인 전에 제공하는 typed 입력이며, u171 통합 전에는 빈 tuple이다.

신규 v3 본문은 `<!-- investo:edition schema=3 -->` marker를 정확히1개 갖는다. marker와 모델 버전이 일치해야 한다. 과거 문서는 marker를 추가하지 않고 기존 v2 events marker/legacy reader 경로로 읽는다.

`EditionAvailability`는 normal/quiet/source_limited/generation_failed/trust_blocked의 결과 분류다. 생성·봉인 가능한 `EventEditionDraft.availability`와 `PublicEditionView.availability`는 `ContentEditionAvailability = normal|quiet|source_limited`로 제한한다. generation_failed는 기존 E1 `input_absences`와 `SegmentFinalizationOutcome.state=generation_absent`, trust_blocked는 기존 finalizer의 같은 이름 outcome으로 전달한다. 두 실패에는 sealed document·archive·event summary·story delta가 없으며 기존 bundle의 실패 시장 안내/partial/exit 정책을 사용한다. quiet는 정상 관측에서 중요 변화가 0건일 때만 사용하고 실패를 quiet로 바꾸지 않는다. `FollowUpEntry`는related_event_id 또는story_id,현재상태,다음확인,source/timebasis를갖고 source-backed standalone schedule도허용한다. v3총량은최대3개이며u162의기존event/numericfamily검증을재사용한다.

필드의 고정 shape:
- `EventDigest(event_id,fact_ids,text,source_refs)`의 text는완성문장140자다. refs는그event의검증된context에속한다.
- `EventArticle(event_id,actor_ids,object_ids,headline,what_changed,fact_ids,required_fact_ids,field_refs,background,meaning,reaction,support)`의 field_refs는headline/what_changed/background/meaning/reaction별refs다. 의미/반응은C2typedcontext를쓴다. 모델이선정ID/fact/ref를추가하지않는다.
- `EditorialPlan(event_ids,required_fact_ids_by_event,evidence_refs_by_event,attachments,placement,exclusions,budget_bytes)`는parent-ownedfrozen값이다. placement는article/follow_up/context/reference중하나다.
- `ContextPanel(panel_id,related_event_id,kind,text,fact_ids,source_refs)`의kind는background/comparison/sector/asset다. 관련event가없으면기본bodycontext가아니라reference다.
- `MarketReferencePanel(panel_id,kind,rows,observed_at,time_basis,source_refs)`의kind는price/macro/positioning/historical_financial이다. row는검증된fact/anchorID/value/unit/period이며LLM이자유표를작성하지않는다.
- `FollowUpEntry`는kind가event/numeric/scheduled인닫힌union이다. event는typedStoryRecord/NextCheck 또는단일event의actualstate/질문, numeric은actual current_fact_id/ContextRef와기존NumericWatchpoint검증을통과한current/trigger/implication, scheduled는source-backed일정과timeprecision을갖는다. free today_watch를재파싱하지않고typedhandoff를사용한다. numeric미해결을eventkind로바꿔검증을우회하지않는다. event와연결되지않은가격threshold카드를분량채우기로자동생성하지않는다.

- `EditorialPlan`은 parent-owned ordered event IDs, required fact IDs, assigned evidence refs, background/asset/follow-up attachments와 placement를 고정한다. source health, novelty, required actual 보호를 입력으로 받는다.
- article 최대5개, event당 source documents최대4/facts최대8. facts4/doc3제약은v3에적용하지않는다.
- `EventArticle`은 검증된 actor/action/object IDs와 short headline(최대120자), `what_changed`(최대600자), optional background/meaning/reaction(각180자), fact IDs/field refs를 갖는다. 필수 fact는 renderer에서 별도 사실 rows로 보존한다. 본문 첫 문장80자/원문 이름 동시 포함 의무는 폐기한다. 이름의 정확성은 entity ID/표시 alias/ref와 전체 factual text에서 검증한다.
- digest 최대3개, 한 항목의 완성 문장 최대140자. body와독립된projection이다. 길이/문장완결성만의presentation실패는해당digest만제외하고유효article을버리지않는다. unsupportedfact/entity/actualforecast/compliance위반은originalhardfinding을수집해기존trust정책을적용하며삭제로숨기지않는다. 제거된article은digest/관전/자산영향에재등장하지않는다.
- 사실상 important event가0개면 중요 변화 없음/수집 제한/생성 또는 검증 실패를 `EditionAvailability`로 구별한다. filler, 최소 사건 할당량, 정확히3개 요약 채우기는 폐기한다.
- context panel은 실제 사건을 설명할 때만 기본 본문에 노출한다. 새발표없는월간값/과거재무/주간포지션은reference panel에서 날짜와단위를명시한다. release-day required actual은 editorial plan의 필수 fact로 보호한다.

고정 읽기 순서: 한 H1 → 짧은 면책/시장nav/가격일과뉴스창 → 한눈에보기0~3 → 주요사건0~5 → 진행상황/다음확인 → 사건관련자산영향 → 접힌시장참고/진단 → 면책본문. global macro/thesis/가격/watchlist별도상단callout이같은내용을반복하면생성하지않는다. hero는기본없음,실제사건이해에관련되고기존provenance를통과한경우에만주요사건후보조로1개허용한다.

## C5. Finalizer·compatibility와 영구 이력 — u169

u144 `publisher.public_document.finalize_public_bundle`가 유일한 generated→sealed owner다. 새finalizer나post-sealrewrite를만들지않는다. `GeneratedPublicDraft`는discriminated union(`LegacyBriefingDraft|EventEditionDraft`)이며 한draft에한variant만존재한다. publisher의frozen결과는같은 writer API가읽는 `rendered_markdown`, `target_date`, `segment`, `markdown_sha256`, `notification_summary`, survivor/artifact/receipt필드를직접제공한다.

현재 `FinalizedPublicDocument.briefing: Briefing`에 의존한 소비자는 공통 sealed-text accessor로 전환한다. local FinalizedPublicDocument의 canonical `payload: Briefing|PublicEditionView`는 한 variant만 가진다. rendered_markdown/target_date/segment/hash는 readonly accessor다. legacy `.briefing` compatibility accessor는 payload가Briefing일때만제공하며v3소비자가이를읽으면명시적오류다. 실제 변경 owner는 현재 public_document.py(출력model)+models(컴포넌트간DTO)다. models가publisher타입을import하지않는다. v3에7개빈section을만드는bridge를허용하지않는다.

models의 `PublicEditionView(schema_version,segment,target_date,price_reference_date,price_time_basis,news_window,rendered_markdown,markdown_sha256,availability,events,digests,follow_ups,asset_impacts,story_publication_deltas)`가 visuals/notifier에 전달하는 공통 sealed view다. local `FinalizedPublicDocument`가 이 view와 기존 notification/artifact/receipt를 보유하고, writer는 동일 view의 exact bytes를 쓴다. `story_publication_deltas`는 `tuple[models.event_story.StoryPublicationDelta,...]`이며 실제 살아남은 article/follow_up의 IDs/facts/상태/검증된 공개 출처/clock만 포함한다. models가 publisher를 import하지 않으며 type 검증과 seal 일치 검사는 writer에도 유지한다.

`models/public_notification.py::EventNotificationSummaryV3(schema_version=3,segment,target_date,price_reference_date,price_time_basis,availability,coverage_status,coverage_label,events,digests,asset_impacts,news_window)`는 terminal view의 공개 projection이다. events는 source href, 최대 120자 headline, 검증된 사실과 support vector를 가진 순서 있는 부분집합이다. digests는 최대 3개이며 각각 최대 140자의 완성 문장이다. 기존 schema1/2 `PublicNotificationSummary`와 별도 닫힌 variant로 전달한다. notifier는 union variant를 판독하고 generated article/chunk를 사실 원본으로 읽지 않는다. private chunk text를 public view/DTO에 담지 않는다.

u169는 `models/event_asset_impact.py::EventAssetImpact(event_id,asset_id,relation,mechanism,condition,fact_ids,source_refs)`의 frozen 선언도 소유한다. relation은 direct/related/uncertain/rejected이며 공개에는 검증된 direct/related만 투영한다. u171은 기존 relevance engine을 확장하는 matcher와 독자 표면 표시를 소유한다. 이렇게 타입 선언을 먼저 제공하여 u169→u171→u169 순환을 막는다. finalizer는 사건/fact/ref 소유권과 survivor 일치를 검증하고 삭제 사건의 asset impact를 모든 표면에서 제거한다.

u169는 `models/event_document.py::EventVisualInput(schema_version=3,segment,target_date,events,reference_rows,placements)`도 선언한다. events는 parent가 검증한 ID·headline·fact/ref·context의 typed projection이다. u171은 이 입력으로 본문 supplement 자산을 E1 이전/동결 과정에서 stage한다. finalizer는 survivor와 사실이 일치하는 후보만 선택하여 used-only manifest를 봉인한다. 삭제 사건의 후보는 제외하고 유효 후보가 없으면 본문 이미지를 생략한다. 봉인 후 본문 이미지 생성·caption 재작성·본문 변경은 없다.

OG는 본문 supplement와 다르다. 기존 `_stage_publish_segments`의 post-seal `write_og_card` 경로를 유지하고, PublicEditionView의 공개 필드로 결정론적 OG를 생성한다. 새 사실·LLM·외부 요청·본문 rewrite 없이 reader-page artifact로 같은 publication transaction과 rollback에 포함한다. 본문 E1→E5 asset promotion과 OG의 transaction artifact 책임을 합치지 않는다.

### C5a. 공개 projection과 다음 실행의 복원

u169는 `models/event_document.py`의 닫힌 public 타입을 선언한다. private ContextRef를 public 객체에 그대로 넣지 않는다. `PublicSourceLocator(document_id,revision_id,chunk_id,start,end,ref_sha256,source_href)`는 검증된 공개 href와 이미 사용한 source span의 hash/offset만 포함하며 raw chunk text는 없다. `PublicSourceLocator`는 u168의 `SealedStorySourceRef`에 대한 type alias이며 같은 필드·검증 의미를 사용한다. 별도 locator model을 중복 선언하지 않는다.

- `PublicFactView(fact_id,subject_id,object_id,metric_key_hash,reader_label,value,unit,period,status,source_refs)`는 최종 본문에서 확인 가능한 사실만 보존한다.
- `PublicEventView(event_id,actor_labels,object_labels,headline,what_changed,facts,time,background,meaning,reaction,support,source_refs,story_id)`의 의미·반응은 C2와 같은 닫힌 mode/status지만 refs는 PublicSourceLocator로 변환한다. 본문에 없는 claim은 넣지 않는다.
- `PublicDigestView(event_id,fact_ids,text,source_refs)`는 유효한 최종 digest다.
- `PublicFollowUpView(kind,event_id,story_id,reader_state,question,next_check,numeric_values,source_refs)`는 C4의 tagged union 의미를 유지한다. numeric 값은 기존 NumericWatchpoint validator를 통과해야 한다.
- `PublicAssetImpactView(event_id,asset_id,relation,mechanism,condition,fact_ids,source_refs)`는 검증된 direct/related만 포함한다.

PublicEditionView와 notification의 events/digests/follow_ups/asset_impacts는 위 frozen public 타입의 tuple이며 동일 C4 개수·문장 상한을 적용한다. private→public 변환과 href·claim·survivor 결속 검증은 u144 finalizer만 한다. price_reference_date는 확인된 MarketAnchor.trading_date에서 가져오고 price_time_basis는 `trading_date|unavailable`다. 가격 기준일 미확인은 null/unavailable이며 target_date에서 ‘전 거래일’을 계산하지 않는다. news_window도 parent가 확인한 실제 관측창을 봉인한다.

`PublishedEventEdition(schema_version=3,segment,target_date,archive_relative_path,markdown_sha256,projection_sha256,price_reference_date,price_time_basis,news_window,availability,events,digests,follow_ups,asset_impacts,story_publication_deltas)`는 rendered_markdown을 중복 저장하지 않는 공개 sidecar다. finalizer가 sealed public projection을 만들고 publisher/writer.py가 같은 document의 exact bytes/hash를 검증하여 `archive/_meta/event_editions_v3/{segment}/{YYYY-MM-DD}.json`에 쓴다. projection_sha256은 자기 hash 필드를 제외한 canonical JSON bytes의 hash다. orchestrator는 sidecar와 Markdown·자산·identity/story/news metadata를 같은 publication transaction, 같은 baseline SHA/CAS, 같은 rollback 범위에 넣는다. private refs/text/model 실패문장은 저장하지 않는다. immutable archive와 sidecar는 발행 당시 사실·상태를 보존한다.

u171의 `publisher/event_archive_reader.py::read_published_event_edition`은 다음 실행에서 sidecar/schema/projection hash/Markdown hash를 검증해 복원한다. 없음·불일치·지원하지 않는 schema는 `missing|hash_mismatch|unsupported_schema`로 계측하고 해당 사건 요약을 제외하며 archive 링크와 ‘과거 사건 자료 확인 불가’를 제공한다. v3 Markdown을 legacy parser로 재해석하거나 새로운 fact/state를 추론하지 않는다. 회고는 당시 projection을 묶고 최신 story ledger 상태는 별도 시점 표시가 있을 때만 추가한다.

모든 표면의 대표 내용 선택은 `유효 digest → 동일 terminal event의 검증된 headline → 사건 0건일 때 availability` 순서다. article이 남고 digest가 없으면 사건 없음으로 표시하지 않는다. 현재 실패 시장의 안내는 기존 bundle outcome에서 별도로 전달한다.

순환 의존성을 피하기 위해 u168 foundation 단계가 `models/event_story.py`의 frozen StoryState/SealedStorySourceRef/NextCheck/StoryRecord/StoryStateProposal/StoryPublicationDelta 선언을 먼저 소유한다. u169가 이를 소비하고, u170은 상태 reducer·ledger·후속 입력 로직을 소유한다. u170 통합 전 delta tuple은 비어 있고 실제 상태 진전을 생성하지 않는다. opaque hash나 free mapping 대신 typed next_record와 실제 표시 필드의 일치를 검증한다. 별도 duplicate story/delta model을 만들지 않는다.

RegionSpec/expectation/structure checks는schema별required region을쓰지만numeric/entity/compliance/disclaimer/notification/seal/asset/transaction invariant는같게적용한다. v3의사건지역은event_id,하위claim은fact/refidentity로소유한다. hard trust finding을구조변경으로없애지않는다. 숫자-only local containment와부분발행 정책은기존owner를재사용하며절대불변사실을임의로‘미확인’으로바꾸지않는다.

기존archive본문/URL/자산은수정하지않는다. 과거본문읽기parser만read-only로남긴다. 신규v3에①~⑦헤더를숨겨서공존시키거나기존reader-format재작성체인을실행하지않는다. v3전환은판독된schema로분기한다.

## C6. Story state와 후속 확인 — u170

canonical DTO owner는 `models/event_story.py`(u168 선언), advance reducer는 `briefing/event_story.py`(u170), frozen input/remote writes는 `orchestrator/event_story.py`(u170)다. renderer/관전은 publisher에서 이 타입만 소비한다. ResolutionTarget은 일반 동일 occurrence와 source-backed linked release/result를 구별하여 예정 발표와 actual 결과의 별도 event IDs를 명시적으로 연결한다.

`StoryRecord(story_id,segment,kind,event_ids,latest_state,verified_delta,open_question,next_check,resolution_evidence,updated_at,last_evidence_at,closed_at,disposition,state_time,related_story_ids,source_refs)`의state는`announced|pending|confirmed|implemented|resolved|cancelled|unknown`이다. disposition은 active/archived_unknown/closed다. 각종류별transitiontable은u170에서정하며no-new-evidence는state유지다. 회사명/ticker재등장·일정경과·ledger TTL만으로resolved하지않는다. 협상결렬/법안철회도source-backed cancelled다. source의state_time은exact/date/unknown을유지한다. closed_at은 resolved/cancelled proposal과 seal에 사용한 고정 observed_clock(UTC)이며 90일 retention용이다. remote confirmation 이후에만 확정 상태와 retention authority를 갖는다. push 완료 시각을 미리 만들지 않고 실제 confirmation 시각은 기존 PublishReceipt에 별도 기록한다. source의date-only값을임의장중UTC로바꾸지않고일반confirmed상태를자동종료하지않는다.

진행story는segment당최대200개,`archive/_meta/event_stories_v3.json`합계5MiB,본문후속최대3개. 같은event ID에fact delta가없는반복보도는headline승격하지않는다. 마지막근거가180일지난story는disposition=archived_unknown으로activeview에서제외하되state를resolved로변경하지않는다. closedrecord는closed_at이후90일retention,immutable기존archive가영구이력이다. publicledger에는이미봉인된readerstate·sourcehref·ID/hash/시각만보존하고rawevidencechunk/secret/privatefixture를쓰지않는다. source_refs는privateContextRef그대로가아니라검증된공개href와문서/revision/chunkhash/span의sealed locator projection이다.

`StoryStateProposal`은pre-sealprivate입력이다. `StoryPublicationDelta`는실제terminalsurvivor에서 봉인된projection이며orchestrator만이를같은publicationtransaction에담아remote-confirmation후확정한다. 렌더/봉인되지않은수집transition은publicledgerupdate0이며last_evidence_at도갱신하지않는다. ledger의priorhash/CAS와push응답유실은기존PublishReceipttransaction계약을재사용한다.

scheduled next check는source-backed timestamp와ref가필요하다. 시각이없으면구체적인observation_question으로표시하고예정일을만들지않는다. 기존u162숫자와정성taggedfamily를재사용한다.

## C7. Budgets / semantics / sources — u167/u172/u173

- Stage1 candidate96/source24/lookahead12, typed drafts12와provider의기존attempt/deadline총예산을유지한다.
- Stage1 transmitted evidence24KiB total. 모든v3chunk/header/referencebytes를실제직렬화UTF-8로계산한다.
- v3 protected Stage2 evidence16KiB; 기존v2의8KiB는변경하지않는다. 필수fact/identity/time→meaning/reaction→background/followup순서로배정한다. optionalspans을줄여도필수budget을못맞추면후순위사건을budget_deferred로제외한다. selectedplan과실제transmittedrows는정확히일치한다.
- 두 LLM 단계와 기존 timeout/attempt budget을 유지한다. 한 event/field의 실패는 진단하되 재시도/부분 회복 총량을 추가하지 않는다. 이전 버전 rollback은 별도 운영 정책이며 매일 추가 LLM 재생을 실행하지 않는다.
- 신규원문HTTP는기존u161의max6/동시2/20초/decoded500KiB/소스당2/redirect1/retry0안에서만가능하다. qualification없는provider/body/URL/path를열지않는다.
- performance는현NFR-001과DEBT-090을유지하며새16KiB의실제측정없이는성능통과를주장하지않는다.
- 실제사람what/when/why/react/source5/5,필수fact100%,근거없는사건/인과0을유지한다. 내부선정·생존·fact보존·외부must-cover포착·사람점수의분모를분리한다.
- u173은정책/실적/국내공시의source-slotqualification을소유한다. unknown권리/접근/schema는blocked판정으로보존하며동작하는신규provider를발명하지않는다. qualification작업과새sourceadapter도입/activation은별도다.
- 평가 canonical owner는 기존 models/event_quality.py와 scripts/_event_coverage_replay.py/check_event_coverage.py다. v2의 human pending fixture를 다시 채점하지 않고 별도 v3 합성 matrix/private 실제 corpus/사람 수용 record를 둔다. 세시장×기존12시나리오=최소36개 합성 case, 실제 문서 최소12개(시장별4개/발행일2개 이상/각시장뉴스-rich 포함)를 요구한다.
- source-slotqualificationcanonicalowner는models/enrichment.py의 `SourceSlotQualification(status=verified|blocked)`와`ops/event_source_slot_qualification.json`이다. slotverified는기존u161bodyfetchqualification/HTTPactive권한과다른판정이다. 기존ops/event_source_qualification.json은독립된sourcegate다.

## C8. 최종 runtime 폐기와 정착 — u172

C1의기본schema2/off/shadow호환은전환기간에만적용한다. 세시장accepted와실제v3예약10회관찰뒤별도reviewedcleanup은기본schema3로바꾸고defaultruntime의legacygenerator/6freebody/빈bridge/활성readerrewrite를제거한다. legacyoff/shadowschema2요청은명시적으로거절하거나deprecated 안내 후 중단하며숨겨진구형생성을실행하지않는다. 정상v3생성policy는active/schema3이고비게시검증은preview/schema3다. 실제activation/default변경은reviewedcode/policy와명시적release지시의후속작업이다. historicalreaders와이전reviewedcommit전체rollback을보존한다.

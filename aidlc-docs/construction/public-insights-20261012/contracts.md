# 공통 계약 C180–C183

상태: 2026-10-12 설계 초안. 기존 코드에서 이미 동작하는 타입·flag·hook 라고 주장하지 않는다. 구현은 u180 부터 진행하며 각 화면의 원천 매핑은 해당 유닛이 소유한다.

## C1. 입력과 소유권

공유 타입은 신규 `src/investo/models/insights.py`가 소유한다. `SourceInsightEnvelope`는 source_name, 최대 16 개 `SourceInsightMetric`, 최대 128 개 `SourceInsightEvent`를 가진 immutable 객체다. source-specific 원 응답 구조는 포함하지 않는다. metric/event 의 종류·단위·시간·출처는 같은 envelope 의 source_name 과 일치해야 한다.

`NormalizedItem`에 선택 필드 `insight_envelope: SourceInsightEnvelope | None = None`를 추가한다. `items.py`의 기존 serializer 는 이 필드를 항상 제외한다. envelope 자체는 별도 private boundary 에서만 검증·직렬화 가능하며 public writer 가 직접 소비하지 않는다. 필드 없이 기존 모델을 만들면 serialized bytes 와 기존 round-trip 가 유지된다.

`FetchWindow.insights_enabled: bool = False`와 `collect_sources(..., insights_enabled=False)`는 수집 요청을 늘리지 않고 기존 응답에서 typed observations 를 추출하는 opt-in 이다. source adapters 만 원 payload 를 읽는다. u181/u182/u183 이 기존 source 파일에서 envelope 생성 로직을 소유한다. envelope 가 없으면 prose·title·summary 에서 값을 복구하지 않는다.

`orchestrator/insights.py`는 envelope 를 모으고 private raw items 의 `insight_envelope=None`인 복사본을 기존 후속 단계에 전달한다. active news window 경로와 보통 `_stage_collect` 경로 모두 동일 handoff 를 사용한다. `_stage_collect`의 기존 tuple 반환과 fetch injection callable 은 유지한다. empty/legacy items-only input 은 dashboard unavailable 이며 임의 source outcome 을 보충하지 않는다.

sources·publisher·briefing·notifier 는 서로 import 하지 않는다. shared DTO 는 models 만 통과한다. deterministic dashboard 는 LLM-generated 문서가 아니며 기존 u144 brief finalizer 의 봉인 권위를 대체하지 않는다.

collector는 각 adapter 결과를 flatten하기 전에 envelope의 origin_adapter_name을 실제 호출한 registry adapter에 결속한다. 이 필드는 source의 임의 주장이나 공개 source 이름으로 추론하지 않는다. source_name은 NormalizedItem의 실제 producing source와 맞고 origin은 해당 SourceOutcome에 맞아야 한다. 기존 Bybit→OKX fallback만 명시된 producing/origin 조합으로 허용한다. standalone OKX의 실패가 Bybit 경유 정상 OKX 관찰을 실패로 덮지 않으며, 반대로 request origin의 실패를 emitter 이름만으로 정상 처리하지 않는다. mode off의 envelope/직렬화 필드는 계속 생략한다.

## C2. 시간과 숫자 의미

`InsightTime`은 `basis=effective_date|period|source_response|collection_window|schedule`, `precision=exact|date|month|quarter|unknown`, local_date/start_date/end_date/period/source_timezone/exact_at/source_updated_at 를 가진다. source observation/effective date 와 공표시각, run_started_at/collection_completed_at 는 별개다. exact 는 tz-aware timestamp, date 는 현지 날짜+IANA timezone, period 는 YYYY-MM 또는 YYYY-Qn 이다. unknown 은 숫자 의미를 판단할 수 없으면 카드 unavailable 이다.

원천에 없는 공표·관측 시각을 midnight·NYSE close·run clock 으로 생성하지 않는다. 단순 수집 window 끝은 거래소 snapshot timestamp 가 아니다. collection_window 는 시작·종료 구간을 제공하며 “수집 구간의 관찰값”으로 표시한다. `collection_completed_at`은 모든 수집 완료의 운영 시계이며 원천 시계라고 표시하지 않는다.

숫자는 Decimal finite, bool 금지, decimal string 최대 64 자다. 단위는 percent/percentage_point/basis_point/usd/krw_per_usd/index/contracts/usd_notional/fraction/count 의 closed set 이다. value·단위·definition_id·provider·scope_id·methodology_id 가 함께 검증되어야 한다. percent 는 0..100 점유율 등에 사용하며 모든 percent 값을 그 범위로 일반화하지 않는다. 금리 음수는 그 이유만으로 차단하지 않는다. source-specific 물리 범위는 유닛 규칙에 명시한다.

## C3. 권리와 source 상태

`InsightSourceQualification`은 source_name, 정확한 endpoint/field_scope/definition_ids, display_allowed, public_git_history_allowed, retention_allowed, provenance/terms href·확인일·요구 attribution, required_env_names, runtime_probe_state 를 가진다. proposed `ops/insights_source_qualification.json`은 공개 출력 permission matrix 이며 adapter registry 가 아니다. 현재 discovery 와 `_internal/source_specs.py`의 tier/window/segment 정책을 변경하지 않는다.

문서 판정·source runtime probe·권리·카드 숫자 검증은 서로 다른 축이다. 유효한 primary evidence와 실제 범위가 없으면 display_allowed=false, public_git_history_allowed=false다. 현재 JSON·Markdown도 공개 Git commit에 영구적으로 남으므로 current 숫자까지 display_allowed와 public_git_history_allowed를 모두 요구한다. display-only/TTL-only 허용을 Git 영구 이력 허가로 확대하지 않는다. 둘 다 허용되지만 dashboard 분석용 이력만 제한된 경우 retention_allowed=false로 현재 카드만 제공하고 history.json에는 넣지 않는다. provider 약관 고지는 링크와 검증한 문구를 함께 표시하며 플랫폼의 일반 면책만으로 대체하지 않는다.

카드의 `availability=available|limited|unavailable`, `freshness=fresh|delayed|stale|unknown`, `latest_attempt=ok|zero|failed|skipped`를 분리한다. reason 은 missing_input/invalid_value/definition_conflict/time_unknown/stale/source_failed/source_zero/source_skipped/rights_unverified/rights_revoked/history_insufficient/history_incompatible/publication_unconfirmed 의 closed set 이다. internal exception·raw body·secret·query string 은 공개하지 않는다.

zero/failed/skipped 는 0 이 아니다. 현재 permission 이 유지된 과거 verified 값만 last-good 로 쓸 수 있다. 권리 철회·정의 변경은 과거 숫자/이력에도 적용되어 신규 공개 projection 에서 제거한다. pending 또는 outcome_unknown local 데이터는 baseline 으로 읽지 않는다.

공개 source href는 검토한 HTTPS hostname/path에 한정하고 userinfo·secret-bearing query·javascript/data scheme을 거부한다. qualification의 허용 출처와 source envelope의 owner를 대조한다. source original title/summary/raw_metadata를 HTML로 복사하지 않으며 labels/URL을 escape한다.

## C4. freshness 와 비교

관측 주기와 공표 주기를 함께 판정한다. Treasury/NY Fed 는 소스별 발표 일정·금융/연방 영업일로 예상 관측일을 결정하며 NYSE 휴장일을 복사하지 않는다. SOFR 와 EFFR 에도 같은 holiday table 만 적용하지 않는다. 2026-07-03 의 repo-reference-rate publication 변경과 EFFR 의 다른 일정은 source 별 exception fixture 로 고정한다. 소스별 공휴일 정책은 `models/insights_calendar.py`의 2026 지원 범위와 공식 근거로 버전 관리한다. 미지원 연도는 freshness unknown 이며 비교를 억제한다.

DEXKOUS/H.10 은 관측빈도 daily 와 공표빈도 weekly 를 구별한다. 직전 영업주의 일별 FX 를 월요일 16:15 ET, 연방휴일이면 다음 영업일에 발표하는 공식 정책을 적용한다. 예상 관측일은 마지막 도래한 공식 발표에 포함되는 마지막 원천 영업일이다. 그 주의 미발표 일별 관측을 기대하여 목요일마다 정상 FX 를 stale 로 만들지 않는다. FRED 의 반영시각은 별도이며 공식 발표 도래 후 1 source 영업일 lag 는 delayed,2 일 초과는 stale 이다. [H.10 공식 일정](https://www.federalreserve.gov/releases/h10/), [NY Fed 휴일](https://www.newyorkfed.org/aboutthefed/holiday_schedule.html), [2026-07-03 지표별 공표 예외](https://www.newyorkfed.org/markets/opolicy/operating_policy_260618a).

예상 날짜가 원천 날짜보다 1~2 개 해당 소스 영업일 뒤면 delayed, 2 개를 초과하면 stale 이다. 공개 freshness unknown/stale 값은 날짜와 상태를 붙인 last-good 카드로만 표시하고 새 변화/종합 요약에는 쓰지 않는다. 월간 actual 은 대상 월을 표시하고 다음 공식 예정 발표+1 미국 영업일 이후에도 갱신되지 않으면 delayed, +2 일 이후 stale 이다. 공식 다음 일정이 없으면 freshness unknown 이며 “최신 수집 자료”와 대상 월만 표시한다. 이 월간 예외는 2026 지원 범위의 이미 종료된 최근 대상 월과 알려진 period precision에만 적용하며, 미래 clock/period·시점 자체 unknown에는 적용하지 않는다. 이 상태의 새 이력/변화값은 만들지 않는다. 숫자는 64문자 및 adjusted exponent ±64 이내로 제한하고, 금리차는 precision256으로 연산해 묵시 반올림을 막는다.

calendar의 수집 snapshot은 collection_completed_at 기준 36시간 이내에만 fresh다. 원천 일정 갱신시각은 별개이며 수집 성공을 원천이 수정됐다는 근거로 쓰지 않는다. 실패한 source의 last-good 일정은 당시 수집시각과 source 상태를 붙여 유지하고, 원래 range를 현재로 갱신한 완전한 달력으로 표시하지 않는다.

crypto current 는 신뢰 가능한 source_updated_at 또는 알려진 collection_window 종료가 36 시간 이내일 때 fresh 다. unknown timestamp 를 run clock 으로 치환하지 않는다. 게시 당시 판정과 독자가 지금 보는 경과 시간을 구별한다. base HTML 에 관측일/운영 판정시각을 고정하고, 보조 same-origin JS 가 경과를 다시 계산할 수 있다. JS 없이는 “최신/실시간” 단정을 피하고 기준 시점을 명시한다.

비교 키는 metric_id+definition_id+provider+scope_id+methodology_id+unit+sample_policy 다. 하나라도 바뀌면 이력 연결을 끊는다. macro 5 거래일 비교는 같은 정책의 정확한 두 관측일이 있을 때만, 월별 비교는 같은 정의의 연속 대상 기간이 있을 때만 계산한다. crypto 7 일 비교는 같은 UTC 일별 표본 정책의 D 와 D−7 기록이 있을 때만 제공한다. 제공자·단위·시점 불일치, missing baseline 에는 변화값을 만들지 않는다.

## C5. 공개 snapshot 과 이력

공개 타입은 `ValidatedInsightMetric`, `ValidatedInsightEvent`, `ValidatedInsightModule`, `PublicInsightsManifest`, `InsightRunOutcome`다. 원천 숫자 검증과 qualification 을 모두 통과한 객체만 renderer 에 들어간다. 현재 숫자와 footer·links·상태를 포함한 immutable public module 을 완성한 후 저장한다. source envelope 와 LLM 초안은 직접 게시하지 않는다.

경로는 `site_docs/insights/_data/manifest.json`, 각 모듈의 `_data/{macro,calendar,crypto}/current.json`, numeric 모듈의 `history.json`, 화면별 `{macro,calendar,crypto}/index.md`, 모음 `site_docs/insights/index.md`다. module ID 는 macro/calendar/crypto 만 허용한다. module snapshot_id 는 canonical JSON 의 snapshot_id 필드를 제외한 payload hash 다. manifest 는 모든 module identity 와 index/history file hash 를 결속하며 renderer Markdown 의 snapshot comment 와도 맞는다.

최대 3modules, 모듈당 32metrics 또는 128events, current JSON 256KiB, history 모듈당 4MiB, 프로그램 전체 12MiB 다. input envelope 모듈 합계 512KiB 를 넘으면 해당 모듈을 억제한다. 숫자 이력은 metric 당 최대 366 개 유효 관측, 월간은 최대 24 개 기간이다. history row 에는 value·time·definition reference 만 보관하고 반복된 원문/attribution/URL 은 definition table 로 참조한다. regular retention 은 공개 확정된 최신 유효 관측을 기준으로 수행하며 넘치는 malformed input 을 조용히 잘라 정상으로 만들지 않는다.

calendar 는 첫 버전에 별도 일정 이력을 만들지 않는다. 갱신된 upcoming snapshot 만 게시한다. crypto 일별 표본은 같은 UTC day 의 마지막 remote-confirmed 수집 관찰을 사용하되 하루 종가·하루 평균으로 표시하지 않는다. 같은 날 수정과 source revision 은 기존 record hash 와 수정 사실을 보존하는 current representation 으로 구별한다. 공개 보관의 의미는 현행 git history 에도 해당하므로 license 가 삭제를 요구하면 파일 retention 만으로 해결됐다고 선언하지 않는다.

## C6. 게시와 현재 production 경계

`INVESTO_INSIGHTS_MODE=off|shadow|active` 기본은 off, `INVESTO_INSIGHTS_MODULES` 기본은 macro 이다. unknown mode/module 은 configuration error 다. 등록은 배포/활성화와 별개다. shadow 는 메모리의 검증 결과와 bounded 진단만 만들고 public files/git/Pages/history/Telegram write=0 이다. off 는 legacy collect options/input/output bytes 를 유지한다. 기존 dry-run, news_replay 또는 선언된 historical replay 에서는 active 여도 공개 write0 이다. target_date 는 source/window 요청 기준이지 현재 조회한 crypto 의 원천 날짜가 아니다. active 라도 qualification 이 없는 카드는 suppress 한다.

활성 phase 순서: 기존 collection 1 회 → envelope 분리 및 legacy item 복원 → module projection/검증 → dashboard scoped publication → 기존 enrichment/generation/finalization/publication/notification. news-active 와 legacy collect 경로 모두 적용한다. dashboard publish 가 event/news 의 state/cursor 를 읽거나 진전시키지 않는다. generation 이 실패해도 dashboard 의 remote-confirmed 결과는 `PipelineResult.insights`의 opt-in 결과로 보존하고 시황 PipelineStatus 는 기존 규칙대로 실패/부분 상태다.

publisher 의 신규 `insights/store.py`가 local multi-file 준비·복구·rollback 을 소유한다. `orchestrator/insights_publication.py`가 기존 `PublicationRequest`/`PublishReceipt`/`commit_and_push`를 호출한다. metadata_paths 에는 insights manifest 만 넣고 그 hash 는 fixed remote baseline 에서 읽는다. 이전 결과를 읽을 때도 같은 remote-confirmed baseline 을 사용한다. 모든 insights paths 를 명시적으로 stage 하고 범위 밖 dirty/index 를 건드리지 않는다.

index/current/history/manifest 는 한 scoped git commit 으로 게시한다. 충돌·취소·pending·unknown 결과에서 새 이력 baseline 또는 성공을 기록하지 않는다. 기존 receipt 의 metadata CAS·remote ancestry·timeout·rollback 을 재사용하고 이미 지원되는 경로인지 구현 첫 단계에서 검증한다. 동일 manifest 를 동시에 바꾸는 writer 는 경쟁 실패이며 다른 event/news/sector metadata 는 보존한다. 새 snapshot write/readback identity 가 확인돼야 원격 게시 성공이다. local file rename 을 원격 CAS 대신 쓰지 않는다.

기존 private runtime 의 collector 와 Pages 결과 신호에 opt-in hook 만 연결한다. 새 public credential-bearing source workflow·scheduler·LLM invocation·Telegram message 를 추가하지 않는다. 현재 `src/investo/__main__.py`의 GHA 출력과 `ops/private-runtime/production-briefing.yml`의 Pages step 은 briefing 의 publication_committed 를 사용한다. 신규 `insights_publication_committed` 신호는 remote-confirmed insights 가 있을 때만 true 이며 `pages_required = publication_committed OR insights_publication_committed`로 묶는다. briefing 의 기존 publication_committed·종료 0/1/2 의 의미를 바꾸지 않고 실패 종료에서도 저장한 결과로 Pages step 을 실행한다. private workflow 의 검토된 코드 pin 과 전체 225 분 예산은 그대로 따른다.

새 모듈의 배포 시 기존 Pages build 의 포함과 private runtime 코드 pin 은 각자 확인한다. Pages 실패는 데이터 commit 성공과 구별해 운영 기록한다. root 문서 설계만으로 mode/modules/pin/secrets 를 바꾸지 않는다.

## C7. 자원·실패·UI

기존 source HTTP/retry/concurrency/timeout 은 증가하지 않는다. 추가 dashboard phase 는 60 초: local projection/render/store 10 초, remote publication 최대 45 초, 나머지 정리 5 초다. publish budget 은 남은 wall deadline 이하로 전달하며 cancellation 을 drain 한 후 rollback/receipt 를 완료한다. peak 추가 RSS 96MiB, local compute CPU 5 초 이하를 최대 fixture 로 측정한다. DEBT-090 의 기존 전체 10 분 목표 위반을 이 추가 상한으로 해결했다고 표시하지 않는다.

예상 source/숫자/권리/게시 오류는 해당 module 또는 dashboard 만 실패시킨다. unexpected programming error 는 기존 error owner 에게 전달하고 조용히 정상값으로 복구하지 않는다. dashboard 오류를 이유로 기존 정상 시황·event gate 를 완화하지 않는다.

세 화면은 MkDocs·u176 token·u178 가독성·면책을 재사용한다. 신규 CSS/JS 는 insights scope, same-origin 만 읽고 외부 network/telemetry=0 이다. JS 없는 핵심 카드·일정·출처·링크를 제공한다. 390×844/1440×900, light/dark, keyboard, 200% 확대를 실제 렌더로 확인한다. 실제 viewport 를 못 봤으면 미검증 상태이며 기존 u145 waiver 를 승계하지 않는다.

상위 메뉴는 기존 섹터 URL 을 포함한 `대시보드` 그룹으로 확장한다. macro 가 첫 배포될 때 u181 이 hub/메뉴를 소유하고 u182/u183 은 기존 그룹에 자신만 추가한다. 미개발 module 의 placeholder 메뉴나 dead link 는 생성하지 않는다.

## u182 구현 구체화 (2026-10-25)

일정 details(kind/category/official occurrence/family/명시된 target_period)와 병합 출처 참조, module coverage를 shared DTO에 추가한다. 새 필드가 없는 기존 schema-v1 snapshot/envelope/event는 선택 필드를 생략해 이전 canonical bytes/hash를 유지한다. 날짜-only의 범위는 source-local 오늘, exact의 범위는 KST 오늘이다. inactive module의 rights sanitation은 이전 일정의 원래 수집시각을 유지하며 철회된 병합 참조를 제거한다. 활성 수집의 정상 새 snapshot에 없는 이전 행은 완료/취소를 단정하지 않고 제거한다.

## u183 구현 구체화 (2026-10-25)

funding의 적용구간은 InsightTime.applicable_start/end로 response clock과 분리한다. 두 경계를 함께 검증하고 history clock에도 보존한다. 새None필드는생략해기존v1canonical/hash를유지한다. 알려진crypto정의는UTC수집날짜별마지막remote-confirmed표본을사용한다. 같은날다른원천시각의표본교체는superseded_from,같은원천시각의값수정은revised_from으로구별하며원래record hash를보존한다. provider/계약/주기/정의가바뀌면이력key가바뀐다. source/slotcoverage와인접attribution을추가하되새HTTP/키/기본활성화는없다.

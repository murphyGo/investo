# Functional Design: u172 실제 사건 의미 수용과 v3 운영 전환

**Date**: 2026-10-10 KST. **Status**: Functional Design / NFR Requirements 초안. 구현과 운영 미적용. **Priority**: P0. **Baseline**: `19c89b92`.

## 문제와 목표

u159의 합성 replay는 12개 시나리오와 25개 변형에서 구조와 terminal 일치를 검증한다. 그러나 실제 사람 검수는 `pending`이며, golden manifest의 정상 사건 양성은 미국에 집중되어 있다. 미국 expectation 25개, 국내 2개는 차단 음성, 코인은 0개다. 자동 회귀 성공을 세 시장의 의미 품질 합격으로 사용할 수 없다. 실제 v2 preview에서도 국내·미국과 코인의 성공 여부가 달랐다.

v3의 전체 문서, story, 소비자 전환을 실제 근거와 사람 기준선으로 수용한다. 수집 이후의 구조 생존, 필수 사실 보존, 외부 주요 사건 포착, 사람의 이해 가능성, 실제 배포 성공을 서로 다른 결과로 기록한다. 승인된 목표인 사람 `what/when/why/react/source` 5/5, 필수 fact 100%, 근거 없는 사건과 인과 0은 유지한다.

근거: [u159 검증](../u159-event-coverage-replay-and-gate/code/validation.json), [기존 평가 계약](../news-event-briefing/nfr-and-validation.md), [현재 golden manifest](../../../tests/fixtures/event_briefing/manifest.json), [10월 9일 운영 전환](../../../docs/sessions/2026-10-09-event-active-rollout.md). 위 증거는 해당 기록 시점의 상태이며, 구현 또는 운영 시작 시 현재 owner/pin을 재조회한다.

## 소유권과 의존성

| 경계 | Canonical owner / 재사용 경로 |
| --- | --- |
| 평가 DTO와 nullable 분모 | `src/investo/models/event_quality.py` 확장 |
| 봉인된 문서의 구조 관측 | `src/investo/publisher/event_quality.py`; u144 finalizer가 만든 bytes만 읽음 |
| 기록 재생과 자동 기대값 대조 | `scripts/_event_coverage_replay.py`, `scripts/check_event_coverage.py` 확장 |
| 실제 비게시 preview | `scripts/preview_event_briefing.py`, `scripts/preview_event_briefing_codex.py`, `scripts/seal_event_preview.py` |
| Reviewed code / 암호화 산출물 | `ops/private-runtime/event-preview.yml`, `.github/workflows/event-preview.yml`의 기존 경계 |
| 실제 운영 코드/policy와 발행 관측 | `ops/private-runtime/production-briefing.yml`, `ops/private-runtime/daily-briefing.yml`, 기존 publisher transaction과 Pages workflow |
| 공개 품질의 기존 필드 의미 | `src/investo/briefing/quality_history.py`, `src/investo/models/quality_history.py`, `src/investo/publisher/quality_consistency.py` |

Hard dependency는 u169 전체 문서와 finalizer, u170 story, u171 소비자 전환이다. corpus annotation과 외부 baseline 수집 설계는 먼저 준비할 수 있다. 완성되지 않은 v3 renderer를 대신하는 평가 전용 renderer나 별도 finalizer를 만들지 않는다. u167/u168의 evidence/identity는 상위 유닛의 완성된 계약으로 소비한다. 공통 필드와 budget은 [공통 계약 C1–C7](../event-news-v3/contracts.md)이 단일 출처다.

## 고정 평가 계약

`models/event_quality.py`에 frozen `EventSemanticAnnotation`, `EventSemanticReview`, `EventQualityV3Measurement`, `EventCutoverAcceptance`를 추가한다. 이는 계획된 타입이며 현재 구현 존재를 뜻하지 않는다. source/briefing/publisher/notifier는 이 모델 경계만 공유하며 서로 import하지 않는다.

1. `EventSemanticAnnotation`은 `case_id`, `segment`, `document_schema=3`, reviewed code SHA, remote data baseline SHA, 뉴스창, source availability, 기대 event/story IDs, `must_include`, `required_fact_ids`, `forbidden_claims`, `allowed_uncertainty`, expected support vectors와 public outcome을 고정한다. expected IDs/facts는 사람 또는 명시된 합성 oracle이 출력 생성 전에 작성한다. source chunk 원문과 주장별 refs는 private recording에 둔다.
2. `EventSemanticReview`는 annotation ID/hash, sealed Markdown hash, reviewer의 비식별 ID, 검토 시각, 각 사건의 `what/when/why/react/source` 0/1, 실패 rule code, `pass|fail|pending`을 저장한다. `pending` 점수는 null이다. 사람이 검토하지 않은 AI annotation에 human 점수를 발급하지 않는다. 자동 대조와 사람 판정이 불일치하면 각각 유지하고 cutover는 blocked로 둔다.
3. rubric은 다음과 같다. what은 주체와 실제 변화 및 필수 사실, when은 사건/발표/보도/예정/기준 기간 구분, why는 해당 시장에 의미 있는 source-reported 또는 근거와 연결된 조건부 경로, react는 출처가 확인된 반응 또는 명시적 미확인, source는 공개 주장에 맞는 원자료 locator다. eligible supported 사건은 5/5여야 한다. why unavailable은 why 0이며 합격으로 정규화하지 않는다. 시간의 unknown을 정확히 표현하면 when을 충족할 수 있고, 반응 미확인도 명시하면 react를 충족할 수 있다. 원문에 없는 세부 정보나 실제 인과를 발명하면 즉시 실패다.
4. `EventQualityV3Measurement`는 `segment`, `document_schema=3`, `basis=terminal|remote_confirmed`, 각 분자/분모, excluded segments, support-vector 축별 count, automated result와 review reference를 갖는다. 자동 metrics가 human result를 변경하지 않는다. 기존 v2 `qualified`와 `selection_coverage`의 의미를 소급 변경하지 않는다.
5. 내부 지표는 후보 내 must_include 선정률, selected→terminal 생존률, 선정된 supported 사건의 required-fact 보존률을 각각 저장한다. 외부 지표는 사람이 별도로 고정한 관측창 내 주요 사건 목록 중 관측·후보·최종 본문에 도달한 event 수 / 해당 목록 event 수다. 기사 row 수를 event denominator로 사용하지 않는다. denominator 0 또는 baseline 부재/판단 불가이면 ratio는 null이다. source 제한, candidate cap, budget 제외를 이유별로 유지한다. source-limited 내부 100%를 외부 포착 100%로 표시하지 않는다.
6. 내부 must_include 목록은 실제 후보 근거에서 확인되는 최대 5개 주요 사건을 사람이 선정한다. 외부 baseline은 최대 5개로 잘라 성공률을 높이지 않는다. 외부 목록이 본문 cap을 넘으면 전체 denominator와 cap 제외를 공개 집계에 남기고, 사건 중요도와 placement를 별도로 검토한다. 구체적인 공개 본문은 u169 cap을 따른다.

## Corpus와 재생 계약

기존 `tests/fixtures/event_briefing/manifest.json`과 `records.json`은 v2 회귀로 그대로 유지한다. 기존 loader의 AI 합성 / human pending 불변식을 바꾸거나 과거 18개 발행본을 원시 입력 녹화로 승격하지 않는다. 새로운 public synthetic manifest는 `tests/fixtures/event_briefing_v3/manifest.json`과 `records.json`으로 분리하고, 실제 녹화는 ignored `.tmp/event-news-v3/corpus/` 또는 암호화된 private artifact에 둔다. replay 로직과 evaluator는 기존 경로에서 schema별 분기한다.

- 합성 matrix는 기존 12개 필수 시나리오를 세 시장 각각에 적용한 최소 36개 market/scenario 사례로 고정하고 세 시장 모두의 정상 사건 양성을 포함한다. 국내/코인을 valid sibling의 차단 사례로만 대체하지 않는다. source 전면 실패와 주말/장후 재생을 명시하며, 본문과 digest의 서로 다른 길이, 표현·길이만 무효인 digest의 국소 제외, 변경된 4 document/8 fact 한도, 독립 meaning/reaction chunks, story material delta/무근거 상태 승격을 포함한다.
- 사람 수용 corpus는 최소 12개 실제 market-run 사례, 시장별 최소 4개와 서로 다른 발행 날짜 최소 2개로 고정한다. 각 시장에 뉴스가 풍부한 날, 뉴스 부족/수집 제한, 주말 또는 장후 사건, source-backed 정상 주요 사건을 포함한다. 여러 성격이 한 사례에 겹칠 수 있으나 실제 관측 날짜/시장/입력과 검토 결과는 별개로 기록한다. 부족한 사례는 pending으로 남기며 합성자료로 횟수를 채우지 않는다.
- 실제 corpus에는 collection→candidate→plan→transmitted refs→generated draft→sealed HTML/DTO/후속 카드의 연결을 고정한다. 모델 응답과 근거는 허용된 녹화에서 재생한다. 과거 Markdown만 가진 경우 output regression으로 분류하며 ingestion recall의 분모에 넣지 않는다.
- 실제 입력의 자유 문장 claim은 사람이 근거 span과 대조한다. 단순 required-fact 문자열 포함, event ID 존재, regex 또는 같은 모델의 자기채점은 의미 수용의 대체 증거가 아니다.

## Preview / cutover / rollback

`EventCutoverAcceptance`는 code/policy/annotation/review hash, 시장 allowlist, auto result, human result, source/cursor의 별도 gate 상태, release instruction reference, 실제 운영 receipt 목록을 갖는다. status는 `blocked|ready|active_observing|accepted|rolled_back|cleanup_complete`다. accepted는 시장별 초기 수용이고 cleanup_complete는 최종 프로그램 종료다. capability는 기본 false이며 release instruction 없이 `ready`를 active로 바꾸지 않는다.

1. u169/u170/u171 통합 및 정확한 SHA의 자동 gate를 확인한다. C1 policy를 entrypoint에서 한 번 구성하고 schema 3 preview를 기존 비게시 entrypoint에서 실행한다. 기존 두 호출 단계 안에서 v3를 생성하며 archive/git/알림/production ledger/cursor 쓰기는 0회다.
2. 실제 시장별 corpus 수용, 자동 must_include/fact 100%, unsupported 사건/인과 0, 사람 5/5를 확인한다. 각 시장의 실제 뉴스 풍부한 날에서 최소 1개의 정상 supported 주요 사건이 포함되어야 한다. pending 시장은 allowlist에서 제외한다. all-detail-limited 출력만으로 그 시장의 정상 supported 수용을 통과시키지 않는다.
3. 운영자가 실제 release를 지시한 경우 현재 runtime owner, reviewed code SHA, document schema와 시장 allowlist, 이전 schema 2 rollback pin/policy를 읽어 고정한다. 이 지시는 human score와 source qualification이 아니며 별도 증거로 저장한다. 운영 예외를 승인해도 score와 미완료 수용 항목은 그대로 남긴다.
4. allowlist에 편입된 시장마다 최초 3회의 서로 다른 실제 예약 발행에서 생성 schema, terminal outcome, remote-confirmed publication SHA, Telegram, 해당 publication의 Pages, ledger/cursor 상태를 확인한다. 한 실행이 여러 시장의 증거가 될 수 있지만 각 시장의 성공 receipt가 있어야 한다. 수동 재생·취소·skip은 예약 횟수로 세지 않는다. 정상 sibling 게시와 전체 성공도 분리한다. 해당 시장의 첫 3회가 완료되어야 시장별 운영 `accepted`다.
5. v3 trust invariant 위반, 제거 사건의 재노출, schema/policy 불일치, ledger 무근거 전진 또는 필수 사실 누락이 확인되면 해당 시장을 이전 reviewed schema 2 전체 code/policy로 복귀시킨다. 추가 LLM stage로 그날 schema 2를 자동 재생하지 않는다. 기존 archive는 재작성하지 않고 실제 사실 교정은 기존 별도 교정 절차를 따른다. rollback 후 auth owner와 게시/알림/Pages 연결도 재확인한다.

u160 cursor active와 u161 새 HTTP activation은 이 cutover가 자동 승인하지 않는다. u173 slot verified도 runtime fetch 자격을 대신하지 않는다. 코인 v3 승격에는 코인 자체의 실제 수용과 release evidence가 필요하다. 세 시장 전체 ready를 정상 sibling 생성/게시의 선행조건으로 만들지 않는다. DEBT-090과 기존 runtime budget은 유지한다.

### 전환 코드의 최종 제거

v1/v2와의 호환은 한시적인 전환 장치다. 세 시장 모두 accepted이고 실제 schema 3 예약 발행을 최소 10회 관측한 뒤 별도 reviewed cleanup을 수행한다. 10회에는 세 시장 각각의 실제 v3 발행 receipt가 포함되어야 하며 부분 실패/누락 시장/알림 실패는 별도 집계한다. 같은 예약 run의 재시도, 수동 재생, 취소/skip을 별도 정상 관측으로 더하지 않는다. 단순 10회 실행으로 실패를 지우거나 미수용 시장을 완료 처리하지 않는다.

cleanup 범위는 `briefing/pipeline.py`, `briefing/prompts.py`, `briefing/event_narrative.py`, `models/briefing.py`, `models/event_narratives.py`, `publisher/segment_reader_format.py`, 기존 `publisher/reader_format/`의 활성 재작성 경로와 그 호출부다. u169/u171과 대조하여 legacy v1/v2 generator, 여섯 개 자유 section string 생성 의무, 일곱 섹션의 빈 bridge, 이전 문서의 활성 rewrite chain을 정상 runtime에서 제거한다. 공용 numeric/entity/compliance/disclaimer 또는 합법적인 증거 producer는 역할을 확인하여 보존한다.

전환 중 schema 기본값은 2, 최종 reviewed cleanup 이후 기본값은 3이며 정상 생성은 v3만 사용한다. 이전 off/shadow/schema 2 정책을 명시적으로 폐기 또는 거부하고 구형 별칭이 제거된 일곱 섹션을 조용히 재생성하지 못하게 한다. 과거 archive 판독 parser는 read-only로 유지하고 기존 본문/URL/자산은 immutable이다. v2 corpus도 과거 출력/입력의 read-only 회귀 자료로 남기되 이를 위해 resident production generator를 보존하지 않는다.

제거 전에 reviewed 전환 SHA의 v2 합성 12/25 replay에서 terminal HTML/DTO snapshot과 hash를 `tests/fixtures/event_briefing/terminal_snapshots.json`으로 고정한다. 제거 후 현재 코드의 v2 검사는 이 snapshot의 historical parser/output 회귀에 한정하고 자동 결과에 `basis=historical_output`을 명시한다. 새 코드에서 v2 generation을 재생했다고 기록하지 않는다. 기존 원시 합성 기록/manifest와 human pending은 유지한다. 과거 generator 전체 재생이 필요한 검토는 보관한 prior reviewed commit의 독립 checkout에서만 수행한다. 정상 runtime의 schema 2 정책은 계속 거부된다.

cleanup 후 rollback은 보관된 이전 reviewed commit과 전체 policy를 되돌리는 방식이다. 동일 신규 runtime에 duplicate legacy generator를 상주시키는 rollback은 제공하지 않는다. 제거 코드의 독립 리뷰, full gate, default 3 readback, retired-policy negative와 prior commit rollback rehearsal을 모두 확인해야 `cleanup_complete`다. 설계 문서나 점수 JSON은 default 변경/코드 배포를 자동 실행하지 않는다.

## NFR Requirements / 단계 결정

Functional Design과 NFR Requirements는 **REQUIRED**다. 새로운 의미 점수, 분모, 사람 evidence, 버전별 수용과 rollback을 이 설계에서 검토한다. 새 논리 저장소/배포 플랫폼은 없으므로 별도 NFR Design/Infrastructure boilerplate는 생략하며 기존 u155 auth 격리와 preview 암호화, u144 publication transaction을 재사용한다. 코드와 운영은 각각 승인과 실제 실행 증거가 필요하다.

- NF-172.1: 추가 평가 LLM, 생성 단계, 독립 retry, preview의 신규 외부 fetch는 0이다. 실제 source recording은 기존 qualification/수집 계약으로 확보한다.
- NF-172.2: 실제 raw chunk, 원문, 모델 출력과 키는 public git/log에 0건이다. 공개 evidence는 hash/count/closed status/path와 허용된 합성/요약만 저장한다. private corpus 경로는 `git check-ignore`와 artifact 암호화로 확인한다.
- NF-172.3: C7의 Stage1 24KiB / v3 Stage2 16KiB, 두 단계와 기존 deadline/attempt를 실제 직렬화 bytes와 실행 기록으로 검증한다. 기존 1000 item warm 10회 p95 200ms와 end-to-end p95 회귀 10% 규칙을 적용하고 baseline/표본 수를 함께 기록한다. 측정이 없으면 pending이며 DEBT-090 절대 성능 목표의 완료로 기록하지 않는다.
- NF-172.4: 전환 중 off/shadow는 기존 public bytes/알림/receipt/cursor 불변, schema 2 golden 회귀 유지, schema 3는 한 문서 한 variant다. 최종 cleanup은 구형 생성 정책을 명시적으로 폐기/거부하되 read-only archive 회귀와 기존 numeric/entity/compliance/disclaimer/seal/asset/partial-sibling gate를 보존한다.

## 수용 기준

1. **AC-172.1**: 동일 runner가 schema 2의 기존 12/25 합성 회귀와 schema 3 matrix를 구별해 재생한다. 새로운 matrix에는 최소 36개 market/scenario 사례, 세 시장의 정상 사건 양성, source 실패/주말 재생과 각 12개 필수 scenario group이 존재한다. 원시 입력 없는 발행본은 output-only로 명시된다.
2. **AC-172.2**: 후보에 존재하는 must_include 100%, supported required fact 보존 100%, 합성 및 주석된 실제 corpus의 근거 없는 사건/인과 0을 달성한다. 필수 누락·근거 조작·unsupported digest fact/entity/compliance·무근거 story 승격의 hard negative는 original finding을 보존해 실패한다. 길이·문장 완결성만 무효인 digest는 그 항목만 제외하고 유효 article과 headline fallback을 유지하는 성공 사례로 검증한다.
3. **AC-172.3**: 실제 12개 이상, 시장별 4개 이상과 서로 다른 발행 날짜 2개 이상 corpus, 각 시장의 뉴스 풍부/부족/주말 또는 장후 case가 확보된다. eligible supported 사건은 사람 5/5이며 pending/AI-only는 사람 합격 count에 포함되지 않는다.
4. **AC-172.4**: 내부 선정/생존/fact 비율, 외부 포착률, 인간5/5 비율의 분모가 별개다. source-limited 내부 1/1과 외부 baseline 부재, 정상0, 분류 실패null, segment 제외를 정확히 표현하고 전체 포착 성공을 발명하지 않는다.
5. **AC-172.5**: schema 3 preview에서 실제 finalizer의 sealed text/HTML/digest/notification/follow-up을 검토한다. 신규 publish/notify/production ledger/cursor write 0, 추가 LLM stage 0이며 code와 data baseline SHA/hash가 맞는다.
6. **AC-172.6**: ready 시장 allowlist, 실제 release 지시, reviewed code/policy/rollback snapshot이 각각 필요하다. 불합격·미검수 시장을 active로 승격하지 않으며 operator exception은 점수를 변경하지 않는다.
7. **AC-172.7**: 시장별 최초 3회 실제 예약 게시·Telegram·해당 SHA Pages와 remote ledger/cursor가 확인되어야 해당 시장은 accepted다. rollback rehearsal은 schema 2 전체 복귀·기존 archive 불변·auth/side-effect 연결을 입증한다.
8. **AC-172.8**: private evidence와 budget/performance 규칙을 지킨다. 기존 source/body/cursor gates 및 숫자·entity·compliance·seal·부분발행 invariants를 그대로 통과하며 미측정 성능은 pending으로 보고한다.
9. **AC-172.9**: 세 시장 모두 accepted, 최소 10회의 서로 다른 실제 v3 예약 발행과 부분 실패의 정확한 집계, 별도 reviewed cleanup을 완료해야 전체 프로그램은 cleanup_complete다. final runtime의 기본 schema 3/정상 v3 생성, legacy generator/자유 section string/빈 bridge/활성 rewrite 제거, retired-policy 명시적 거부, immutable archive parser 유지, prior reviewed commit/policy 전체 rollback을 증명한다.

# Functional Design: u173 공식 사건 source-slot 자격 검증

**Date**: 2026-10-10 KST. **Status**: Functional Design / NFR Requirements 초안. qualification 결과와 신규 adapter를 작성한 상태가 아니다. **Priority**: P1. **Baseline**: `19c89b92`.

## 문제와 목표

사건 설명에 필요한 결정 내용, 실적 actual/guidance, 국내 공시의 실제 조치가 기존 feed의 제목이나 접수 목록만으로 확보되는지 명확하지 않다. HTTP 200, 공식 도메인, source 개수, 과거 feed 성공만으로 본문 권리와 fact 완결성을 인정하면 얕은 근거를 정상 supported 사건으로 승격하게 된다.

정책·실적·국내 공시의 이름 있는 source-slot을 조사하고 각 경로를 **verified 또는 blocked**로 판정한다. 접근, 공개 사용 범위, 실제 schema, 주장 locator, 사건별 핵심 슬롯, 시간 정밀도와 v3 typed chunk 매핑을 함께 확인한다. 동작하는 provider, 권리, 파서나 운영 복구를 설계만으로 발명하지 않는다. 전부 blocked인 결과도 근거가 정확하면 qualification 작업의 유효한 완료이며, source 확보 또는 운영 복구 완료는 아니다.

## 기존 증거와 중복 경계

- `ops/event_source_qualification.json`은 u161의 body HTTP 자격에 대한 단일 runtime manifest다. 2026-09-26 검증에서 `fomc-rss` / `fed-speech-rss` / `cftc-policy-rss`의 특정 official body family는 qualified였고 `sec-newsroom-rss` 본문은403으로 blocked였다. 이 과거 snapshot을 오늘의 접근 성공이나 모든 path의 권리로 확대하지 않는다.
- Fed 발표 `/newsevents/pressreleases/`와 발언 `/newsevents/speech/`의 Board 작성 본문은 기록된 범위만 재사용한다. testimony, 첨부물, 이미지/로고, third-party material은 별도 qualification 없이는 범위 밖이다. CFTC도 `/PressRoom/PressReleases/` 범위만 가진다. 실제 selector는 `fed-article-body-v1`, `cftc-press-article-body-v1`이다.
- u161의 `korea-policy-rss` HTTPS/`dc:date` 수리는 완료했다.10월9일 source reliability의 upstream503은 별도 상태다. `cnbc-top-news`403, Yahoo 뉴스404, failed/zero/skipped 표현은 u165가 소유한다. u173은 이 이름 아래 다른 언론을 끼워 넣거나 복구 성공을 선언하지 않는다.
- `sec-edgar-8k`는 8-K Atom metadata, `sec-company-facts`는 watchlist의 bounded submissions/XBRL actual이다. SEC newsroom body 403을 이 API 전체의 실패로 일반화하지 않으며, API actual이 earnings release의 guidance나 해당 발표 시점을 보장한다고도 해석하지 않는다.
- `dart-disclosure`는 `report_nm` 키워드로 buyback/dividend/capital_change/ownership_change를 제한하는 접수 목록이다. 현재 summary는 보고서 이름과 접수번호다. 금액·변경 전후 조건·공시 본문을 확보했다는 증거가 아니다. `nasdaq-earnings-calendar`도 actual/estimate/guidance 역할은 실제 필드로 판별하며 calendar 존재만으로 실적 결과 사건을 생성하지 않는다.

근거: [u161 source qualification](../u161-bounded-official-event-evidence/evidence/source-qualification.md), [기존 runtime manifest](../../../ops/event_source_qualification.json), [source reliability 점검](../source-reliability-20261009/review.md), `src/investo/_internal/source_specs.py`, `sources/event_evidence.py`, `sources/sec_edgar_8k.py`, `sources/sec_company_facts.py`, `sources/nasdaq_earnings_calendar.py`, `sources/dart_disclosure.py`. 실제 새로운 qualification 시 현재 공식 문서와 endpoint를 다시 확인한다.

## Canonical owner와 의존성

| 경계 | Owner / 정확한 경로 |
| --- | --- |
| 기존 adapter 등록·tier·routing·window | `src/investo/_internal/source_specs.py` / `sources/_registry.py` 유지 |
| 기존 body HTTP 자격과 제한 | `src/investo/models/enrichment.py::SourceQualification/EnrichmentPolicy`, `ops/event_source_qualification.json` 유지 |
| 새 source-slot 판정 DTO | `src/investo/models/enrichment.py::SourceSlotQualification/SourceSlotQualificationSet` 확장 예정 |
| Qualification-only 자료 | `ops/event_source_slot_qualification.json` 예정; runtime routing registry가 아님 |
| Bounded evidence loader / chunk 매핑 | `src/investo/sources/event_evidence.py`, u167의 `src/investo/models/event_context.py` 타입 소비 |
| 독립 판정 자료 검사 | `scripts/check_event_source_slots.py` 신규 offline 도구 예정 |
| Private 원문과 현재 probe 증거 | ignored `.tmp/event-news-v3/source-qualification/`, 공개 요약은 `aidlc-docs/construction/u173-official-event-source-slot-qualification/evidence/` 예정 |

u167은 typed chunk 출력 통합의 hard dependency다. 현재 공식 증거 탐색·기존 파서 진단·권리 확인은 u167 전에도 수행할 수 있다. u172의 사람 의미 점수와 이 source qualification은 독립 실행/결과다. u169 문서 렌더링, u170 story, u171 consumer, u160 cursor activation은 이 qualification의 통과 조건이나 자동 활성화 결과가 아니다.

## 이름 있는 source-slot matrix

| Slot ID | 기존 source / 조사 경로 | 실제로 확인할 최소 내용 | 현재 설계의 판정 경계 |
| --- | --- | --- | --- |
| `policy.monetary_decision` | `fomc-rss`, 기존 qualified Fed body family | 결정 주체·방향·규모 또는 범위·발표일, 기간/단위, 원문 locator | 과거 family qualification 재사용 가능. 현재 path/parser/필수 슬롯은 재확인 |
| `policy.official_statement` | `fed-speech-rss`, 기존 qualified Fed speech | 발언자·직책/대상·핵심 인용 주장·발언/보도시점 | 발언을 사실 또는 정책 결정으로 승격 금지. testimony body는 미자격 |
| `policy.regulatory_action` | `cftc-policy-rss`, `sec-newsroom-rss`의 기존 feed와 직접 연결 body | 시행/제안/합의/조치 상태, 적용 주체와 범위, 발표/효력 시점 | CFTC body의 과거 scoped 자격과 SEC body403 blocked를 별개로 보존 |
| `policy.domestic_announcement` | `korea-policy-rss` FSC feed | 정책 발표의 실제 조치·범위·발표 날짜 | feed 수리 완료와 현재503을 분리. 새 FSC body는 별도 path/권리/parser 필요 |
| `earnings.reported_actual` | `sec-company-facts`, `sec-edgar-8k` metadata와 직접 연결 공식 filing/issuer 경로 | 회사·발표/접수 문서·회계기간·actual·단위·정정 여부 | API actual과 발표-event 연결을 검증.8-K metadata만으로 값 생성 금지 |
| `earnings.guidance` | 위 문서의 공식 release/exhibit 또는 issuer 원문 후보 | 회사·전망 기간·guidance 내용·actual과의 구분·주장 locator | 기존 일반 body 허용목록 밖. 각 새 path/issuer 권리가 미확인되면 blocked |
| `domestic.disclosure_action` | `dart-disclosure` 접수 API와 공식 직접 연결 공시 경로 | 회사·조치 종류·상태·source에 있는 금액/조건·접수일/효력일 | 기존 목록은 discovery 근거. 공시 본문/새 API/path는 별도 qualification |
| `earnings.schedule_context` | `nasdaq-earnings-calendar` 기존 JSON | 회사·발표 예정 날짜/버킷·estimate/actual의 명시된 역할 | supporting calendar slot. 실제 결과/guidance source로 자동 승격 금지 |

CNBC/Yahoo 등 commercial media body는 이 공식 matrix의 대체 경로가 아니다. 기존 feed 항목은 기존 규칙으로 소비할 수 있지만 신규 commercial body HTTP는 권리/접근 미확인 blocked로 둔다. 신규 한국은행 RSS, issuer별 provider나 DART 추가 API는 명시된 후보로만 조사하며, 채택하려면 별도 adapter·등록·비용·권리 계획이 필요하다.

## 고정 DTO / 판정 계약

`SourceSlotQualificationSet(schema_version=1,records)`는 최대 64개의 frozen row로 구성하고 serialized JSON 최대 64KiB다. `(source_name 또는 proposed_source_name, slot_id, access_kind, endpoint_scope)`는 유일해야 한다. 기존 경로는 SOURCE_SPECS의 정확한 `source_name`과 `proposed_source_name=null`을 사용한다. 새 provider 후보는 `source_name=null`, 명시적인 `proposed_source_name`으로만 기록하며 기존 등록 이름으로 가장하지 않는다. 두 name 중 정확히 하나만 값이 있어야 한다.

`EndpointScope(scheme=https,host,path_prefix,query_keys)`는 literal 공식 host/path와 허용 query 이름의 닫힌 tuple을 저장한다. 실제 키/개인 query 값은 저장하지 않는다. private/local host, credential 포함 URL, path escape를 거부한다. official body row는 query 없는 기존 u161 scope를 유지하고 API의 query 이름을 body 허용목록으로 확대하지 않는다. 이 타입의 owner도 `models/enrichment.py`다.

`SourceSlotQualification` 필드는 다음과 같이 고정한다.

- `source_name|null`, `proposed_source_name|null`, 위 matrix의 8개 닫힌 `slot_id`, `access_kind=feed|structured_api|official_body`, typed `endpoint_scope|null`, `official_discovery_url|null`, `checked_at`(UTC), source 코드 SHA 및 parser version. blocked의 미확인 discovery/path는 null이며 verified는 둘 다 필요하다. 시각은 timezone-aware UTC, SHA/hash는 실제 40자리 commit/64자리 SHA-256 형식을 검증한다.
- `status=verified|blocked`, `reason_codes`, `access_evidence_hash|null`, `rights_evidence_url|null`, `rights_scope|null`, `schema_fixture_sha256|null`, `parser_version|null`, `required_slots`, `verified_slots`, `missing_slots`, `chunk_roles`, `time_precision`, `public_locator_basis|null`.
- `runtime_probe_status=verified|blocked|not_run`, `runtime_evidence_ref|null`, `activation_ready=false`가 default다. 로컬 probe로 runtime/GHA 접근을 통과했다고 기록하지 않는다. qualifier가 activation_ready를 env로 변경할 수 없다.
- closed `reason_codes`는 `access.denied|access.unavailable|access.not_verified|rights.unknown|rights.out_of_scope|schema.unknown|schema.mismatch|slot.required_missing|time.unknown|locator.missing|runtime.not_verified|candidate.new_provider`다. blocked는 최소 1개 실제 이유가 필요하며 raw 예외/본문/키를 reason에 넣지 않는다. event 시간 unknown이 합법적인 slot의 경우 time.unknown은 제한 이유로 남기되 자동으로 사실 오류로 취급하지 않는다. runtime.not_verified는 runtime readiness 제한이며 로컬 slot 자격 판정과 분리한다.

verified는 현재 authorized access, scoped public rights, 실제 schema/private fixture, 버전 있는 유일한 parser region, 모든 required slots, 전달 buffer의 ref/locator 검증이 모두 충족된 경우다. 실제 required slot 부재는 blocked다. unknown time은 역할과 precision을 보존하는 조건으로 허용하고, 필수 fact의 부재와 혼동하지 않는다. 조사가 없으면 `blocked/access.not_verified`이며 synthetic 성공만으로 verified가 되지 않는다. 전체 source 상태와 각 slot 상태는 동일하지 않다. 동일 source의 actual slot verified/guidance slot blocked를 표현할 수 있다.

`required_slots`는 다음 최소 집합을 고정하고 row 작성자가 빈 목록으로 줄일 수 없다. 정책 결정은 actor/decision/size_or_scope, 공식 발언은 speaker/quoted_claim, 규제 조치는 authority/action/action_status/target_scope, 국내 정책은 authority/action/target_scope, 실적 actual은 issuer/metric/actual_value/unit/period/filing_locator, guidance는 issuer/guidance_claim/guidance_period, 국내 공시는 issuer/action/action_status/action_terms/filing_locator, 실적 일정은 issuer/scheduled_date/report_bucket이다. 국내 action_terms는 실제 조치의 source-backed 규모/조건/변경 내용이며 보고서 이름과 접수번호만으로 충족하지 않는다. 원문에 없는 필수 내용을 확보하지 못하면 blocked다. 명시된 금액/이전 값/예상 값이 있는 경우 각각의 status/unit/period를 보존하되 존재하지 않는 비교값은 요구하거나 생성하지 않는다. `missing_slots=required_slots-verified_slots`이며 verified는 missing_slots가 비어야 한다.

`verified` source-slot은 u161의 `qualified` body family와 다른 계약이다. 이 JSON을 `SourceQualification`으로 coercion하거나 기존 loader가 fallback manifest로 읽는 동작은 금지한다. body HTTP는 기존 `ops/event_source_qualification.json` + `EnrichmentPolicy.validate_activation()` + reviewed operational instruction을 그대로 요구한다. 새 source/path는 qualification 결과가 있어도 adapter 도입·runtime activation은 별도다.

## Typed chunk 매핑과 fixture

u167 C2의 `EventContextDocument/EvidenceChunk/ContextRef/EventTimeContext/EventSupportVector`만 출력 모델로 소비한다. source parser는 확인한 원문 위치와 문맥을 locator에 보존한다. `identity`는 actor/action/object, `fact`는 정책 결정·실적·공시 핵심 변화, `comparison`은 명시된 이전/예상/actual 구분, `background`는 원문의 배경, `meaning/reaction/follow_up`은 각각 해당 주장의 원문 구간에서 만든다. 없는 role은 빈 근거로 보존하고 제목을 의미/시장 반응으로 재분류하지 않는다.

- document당4 chunk, chunk당1..1200 codepoints, ref1..240codepoints, Stage1 전체24KiB와 v3 Stage2 protected16KiB를 유지한다. slot 개수가 실제 chunk/document 한도를 늘리지 않는다. 같은 문서의 여러 slot은 동일 document identity를 공유한다.
- `published/received`, filing 접수일, 회계기간, 결정/발언/시행시각을 구분한다. DART 날짜용 내부09:00KST나 Nasdaq calendar UTC midnight를 실제 사건의 exact time으로 복사하지 않는다. 날짜만 확인되면 date precision, occurrence가 없으면 publication_only/unknown이다.
- 공개 fixture는 `tests/fixtures/event_source_slots/`의 합성 구조·허용된 최소 요약으로 만든다. 실제 raw body/API payload/header와 모델 출력은 `.tmp/event-news-v3/source-qualification/`에서만 보존하고 `git check-ignore`로 확인한다. 공개 evidence에는 공식 discovery/path, 상태/byte/item count, 제한된 parser 결과와 hash만 남긴다. 키는 기존 secret 이름/연결 여부만 확인한다.
- 각 slot은 actual/forecast 바뀜, 단위/기간 변경, 동일 문서 수정, missing required field, 다중/누락 parser region, 잘못된 source/locator, denied/empty/partial/window 제한을 포함하는 양성/음성 fixture를 갖는다. parser fixture가 운영 복구 evidence로 집계되지 않는다.

## 단계 결정 / NFR Requirements

Functional Design / NFR Requirements는 **REQUIRED**다. 소스별 접근·권리·시간·핵심 fact와 typed context mapping을 이 설계로 검토한다. 기존 u161 외부 요청과 private fixture 구조를 재사용하므로 별도 배포 플랫폼은 도입하지 않는다. 새로운 adapter 또는 다른 infrastructure가 필요하면 이 qualification 결과를 입력으로 별도 설계한다.

- **NF-173.1**: 신규 body 요청은 기존 u161 max6 / concurrency2 / total20초 / request8초 / decoded500KiB / source당2 / redirect1 / retry0 안에서만 실행한다. qualification discovery/probe도 승인된 정확한 host/path와 bounded read로 기록하며 접근 우회, credential 추정, paid fallback을 하지 않는다.
- **NF-173.2**: 권리 근거는 해당 source/path/content/공개 사용 형태에 대응한다. 정부 도메인이라는 이유로 외부 저작물·첨부·이미지까지 허용하지 않는다. 기존 Fed qualification에서 보이는 범위를 일반 commercial/SEC body에 전파하지 않는다.
- **NF-173.3**: public raw body/secret/private payload 0, 추가 runtime LLM 0, adapter registration 변경0, schema2 fetch/order/serialization 변경0이다. qualification-only script는 network/generation/publication/cursor를 호출하지 않는다.
- **NF-173.4**: 정책 슬롯, 실적 슬롯, 국내공시 슬롯 각각의 충분한 actual 내용과 runtime 접근을 별도로 보고한다. 모든 blocked 이유를 유지하며 사람 semantic score, included market metric, external recall에 source qualification을 합산하지 않는다.

## 수용 기준

1. **AC-173.1**: matrix의8개 named slot과 각 source/path에 current evidence reference, verified 또는 blocked, exact reason이 있다. 과거 Fed/CFTC qualified 범위, SEC/commercial body blocked, 기존 API/feed와 신규 body 후보를 구별한다.
2. **AC-173.2**: verified row는 actual access/rights/schema/private fixture/required slots/ref locator를 모두 만족한다. 권리 또는 required slot이 unknown이면 blocked이며 HTTP200·공식 host·synthetic parse만으로 verified가 되지 않는다.
3. **AC-173.3**: 독립 offline checker가 duplicate/unknown slot/source, verified의 missing evidence, scope/rights/hash 불일치, forged verified, raw exception reason을 거부한다. 실제 access/rights/schema 미확인과 null을 정확하게 나타낸 blocked row는 유효한 판정 자료로 통과하지만 source-ready 수에는 포함되지 않는다.
4. **AC-173.4**: u167 chunk mapping에서 actor/action/fact와 meaning/reaction/follow-up의 독립 source context, actual/forecast/period/unit, 시간 precision을 보존한다. runtime/library parser를 재생하며 지원하지 않는 슬롯을 생성하지 않는다.
5. **AC-173.5**: 등록44개/정확한 source identity/tier/routing/window와 기존 v2 bytes가 유지된다. 새 issuer/body/API/provider가 필요하면 qualified 조사 결과와 별도 adapter/등록/secret/cost/license/consumer 계획을 handoff하며 몰래 도입하지 않는다.
6. **AC-173.6**: slot verified로 HTTP capability, enrichment mode, production pin, u160 cursor, u172 human score가 변경되지 않는다. enrichment failure는 원래 feed item을 삭제하지 않으며 source unavailable과 주요 사건 없음은 구분된다.
7. **AC-173.7**: raw/private/secret public 유출0, 요청·크기·chunk/전송 budget 및 redirect/SSRF negative를 통과한다. GHA/not_run을 live recovery로 표시하지 않는다.
8. **AC-173.8**: 최소 정책/실적/국내공시 family의 ship-existing/defer-new/blocked 결론과 후속 owner가 명시된다. 전부blocked여도 qualification 완료로 기록 가능하나 source 확보/운영 활성화/복구는 pending으로 유지한다.

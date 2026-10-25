# u180 공개 인사이트 스냅샷·이력·게시 기반 — Business logic

작성일: 2026-10-12 · u180 · 상태: 사용자 “유닛 하나씩 진행시켜” 지시로 설계 채택, 로컬 구현·검증 진행. 공개/운영 활성화는 pending.

## 목표와 사용자

현재 수집 결과의 숫자·일정을 독립 typed snapshot 으로 검증하고 제한된 이력과 화면 파일을 원격에 일관되게 게시한다. 시황 LLM 실패와 데이터 dashboard 결과를 구별한다.

사용자: P1 운영자/개인 투자자, P2 인증 없는 공개 독자. US-011/012/013 와 FR-026; 기존 FR-001/003/005/006/010/011/017/021 를 구현할 후속 기준이다. 기술 단계와 public 데이터/화면/운영 수용은 구별한다.

## 책임과 선행 조건

기존 u102 source registry, u113 scoped publish, u144 sealed/public boundary, u155 private runtime, u164 temporal truth, u165 source lifecycle. 새 화면 및 event/news v3 미완료를 prerequisite 로 추가하지 않는다.

구현 범위: models/insights.py, models/insights_calendar.py, models/items.py 의 선택 envelope 와 serializer, models/results.py 의 optional insights 결과; sources/_window.py 및 aggregator.py 의 default-false opt-in; orchestrator/insights.py/insights_projection.py/insights_publication.py 와 CollectStage handoff; publisher/insights/__init__.py/store.py; ops/insights_source_qualification.json 의 검증 타입·loader; __main__.py 의 optional GHA output 및 ops/private-runtime/production-briefing.yml Pages 신호 연계; 신규 공통 tests.

제외 범위: 원천별 metric parser, 신규 source/secret/HTTP/scheduler, standalone 모듈 UI, event/news ledger/cursor, u145 store, 기존 archive/LLM finalizer, Telegram 추가 발송, production activation.

## 데이터 흐름과 행동


1. run input 에 mode 와 허용 module IDs 를 freeze 한다. mode off 는 collect 옵션·기존 결과를 그대로 반환한다. report/callback 없이 items 만 주입하는 DI 경로는 source truth 를 invent 하지 않는다.
2. collection 을 1 회 수행하고 동일 run_started_at/collection_completed_at 를 기록한다. CollectStage 의 legacy 와 news-active 분기를 모두 연계한다. `_stage_collect`가 empty 를 검사하기 전에 report 를 받을 선택적 private report_sink 를 추가하여 실패/zero outcome 도 capture 한다. 기존 tuple/callable shape 는 보존한다.
3. private envelopes 만 분리하고 기존 item 복사본의 envelope 를 None 으로 만들어 enrichment/LLM/기존 source-health/anchor consumers 에 전달한다. 모듈별 envelope owner·metric definition·time·unit·값·권리를 검증한다.
4. same-remote-baseline 의 이전 manifest/current/history 를 읽는다. missing/unknown/pending local 파일을 성공 baseline 으로 쓰지 않는다. 신규 검증 자료와 유효한 last-good 만으로 module 을 구성한다.
5. mode shadow 는 immutable 검토 결과와 bounded counts/reasons 만 반환한다. active 는 모듈을 완성한 뒤 local staging, manifest 결속, scoped receipt publication 을 수행한다.
6. dashboard remote-confirmed/failed/unknown 결과는 stage output 에서 run result 로 보존한다. 이후 LLM 오류를 dashboard rollback 사유로 삼지 않고, 기존 시황 failure/partial 여부는 기존 규칙으로 반환한다.
7. 모듈 내부 source 실패는 사용 가능한 sibling 값을 유지한다. storage/CAS 문제가 생기면 해당 dashboard promotion 을 중단하며 기존 시황 publisher 는 기존 snapshot/metadata 를 이어받는다.


## 실패와 대체

[공통 계약](../../public-insights-20261012/contracts.md)의 C2–C7 을 적용한다. available 숫자·일정에 없는 time/period/단위/원천을 발명하지 않는다. 해당 source 실패·미확인·key 없음은 해당 card/module 의 명시된 상태와 유효 last-good 로 표현하며 정상 sibling 을 유지한다. 권리가 미확인/철회된 숫자는 current/history 에 포함하지 않는다. LLM text 또는 다른 source 의 유사 제목으로 채우지 않는다.

## 수용 시나리오

[시나리오 목록](../../public-insights-20261012/acceptance-scenarios.md)과 [실행 계획](../../plans/u180-public-insights-snapshot-and-publication-code-generation-plan.md)의 numbered AC 를 함께 따른다. 현재 문서 작성은 제품 test/pass 결과가 아니다.

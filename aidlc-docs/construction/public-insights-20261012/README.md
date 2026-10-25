# 공개 인사이트 u180–u183 유닛 설계

작성일: 2026-10-12. 기준: origin/main `55c00fc85e2828f62cd69d5583afd3761ef86d45`.

사용자 지시: “매크로 환경판 → 주요 일정 → 크립토 시장 내부 순서로 진행하자. 먼저 유닛 설계부터 진행해줘”. 세 제품과 순서를 선택하고 설계 문서화를 허가한 지시다. 초기 요청은 설계 범위였으며, 이후 “유닛 하나씩 진행시켜” 지시로 첫 u180의 로컬 구현·검증을 진행했다. 커밋/푸시·실서비스 배포·private runtime 변경·공개 메시지 발송은 수행하지 않았다.

## 유닛과 순서

| 유닛 | 소유 범위 | 선행 조건 | 산출물 |
| --- | --- | --- | --- |
| u180 public-insights-snapshot-and-publication | typed 관찰 입력, 시간/단위/권리, 제한된 이력, 원격 확정 게시, 기존 수집 연계 | 기존 u102/u113/u144/u155/u164/u165/u176 계약 재사용 | 공통 데이터·저장·게시 foundation |
| u181 macro-environment-dashboard | 13 개 macro metric 정의·원천 매핑·계산·화면 | u180 구현 | `/insights/macro/` 및 대시보드 진입 |
| u182 upcoming-events-dashboard | 7/30 일 공식 일정, 정확한 시각/날짜, 기간·중복·필터 | u180/u181 구현 | `/insights/calendar/` |
| u183 crypto-market-internals-dashboard | 7 개 crypto metric, 거래소/계약/주기·조회 관찰, 조건부 카드 | u180/u181/u182 구현; 소스별 공개 표시/이력 조건 | `/insights/crypto/` |

권장 실행 순서는 **u180 → u181 → u182 → u183**다. u182/u183 의 화면 로직은 서로 독립적이지만 사용자 지정 순서에 따른 전달 의존성을 등록한다. v3 u168–u173 완료를 세 화면의 선행 조건으로 추가하지 않는다. 사건 추적·선물 포지션·섹터 이력은 이번 네 유닛에서 제외한다.

## 설계 상태

네 유닛의 Functional Design·focused NFR·코드 실행 계획·수용 시나리오를 작성했다. 사용자 후속 진행 지시로 u180 설계를 채택하고 로컬 구현·검증 **7/8**을 마쳤다. [u180 결과](../u180-public-insights-snapshot-and-publication/code/summary.md). Step 8의 실제 source qualification·private pin/mode·Pages·5회 예약 실행은 모듈 구현 이후 운영 수용이다. u181도 2026-10-25 후속 지시로 로컬 구현·검증7/8을 마쳤다. [u181 결과](../u181-macro-environment-dashboard/code/summary.md). u182도 2026-10-25 로컬 구현·검증6/7을 마쳤다. [u182 결과](../u182-upcoming-events-dashboard/code/summary.md). u183도2026-10-25 로컬구현·검증7/8을마쳤다. [u183 결과](../u183-crypto-market-internals-dashboard/code/summary.md). 요청한세화면의로컬구현을마쳤고운영수용은별도다.

각 유닛의 상세 링크:

- [u180 공통 기반](../u180-public-insights-snapshot-and-publication/functional-design/business-logic-model.md), [실행 계획](../plans/u180-public-insights-snapshot-and-publication-code-generation-plan.md)
- [u181 매크로](../u181-macro-environment-dashboard/functional-design/business-logic-model.md), [실행 계획](../plans/u181-macro-environment-dashboard-code-generation-plan.md)
- [u182 주요 일정](../u182-upcoming-events-dashboard/functional-design/business-logic-model.md), [실행 계획](../plans/u182-upcoming-events-dashboard-code-generation-plan.md)
- [u183 크립토](../u183-crypto-market-internals-dashboard/functional-design/business-logic-model.md), [실행 계획](../plans/u183-crypto-market-internals-dashboard-code-generation-plan.md)

[공통 계약](contracts.md), [현재 소스 판정](source-assessment.md), [수용 시나리오](acceptance-scenarios.md), [설계 검토](review-record.md).

## 기획에서 구체화한 결정

1. 기존 collection 결과를 한 번 소비한다. 화면별 fetch 나 새 polling/scheduler 를 만들지 않는다.
2. 활성 모드에서는 collection 후·LLM 전 dashboard phase 가 독립적으로 검증·게시된다. 이후 시황 생성이 실패해도 확인된 dashboard publication 은 남는다. 시황 실패 상태를 success 로 바꾸지 않는다.
3. 소스 어댑터는 opt-in typed side channel 만 추가한다. 뉴스/시황에 전달하기 전에 이를 제거하여 기존 LLM 입력·기본 직렬화·source tier·window·legacy public payload 를 보존한다.
4. 현재 값부터 공개한다. 이력이 부족하면 변화를 계산하지 않는다. 월별 CPI 지수, 주기별 펀딩, 조회 시점 TVL 을 서로 다른 의미로 표현한다.
5. 원천의 공개 표시와 이력 허용 조건이 검증된 카드만 게시한다. 수집 성공·무료 접근·u145 의 Yahoo 예외는 이 조건을 대신하지 않는다.
6. 일정은 처음에 예정 조회만 제공한다. schedule/actual 연결·발표 완료·consensus/surprise 는 제외한다.

## 기존 유닛과 중복 대조

| 기존 owner | 재사용 | 새 유닛에서 하지 않는 일 |
| --- | --- | --- |
| u145 | 기존 분야별 레이더 링크, 제한 공개와 last-good 의 원칙 | 레이더 source/store/schema·국면·순위 변경 |
| u35/u43/u59/u105 | 이미 수집되는 공식 일정과 actual 메타데이터 | 새 calendar 어댑터·가짜 발표 결과·carryover 재구현 |
| u151 | macro 와 positioning 의미 구별 | CFTC 를 현물 수급으로 표시 |
| u164 | source vs 조회 시각과 nullable 숫자 원칙 | crypto price 과거 복원·Demo 키 활성화 |
| u165 | ok/zero/failed/skipped 상태와 default source policy | 새 adapter registry·소스 장애 복구 완료 선언 |
| u144/u113 + publication receipts | immutable 입력·scoped git·원격 확인·부분 실패 | LLM finalizer 우회·sealed 본문 수정·event ledger 변경 |
| u176/u178 | MkDocs 메뉴·토큰·테마·키보드·모바일 표준 | 홈 재설계·전역 테마 재작성 |
| u169/u170/u171/u172 | sealed 시황의 기존 URL 연결 | 새로운 사건 모델·자산 영향·semantic cutover |

2026-10-11 기획과 증거는 [원 기획](../../../docs/planning/public-insights-roadmap-20261011.md), [기록](../../../docs/planning/public-insights-evidence-20261011.json)에 보관한다. 당시 10 개 날짜의 수집 기록은 최신 SHA 의 운영 수용 시험으로 간주하지 않는다.

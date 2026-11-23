# DART 일정 정정 양식 — u173 Step4 / u184 Step5

사용자 “그거부터 진행”을 보관된 새 정정표의 분석·지원 판정과 bounded 구현 승인으로 적용한다. 기존 유닛의 후속이며 새 유닛을 만들지 않는다.

## Stage Decision

Functional Design/NFR Requirements는 아래 기존 계약의 양식별 구체화로 이 문서에서 완료한다. FR-001/017/024, NFR-002/003/005/006/008, 기존 DART parser/공통 준비 설계를 재사용한다. 새로운 HTTP·권한·모델·게시 경로는 없다. 별도 NFR/Infrastructure Design은 생략한다.

## 지원 계약

- 기존 `dart-cb-correction-6.4-v1`과 기본 `parse_dart_document`는 가격 정정용으로 유지한다. 새 `dart-cb-schedule-6.4-v1`은 명시적으로 호출하는 오프라인 진입점이며 기존 transport/slot matrix와 연결하지 않는다.
- 동일 11324/6.4/20260723 양식, 회사·공시·접수일·digest·current series·단위·예정 상태·ZIP/XML 예산을 재사용한다.
- 정정표는 만기일, 이자지급방법, 원금상환방법, 전환청구기간, 옵션, 납입일, 기타 참고사항의 정확한 7개 행만 허용한다. 정정 후 단일 current-body 필드와 일치해야 한다. 모르는 행·누락·중복·다른 차수·값 불일치는 거절한다.
- 기타 참고사항은 주1/주2의 전후 표시를 정확히 구분하고, 정정 후 9개 요소(P 7개/TABLE/P)의 순서·내용·표 구조가 같은 current-body 구간과 일치해야 한다. 주석을 무시하거나 문자열 일부만 일치시키지 않는다.
- 기사 입력은 issuer/action/status/filing과 발행총액·이사회일·만기/납입/전환청구기간의 정정 전후에 한정한다. 긴 이자·상환·옵션·주석은 전체를 대조하지만 projection에 넣지 않는다. `evidence_budget_limited=True`, 최대1,200자, field당16refs와 원문 locator를 유지한다. 날짜가 지났다는 이유로 발행/납입 완료로 승격하지 않는다.
- 실제 raw는 기존 ignored0700/0600 보관본만 읽는다. 공개 fixture는 독립 합성이며 공개 증거에는 count/hash/closed status만 기록한다. 새 HTTP/LLM/게시/알림/ledger/cursor0, 운영·source qualification 승격0.

## 실행

- [x] 1. 보관된 ZIP/hash와 7개 정정행 및 본문/주석 대응을 분석한다.
- [x] 2. 별도 version의 오프라인 parser와 합성 fixture, 변조/기본 경로 유지/PBT 회귀를 구현한다.
- [x] 3. 보관본의 5slot/XML/native refs를 재생하고 독립 검수·관련 품질 검사를 완료한다.
- [x] 4. support 판정·증거·session/cross-check/state/audit와 남은 운영 단계를 기록한다.

## 수용 한계

오프라인 성공은 현재 source의 최신성이나 실제 모델 생성 성공을 뜻하지 않는다. runtime0/activationfalse·human0/12·v3예약0과 상위 u173/u184 미완료를 유지한다. 새 버전의 source/transport 자격과 실제 공통 준비 연결은 후속이다.

## 최종 결과

이 하위 계획4/4 완료. 관련433tests/16.92초, 변경 범위 Ruff/format, 전체 소스 mypy384파일, 무료API/SDK guard, strictdocs5.71초, 독립 QA C/H/M/L0. 보관본5slot/22refs/76XML binding·661자/native3chunks 재생과 기존v1 byte 동등성을 확인했다. [검수표](../../../../docs/cross-checks/2026-11-23-dart-schedule-correction.md).

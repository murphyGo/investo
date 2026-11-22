# DART 일정 정정 양식 지원

보관된 새 양식의 분석과 별도 오프라인 파서 구현을 완료했다. 기존 u173 Step4/u184 Step5의 후속이며 실제 운영 연결은 아직 완료하지 않았다.

## 분석과 구현

사용자 “그거부터 진행”에 따라 11월 21일 보관본을 읽었다. 기존 가격 정정용 파서는 정확히 다른 7개 행을 거절하고 있었다. 새 양식은 납입일·만기·전환청구기간과 관련 조건의 일정 정정이다. 6개 행의 정정 후 값은 같은 발행 차수의 본문 필드와 대응하며, 나머지 행은 별도 정정 후 주석 9개 요소로 연결된다. 그 주석의 순서·내용·표 구조도 같은 본문 구간과 일치했다.

`src/investo/sources/_dart_document.py`에 명시적인 `parse_dart_schedule_document`와 `dart-cb-schedule-6.4-v1`을 추가했다. 기존 기본 진입점과 transport는 가격 정정 v1을 계속 사용한다. 새 파서는 정확한 7개 행·필드 유일성·같은 본문 표·정정 후 값·날짜·주석 전체를 확인한다. 불일치/누락/미지원 양식은 닫힌 오류로 거절한다.

기사 입력에는 회사·조치·상태·접수번호와 발행총액·결정일·만기/납입/전환청구기간의 전후 값만 넣는다. 긴 이자/상환/옵션/주석은 일치를 검증하지만 전달하지 않는다. `evidence_budget_limited`와 1,200자·slot별16refs 한도를 유지한다. 발행 예정 상태를 완료로 바꾸지 않는다.

## 검증

보관된 5개 private 파일의 hash와 원문 XML hash를 확인했다. 새 파서의 필수5slot·22refs·76XML binding을 원문 위치로 역검증했고, 661자 projection의 native3chunks에서도 모든 ref 값이 일치했다. 새 HTTP/모델 호출은 없었다. [기계 증거](../../aidlc-docs/construction/event-v3-acceptance-20261028/dart-schedule-20261123/evidence.json).

별도 검수에서 발견한 Medium2건을 고쳤다. 페이지 구분 뒤/태그 사이의 조건을 버리지 않도록 mixed text를 거절했고, 평탄화한 표 순서가 같아도 부모·자식 구조가 다르면 거절한다. 관련 회귀와 독립 검수 결과는 [검수표](../cross-checks/2026-11-23-dart-schedule-correction.md)에 기록한다. 새 테스트의 순수 변환 속성 검증은 유효 날짜23개와 본문만 변조한 날짜27개를 다룬다.

최종 관련433tests/16.92초(신규49cases), 변경 범위 Ruff/format, 전체 소스 mypy384파일, SDK/유료API guard, strict MkDocs5.71초와 diff-check가 통과했다. 최초 전체 mypy는 진단용 가상환경에 다른 BTC 작업의 websockets가 없어 실패했으나, 해당 의존성이 이미 설치된 프로젝트 `.venv`에서384파일을 다시 검사해 통과했다. 환경 의존성을 임의로 변경하지 않았다. 전체 pytest/원격 CI는 실행하지 않았다.

기존 가격 정정 fixture의 item/context 직렬화·refs·XML bindings가 변경 전과 동일하다. 기존 ops 자격표·transport·가격 fixture hash를 보존했고, 기본 파서는 새 양식을 계속 거절한다. 새 공개 fixture는 가상의 회사/조건으로 독립 작성했으며 실제 원문·회사·조건값은 공개 문서나 fixture에 복사하지 않았다.

## 변경 파일과 다음 단계

- 코드: `src/investo/sources/_dart_document.py`
- 합성 검증: `tests/fixtures/dart_document/cb-schedule-6.4.xml`, `tests/unit/sources/test_dart_schedule_u173.py`
- 계획/증거: `aidlc-docs/construction/event-v3-acceptance-20261028/dart-schedule-20261123/`
- 상태/감사 및 기존 u173/u184 계획에 이번 하위 단계 결과를 추가했다.

다음은 새 parser/fixture/version에 한정한 source qualification과 공통 준비 경로 연결, 정확한 전달 코드의 CI 및 실제 비게시 검증이다. 과거 clock의 보관본 재생은 현재 최신성이나 runtime 수용이 아니다. 기존 local3/8·runtime0·activationfalse·human0/12·v3예약0과 상위 유닛 미완료를 유지한다. 이 단계에서 commit/push/배포/핀 변경/게시/알림은 하지 않았다. 새 기술부채는 없다.

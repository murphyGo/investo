# DART 공통 준비 경로와 관측 최신성

사용자의 “진행해줘”로 u173 Step4/u184 Step5의 [계획](../../aidlc-docs/construction/event-v3-acceptance-20261028/dart-preparation-20261117/plan.md)을 진행한다. 기존 commit/push/private probe 승인을 적용한다. 다른 작업이 갱신한 main5ab1641a와 production3ce35148은 보존한다.

## 구현과 근거

수동 원문 parser를 별도 수집기로 복제하지 않고 prepare_event_evidence의 source HTTP owner에 연결했다. 기본값은 off이며 명시적 DART preview 선택·별도 transport 승인·slot matrix/hash/parser/fixture/code/rights 일치가 필요하다. 기존 HTML4종 policy JSON/hash와 Fed-only preview를 유지한다. 새 optional 필드와 false 차단 flag는 직렬화에서 생략한다.

고정 list.json의 last_reprt_at=Y·완전한 한 페이지·회사/공시/정규화 identity·정정/철회 표지를 먼저 검사한다. 통과해야만 같은 공시 document.xml을 요청한다. 정/철/누락/미지 상태는 닫힌 실패이며 다른 공시로 교체하지 않는다. 결과는 목록 수신 시점의 관측 검사일 뿐 API 간 atomic snapshot이나 현재 발행 완료를 보증하지 않는다.

공통 예산6HTTP/동시2/20초, GET8초·redirect/retry0·raw500KiB와 기존 ZIP/XML 한도를 적용한다. 새 무료 API/secret/SDK는 없다. Canonical secret filter를 HTTPX/httpcore에 idempotent하게 적용하고 전역 logger level은 바꾸지 않는다. 취소 시 task를 수거한다. 명시 경로의 검증 실패·지원 외·quota 밖 DART는 원래 legacy 값을 유지한 채 generic event_input_blocked로 classifier와 verified fact context에서 제외한다. 자료 부족 상태는 source_limited다.

원래 parser와29XML binding은 바꾸지 않았다. 25줄 field projection은 native passage 한도에 맞춰 LF만1:1 space로 바꾼 한 문단으로 재구성하고 새 revision/native2 context를 만든다. 원래 source locator별25ref 값을 다시 대조하며 policy/transport excerpt 상한을 넘으면 전체를 거절한다.

새 private 수동 workflow는 전용 REVIEWED_DART_PREPARATION_SHA만 사용한다. 한 회사/31일 이내의 bounded collection으로 원래 target과 별도 최신 지원 후보를 명시하고 같은 준비 경로를 호출한다. 최대5HTTP·공유20초, 모델/게시/알림/ledger/cursor0이다. ignored0700/0600·recipient preflight·ciphertext1일을 유지한다. 비용 영향은 기존 무료 OpenDART 최대5calls와 수동 Actions job1회다.

## 검증

관련 회귀338PASS/6.64초, Ruff/format874·source+script mypy373PASS. 독립 QA의 native locator 잘못 연결·excerpt 상한 누락·진단 JSON shape/deadline 영수증 오류를 수정하고 회귀를 추가했다. 마지막 독립 검수와 exact CI, 실제 source 결과는 후속 기록에 반영한다. 원격5ab의 visuals 변경을 fast-forward로 보존했다.

## 수용 상태

현재 local3/8·runtime0·activationfalse·human0/12·v3예약0이다. 공통 코드 연결이나 mock 성공만으로 runtime 자격을 승격하지 않는다. actual source·native 결과를 독립 검수한 후 별도 판정한다. u173/u184 전체, 다른5source·사람 인수·화면/성능·실제 기사·운영 전환은 잔여다.


## 독립 코드 검수 완료

별도 QA가 관련300PASS/5.83초·변경Python13파일 Ruff/format·mypy373·diff-check를 통과하고 C/H/M/L0으로 승인했다. 보관본의25refs/29XML→native1문단599자 재생도 통과했으며 새HTTP는0이다. 마지막 main 통합 후 format875와 무료API/SDK guard를 확인했다. exact CI 후에만 전용 private 진단을 실행한다.

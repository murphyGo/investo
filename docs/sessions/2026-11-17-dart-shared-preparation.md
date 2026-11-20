# DART 공통 준비 경로와 관측 최신성

공통 연결과 실제 차단 경계 검수는 완료했다. 새 정정표 후보는 지원 범위 밖이라 native0/runtime0이며 운영 전환은 미완료다.

사용자의 “진행해줘”로 u173 Step4/u184 Step5의 [계획](../../aidlc-docs/construction/event-v3-acceptance-20261028/dart-preparation-20261117/plan.md)을 진행한다. 기존 commit/push/private probe 승인을 적용한다. 다른 작업이 갱신한 main5ab1641a와 production3ce35148은 보존한다.

## 구현과 근거

수동 원문 parser를 별도 수집기로 복제하지 않고 prepare_event_evidence의 source HTTP owner에 연결했다. 기본값은 off이며 명시적 DART preview 선택·별도 transport 승인·slot matrix/hash/parser/fixture/code/rights 일치가 필요하다. 기존 HTML4종 policy JSON/hash와 Fed-only preview를 유지한다. 새 optional 필드와 false 차단 flag는 직렬화에서 생략한다.

고정 list.json의 last_reprt_at=Y·완전한 한 페이지·회사/공시/정규화 identity·정정/철회 표지를 먼저 검사한다. 통과해야만 같은 공시 document.xml을 요청한다. 정/철/누락/미지 상태는 닫힌 실패이며 다른 공시로 교체하지 않는다. 결과는 목록 수신 시점의 관측 검사일 뿐 API 간 atomic snapshot이나 현재 발행 완료를 보증하지 않는다.

공통 예산6HTTP/동시2/20초, GET8초·redirect/retry0·raw500KiB와 기존 ZIP/XML 한도를 적용한다. 새 무료 API/secret/SDK는 없다. Canonical secret filter를 HTTPX/httpcore에 idempotent하게 적용하고 전역 logger level은 바꾸지 않는다. 취소 시 task를 수거한다. 명시 경로의 검증 실패·지원 외·quota 밖 DART는 원래 legacy 값을 유지한 채 generic event_input_blocked로 classifier와 verified fact context에서 제외한다. 자료 부족 상태는 source_limited다.

원래 parser와29XML binding은 바꾸지 않았다. 25줄 field projection은 native passage 한도에 맞춰 LF만1:1 space로 바꾼 한 문단으로 재구성하고 새 revision/native2 context를 만든다. 원래 source locator별25ref 값을 다시 대조하며 policy/transport excerpt 상한을 넘으면 전체를 거절한다.

새 private 수동 workflow는 전용 REVIEWED_DART_PREPARATION_SHA만 사용한다. 한 회사/31일 이내의 bounded collection으로 원래 target과 별도 최신 지원 후보를 명시하고 같은 준비 경로를 호출한다. 최대5HTTP·공유20초, 모델/게시/알림/ledger/cursor0이다. ignored0700/0600·recipient preflight·ciphertext1일을 유지한다. 비용 영향은 기존 무료 OpenDART 최대5calls와 수동 Actions job1회다.

## 검증

관련 회귀338PASS/6.64초, Ruff/format874·source+script mypy373PASS. 독립 QA의 native locator 잘못 연결·excerpt 상한 누락·진단 JSON shape/deadline 영수증 오류를 수정하고 회귀를 추가했다. 최종 독립 검수와 exact CI, 실제 source 결과는 아래에 기록했다. 원격5ab의 visuals 변경을 fast-forward로 보존했다.

## 수용 상태

현재 local3/8·runtime0·activationfalse·human0/12·v3예약0이다. 공통 코드 연결이나 mock 성공만으로 runtime 자격을 승격하지 않는다. actual source·native 결과를 독립 검수한 후 별도 판정한다. u173/u184 전체, 다른5source·사람 인수·화면/성능·실제 기사·운영 전환은 잔여다.


## 독립 코드 검수 완료

별도 QA가 관련300PASS/5.83초·변경Python13파일 Ruff/format·mypy373·diff-check를 통과하고 C/H/M/L0으로 승인했다. 보관본의25refs/29XML→native1문단599자 재생도 통과했으며 새HTTP는0이다. 마지막 main 통합 후 format875와 무료API/SDK guard를 확인했다. exact CI 후에만 전용 private 진단을 실행한다.


## exact CI와 중단된 실제 진단

코드eff7b5c0의 [CI43915660414](https://github.com/murphyGo/investo/actions/runs/43915660414)는 Python3.11.9에서8,087PASS/1knownskip·562.90초, Node39·Ruff/format875·mypy371·모든 정책/strictdocs PASS다. 전용 private workflow0161839b와 REVIEWED_DART_PREPARATION_SHA=eff7만 추가했으며 기존4개 reviewed pin을 보존했다.

실제43917658215와 재측정44237332046은 workflow success였으나 daemon 중단과 재개 사이 각각1일 보관 암호문이 만료됐다. 로컬 원본·clock·native 대조가 없어 두 실행을 runtime 수용으로 세지 않는다. 후속 실측은0600 dispatch intent/run ID를 저장하고 동일run 재조회→bounded ciphertext 즉시 다운로드를 한 프로세스로 묶는다. source20초·최대5HTTP·모델/게시/알림0과 암호문1일 보관은 유지한다.


## 2026-11-21 실제 공통 경로 검수

실제44781000456은 동일eff7 코드와 private0161839b에서4GET/모두200·1.401445초로 끝났고, 즉시 암호문19,317bytes를0600으로 확보했다. collection1+enrichment3요청이며 두 후보를 구분한다. 원래20261027000337은last_reprt_at=Y 목록에서 빠져 latest_unavailable/missing, 원문0회다. 별도로 발견한20261029000461은 목록 시점as_observed를 통과했지만 원문이dart.correction_mismatch로 거절돼 evidence_invalid다. 입력2건 모두차단·enriched/native0·모델/게시/알림/ledger/cursor0이다.

새 ZIP은13,868/XML86,738bytes·974nodes다. source 수신clock/응답·XML hash와 native0·차단 상태를 보관본으로 재생했다. 이는 원문 HTTP200과 최신성 목록 통과만으로 기사 근거를 승인하지 않는 경계 검증이며 positive body/runtime 수용은 아니다. 기존parser를 완화하거나 정정 전 값/다른차수/새row를 임의 선택하지 않았다. 공개문서에는 count/hash/clock/closedcode만 남기며 원문은ignored0700/0600에 보존한다.

재시작 저장 도구는 별도 C/H/M0·합성저장복구8검사와 다른접수일/역순outcome의 positive mock 검수를 통과했다. unique temp/fsync/atomic replace, 암호문SHA+크기재확인, 동일원본의 partial capture/summary 복구와 재개 시POST0을 확인했다. group signal의 실제 sandbox 검사 제약은 통과로 세지 않았다. 별도 private artifact의1일 보관 정책은 그대로다.

판정은 **공통 live 연결 구현 통과·실제 차단 경계 검증 통과·positive runtime 미수용**이다. local3/8은 기존 과거 지원 양식 자격이며 canonical matrix/transport hashes는 바꾸지 않았다. 이번 최신 후보의 정정표 변형은 그 과거 자격을 소급 취소하거나 새 양식 자격으로 확장하지 않는다. runtime0·activationfalse·human0/12·v3예약0과상위u173Step4/u184Step5는미완료다. 다음 bounded 후속은 보관된 새 정정표 변형의 구조·필수field 일치 검수와 versioned parser 지원 판정이며, 새HTTP 없이 먼저 분석할 수 있다.


## 최종 독립 검수와 잔여

actual QA는 C/H/M0이다. collection25행·회사/날짜/유일성/정규화, 각GET8초·전체20초·실제clock/hash를 대조하고2outcome을정확한문서ID로재생했다. 실제prepareditems의 비게시preview도source_limited·모델0이었다. 새정정표는header포함8행/고유7행/중복0이며7행모두현재v1허용집합밖이라440행guard가정상거절했다. 날짜오탐이나native한문단변환오류가아니다. 원문/rowlabel/회사본문은공개하지않았다.

현재subplan6/6과main코드전달을마쳤다. 기존production3ce35148·preview7c5b8912·AI53037fc2·DARTqualification6ac 핀을보존하고전용preparation핀만eff7로남겼다. source/parser/policy의추가변경은없으며최종문서갱신때문에전체회귀를재실행하지않는다. [검수표](../cross-checks/2026-11-17-dart-shared-preparation.md)와기계증거에잔여를기록했다.

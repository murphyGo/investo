# 기사형 v3 실제 전달·원문 검수 — PARTIAL

전체 u171–u173/u184–u186 완료 승인이 아니다. [세션](../sessions/2026-10-30-v3-runtime-validation.md), [count/hash 증거](../../aidlc-docs/construction/event-v3-acceptance-20261028/runtime-20261030.json).

| 계약 | 실제 증거 | 판정 |
| --- | --- | --- |
| 검토한 변경 전달 | publica7e89802, exact CI40924747358 SUCCESS7679/1skip; 통합299/독립101 | 통과 |
| private 변경 범위 | 6446e077의 수동 DART workflow1개; 기존 daily/preview·queue:max 보존 | 통과 |
| 운영/preview 격리 | production91d5a4f3 보존, CI 후 preview만a7e89802로 갱신 | 통과 |
| DART 원문 접근 | HTTP200·1GET·ZIP13524/XML79039bytes·1file/980nodes/depth9, 응답/원본 hash 일치 | 진단 수집 통과 |
| DART 의미·필드 | 정정된 발행 결정/미래 계획; 5개 field 후보, 정정 후 열·locator·clock 구분 필요 | slot blocked 유지 |
| private evidence | 암호화 artifact1일, local0700/0600, raw/키 공개0 | 통과 |
| 실제 비게시 producer | 국내/미국/crypto 분류1/7/2·작성1/1/2; 각2calls 후 composition_invalid | 합격 증가0 |
| 실패 위치 대조 | 3batch schema PASS, 6call hash pairs PASS, names/귀속 precheck 차단 | 사람의 환각 판정과 구별 |
| 후속 코드 | 이름/이니셜의 같은 원문 결속·정확한 개념/관형형·문서 귀속 작성 지침·policy hash | 집중273/독립101·C/H/M0·Ruff/format852/mypy359 PASS; exactCI·새 실행 인계 |
| 원래 기록 재생 | Fed후보3개/20문장 precheck PASS, agentless crypto는 계속거절 | 녹화 검사; 새 모델/봉인 아님 |
| 실제 수용 | source2 verified/runtime0, DARTblocked, human0/12, v3예약0 | 기존 gate 유지 |
| viewport/성능/운영/cleanup | browserhost unavailable; 실제 측정/수용 미완료 | 미완료 |

후속 코드의 독립 검수·정확한 CI·실제 재생성은 완료한 증거에 따라 갱신한다. API200이나 작성 JSON 성공만으로 source qualification·의미 검수·봉인·운영 수용을 올리지 않는다.


## 2026-10-30 — 후속 CI와 두 번째 실제 preview

이니셜/문서 귀속 수정 `e5326119`를 전달했다. [정확한 CI41014464969](https://github.com/murphyGo/investo/actions/runs/41014464969)는 **7,720PASS/1knownskip/774.96초**이며, 로그 SHA와 prompt/stdout 및 artifact 해시는 [두 번째 실행 증거](../../aidlc-docs/construction/event-v3-acceptance-20261028/runtime-repeat-20261030.json)에 결속한다. CI 후 preview pin만 e5326119로 갱신했고 production91d5a4f3를 보존했다.

[실제 preview41022485896](https://github.com/murphyGo/automation-runtime/actions/runs/41022485896)는 2026-10-29 대상이다. 국내는 분류0·기사0인 source_limited/content_not_ready 안내 edition만 봉인했다. 미국은 분류1/작성1, crypto는 분류2/작성2로 각각 composition_invalid다. 전체 모델 호출은1/2/2이며 기사 합격·사람 인수·예약 실적 증가는0이다. 국내 빈 봉인을 기사 완성으로 세지 않는다.

기록된 입력/출력과 배정된 정확한 source refs를 대조하니 미국의 일반 유형 ‘은행지주회사’와 crypto의 통화명 ‘달러’만 기관명 검사에 걸렸다. 같은 주장 원문 구간에 연속된 bank holding company가 있거나, USD/dollar/dollars 또는 유효한 달러 금액이 있을 때 정확한 일반 명사만 인정하도록 수정했다. 서로 떨어진 단어 조합·원문에 없는 유형·합성 회사명과 $1INCH/$1000PEPE 등의 cash-tag는 계속 거절한다. 수치/발언 주체/문서 귀속 검증은 유지하고 policy hash를 갱신했다.

독립 QA **114PASS/1.63초·잔여C/H/M0**이며 이전 policy의 terminal/finalizer 거절을 확인했다. 두 번째 실행 후보3개/5문장의 녹화 precheck는 통과하지만 새 모델 review·봉인·사람 인수는 아니다. 최신 main91cbbb01의 별도 데이터 확장은 보존해 통합했다. 이 수정의 정확한 CI와 새 실제 preview는 아직 대기 중이다.

통합 후 집중 회귀는240PASS/4.66초, Ruff/format858·mypy363 PASS다. 10:37UTC 재확인에서 다른 작업의 production pin28170546이 관측되어 새 preview 단계에서는 이 값을 보존한다. 이전 실행의91d5a4f3 기록은 당시 값이다.

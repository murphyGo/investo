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

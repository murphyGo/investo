# 기사형 v3 입력 근거 후속 대조 — PARTIAL

2026-10-30. u184 Step5와 u172 실제 preview 실패 원인을 보완했다. 전체 유닛·운영 수용은 미완료다. [세션](../sessions/2026-10-30-event-v3-source-followup.md), [기계 증거](../../aidlc-docs/construction/event-v3-acceptance-20261028/followup-20261030.json).

| 대상 | 증거 | 판정 |
| --- | --- | --- |
| crypto 입력 누락 | 실제 기록 14건 재생, 승인 수령 hint 0→1, 원문 불변, 23,005/24,576 bytes | 코드 보완 통과; 새 모델 생성은 미실행 |
| 실제·예상·조건·귀속 | 승인 수령/출시 구분, future·부정·인용·긴 조건/줄바꿈과 강제 inner-span 음성 | 통과 |
| 미국 빈도 표현 | 원래 `Semiweekly` 양성, 근거 없는 `주 2회` 거절 | hard numeric gate 보존; 작성 지침 보완 |
| 국내 원문 접근 준비 | 공식 단일 endpoint·1회·시간/바이트/XML cap·no redirect, recipient 사전 검증·암호문 artifact | 합성 검증 통과; 실제 DART 미실행 |
| 키 부재 | 로컬 CLI exit1/credential_missing/HTTP0/원문 없음 | 통과 |
| 비공개 자료 | compressed/decoded key echo·unsafe ZIP/XML·HTTP 오류·경로 탈출 음성 | 통과 |
| 독립 검수 | 두 High 수정 후 118 tests 및 정적 검사 PASS, 잔여 C/H/M0 | APPROVE |
| 격리 검증본 | HEAD4cc54675 + 이번 작업 코드16개, 다른 세션의 소스 변경 제외 | 파일별 SHA로 결속 |
| 최종 정책·ZIP 제한 | 총17개 파일; STORED/DEFLATED만 허용, 알 수 없는 XML 인코딩의 닫힌 실패 처리, 새 article policy hash. 최종 집중207/독립 DART31·policy58 PASS | 전체 검사 스냅샷과 최종 delta 별도 결속 |
| 이전 readiness·prompt cap | 이전 policy의 terminal/finalizer 거절; 현재 policy 정상 봉인; 최대 근거 prompt59,217/65,536bytes | 통과 |
| 전체 pytest | 격리 스냅샷7,630 PASS/1 known skip, 998.94초 | 통과; 이후 최종 delta는 집중207회귀로 별도 검증 |
| native/static/policy/site | replay57/12groups, Node39, Ruff/format845, mypy355, 정책4종, strict MkDocs7.68초 | 통과 |
| source·사람·화면·운영 | runtime0, human0/12, genuine v3 예약0, viewport/성능/전환/cleanup 미완료 | 기존 gate 유지 |

준비된 수동 probe는 source qualification을 발급하지 않고 본문 수집 경로를 활성화하지 않는다. 전달 후 실제 원문으로 접근·권리·parser·필수 필드와 retained evidence를 확인해야 한다. 변경은 미커밋 상태다.

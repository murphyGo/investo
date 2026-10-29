# 2026-10-30 — 기사형 v3 입력 근거와 원문 점검 후속

사용자의 u171–u173/u184–u186 진행 지시를 이어 u184 Step5와 실제 비게시 실패 원인을 보완했다. 기준은 `4cc546755f1175111b377d42d3b26b426274dd52`다. 동시 진행 중인 데이터 추가·u163–u166 작업은 보존했다.

## 변경과 실측

- 도메인 이름의 마침표를 문장 끝으로 잘라 주체를 잃던 문제를 수정했다. `gained/gains/received/receives`의 승인 수령을 지원하며, 허용된 부정사 목적이 함께 있어도 실제 출시로 승격하지 않는다.
- 실제 crypto preview `40705984134`의 기록된 분류 입력 14건을 재생했다. 기존 hint 0개에서 런타임 검증을 통과하는 승인 수령 frame 1개가 됐다. 원문·문서 순서·14건을 그대로 보존했고 새 context는 23,005/24,576 bytes다. 새 모델 호출이나 기사 봉인 결과는 아니다.
- 미국 preview의 `Semiweekly`→숫자 빈도 변환 실패에 대해 작성 지침을 보완했다. 원래 표현은 허용하고 근거 없는 `주 2회`는 기존 hard numeric gate가 거절하는 회귀를 추가했다.
- article policy hash를 갱신해 이전 정책의 readiness 재사용을 거절한다. 독립 검수에서 이전 해시의 terminal 검증·최종 봉인이 차단되고 새 해시의 동일 표본은 봉인됨을 확인했다.
- `scripts/probe_dart_event_evidence.py`와 수동 private workflow template을 준비했다. 기존 OpenDART 원본 XML 경로 한 곳에 요청 1회, redirect/retry 없음, HTTP 8초/전체 요청 20초, 압축·총 해제 각각 500KiB, XML 최대 16개·20,000 nodes·depth256이다. defusedxml로 DTD/entity/external 접근을 차단한다.
- 원문은 gitignored 새 전용 디렉터리 0700·파일 0600에만 쓴다. workflow는 recipient 암호화 검증 뒤 기존 DART secret만 사용하고 ciphertext만 1일 보관한다. LLM·게시·알림 권한을 연결하지 않는다. 실제 source selector/fact 추출/본문 활성화는 추가하지 않았다.
- 로컬 키 부재 경로를 CLI로 확인했다. `credential_missing`, 요청 0회, 원문 미보관, exit1이다. GitHub의 키를 읽어내거나 채팅으로 전달받지 않는다. workflow는 아직 설치·실행하지 않았다.

OpenDART의 [원본 공시파일 개발 가이드](https://opendart.fss.or.kr/guide/detail.do?apiGrpCd=DS001&apiId=2019003)와 [소개](https://opendart.fss.or.kr/intro/main.do)를 접근 경로의 근거로 사용했다. 실제 응답·parser/필드·retention qualification을 통과했다는 의미는 아니다.

## 독립 검수와 검증

독립 검수에서 두 High finding을 발견해 수정했다. 압축 XML의 주석·이름 등에 숨은 인증 값은 해제된 바이트와 decoded 내용에서 검사해 저장을 거절한다. 줄바꿈·세미콜론 앞의 인용·긴 조건을 놓치는 문제는 hint와 런타임 모두 전체 문장을 검사하도록 수정했다. 모델이 내부 span만 선택하는 음성도 거절한다.

독립 재검증은 118 tests, scoped Ruff/format, mypy PASS이며 잔여 Critical/High/Medium 0이다. 기존 u173 private capture 보완 7개 파일과 이번 코드 9개 파일만 기준 HEAD에 적용한 격리 검증본을 만들었다. 공유 작업공간 전체를 배포 후보로 사용하지 않는다. 해당 검증본은 Ruff/format 845 files, mypy 355 source files, native replay 57/12 groups, Node 39, 정책 4종과 strict MkDocs PASS다. 전체 pytest 결과는 [검수 보고서](../cross-checks/2026-10-30-v3-source-followup.md)에 기록한다.

전체 검사 시작 뒤의 최종 변경은 ZIP 해제 메모리 범위를 위해 STORED/DEFLATED만 허용하는 제한, 알 수 없는 XML 인코딩의 닫힌 실패 처리, article policy hash 갱신이다. 최종 코드 범위는 17개 파일이며 전체 검사 스냅샷과 별도 SHA로 기록한다. 최종 집중207 tests PASS, 독립 DART31/policy58 PASS, 이전 policy readiness 거절 및 최대 근거 포함 prompt59,217/65,536bytes를 확인했다.

격리 스냅샷 전체 pytest는 **7,630 PASS/1 known skip/998.94초**로 종료됐다. 이후 최종 보완을 같은 격리 검증본에 반영해 집중 회귀와 정적 검사를 확인했다. 전체 스냅샷과 최종 코드 SHA는 기계 증거에서 구분한다.

## 남은 인계

검토된 코드의 커밋·전달 후 새 preview pin으로 실제 crypto/US 재생성과 DART 수동 원문 점검이 필요하다. DART 응답을 확인한 뒤 기존 source의 selector·필드·권리·보존 조건을 검수하고 필요한 bounded body 보강 범위를 결정한다. 현재 준비 상태를 source/runtime verified로 올리지 않는다.

u171 7/8, u172 5/9, u173 6/7, u184 5/6을 유지한다. source slot 로컬 2 verified/6 blocked와 runtime0, human0/12, genuine v3 예약0, 정확한 viewport·성능·운영 전환·cleanup은 미완료다. 이 작업에서 production pin/schema·cron·실제 게시·Telegram 상태는 변경하지 않았다.

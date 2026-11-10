# 2026-11-08 — 기사형 v3 실제 검수 후속

승인된 u171–u173/u184–u186 작업의 연속이다. 공유 작업공간의 다른 수정과 운영 pin을 보존하고 분리 checkout에서 진행했다. 기존 수정 `31885e96`의 [정확한 CI41042172197](https://github.com/murphyGo/investo/actions/runs/41042172197)는 **7,777PASS/1knownskip/780.47초**, Ruff/format858·mypy363·나머지 정책/문서 검사 SUCCESS다.

## 실제 비공개 실행

[11월6일42149390928](https://github.com/murphyGo/automation-runtime/actions/runs/42149390928)은 국내 context.status_unbound, 미국/crypto article.composition_invalid로 종료했다. 로그에는 실패 코드가 남았으나 서버 중단 사이 1일 보관 암호문이 만료돼 상세 입력/출력 검수는 불가하다. 이 실행의 합격 수는0이다. 작업의 generation/auth 단계50/128/75초는 모델 stage별 시간이나 end-to-end p95가 아니다.

[11월8일 진단42462350797](https://github.com/murphyGo/automation-runtime/actions/runs/42462350797)은 같은 검토 코드와 schema3/article_v2, 11월6일 기준으로 실행했다. 각 시장이 끝난 즉시 암호문을 회수했고 3개 artifact·4개 prompt/stdout hash pairs·개별 파일 hash와 0700/0600 경계를 확인했다.

| 시장 | 실제 결과 | 인수 해석 |
| --- | --- | --- |
| 국내 | 분류 첫 호출 후 context.status_unbound | 기사0, 실제 발언 문법의 지원 범위 누락 |
| 미국 | source_limited/content_not_ready, 분류0/기사0 안내 edition 봉인 | 정상 기사 인수0 |
| crypto | 작성 후보1/2문장의 composition_invalid | 일반 명사·문서 귀속 표현 오탐, 기사 봉인0 |

세 job의 generation/auth 단계는53/30/73초다. auth checkpoint·암호화·ciphertext 보관 단계는 모두 SUCCESS이며 stage별 지연이나 품질/성능 합격으로 대체하지 않는다. 게시·알림·production cursor/receipt 쓰기는0이다. preview pin만31885e96으로 연결했고 production28170546을 보존했다.

## 원문에 결속한 후속 수정

국내는 정형 `(지역=매체) 기자명 기자 = ` 머리말, 발언 주체와 동일한 보어, 발언 동사 앞1~31일 부사가 있었다. 기존 proof는 이 형식을 지원하지 않아 닫힌 실패로 거절했다. 기존 한국어 발언 동사의 statement/actual에만 이 두 형식을 지원하고 전체 문장의 부정·미래·중첩 guard, 같은 주체/보어/action, 원문 좌표와240자 한도를 유지한다. 임의 전언/조건 prefix·다른 주체·잘못된 날짜·인용 속 승인/출시의 독립 완료 주장은 계속 거절한다. 발언일을 공표 순간으로 추론하지 않는다.

crypto의 ‘의혹’은 정확한 일반 개념으로만 처리하고 합성 회사명은 계속 근거를 요구한다. ‘…라고 전한다’는 문서 귀속 표현을 독립 어절과 문장 끝 경계에서만 인정한다. 회전한다/운전한다/충전한다 등 동사의 끝부분을 잘못 인정하지 않도록 독립 검수 중 발견한 Medium을 수정했다. 기존 주체 없는 ‘소개됐다’ 거절, 원문 actor/ref·숫자·역할 검사는 유지한다. policy hash도 갱신해 이전 readiness 재사용을 거절한다.

수정 전후의 실제 녹화 재생은 진단이며 새 모델 review·최종 봉인·사람 수용은 아니다. 집중 회귀와 독립 검수 이후 정확한 새 코드 CI와 새 비공개 실행을 이어 기록한다. 공개 [실행 증거](../../aidlc-docs/construction/event-v3-acceptance-20261028/runtime-20261108.json)는 count/hash/closed code만 포함한다.

## 남은 인수

local source2/8 verified·runtime0, DART blocked·human0/12·genuine v3예약0과 exact viewport·성능·운영 전환·cleanup은 미완료다. DART는 실제 원문 접근과 공식 문서 확인까지 완료했고 [parser 후속 범위](../../aidlc-docs/construction/event-v3-acceptance-20261028/dart-parser-handoff-20261030.md)를 기존 u173 Step4/u184 Step5에 연결했다. ZIP 처리 범위 개정과 정정 후 열·5개 field의 실제 refs/factory replay가 남으며 진단 probe를 production fetcher로 우회 사용하지 않는다.

최종 집중254PASS/11.33초, 독립111PASS/1.46초·잔여C/H/M0, Ruff/format859·mypy363·strictdocs PASS다. 국내 실제 녹화의1event/1statement fact가 전체 원문과 좌표를 보존해 parser를 통과했고 crypto후보1개2문장 precheck도 통과했다. 부정/계획/조건·전언prefix·외부주체/인용action승격·위조status/날짜의 합성11개와 비보고 동사4개는 계속 거절된다. 이전policy readiness도 terminal/finalizer 양쪽에서 거절한다. 새 모델 review·기사 봉인·사람 인수는 대기다.


## 2026-11-10 — 최종 코드 전달·실제 실행 결과 기록

후속 코드 `7c5b8912`를 main에 전달했다. [정확한 CI42464723553](https://github.com/murphyGo/investo/actions/runs/42464723553)는 **7,805PASS/1knownskip/646.08초**, Ruff/format859·mypy363 및 정책/strictdocs SUCCESS다. 독립 코드·전달 검수는 잔여C/H/M0이며 승인6개 hash와 공유 작업공간의 소유11개 파일이 일치한다. 기존 다른 작업은 보존했다.

CI 후 preview pin만7c5b8912로 갱신했다. [최종 비공개42465588085](https://github.com/murphyGo/automation-runtime/actions/runs/42465588085)의 미국은 분류0/기사0 source_limited 안내 edition만 봉인했다. 국내와 crypto는 Python 또는 pinned Codex의 GitHub release 다운로드504로 **auth/model 시작 전 설치 단계에서 실패**했다. 실패 job 재실행을1회 요청했으나 국내는Codex, crypto는Python 설치504로 다시 실패했다. 따라서 이 두 시장의 최종 코드 실제 생성/semantic review/기사 봉인은 미검증이다. 원문 근거 실패나 새 모델 품질 판정으로 분류하지 않는다.

미국 암호문·prompt/stdout pair·Markdown/projection hash는 즉시 회수·검수했다. 초기 실행과 재시도 job은 별도 보존하고 동일한 미국 결과를 새 corpus로 합산하지 않는다. 기사 합격0·사람0/12·예약0과 source2/8/runtime0·DARTblocked를 유지한다. 11월10일 readback에서도 production28170546·preview7c5b8912가 확인됐으며 운영 전환·게시·알림을 하지 않았다. [최종 count/hash/실패 단계 증거](../../aidlc-docs/construction/event-v3-acceptance-20261028/runtime-final-20261108.json).

브라우저 host도 재확인했으나 unavailable이라390×844/1440×900 화면 인수는 미검증이다. 모델 검토나 녹화 precheck를 사람 합격으로 바꾸지 않는다. 다음 잔여는 외부 다운로드 정상화 후 최종 코드의 국내/crypto 재생성, DART bounded parser/정정 후 열·5필수ref의 source 자격, 실제 사전 주석·12건 사람 검수, viewport/성능 및 그 뒤의 운영 수용이다. 유닛 전체 완료나 release-ready를 선언하지 않는다.

# 뉴스·사건 기능 main 통합 및 운영 출시

2026-10-04 사용자가 “main 통합, 운영 활성화해줘”라고 승인했다. 기존 u157–u162와 필수 u152를 최신 main에 통합하고 운영 증거 수집을 진행한다. root의 미커밋 파일 및 별도로 진행 중인 u155 Codex 전환 작업은 보존한다.

## 통합

기준 main `77ff63d19834f3c19c40b4e8fa5ace995b5c4b34`, 검증된 기능 브랜치 `47518dba46c7b37c72f6be649897ac4c764deadc`. 별도 `codex/news-event-main-20261004` 작업 폴더에서 병합했다. audit의 두 이력을 보존하고, pipeline 충돌은 main의 dry-run 임시 품질 기록과 사건/뉴스 관측 지표를 함께 유지하도록 해결했다. dry-run도 이번 실행의 사건 지표를 실제 consistency gate에서 비교하며 canonical history를 수정하지 않는다.

## 운영 제어

통합 시작 시 운영 owner는 공개 `daily-briefing`의 Claude CLI였다. 공개 workflow에 event/news shadow를 연결하고 repository variable로 `off` 복귀가 가능하도록 했다. 14:30 UTC 별도 u155 작업이 private Codex runtime으로 운영을 전환했고 동일 shadow 설정을 보존했다. 원문·URL·LLM 응답 없이 후보 수와 계산된 관측기간만 로그로 남긴다. 같은 기록 응답에서 기존 본문·알림·cursor 불변을 실제 통합 테스트로 확인했다. 공식 본문 보강은 off를 유지한다.

비게시 미리보기는 별도 `event-preview` workflow가 담당한다. 세 시장을 순차 실행하고 기존 source routing, 숫자 anchor, 두 단계 CLI, 실제 finalizer를 사용한다. contents read 권한이며 게시·Telegram 자격증명이나 public pipeline 호출이 없다. `scripts/preview_event_briefing.py`가 신규 Git-ignored `.tmp`에 봉인된 Markdown과 제한된 manifest를 쓴다. 원문 소스와 native LLM 응답은 출력·보관하지 않는다.

미리보기는 로컬에서 생성한 임시 공개키로 암호화한 뒤 ciphertext만 1일 보관한다. 개인키는 workflow에 전달하지 않는다. `scripts/seal_event_preview.py`는 최대 12개 Markdown/JSON, 합계 2MiB를 허용하고 symlink/경로 이탈을 거부한다. 정상 키 복호화, 다른 키 거부 및 출력 경계 회귀를 검증했다.

## 검증

병합 집중 158개/45.65s, dry-run 사건 지표 8개/1.17s, shadow/기존 workflow 25개/24.17s 통과. 별도 작성자 preview 신규21+기존8개/2.14s, 독립 preview/암호화25개/1.98s와 source/window22개/22.70s 통과. 전체 Ruff, format666개, mypy290개 및 두 workflow actionlint 통과. 최종 전체 **6149개/487.31s**, 정책4, strict docs6.29s/Material 통과. source/workflow671개 SHA-256이 전체 테스트 시작 이후 동일함을 확인했다. 독립 리뷰는 정적 수정 재검까지 CLOSED이며 미해결 P1/P2가 없다. 원격 SHA와 실제 운영 결과는 후속 기록에 남긴다.

## 출시 증거와 상태

| 항목 | 현재 증거 |
|---|---|
| 유닛 구현 | u157–u162 및 u152 완료 |
| main 통합 | `e5487c2a`까지 전달, exact-SHA 원격 CI 성공 |
| 실제 v2 비게시 미리보기 | Codex `37213412858` 국내 봉인 성공(사건0), 미국 synthesis2회 실패, 코인 unexpected 실패. 실패 원인 진단 중 |
| 사람 의미 검수 | frozen12 시나리오 what/when/why/react/source 검수 대기 |
| 실제 예약 shadow | 1/5 관찰; 주말 직후 scheduled37248296267 확인, 뉴스 풍부한 날의 사람 baseline 판정은 pending |
| 사건 본문 active | false; 위 출시 증거 충족 전 전환하지 않음 |
| 새 뉴스 cursor / 공식 본문 HTTP | active false |
| active 첫 3회 게시·알림·Pages | 미실행 |

기존 NFR 출시 단계5는 “못채우면해당운영AC는pending,합성검증을대신완료로기록하지않는다”고 규정한다. 수동 실행을 예약 실행으로 계수하거나 모델 검토를 사람 검수로 기록하지 않는다. 5회 관찰은 기존 예약 시각에 실제 실행돼야 하며 자동 active 전환은 추가하지 않았다. 기존 10분 성능 목표의 DEBT-090도 별도 유지한다.

## 운영 명령과 복귀

현재 production owner인 `investo-runtime`의 repository variables `INVESTO_EVENT_BRIEFING_MODE=off`, `INVESTO_NEWS_WINDOW_MODE=off`로 shadow를 중지할 수 있다. readiness 상수는 false여서 실수로 active를 지정하면 기존 preflight가 차단한다. 공개 `daily-briefing`은 `disabled_manually`다. 두 예약 실행을 동시에 활성화하지 않는다. 공개 preview는 기존 Claude의 비게시 검증이며 Codex v2 운영 수용을 대신하지 않는다.

현재 Codex 미리보기는 `gh workflow run event-preview.yml --repo murphyGo/investo-runtime --ref main -f target_date=YYYY-MM-DD -f segment=all -f recipient_public_key=<public hex>`로 실행한다. 공개 저장소의 같은 이름 workflow는 이전 Claude 진단용이다. 공개키와 일치하는 개인키가 있어야 결과 artifact를 읽을 수 있다. 개인키와 복호화 출력은 Git에 추가하지 않는다. source receipt baseline이 unavailable인 미리보기의 신규성 판정 한계는 manifest에 명시한다.

최종 전달 직전 main의 문서 전용4e029015가 추가되어 함께 통합했다. u155 기록5개를 보존했으며 검증된 source/test/script/workflow671개는 SHA-256까지 동일하다. 실행 코드에 대한 전체6149 결과는 동일 내용의 증거로 유지하고, 합쳐진 문서는 strict 빌드를 다시 수행했다.

## 실제 운영 shadow — 수동 smoke

[daily-briefing 37208127537](https://github.com/murphyGo/investo/actions/runs/37208127537)은 `95c73a8b`에서 `workflow_dispatch`로 실행되어 성공했다. 대상 거래일은 2026-10-02, 실행 시각은 2026-10-04 14:08 UTC다. 수집 283건/44 source outcomes, 세 시장 생성 `ok=3 failed=0`, pipeline `status=success`, exit 0, 849.566초다. 10분 목표 미달은 기존 DEBT-090에 해당하며 성능 완료로 기록하지 않는다.

| 시장 | 입력 | 후보 | 뉴스 | 누락 | 최종 상태 |
|---|---:|---:|---:|---:|---|
| 국내 | 119 | 54 | 48 | 65 | finalized_degraded, numeric.anchor_assertion |
| 미국 | 144 | 96 | 36 | 48 | finalized |
| 코인 | 19 | 19 | 8 | 0 | finalized |

세 시장 모두 `reservation_starved=False`. 관측기간 계산 19개 source/segment 행은 모두 `fetch_changed=false cursor_write=false`다. 발행 전 `95c73a8b`와 발행 후 `f4d95326`에 `archive/_meta/event_receipts.json`, `archive/_meta/news_cursors.json`, `archive/_meta/news_windows/`가 없음을 각각 확인했다. 독립된 실제 LLM 실행 사이의 본문 byte 동일성은 주장하지 않는다. 같은 기록 응답에 대한 off/shadow 비간섭은 앞서 수행한 통합 테스트의 증거다.

세 문서는 `f4d9532607fcf742f6a60cec409dfc85e78cef76`으로 발행되었고 Telegram `message_id=147`이 반환됐다. [Pages 37209101940](https://github.com/murphyGo/investo/actions/runs/37209101940) 성공 후 공개 세 URL HTTP200, 이전 archive와 달라진 문단의 실제 HTML 포함을 국내24/미국20/코인28개씩 확인했다. 이는 shadow에서 기존 발행 경로가 동작한 증거이며 active 첫3회 게시 수용으로 계수하지 않는다. 실제 예약 shadow는 여전히 0/5다.

최초 preview `37207945939`는 숨김 폴더의 ciphertext 업로드 설정을 보정하기 위해 중단하고 `95c73a8b`에서 재실행했다. 재실행의 국내 artifact는 개인키로 정상 복호화됐으나 `briefing_generation`, `stage=classification`, `attempt_count=3`으로 실패했다. 모델 원문을 보관하지 않는 경계는 유지하며, 실패를 성공 미리보기나 사람 의미 수용으로 기록하지 않는다. 실패 원인을 구분할 수 있도록 고정된 오류 종류/스키마 필드만 담는 진단과 시장별 재실행을 보강한다.

동시 main `056dd8a1`의 private runtime shadow mode 연결과 테스트도 보존했다. 현재 작업의 진단 보강은 새 모델 호출이나 재시도를 추가하지 않으며 기존의 schema/evidence 거부 조건을 완화하지 않는다.

## 동시 운영 owner 전환 확인

별도 u155 작업의 private [Codex daily briefing 37209545723](https://github.com/murphyGo/investo-runtime/actions/runs/37209545723)은 검토 코드 `056dd8a1`로 성공했다. 원격 `CODEX_PRODUCTION_ENABLED=1` 및 공개 daily 중지를 읽기 전용으로 확인했다. 세 시장 모두 finalized, 245.888초, 발행 `e5e59729`, Telegram148이다. 이 실행에서도 후보54/96/19, 뉴스48/36/8, `reservation_starved=False` 및 19개 window의 `fetch_changed=false cursor_write=false`가 관찰됐다. 수동 replay이므로 예약5회에는 포함하지 않는다. 이 작업에서는 provider/credentials/운영 enable 변수를 변경하지 않았다.

## 실제 실패의 안전한 진단 보강

국내에 이어 미국 preview도 classification 2회 후 실패했다. 기존 artifact에는 원문 없이 단계/횟수만 있어 두 시장의 상세 원인은 아직 미확인이다. v2 파서가 기존 오류 메시지와 거부 조건을 유지한 채 알려진 schema 필드/오류 종류 및 evidence 오류만 최대8개 진단 토큰으로 전달하도록 했다. 동적 필드명, 입력값, 원문, URL, native stdout/stderr는 전달하지 않는다. 미리보기 workflow는 `segment=all|domestic-equity|us-equity|crypto`로 해당 시장만 다시 실행할 수 있다. 현재 운영 owner의 reviewed code 포인터는 이 비게시 진단 때문에 변경하지 않는다.

최종 진단 보강 전체6152/656.75s, 집중64/2.80s, 독립40/2.45s 및 리뷰 CLOSED/P1P2없음. Ruff/format666/mypy290, actionlint2, 정책4, strict docs7.58s/Material 통과. 이 전체 검증 후 동시 발행 e5e59729의 archive/site 데이터와 b0a80eab의 운영 문서를 함께 보존한다. 동시 변경에는 실행 코드/테스트 수정이 없다. 합쳐진 문서/게시 자산 검사와 원격 CI는 별도로 확인한다.

진단 보강은 `6e12da89433e6f0cbd6dccbc94cb9c0fe844a124`로 main에 전달하고 정확한 원격 SHA를 확인했다. [quality 37210613485](https://github.com/murphyGo/investo/actions/runs/37210613485)가 성공했다. [국내 진단 재실행 37210636616](https://github.com/murphyGo/investo/actions/runs/37210636616)은 세 시장 run 종료 후 시작했다. 기존 run의 코인도 classification 3회 후 실패했으며 성공 미리보기는 아직 없다.

## 2026-10-05 KST — 현재 Codex owner의 비게시 검증 연결

운영 owner 변경 후에는 Claude preview가 Codex v2 수용을 대신하지 못한다. `ops/private-runtime/event-preview.yml`과 reviewed wrapper `scripts/preview_event_briefing_codex.py`를 추가해 현재 Codex 모델/고정 CLI/비공개 Environment를 재사용한다. 기존 `codex_runtime`에 검토된 in-process operation 인자만 추가했으며, 생략 시 production의 `_async_main` 호출과 auth 보존·취소·정리 경로는 동일하다.

새 preview는 production과 같은 `investo-codex-auth-v1` 잠금, private/main guard, Python `-I` 및 설치 provenance를 사용한다. 실행 코드는 별도 trusted variable `REVIEWED_EVENT_PREVIEW_SHA`로 고정하고 production의 `REVIEWED_CODE_SHA`는 바꾸지 않는다. public-data checkout은 입력 데이터와 Git-ignored preview 파일에만 사용하며 실행 모듈은 reviewed sibling에서만 읽는다. publish token이나 Telegram 자격증명은 전달하지 않고, recipient ciphertext만 하루 보관한다. 기존 인증 갱신 보존은 같은 owner가 맡는다.

독립 리뷰에서 setup 지연 때문에 job 상한이 auth cleanup보다 먼저 올 수 있는 P2를 발견했다. 첫 step 시각부터 setup 600초 미만임을 auth 복원 직전에 확인하고, 작업100분·정리120초가 job120분 안에 들어가도록 보정했다. 실제 guard 실행에서 30초 허용, 601초와1500초 차단을 확인했다. 집중81/9.18s, provider 회귀 추가 후60/6.14s, 독립60/5.99s 통과 및 리뷰 CLOSED/P1P2없음. 전체 회귀와 실제 배치·미리보기 결과는 후속 기록한다.

최종 전체 **6163/655.75s**, Ruff/format668/mypy290, 정책4, 세 workflow actionlint, strict docs/Material 통과. 검증 중 source/test/script/workflow679개를 SHA-256으로 고정했다. 미리보기 전용 workflow를 배치하고 원격 CI로 확인된 SHA만 별도 변수에 등록한 뒤 실제 Codex preview를 실행한다. 이 배치는 사건 본문 active 전환이 아니다.

## 비공개 Codex preview 배치 증거

실행 코드는 `e5487c2a95a7ec91b7f84ba1f290d00132cb370e`로 main에 정상 push하고 정확한 원격 SHA를 확인했다. [quality 37212807946](https://github.com/murphyGo/investo/actions/runs/37212807946)가 모든 검사를 통과했다. private runtime에는 preview workflow 한 파일만 `278ce158c44be3a304a6c9ed1f4150171d63e133`으로 전달했고, public의 검토된 template과 실제 배치 파일이 byte 단위로 같음을 확인했다. production과 preview 모두 동일한 `investo-codex-auth-v1` lock을 사용한다.

원격 CI 성공 후 `REVIEWED_EVENT_PREVIEW_SHA=e5487c2a95a7ec91b7f84ba1f290d00132cb370e`를 별도 등록하고 재조회했다. production의 `REVIEWED_CODE_SHA=056dd8a1b4a8e599f44519e54b5bf4f486275dbd`, `CODEX_PRODUCTION_ENABLED=1`은 유지된다. [Codex preview 37213412858](https://github.com/murphyGo/investo-runtime/actions/runs/37213412858)을 대상일 2026-10-02, 세 시장 순차 실행으로 시작했다. 결과는 완료 후 별도 기록한다.

## 예약 관찰 장부

2026-10-05 최신 조회 기준 실제 예약 관찰은 **1/5**다. private daily의 cron은 KST 월–금 07:00와 토요일 09:00이며 공개 daily는 중지돼 있다. 아래 시각은 예정이며 실행 성공이나 수용을 뜻하지 않는다. GitHub 예약 지연, 뉴스량, 실패 여부에 따라 수용 가능한 관찰 날짜는 달라진다.

| 예정 시각 KST | 실제 run / event | 관찰 조건 | 현재 상태 |
|---|---|---|---|
| 2026-10-05 07:00 예정 → 09:38 실제 | 37248296267 / schedule | 주말 직후, replay=False | 관찰 완료; 국내 numeric degradation 기록 |
| 2026-10-06 07:00 | 미실행 | source/candidate/window·게시 확인 | pending |
| 2026-10-07 07:00 | 미실행 | source/candidate/window·게시 확인 | pending |
| 2026-10-08 07:00 | 미실행 | source/candidate/window·게시 확인 | pending |
| 2026-10-09 07:00 | 미실행 | source/candidate/window·게시 확인 | pending |

각 실제 run에서 GitHub event가 `schedule`인지 확인하고, 세 시장의 후보/뉴스/누락/보호선정 고갈 여부, source window의 fetch/cursor 비변경, finalized 상태, 실제 게시 commit·Telegram 응답·Pages 결과를 연결한다. 뉴스가 풍부한 날은 실제 입력과 사람이 확인한 주요 사건을 근거로 판정하며 예정 날짜만으로 충족 처리하지 않는다. 최소 5회가 쌓여도 frozen12 사람 검수 및 실제 v2 preview가 미충족이면 사건 본문은 활성화하지 않는다. 사람 검수 자료는 로컬 ignored `.tmp/event-review-packet/README.md`와 빈 `human-review.csv`로 준비했으며 사용자 응답은 아직 없다.

## 미리보기의 실제 관찰

이전 Claude 진단 [37210636616](https://github.com/murphyGo/investo/actions/runs/37210636616)은 classification 3회 후 `classification.invalid_schema_or_item`, `schema.json_invalid.envelope`로 실패했다. 이는 v2 JSON envelope 파싱 실패이며, 원문을 보관하지 않아 코드펜스·잘림·다른 형식 중 어느 원인인지는 구분할 수 없다. validator를 완화하지 않았고 현재 Codex의 수용 결과와 분리한다.

Codex `37213412858`의 국내 job은 성공했다. 암호화 artifact를 복호화하고 봉인 Markdown SHA-256 `a6baea165fff09bb7662df28d63937a0620f6f8b12fe86c778128414f1475759`와 실제 파일을 대조했다. collection284/routed116, source ok28/zero11/failed5, finalized1, event selected0/terminal0, state `source_limited`다. 본문은 중요 사건 판단에 필요한 수집 근거가 제한되었다고 명시한다. 게시/알림/production receipt·cursor는 모두 false다.

이 실행은 실제 Codex v2의 schema·최종 봉인·인증 정리·암호화 경로가 동작한 증거다. 사건이 0건이므로 사건의 what/when/why/reaction/source가 실제 뉴스에서 올바르게 이어지는 양성 수용 증거는 아니다. 현재 preview는 뉴스기간 active receipt를 만들지 않고 대상 거래일의 시장 현지일을 사건 선정창으로 쓴다. 실제 관찰 시각과 가격 기준일을 같은 것으로 기록하지 않는다. 사람 의미 검수 및 뉴스가 풍부한 날의 관찰은 pending으로 유지한다.

첫 Codex 세 시장 실행은 전체 failure로 끝났다. 국내 job은 success이고 미국은 `stage=synthesis`, `attempt_count=2`, 코인은 `error_type=unexpected`였다. 실패 artifact는 각각 복호화하여 확인했다. 성공한 형제 시장을 실패로 바꾸거나 전체 성공으로 합치지 않는다. 미국의 기존 고정 `event.*` 코드 6개를 미리보기 manifest에 전달하도록 `fb9e2cfd`를 배포했다. 집중92/3.83s, 독립32/2.29s와 exact-SHA CI37214108637이 통과했다. 이 SHA로 미국 진단 [37214495353](https://github.com/murphyGo/investo-runtime/actions/runs/37214495353)을 시작했다. 코인의 예외도 원문 대신 고정 built-in 종류와 알려진 발생 구간만 표시하도록 `ed9fd7fc`로 보강했다. 집중94/3.90s, 독립41/2.96s, 최종 script34/2.45s 및 Ruff/format 통과; 두 보강 모두 독립 리뷰 CLOSED, validator·prompt·retry·production 변경 없음.

동시 private runtime 변경 `ce772cf5`는 AI 보고서용 workflow를 추가하고 기존 preview/daily의 같은 인증 잠금에 `queue: max` 한 줄을 추가했다. 실제 원격 diff를 확인하여 보존했다. 초기 배치 시 template byte 일치 증거 이후의 명시적 차이이며 production의 reviewed code/enable 값은 그대로다. 이 작업은 다른 보고서의 설정·자격증명·발행을 변경하지 않는다.

미국 진단 `37214495353`은 synthesis 2회 후 `event.output_invalid`로 실패했다. 기존 코드가 JSON/schema/section/macro 실패를 같은 retry code로 축약하므로 이 결과만으로 세부 원인은 확정할 수 없다. 거부 조건과 retry feedback 문자열을 그대로 유지하면서 최대8개 고정 schema/검증 단계 진단을 보존하도록 했다. 독립99/3.08s 및 이전/신규 retry feedback14/14 byte 일치 확인, 리뷰 CLOSED.

코인 진단 [37214893965](https://github.com/murphyGo/investo-runtime/actions/runs/37214893965)은 `failure_stage=finalization`으로 실패했다. finalizer의 기존 `PublicDocumentFinalizationError`는 `ValueError`가 아닌 독립 Exception이므로 generic unexpected로 분류된 경우를 식별하도록 했다. 상태는 failed로 유지하고 허용된 phase/기존 issue code/고정 built-in cause 종류만 전달한다. 임의 issue/phase/원인 메시지는 내보내지 않는다. 독립43/3.28s와 별도 private-cause/phase/issue 비노출 검증 PASS, 리뷰 CLOSED. 이 진단 자체를 실패 해결로 기록하지 않는다.

현재 집중101/6.17s, Ruff/format668/mypy290, 정책4/actionlint3/strict docs7.82s/Material 통과. 핵심 synthesis 파일은 전체 회귀 동안 고정했고, 그 이후 추가한 finalizer manifest/script 테스트는 별도 집중 검증했다. 최종 결합 내용의 전체 회귀·원격 CI와 실제 재실행 결과는 이후 기록한다.

## 첫 실제 예약 shadow 확인 — 2026-10-05

최신 원격 조회에서 private [scheduled37248296267](https://github.com/murphyGo/investo-runtime/actions/runs/37248296267)의 성공을 확인했다. GitHub event는 `schedule`, 생성 시각은 2026-10-05 00:38:23 UTC(09:38 KST), 자동 대상 거래일은 2026-10-02다. `replay=False`이며 19개 source/segment 관측창은 2026-10-02 00:38:53~2026-10-05 00:38:53 UTC, `fetch_changed=false cursor_write=false`다. cron 예정 시각 이후에 시작한 사실을 실제 시각 그대로 기록한다.

후보54/96/19, 뉴스48/36/8, 누락53/51/0이고 세 시장 모두 `reservation_starved=False`다. 국내는 `finalized_degraded`/`numeric.anchor_assertion`, 미국·코인은 finalized다. 265.485초, pipeline success, 발행 `587787f33d9db4e42e52f6e319703f98b30aef87`, Telegram149, [Pages37248604347](https://github.com/murphyGo/investo/actions/runs/37248604347) 성공을 확인했다. 같은 SHA의 quality37248603142도 성공했다. 이 관찰은 예약 **1/5**이며 주말 직후 실행에 해당한다. 뉴스 풍부한 날의 외부 사람 baseline이나 active 첫3회 완료로 대신 계수하지 않는다.

새 main587787f3는 archive/site 발행 데이터45개만 바꾸었고 실행 코드/테스트/워크플로 변경은 없다. 이 발행 이력을 격리 통합 작업트리에 보존한다. 전체 회귀 **6180/675.62s**가 통과했고, 실행 중 추가한 finalizer manifest/script 테스트는 별도 검증했다. source/test/script/workflow/fixture880개 스냅샷 중 변경된 파일은 해당 script/test2개뿐이며 나머지878개는 동일하다. 최종 합쳐진 SHA의 CI를 추가 확인한다.

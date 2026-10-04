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
| main 통합 | `6d0d909d` 및 ciphertext 경로 보정 `95c73a8b` 전달, 두 원격 CI 성공 |
| 실제 v2 비게시 미리보기 | `37208126978` 국내 classification 3회, 미국 classification 2회 실패; 코인 결과 대기 |
| 사람 의미 검수 | frozen12 시나리오 what/when/why/react/source 검수 대기 |
| 실제 예약 shadow | 0/5; 뉴스가 풍부한 날과 주말 직후 실행 포함 필요 |
| 사건 본문 active | false; 위 출시 증거 충족 전 전환하지 않음 |
| 새 뉴스 cursor / 공식 본문 HTTP | active false |
| active 첫 3회 게시·알림·Pages | 미실행 |

기존 NFR 출시 단계5는 “못채우면해당운영AC는pending,합성검증을대신완료로기록하지않는다”고 규정한다. 수동 실행을 예약 실행으로 계수하거나 모델 검토를 사람 검수로 기록하지 않는다. 5회 관찰은 기존 예약 시각에 실제 실행돼야 하며 자동 active 전환은 추가하지 않았다. 기존 10분 성능 목표의 DEBT-090도 별도 유지한다.

## 운영 명령과 복귀

현재 production owner인 `investo-runtime`의 repository variables `INVESTO_EVENT_BRIEFING_MODE=off`, `INVESTO_NEWS_WINDOW_MODE=off`로 shadow를 중지할 수 있다. readiness 상수는 false여서 실수로 active를 지정하면 기존 preflight가 차단한다. 공개 `daily-briefing`은 `disabled_manually`다. 두 예약 실행을 동시에 활성화하지 않는다. 공개 preview는 기존 Claude의 비게시 검증이며 Codex v2 운영 수용을 대신하지 않는다.

미리보기는 `gh workflow run event-preview.yml --ref main -f target_date=YYYY-MM-DD -f recipient_public_key=<public hex>`로 실행한다. 공개키와 일치하는 개인키가 있어야 결과 artifact를 읽을 수 있다. 개인키와 복호화 출력은 Git에 추가하지 않는다. source receipt baseline이 unavailable인 미리보기의 신규성 판정 한계는 manifest에 명시한다.

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

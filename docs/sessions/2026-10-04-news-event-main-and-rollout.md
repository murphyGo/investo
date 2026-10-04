# 뉴스·사건 기능 main 통합 및 운영 출시

2026-10-04 사용자가 “main 통합, 운영 활성화해줘”라고 승인했다. 기존 u157–u162와 필수 u152를 최신 main에 통합하고 운영 증거 수집을 진행한다. root의 미커밋 파일 및 별도로 진행 중인 u155 Codex 전환 작업은 보존한다.

## 통합

기준 main `77ff63d19834f3c19c40b4e8fa5ace995b5c4b34`, 검증된 기능 브랜치 `47518dba46c7b37c72f6be649897ac4c764deadc`. 별도 `codex/news-event-main-20261004` 작업 폴더에서 병합했다. audit의 두 이력을 보존하고, pipeline 충돌은 main의 dry-run 임시 품질 기록과 사건/뉴스 관측 지표를 함께 유지하도록 해결했다. dry-run도 이번 실행의 사건 지표를 실제 consistency gate에서 비교하며 canonical history를 수정하지 않는다.

## 운영 제어

현재 확인된 운영 owner는 공개 `daily-briefing`의 Claude CLI다. 공개 workflow에 event/news shadow를 연결하고 repository variable로 `off` 복귀가 가능하도록 했다. 원문·URL·LLM 응답 없이 후보 수와 계산된 관측기간만 로그로 남긴다. 같은 기록 응답에서 기존 본문·알림·cursor 불변을 실제 통합 테스트로 확인했다. 공식 본문 보강은 off를 유지한다.

비게시 미리보기는 별도 `event-preview` workflow가 담당한다. 세 시장을 순차 실행하고 기존 source routing, 숫자 anchor, 두 단계 CLI, 실제 finalizer를 사용한다. contents read 권한이며 게시·Telegram 자격증명이나 public pipeline 호출이 없다. `scripts/preview_event_briefing.py`가 신규 Git-ignored `.tmp`에 봉인된 Markdown과 제한된 manifest를 쓴다. 원문 소스와 native LLM 응답은 출력·보관하지 않는다.

미리보기는 로컬에서 생성한 임시 공개키로 암호화한 뒤 ciphertext만 1일 보관한다. 개인키는 workflow에 전달하지 않는다. `scripts/seal_event_preview.py`는 최대 12개 Markdown/JSON, 합계 2MiB를 허용하고 symlink/경로 이탈을 거부한다. 정상 키 복호화, 다른 키 거부 및 출력 경계 회귀를 검증했다.

## 검증

병합 집중 158개/45.65s, dry-run 사건 지표 8개/1.17s, shadow/기존 workflow 25개/24.17s 통과. 별도 작성자 preview 신규21+기존8개/2.14s, 독립 preview/암호화25개/1.98s와 source/window22개/22.70s 통과. 전체 Ruff, format666개, mypy290개 및 두 workflow actionlint 통과. 최종 전체 **6149개/487.31s**, 정책4, strict docs6.29s/Material 통과. source/workflow671개 SHA-256이 전체 테스트 시작 이후 동일함을 확인했다. 독립 리뷰는 정적 수정 재검까지 CLOSED이며 미해결 P1/P2가 없다. 원격 SHA와 실제 운영 결과는 후속 기록에 남긴다.

## 출시 증거와 상태

| 항목 | 현재 증거 |
|---|---|
| 유닛 구현 | u157–u162 및 u152 완료 |
| main 통합 | 이 병합의 최종 전체 gate 통과; 원격 전달 진행 |
| 실제 v2 비게시 미리보기 | 실행 준비 완료; 실제 결과 대기 |
| 사람 의미 검수 | frozen12 시나리오 what/when/why/react/source 검수 대기 |
| 실제 예약 shadow | 0/5; 뉴스가 풍부한 날과 주말 직후 실행 포함 필요 |
| 사건 본문 active | false; 위 출시 증거 충족 전 전환하지 않음 |
| 새 뉴스 cursor / 공식 본문 HTTP | active false |
| active 첫 3회 게시·알림·Pages | 미실행 |

기존 NFR 출시 단계5는 “못채우면해당운영AC는pending,합성검증을대신완료로기록하지않는다”고 규정한다. 수동 실행을 예약 실행으로 계수하거나 모델 검토를 사람 검수로 기록하지 않는다. 5회 관찰은 기존 예약 시각에 실제 실행돼야 하며 자동 active 전환은 추가하지 않았다. 기존 10분 성능 목표의 DEBT-090도 별도 유지한다.

## 운영 명령과 복귀

현재 production workflow의 repository variables `INVESTO_EVENT_BRIEFING_MODE=off`, `INVESTO_NEWS_WINDOW_MODE=off`로 shadow를 중지할 수 있다. readiness 상수는 false여서 실수로 active를 지정하면 기존 preflight가 차단한다. 운영 owner를 private runtime으로 옮길 때는 이 mode/로그 연결도 함께 이관해야 하며 두 예약 실행을 동시에 활성화하지 않는다.

미리보기는 `gh workflow run event-preview.yml --ref main -f target_date=YYYY-MM-DD -f recipient_public_key=<public hex>`로 실행한다. 공개키와 일치하는 개인키가 있어야 결과 artifact를 읽을 수 있다. 개인키와 복호화 출력은 Git에 추가하지 않는다. source receipt baseline이 unavailable인 미리보기의 신규성 판정 한계는 manifest에 명시한다.

최종 전달 직전 main의 문서 전용4e029015가 추가되어 함께 통합했다. u155 기록5개를 보존했으며 검증된 source/test/script/workflow671개는 SHA-256까지 동일하다. 실행 코드에 대한 전체6149 결과는 동일 내용의 증거로 유지하고, 합쳐진 문서는 strict 빌드를 다시 수행했다.

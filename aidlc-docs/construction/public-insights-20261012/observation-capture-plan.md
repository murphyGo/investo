# u180 Step8 예약 관찰 증거 보강

2026-10-25. 사용자의 후속 “진행시켜”를 기존 운영 관찰의 계속 지시로 적용한다.
첫 genuine scheduled 실행 전이며 현재 세 모듈의 관찰은 모두 0/5다.

## Stage decision

Functional Design/NFR Requirements는 별도 단계를 추가하지 않는다. FR-026의 exact-SHA 운영 관찰과
기존 u155 private receipt/7일 보존, NFR-002/R13의 비용·비밀 격리 계약을 재사용하는 운영 보강이다.
새 source/scheduler/secret/LLM/Telegram/public 데이터나 application pin 승격은 없다.
현재 application pin `0025497d4280d9bd72bcafd04ffafe026b8ad6fc`를 보존한다.

## 범위와 수용 조건

1. 기존 private daily owner에 기록·업로드 단계만 연결한다. 원래 cron/auth/queue/timeout/Pages/최종 exit code를 보존한다.
2. 실제 실행 checkout SHA, private workflow SHA, run ID/attempt/event, 기존 remote-confirmed 출력과
   공개 Git의 manifest/current hash·시각·개수만 allowlist JSON으로 남긴다. 원문·모델 출력·환경 전체·auth는 저장하지 않는다.
3. 로컬 Git blob만 읽고 공개 writer/source HTTP/LLM/Telegram 호출을 추가하지 않는다.
4. JSON 한 파일만 임시 0700 경로/0600 파일에 쓰고 private artifact로 7일 보존한다. 유일한 metadata artifact 예외다.
5. capture 10초·upload 최대1분을 기존225분 allowance 안에서 처리한다. 75초 미만이면 기록을 건너뛰며 주 시황 결과를 바꾸지 않는다.
6. manual/retry/옛 snapshot/미확정 게시/잘못된 hash는 scheduled 수용으로 세지 않는다.
   artifact의 candidate는 자동 합격이 아니며 실제 source 범위·remote ancestry·Pages snapshot을 추가 대조해야 한다.
7. 정상·실패·권한 경계·초과 크기·clock/hash 불일치·비밀 canary·예산 부족·기존 exit code 보존 회귀를 실행하고 독립 리뷰한다.
8. 공개 template과 실제 private workflow의 기록 블록 bytes를 대조하고 원격 적용을 확인한다.
   로컬 synthetic 검증이나 새 artifact 설정을 genuine scheduled 실행으로 계산하지 않는다.

현재 시점의 nominal 다음 cron은 2026-10-25 22:00 UTC(10월26일07:00 KST)다.
실제 GitHub 시작·게시 시각은 별도로 관찰하며 미래 run ID/합격을 생성하지 않는다.

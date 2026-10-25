# Public insights 운영 연결

2026-10-25. 사용자의 후속 “진행시켜”를 최신 main 통합·원격 전달·조건부 운영 연결 지시로 적용한다.
기존 root의 별도 변경은 보존한다. 구현과 운영 수용은 분리하며 마지막 운영 단계는 실제 증거가 모일 때 완료한다.

## 공개 범위와 순서

매크로 → 주요 일정 → 크립토 순서로 확인한다. qualification의 display와 public Git 보존 권한이 모두 있어야 현재값을 게시한다.
총 46개 정의 중 27개만 허용하며 crypto는 Alternative.me 공포·탐욕 지수만 허용한다.
권한이 미확인된 FRED/CoinGecko/DeFiLlama/Bybit/OKX 정의는 공개하지 않는다.
숫자가 없는 카드는 이유를 표시하고 0이나 다른 원천의 값으로 채우지 않는다.

코드의 mode 기본 off, modules 기본 macro를 유지한다. 기존 유일한 private daily owner의
`INVESTO_INSIGHTS_MODE`와 `INVESTO_INSIGHTS_MODULES`만 운영 지시 범위에서 연결한다.
별도 scheduler, source endpoint, LLM 호출, Telegram 메시지를 추가하지 않는다.
한 collection에서 envelope를 분리하고 기존 시황 입력을 복원한 뒤 insights를 게시한다.

## 전달과 운영 검증

1. 최신 main에 별도 작업공간에서 통합하고 append-only 이력을 양쪽 모두 보존한다.
2. 통합 tree의 전체 회귀·정적·정책·문서·resource 및 세 화면의 실제 임시 Chromium 검증을 기록한다.
3. 독립 통합 리뷰와 정확한 SHA의 GitHub quality 성공을 확인한 뒤 운영 pin을 승격한다.
4. private workflow는 현재 `queue: max`, 인증 owner, timeout, 기존 secrets와 schema 2를 보존한다.
   INSIGHTS env 2개, Pages 조건과 Pages SHA 식 2개만 기존 workflow에 반영한다.
5. 실제 source shadow 결과를 먼저 확인한다. 로컬 수집 증거는 GHA runtime 증거가 아니다.
   필요한 최초 현재값 게시에는 기존 검증·권리·거래·remote receipt 경로를 재사용한다.
6. 실제 HTTPS의 현재 JSON·manifest·HTML·source clocks/hash와 Pages 배포 SHA를 대조한다.
   합성 preview, Actions 성공만으로 실제 데이터 게시를 주장하지 않는다.
7. 모듈별 정확한 구현 SHA에서 서로 다른 genuine scheduled run 5회를 관찰한다.
   manual/retry/cancel/skip은 횟수에 포함하지 않는다. 이 기록 전에는 운영 단계를 완료하지 않는다.

기존 이벤트 설정은 schema 2를 유지한다. v3 active capability false, crypto 이벤트 승격 gate,
source/cursor/human 수용은 이 작업으로 변경하지 않는다. 시황 생성·finalization·publish·Telegram·exit code와
insights의 remote receipt·Pages 상태를 각각 기록한다. 기존 실패를 대시보드 성공으로 덮지 않는다.

## 복구

insights만 중지하려면 `INVESTO_INSIGHTS_MODE=off`로 설정하고 readback한다.
이는 이전 공개 current/history를 삭제하지 않으며 이후 갱신만 중지한다.
현재 reviewed execution pin은 `873cea37c878da3f9363d2457aa2a4c5a01db3fb`다.
NY Fed 표시 코드에 회귀가 있어 이전 pin `0025497d4280d9bd72bcafd04ffafe026b8ad6fc`로 복구하려면
먼저 NY Fed 세 정의의 display/public Git/retention 권한을 닫고 검증된 phase로 현재값·rolling 이력을 정리한다.
그 다음 실행 pin을 복구하고 readback한다. 이전 renderer에 새 NY Fed 권한을 남긴 채 실행하지 않는다.
이번 u181 후속은 private workflow를 바꾸지 않았으며 관찰 기록/queue/cron을 유지한다. 모호한 push는 재게시 전에 기존 receipt reconciliation으로 확인한다.
권리 철회는 qualification을 닫아 다음 검증 게시에서 현재값과 보존 이력을 정리한다.

운영 evidence는 이 디렉터리의 integration/deployment 기록에 추가한다. 5회 관찰 대기는
개발 미완료, 실제 운영 실패, 다른 유닛의 사람 검수 대기와 구분한다.

## 예약 실행 후 확인할 private metadata

기존 daily의 `insights-observation-<run_id>-<attempt>` artifact에는 allowlist metadata JSON 한 파일만 7일 보존한다.
기록기 자체는 source/Git publication/LLM/Telegram을 호출하지 않고 로컬 Git만 읽는다.
시황 실패와 별개로 관찰하며 225분 예산이 부족하면 skip한다. artifact가 없거나 unavailable이면 추정해서 채우지 않는다.

GitHub event가 schedule인 서로 다른 run ID와 원래 attempt를 확인하고,
execution_code_sha가 reviewed pin과 일치하는지 대조한다. published_sha/manifest/current hash와 공개 Git 원본을 확인하고,
각 모듈의 run_started/collection_completed/evaluated와 원천 clock을 읽는다.
마지막으로 실제 Pages 배포 SHA와 같은 snapshot을 결속한다. index/history hash는 manifest 선언값이므로 필요한 Git 파일을 추가로 재해시한다.
candidate만으로 관찰5회를 자동 완료하지 않는다. [회차 기록](scheduled-observations.json)의 미래 nominal 슬롯은 실제 실행이 아니다.


## 2026-10-26 NY Fed 자격 후속

NY Fed SOFR/EFFR/같은 유효일 금리차 세 정의만 현재 원천 조건에 따라 허용한다.
필수924자 출처·비제휴·비보증·DTCC 고지와 Investo 계산 구분을 current/history/값 앞 UI에 보존한다.
Software MIT와 원천 데이터 조건은 별도다. [결정](nyfed-qualification-decision.md), [독립 리뷰](nyfed-policy-review.md).

실행 코드873cea37는 기존0025497d 위의 다섯 파일만 반영한 별도 release다. 다른 이벤트 구현은 승격하지 않았다.
공개 데이터 정책 commit36bd84bf의 SHA256은
`2ac7295452d2fdc5f5c86af850d667f363bfd0a16537950e1dbe98988c7e28f5`이며 검토한7470923e 정책과 byte가 같다.
실행 코드 checkout의 bundled policy와 public-data cwd의 활성 정책을 혼동하지 않는다.
운영 관찰 시 execution SHA와 실제 public-data 정책 hash를 함께 확인한다.

FRED11/CoinGecko2/DeFiLlama2/Bybit2/OKX2 총19정의는 계속 보류다. 외부 라이선스 구매·허가 요청이나
legacy briefing 경로 변경은 하지 않았다. 01:56KST의 개발 조회·추가수집 없는 수동 macro 게시를
genuine scheduled 관찰로 세지 않는다. 다음 nominal은10/26 07KST이며 실제 관찰0/5를 유지한다.

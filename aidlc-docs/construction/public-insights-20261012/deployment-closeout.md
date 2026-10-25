# Public Insights 배포 기록

2026-10-25 KST. 사용자의 후속 진행 지시에 따라 원격 main 통합, 조건별 초기 데이터 게시와 기존 예약 갱신 연결을 마쳤다.
모듈별 실제 예약 실행 관찰은 0/5이며 마지막 운영 수용 단계는 미완료로 유지한다.

| 화면 | 실제 공개 자료 | 초기 게시 SHA | Pages |
| --- | --- | --- | --- |
| [매크로 환경판](https://murphygo.github.io/investo/insights/macro/) | 미 국채 4만기와 스프레드 2개, 2026-10-23 원천 현지일 | `9ad4b26e6329aec287eae96c77147413e47f410b` | [40183971053](https://github.com/murphyGo/investo/actions/runs/40183971053) SUCCESS |
| [주요 일정](https://murphygo.github.io/investo/insights/calendar/) | 19건: 현지 날짜 14건, 확인된 시각 5건 | `e36595786f7d00c86c703a0653a78ab5795a6134` | [40184130560](https://github.com/murphyGo/investo/actions/runs/40184130560) SUCCESS |
| [크립토 시장 내부](https://murphygo.github.io/investo/insights/crypto/) | Alternative.me 공포·탐욕 1개, 원천 시각 2026-10-25 00:00 UTC | `1f6b37c6bcfea1f2ac11fa8716ce5219a441f337` | [40184291651](https://github.com/murphyGo/investo/actions/runs/40184291651) SUCCESS |

자료 수집은 09:38:49–09:39:44 UTC의 실제 로컬 기존 adapter collection이다. BLS는 0건이었다.
표시할 수 없는 값은 0으로 채우지 않았다. 정책은 46개 정의 중 24개 허용/22개 차단을 유지하며
크립토의 나머지 8개 정의는 공개 재배포·Git 보존 조건이 미확인되어 닫힌 상태다.
초기 이력은 허용된 실제 관찰만 포함하며 과거 시계열이나 비교값을 만들어 넣지 않는다.

## 구현과 원격 검증

현재 main `0768d780`과 feature `cb56fd7d`를 별도 작업공간에서 통합했다. 감사 이력 양쪽을 보존했다.
실행 pin은 `0025497d4280d9bd72bcafd04ffafe026b8ad6fc`다.
[구현 CI 40182882842](https://github.com/murphyGo/investo/actions/runs/40182882842)는
7344 passed/1 existing skip, Ruff·format 818개, mypy 344개, 정책·Node 29개·strict docs·Material·Calendar를 통과했다.
독립 통합 리뷰는 직접 교차 회귀 67개 통과, 미해결 C/H/M 0이다.

실제 세 모듈 데이터를 포함한 최종 게시 `1f6b37c6`의
[CI 40184291647](https://github.com/murphyGo/investo/actions/runs/40184291647)도 전체 7344 passed/1 existing skip(506.90초)와 모든 gate를 통과했다.
중간 매크로·일정 게시의 quality도 성공했다. 기존 skip은 migrated public groups dataset이며 별도 schema2 fixture를 검증한다.

최종 실제 HTTPS에서 manifest/current/history/CSS/JS 9파일의 byte hash와 세 HTML snapshot이 일치했다.
임시 Chromium154에서 실제 운영 URL의 390×844/1440×900 및 두 테마 12화면을 검증했다.
페이지 overflow와 JS 오류가 없고 글자 대비 4.5:1 이상을 확인했다. 테마 애니메이션 완료 후 대표 화면을 직접 읽었다.
별도 로컬 합성 데이터 48조건은 JS off/200% 상당 뷰포트/키보드/필터/이력 hash 불일치까지 검증했다.
이 headless 검증은 기존 Browser connector나 다른 유닛의 native viewport gate 복구를 뜻하지 않는다.

## 기존 운영에 연결한 내용

private workflow commit `b58c7f9f6069062e274a855e472ab630cadbdcd1`은 INSIGHTS env 2개와 Pages 조건/SHA 식만 변경했다.
`queue: max`, auth owner, timeout, 기존 secrets를 보존하고 원격 bytes를 대조했다.
`REVIEWED_CODE_SHA=0025497d…`, `INVESTO_INSIGHTS_MODE=active`,
`INVESTO_INSIGHTS_MODULES=macro,calendar,crypto`를 실제 원격 readback으로 확인했다.
private daily만 active이며 공개 daily는 disabled_manually다. 적용 전 실행 중인 private 작업은 없었다.
기존 이벤트 schema 2, v3 active false와 크립토 이벤트 승격 gate는 유지한다.

수동 초기 게시는 동일 collection을 기존 검증·거래·remote receipt 경로로 매크로→일정→크립토 순서로 게시했다.
각 초기 게시의 추가 source HTTP/LLM/Telegram 호출은 0이다. 전체 시황 workflow를 수동 실행하거나 별도 scheduler를 추가하지 않았다.
원래 dirty root와 별도 작업을 보존했으며 root의 local main을 이동하지 않았다.

## 남은 운영 수용

모듈별 정확한 구현 SHA에 결속한 서로 다른 genuine scheduled run 5회를 관찰해야 한다.
현재 모두 0/5다. 로컬 source probe·수동 초기 게시·retry를 예약 관찰로 세지 않는다.
각 실행에서 source clocks/범위, insights receipt, Pages SHA를 확인하고 기존 시황의 생성·finalization·게시·Telegram·exit code는 별도로 기록한다.
이 증거가 모일 때 u180/u181/u183 Step8과 u182 Step7을 완료한다.

모든 count/hash/receipt/readback은 [운영 증거](operations-evidence-20261025.json),
복구와 관찰 절차는 [운영 runbook](operations-runbook.md)에 있다.

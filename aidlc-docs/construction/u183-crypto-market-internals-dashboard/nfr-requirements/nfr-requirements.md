# u183 Focused NFR requirements

작성일: 2026-10-12 · u183 · 상태: 2026-10-25 사용자 후속 “진행시켜” 지시로 설계 채택. 로컬 구현·검증을 진행하며 운영 활성화는 별도다.

기존 NFR-001~008, R10 live-recording/합성 구별, R13 secret hygiene, Partial PBT 의 pure validation/직렬화만 적용하는 범위를 재사용한다. Security Baseline extension 거절을 새 데이터/게시의 명시적 보안 조건 면제로 해석하지 않는다.

| ID | 요구와 수용 조건 |
| --- | --- |
| NF183.1 | 5existing adapters·현재 requests/fallback/routing/keys/cost·legacy24h 제목 bytes 를 보존. 새 화면의 typed semantics 만 명확히 함. |
| NF183.2 | 소스별 public display+retention+attribution·GHA/access/fields/time 결속을 검증. 미확인/철회 card 와 history 숫자 공개 0. |
| NF183.3 | provider/contract/cycle/time/source-response 역할·fraction/percent·USDnotional fixtures 와 negative 범위를 source docs 로 고정. source switch/history/caps 검증 필수. |
| NF183.4 | current7slots·부분 상태를 noJS 제공. incremental module CSS+JS gzip20KiB, HTML100KiB 이하·historylazy. 두 viewport/theme/keyboard/200% 검증. |

## 공통 상한과 실패 정책

[C3–C7](../../public-insights-20261012/contracts.md)의 source 권리·raw/private 분리·payload/보관 상한·source cadence/freshness·time/단위·default-off·remote receipt/CAS·취소/복구를 소비한다. no-paid 와 no-SDK 호출 정책은 유지한다. 새 소스·실시간 API·신규 공개 key path 를 추가하지 않는다.

## 검증 연결

[실행 계획](../../plans/u183-crypto-market-internals-dashboard-code-generation-plan.md)의 tests/AC, [수용 시나리오](../../public-insights-20261012/acceptance-scenarios.md)를 실제 구현 SHA 에 연결한다. source fixture 는 실제로 확인한 endpoint recording 만 live evidence 로 기록하고 합성 숫자/clock case 와 혼동하지 않는다. 현재 draft 를 runtime/viewport qualification 으로 기록하지 않는다.

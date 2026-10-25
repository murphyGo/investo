# u181 Focused NFR requirements

설계 2026-10-12 · 구현 검증 2026-10-25 · 사용자 후속 진행 지시로 설계 채택. 로컬 7/8 완료, 운영 Step8 pending.

기존 NFR-001~008, R10 live-recording/합성 구별, R13 secret hygiene, Partial PBT 의 pure validation/직렬화만 적용하는 범위를 재사용한다. Security Baseline extension 거절을 새 데이터/게시의 명시적 보안 조건 면제로 해석하지 않는다.

| ID | 요구와 수용 조건 |
| --- | --- |
| NF181.1 | source requests/key paths/registry/routing 증가 0. FRED optional key 없이 Treasury/NY Fed/BLS siblings 유지. |
| NF181.2 | 13slot 단위/seasonality/source-date/period 와 spread provenance 검증. public attribution 와 source-specific freshness 를 C2–C4 로 대조. |
| NF181.3 | 첫 읽기 current-only 가능;30 개 관측 차트는 available history 에서만. noJS 카드/만기표/출처와 keyboard/theme/200% 확대 제공. |
| NF181.4 | page critical 신규 CSS+JS gzip50KiB 이하, initial HTML100KiB 이하; history lazy-load. 기존 site bundle 전체 제한으로 오인하지 않음. |

## 공통 상한과 실패 정책

[C3–C7](../../public-insights-20261012/contracts.md)의 source 권리·raw/private 분리·payload/보관 상한·source cadence/freshness·time/단위·default-off·remote receipt/CAS·취소/복구를 소비한다. no-paid 와 no-SDK 호출 정책은 유지한다. 새 소스·실시간 API·신규 공개 key path 를 추가하지 않는다.

## 검증 연결

[실행 계획](../../plans/u181-macro-environment-dashboard-code-generation-plan.md)의 tests/AC, [수용 시나리오](../../public-insights-20261012/acceptance-scenarios.md)를 실제 구현 SHA 에 연결한다. source fixture 는 실제로 확인한 endpoint recording 만 live evidence 로 기록하고 합성 숫자/clock case 와 혼동하지 않는다. 현재 draft 를 runtime/viewport qualification 으로 기록하지 않는다.

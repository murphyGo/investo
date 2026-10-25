# u182 Focused NFR requirements

작성일: 2026-10-12 · u182 · 상태: 2026-10-25 사용자 후속 진행 지시로 설계 채택. 로컬 구현·검증 진행 중이며 운영 활성화는 별도다.

기존 NFR-001~008, R10 live-recording/합성 구별, R13 secret hygiene, Partial PBT 의 pure validation/직렬화만 적용하는 범위를 재사용한다. Security Baseline extension 거절을 새 데이터/게시의 명시적 보안 조건 면제로 해석하지 않는다.

| ID | 요구와 수용 조건 |
| --- | --- |
| NF182.1 | 기존 4adapter·routing/keys/HTTP/forward cap 보존. 추가 raw payload/본문 source 접근 0. |
| NF182.2 | timezone/precision/range/period/identity fixture, DST 와 synthetic midnight negative 필수. 발표완료/시각 발명 0. |
| NF182.3 | 기본 7 일 mobile list, noJS30 일 기본 접근/anchor, keyboard filter·focus·screen-reader date basis 를 제공. 고정 가이드와 source link 표시. |
| NF182.4 | C5 의 128events/256KiB current 적용, calendar history0. module JS+CSS incremental gzip15KiB, HTML120KiB 이하. |

## 공통 상한과 실패 정책

[C3–C7](../../public-insights-20261012/contracts.md)의 source 권리·raw/private 분리·payload/보관 상한·source cadence/freshness·time/단위·default-off·remote receipt/CAS·취소/복구를 소비한다. no-paid 와 no-SDK 호출 정책은 유지한다. 새 소스·실시간 API·신규 공개 key path 를 추가하지 않는다.

## 검증 연결

[실행 계획](../../plans/u182-upcoming-events-dashboard-code-generation-plan.md)의 tests/AC, [수용 시나리오](../../public-insights-20261012/acceptance-scenarios.md)를 실제 구현 SHA 에 연결한다. source fixture 는 실제로 확인한 endpoint recording 만 live evidence 로 기록하고 합성 숫자/clock case 와 혼동하지 않는다. 현재 draft 를 runtime/viewport qualification 으로 기록하지 않는다.

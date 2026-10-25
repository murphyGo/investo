# u180 Focused NFR requirements

작성일: 2026-10-12 · u180 · 상태: 사용자 “유닛 하나씩 진행시켜” 지시로 설계 채택, 로컬 구현·검증 진행. 공개/운영 활성화는 pending.

기존 NFR-001~008, R10 live-recording/합성 구별, R13 secret hygiene, Partial PBT 의 pure validation/직렬화만 적용하는 범위를 재사용한다. Security Baseline extension 거절을 새 데이터/게시의 명시적 보안 조건 면제로 해석하지 않는다.

| ID | 요구와 수용 조건 |
| --- | --- |
| NF180.1 | 추가 source HTTP/LLM/Telegram0. 기존 key·timeout/retry/concurrency/default enabled source 정책 유지. |
| NF180.2 | C5 의 32metrics/128events/256KiB current/4MiB history/module/12MiB 전체 및 private aggregate512KiB 를 enforce. |
| NF180.3 | 추가 phase60s, local10s/remote45s/cleanup5s, CPU5s·추가 RSS96MiB 이하; 최대 fixture 와 cancel/prog-error 로 검증. |
| NF180.4 | raw envelope/body/secret/query 로그·fixture·Pages·repo 유출 0. 기존 R13 redaction 과 scoped positive/negative fixture 재사용. |
| NF180.5 | remote-confirmed baseline/CAS, partial·unknown·rollback, 여러 파일 hash 일관성; unrelated dirty/index/files 보존. |
| NF180.6 | source 지원연도/공휴일/timezone·발표정책을 공식 근거로 고정. unsupported time/freshness 는 unknown 이며 raw 숫자 의미를 새로 추론하지 않음. |

## 공통 상한과 실패 정책

[C3–C7](../../public-insights-20261012/contracts.md)의 source 권리·raw/private 분리·payload/보관 상한·source cadence/freshness·time/단위·default-off·remote receipt/CAS·취소/복구를 소비한다. no-paid 와 no-SDK 호출 정책은 유지한다. 새 소스·실시간 API·신규 공개 key path 를 추가하지 않는다.

## 검증 연결

[실행 계획](../../plans/u180-public-insights-snapshot-and-publication-code-generation-plan.md)의 tests/AC, [수용 시나리오](../../public-insights-20261012/acceptance-scenarios.md)를 실제 구현 SHA 에 연결한다. source fixture 는 실제로 확인한 endpoint recording 만 live evidence 로 기록하고 합성 숫자/clock case 와 혼동하지 않는다. 현재 draft 를 runtime/viewport qualification 으로 기록하지 않는다.

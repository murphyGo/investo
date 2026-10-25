# Session: u181 매크로 환경판

2026-10-25 · 사용자 “진행시켜” · u180 기반의 u181 로컬 구현 및 검증 7/8.

기존 FD/NFR/code plan을 채택했다. 원천 응답의 opt-in typed 관측, closed13 recipes, Decimal exact spread·부모 권한, current-only UI, exact history 비교·lazy reader, hub/nav를 구현했다. 신규 adapter/HTTP/key/routing/LLM/Telegram 또는 source 기본값 변경은 없다.

첫 독립 리뷰의 parent last-good 권한 누락, 파생 범위와 Decimal 정밀도, inline history의 lazy-load 편차를 수정했다. 최종 확인한 C/H/M0, reviewer29 tests. 기존 메뉴명 회귀는 원래 `미국 섹터` 이름을 유지해 해결했다. 모바일 표의 Material negative margin과 다크 메뉴 대비를 insights page 범위에서 보완했다.

검증: 현재 collection7046의 모든 node를 full4 shards, 수정 shard와 최종 scoped로 대조해7045 passed/1 known skipped, 누락0. 최종112 tests, Ruff/format763·mypy322·정책/strictMkDocs/Material/Calendar 및 실제 Chromium16 cases. 200%는 CSS viewport/DPR 등가 확대다. 별도 임시 browser profile과 합성 fixture만 사용했다.

Treasury 실제 응답 replay는 2026-10-23 typed6개를 확인했다. SOFR200·BLS CPI503과 나머지 접근 미실행을 구별했다. 실제 원천 전체/production source 성공을 주장하지 않는다. permission은9 allow/4 blocked로 기록하되 기본 modeoff와 운영 gate를 유지했다.

작업은 기존 `.tmp/public-insights-unit-design-20261012`, branch `codex/public-insights-unit-design-20261012`에 있다. base55c00fc8과 현재 remote dd113ae4를 대조했고 u181 어댑터/자산의 upstream 변경이 없음을 확인했다. u180 미커밋 기반 작업을 보존했으며 최신 main으로 통합·commit/push 또는 실제 배포는 수행하지 않았다. root dirty와 타 유닛 상태를 보존했다.

새 ADR/debt는 없다. 이미 채택한 C1–C7/MkDocs/receipt 경계를 재사용했으며 DEBT-090을 해결했다고 표시하지 않는다. 운영 Step8의 실제 source 조건·private pin/mode·Pages·5회 scheduled 수용은 pending. 다음 코드 대상은 u182 주요 일정이다.

[구현과 변경 파일](../../aidlc-docs/construction/u181-macro-environment-dashboard/code/summary.md) · [AC 대조](../cross-checks/2026-10-25-u181-macro-environment-dashboard.md) · [검증](../../aidlc-docs/construction/u181-macro-environment-dashboard/code/validation.json).

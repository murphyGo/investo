# Unit-of-Work Dependencies & Delivery Order: Investo

**Date**: 2026-04-27

---

## Unit Dependency Matrix

행 = 의존하는 unit (caller). 열 = 의존받는 unit (callee). `models`는 unit이 아니지만 모두가 의존하므로 별도 표기.

| Unit \ Depends on | models | u1 sources | u2 briefing | u3 publisher | u4 notifier | u5 orchestrator |
|-------------------|:------:|:----------:|:-----------:|:------------:|:-----------:|:---------------:|
| **u1 sources** | ✅ | — | — | — | — | — |
| **u2 briefing** | ✅ | — | — | — | — | — |
| **u3 publisher** | ✅ | — | — | — | — | — |
| **u4 notifier** | ✅ | — | — | — | — | — |
| **u5 orchestrator** | ✅ | ✅ | ✅ | ✅ | ✅ | — |
| **u6 infra/CI** | — | — | — | — | — | ✅ (calls `python -m investo`) |

### Properties
- 순환 의존성 없음 (DAG)
- u5 orchestrator만 다른 unit을 호출
- u1~u4는 서로 독립 — Q4 convention rule로 강제
- u6은 외부 entrypoint를 통해 u5만 호출

---

## Delivery Order (Q2=A — Sequential Incremental Delivery)

```
0. models (foundation)
        |
        v
1. u1 sources (US-001, US-008)
        |   verify: PoC fetch from 1 reference source
        v
2. u2 briefing (US-002, US-009)
        |   verify: NormalizedItem(들) -> Briefing markdown via Claude Code CLI
        v
3. u3 publisher (US-003, US-006)
        |   verify: Briefing -> archive/YYYY/MM/...md committed
        v
4. u5 orchestrator (US-005)
        |   verify: pipeline.run_pipeline(date) end-to-end (with mocked notifier)
        v
5. u4 notifier (US-004, US-007)
        |   verify: Telegram channel + operator chat send
        v
6. u6 infra/CI
            verify: GitHub Actions cron runs full pipeline + Pages deploy
```

### Why this order?
1. **models first**: leaf node, all units depend on it. Unstable models break everything.
2. **sources before briefing**: briefing의 입력이 NormalizedItem이므로 sources 산출물이 있어야 briefing의 fixture 생성과 검증이 자연스럽다.
3. **briefing before publisher**: publisher가 검증할 disclaimer는 briefing이 만든 결과를 입력으로 받으므로.
4. **orchestrator before notifier**: notifier는 orchestrator의 happy path 마지막 단계라, orchestrator skeleton이 있어야 통합 위치가 명확. 또한 alert 흐름(orchestrator의 실패 처리)은 orchestrator backbone에 의존.
5. **notifier last (before infra)**: 외부에 메시지를 실제로 발송하는 단계는 안정화 마지막에 둠 — 잘못된 발송으로 인한 외부 노출 위험 최소화.
6. **infra last**: cron 활성화는 모든 코드가 안정된 뒤에. 이전까지는 workflow_dispatch + 수동 실행으로 검증.

---

## Build Phase Gates

각 단위 완료 시점의 "다음으로 넘어가도 되는가" 체크:

| Unit | Gate Criteria |
|------|---------------|
| models | pydantic 모델 정의 + 직렬화 round-trip PBT 통과 |
| u1 sources | 1개 reference 어댑터 + registry/aggregator + 부분 실패 단위 테스트 |
| u2 briefing | Claude Code CLI subprocess wrapper + two-stage prompt + disclaimer auto-append |
| u3 publisher | archive write + git push + disclaimer verify (단위 테스트) |
| u5 orchestrator | run_pipeline 통합 테스트 (외부 호출 mocked, Q9=B 정책 검증) |
| u4 notifier | BriefingPublisher / OperatorAlerter 분리 + httpx mock 단위 테스트 |
| u6 infra/CI | workflow_dispatch 1회 성공 → cron 활성화 |

---

## Parallelization Opportunities

솔로 개발이라 진정한 병렬은 없지만, 한 unit 내에서 sub-task를 병렬로 진행 가능:

- **u1 안에서**: registry/aggregator (코어) ↔ 개별 source 어댑터 (병렬 작업)
- **u2 안에서**: prompts.py (LLM 미의존) ↔ claude_code.py wrapper (PoC subprocess test) ↔ disclaimer.py (코드 상수)
- **u4 안에서**: BriefingPublisher와 OperatorAlerter는 독립

이는 PR 단위를 작게 쪼개는 데 활용.

---

## Rollback Strategy

각 unit이 머지된 후 문제 발생 시:
- **코드 롤백**: `git revert <commit>` — 모든 unit이 단일 repo이므로 단순.
- **시황 롤백**: 게시된 archive markdown은 history 보존 (덮어쓰기 + 이전 버전은 git log로 접근 가능). 잘못된 시황은 git revert 후 mkdocs 재빌드.
- **Cron 비상 정지**: GitHub Actions UI에서 workflow disable.
- **Telegram 채널 메시지 회수**: Telegram Bot API의 `deleteMessage` 사용 가능 (24시간 내).

---

## Dependency Risks

| Risk | Mitigation |
|------|------------|
| `models` 변경 시 모든 unit 영향 | 변경은 PR로 명확히 표시 + 모든 unit test 회귀 |
| u5 orchestrator가 4 unit 모두 import → 전파 위험 | orchestrator 내부에서 각 unit과 thin adapter (즉 `_stage_*`) 통해 격리 |
| u6 workflow 수동 점검 부족 | 첫 cron 실행 후 1주는 매일 결과 확인 + 실패 alert 검증 |
| Claude Code CLI binary 부재 (GH Actions runner) | u2 도입 전에 install step 정합성 검증 (curl/install) |

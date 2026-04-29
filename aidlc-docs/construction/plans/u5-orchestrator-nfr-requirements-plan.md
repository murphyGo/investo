# NFR Requirements Plan: `u5 orchestrator`

**Date**: 2026-04-30
**Unit**: u5 orchestrator — pipeline integration (`run_pipeline`, stage runners, date resolution, entrypoint)
**Stage**: NFR Requirements (FD = SKIP per execution-plan; NFR Requirements = EXECUTE)

**Plan source**:
- `aidlc-docs/inception/application-design/application-design.md` — Time Budget table + Error Policy (Q9=B) summary
- `aidlc-docs/inception/application-design/component-methods.md` — C5 orchestrator method signatures
- `aidlc-docs/inception/application-design/unit-of-work.md` — u5 module structure + DoD
- `docs/requirements.md` — NFR-001 (≤10분) / NFR-003 (graceful degradation + retry) / NFR-006 (testing) / NFR-007 (secrets)

---

## Context Recap

u5 orchestrator is the **integration glue**. It does not do data work — it composes the four work units (u1 sources, u2 briefing, u3 publisher, u4 notifier) under a single `run_pipeline` async function and a `python -m investo` entrypoint. Application-design has already locked in:

- **Q9=B graceful degradation policy** with stage-by-stage failure routing (`application-design.md` Error Policy Summary).
- **Time budget table** — collect ≤ 4 min / generate ≤ 4 min / publish ≤ 1 min / notify ≤ 30 s / GHA overhead ≤ 30 s = **10 min total**.
- **Component-methods C5** — `run_pipeline(target_date)` returns `PipelineResult`; never raises on stage failure; only programmer errors propagate.
- **Module boundary** — orchestrator is the ONLY unit allowed to import all four other work units.

This plan converts those design-level specs into **measurable, testable acceptance criteria** (the AC-001-X / AC-003-X form used in u1/u2 NFR Requirements) plus the few open decisions u5 actually needs to make.

---

## Steps

- [x] **1.** Generate context-appropriate questions (this file). 10 questions across NFR-001 timeout enforcement / NFR-003 status taxonomy + retry / NFR-005 date resolution + concurrency + logging / NFR-006 testing / NFR-007 env vars / tech stack subprocess+asyncio. **Pre-filled with proposed answers** based on existing application-design.md (Q9=B Error Policy + Time Budget) + CLAUDE.md project rules + u1-u4 patterns already shipped — reduces user review burden to "approve / change Qn to alternative". The user can override any answer; the proposed answers are NOT decisions.
- [ ] **2.** User review pass — approve proposed answers OR request changes. Resolve any disagreement with follow-up clarification.
- [ ] **3.** Generate `aidlc-docs/construction/u5-orchestrator/nfr-requirements/nfr-requirements.md` (measurable AC for NFR-001 / NFR-003 / NFR-005 / NFR-006 / NFR-007 as they touch u5; ~10-15 AC per Q10)
- [ ] **4.** Generate `aidlc-docs/construction/u5-orchestrator/nfr-requirements/tech-stack-decisions.md` (asyncio / subprocess / logging / retry library choices)
- [ ] **5.** Present 2-option AIDLC completion message; wait for explicit approval
- [ ] **6.** Update `aidlc-state.md` + `audit.md` on approval

---

## Questions

### Q1. Top-level timeout enforcement (NFR-001)

**Background**: The application-design's Time Budget table allocates per-stage budgets summing to 10 minutes. Each unit (u1/u2/u3/u4) already has internal timeouts (httpx 30 s / source, two-stage Claude 4 min total via `RetryBudget`, git push retry, etc.). The orchestrator can either:
- **(A) Trust the unit-level timeouts** — no orchestrator-level wall-clock enforcement. If a unit hangs beyond its budget, GHA's job-level timeout (set via `timeout-minutes` in YAML) kills the whole job.
- **(B) Wrap each `_stage_*` call in `asyncio.wait_for(...)` with the design-level budget** — orchestrator-side enforcement; on timeout, route the stage to its Q9=B failure policy.
- **(C) Hybrid: orchestrator sets a single wall-clock deadline (e.g., 9 min from start), checked between stages — no mid-stage cancellation.**

What did you have in mind?

**[Answer]:** A
[정확히는 A + GHA 'timeout-minutes: 12' 안전망 (10 min 설계예산 + 2 min 여유). 각 unit의 내부 타임아웃이 1차 방어선이고 GHA가 마지막 안전망. orchestrator가 mid-stage cancel하지 않으므로 부분 결과 보존 정책이 단순함]

### Q2. PipelineResult status taxonomy (NFR-003)

**Background**: `application-design.md` mentions `Result.status SUCCESS/PARTIAL/FAILED` but does not define the boundary precisely. The Q9=B error policy implies:
- **SUCCESS**: every stage succeeded, including the public-channel notify
- **FAILED**: collect-empty, generate-final-fail, disclaimer-missing, publish-git-fail (any stage that aborts publish)
- **PARTIAL**: ??? (the only mentioned case is "notify_briefing best-effort failure → publish 살림 → PARTIAL")

Are there other PARTIAL cases beyond "publish succeeded but public-channel notify failed"?
- Is per-source collect failure (graceful degradation in collect) a PARTIAL or still SUCCESS as long as some sources returned?
- Is operator-alert failure during a FAILED run still FAILED, or a separate sub-status?

**[Answer]:** PARTIAL은 정확히 한 케이스: publish 성공 + public-channel notify 실패. 그 외:
- 단일 source collect 실패 (다른 source 성공) → SUCCESS (Q9=B 정의대로 graceful)
- 모든 source 실패 (collect 전체 비어있음) → FAILED
- operator-alert 실패는 FAILED 상태에 영향 없음 (이미 FAILED 인 상태에서 alert 자체가 best-effort). GHA log에만 마킹 (FR-007 마지막 AC).

### Q3. Date resolution edge cases (US-005)

**Background**: `resolve_target_date(now_utc, weekday_only_us_close=True)`:
- KST 평일 07:00 cron → 미국장 마감일(전일 KST)
- 토요일 09:00 cron → 금요일

Open: 미국 공휴일 (Thanksgiving, July 4 등) 처리. 미국장이 닫힌 날의 다음 거래일 KST 07:00 cron이 "어제" 데이터를 보면 비어 있음. 어떻게 처리?

- **(A) 무시** — 미국 휴장일 다음날도 어제 날짜로 시도. 데이터 비면 collect-empty → FAILED → operator alert. 운영자가 수동 처리.
- **(B) 미국 trading-day calendar 내장** — `pandas_market_calendars` 같은 라이브러리로 가장 최근 거래일 자동 찾기.
- **(C) 단순 규칙**: 미국 공휴일 일부(주요 6-7일)는 하드코딩 + 그 외는 (A) 정책.

NFR-002 (월 $0) 관점에서 (B)는 의존성 추가, (A)는 의존성 0 + 연 ~10회 운영자 개입.

**[Answer]:** A
[연 ~10회 수동 처리는 1인 운영 부담 허용 범위. 의존성 최소화가 더 중요. operator alert로 충분히 가시성 확보. (NFR-002 의존성 줄이기 우선; pandas_market_calendars는 transitively pandas/numpy 끌어옴 → 거대)]

### Q4. Retry strategy at orchestrator level (NFR-003)

**Background**: 각 unit이 이미 자체 retry를 가지고 있다:
- u1: `retry_get` (3-attempt exp backoff per source)
- u2: `RetryBudget` (Claude Code subprocess, ~3-attempt with timeout budget)
- u3: `commit_and_push` (3-attempt git retry with idempotent-commit detection)
- u4: 단일 시도 (Telegram failure → SendResult.ok=False, no retry — graceful)

Orchestrator-level meta-retry가 필요한가?
- **(A) None** — unit-level retry가 1차 방어선; orchestrator는 결과만 라우팅.
- **(B) Generate stage only** — Claude Code subprocess가 transient 실패 가능성이 가장 높으므로 generate만 한 번 더 retry.
- **(C) All stages** — collect / generate / publish 각각 1회 추가 retry (cron 주기 24h이므로 한 번의 실행에 신뢰성 집중).

NFR-001 10분 예산 안에서.

**[Answer]:** A
[unit 내부 retry로 충분. orchestrator meta-retry는 budget 압박 + 복잡도 증가. generate transient 실패는 다음날 cron으로 자연 복구 (1인용 도구).]

### Q5. Concurrency between stages (NFR-001)

**Background**: 4 stages를 sequential로 실행하면 위 시간 예산이 가장 안전. `notify_briefing`은 publish 직후 = 의존성. `collect`와 `generate`는 sequential (generate가 collect 결과 의존). publish는 generate 결과 의존.

→ 사실상 모든 stage가 직렬 의존이라 stage-level 병렬화 여지 없음.

**확인만**: stage는 모두 sequential. 단, **collect 내부**는 이미 `asyncio.gather` (u1 aggregator)로 source 병렬. orchestrator는 추가 병렬화 안 함.

**[Answer]:** 확인. 모든 stage sequential. stage 내부 병렬은 u1 aggregator의 asyncio.gather가 유일하고 이미 구현됨. orchestrator는 추가 병렬 안 함.

### Q6. Logging strategy (NFR-005 / NFR-006)

**Background**: GitHub Actions에 stdout/stderr이 곧 영구 로그. 추가 로그 시스템 없음.

- **(A) print()로 단순 출력** — 의존성 0, 구조화 없음.
- **(B) Python `logging`** — 표준 모듈, 구조화된 레벨 (INFO/WARNING/ERROR), 의존성 0. orchestrator stage 시작/종료, 단계별 elapsed time, source별 success/fail 카운트 정도.
- **(C) structlog** — JSON 구조화 로그, 외부 의존성 +1. GHA 로그 뷰어에서는 가독성 떨어짐 (1인용).

운영자 alert는 별도 (OperatorAlerter); 로깅은 GHA 로그 디버깅용.

**[Answer]:** B
[표준 logging이 균형. structlog는 GHA 1인 운영에 과함. INFO 레벨로 stage 경계 + elapsed + source별 결과 + 최종 PipelineResult.status. WARNING은 graceful degraded source, ERROR는 stage failure.]

### Q7. Subprocess + asyncio interaction (tech stack)

**Background**: u3 `commit_and_push`는 sync `subprocess.run` (간단). u2 `claude_code.py`도 sync `subprocess.run`. orchestrator의 `run_pipeline`은 async.

- **(A) Wrap sync subprocess in `asyncio.to_thread`** — 다른 stage가 async이므로 일관성. CPU 안 쓰지만 진행은 됨.
- **(B) 각 stage 함수가 각자 알아서** — `_stage_publish`는 sync로 호출 (`commit_and_push`), `_stage_generate`는 sync (`generate_briefing`). orchestrator만 async (collect는 진짜 async).

application-design.md에 이미 명시: `_stage_collect`/`_stage_generate`/`_stage_publish`/`_stage_notify_briefing` 모두 `async def`.

→ (A)로 가야 일관성. 단순한 wrapping.

**[Answer]:** A
[component-methods.md에서 모든 _stage_* 가 async로 선언됨. 동기 호출은 asyncio.to_thread로 wrap해서 일관된 async 인터페이스 유지. 성능 효과는 미미하나 코드 일관성 가치가 큼 (특히 테스트 await 패턴 통일).]

### Q8. Test record/replay strategy (NFR-006)

**Background**: u2가 이미 `FakeClaudeRunner` (record/replay fixture mechanism)를 도입. integration test에서 LLM call을 record/replay로 재현.

orchestrator integration test (`tests/integration/test_pipeline.py`)는:
- u1 sources의 HTTP를 어떻게 mock?
- u2 LLM을 어떻게 record/replay?
- u3 git을 어떻게 mock?
- u4 telegram을 어떻게 mock?

각 unit 테스트가 이미 mock 패턴 확립 (httpx.MockTransport for u1+u4, FakeClaudeRunner for u2, GitRunner Protocol for u3). orchestrator integration test는 그것들을 모두 동시에 활성화.

확인 질문: integration test에서 LLM은 **재생 fixture** (FakeClaudeRunner)를 쓰고, 외부 HTTP는 모두 MockTransport, git은 fake GitRunner. 새 mock 인프라는 도입 안 함.

**[Answer]:** 확인. 새 mock 도입 없음. 기존 unit 테스트의 mock 패턴 4개 (httpx.MockTransport / FakeClaudeRunner / fake GitRunner) 모두를 integration test가 동시 활성화. orchestrator는 그 dependency injection seam만 노출 (constructor params or function args).

### Q9. Environment variable validation (NFR-007 / US-005)

**Background**: `main()`은 `CLAUDE_CODE_OAUTH_TOKEN`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_BRIEFING_CHANNEL_ID`, `TELEGRAM_OPERATOR_CHAT_ID`, `SITE_URL_BASE` 5개 env var 읽음.

CLAUDE.md #5: `TELEGRAM_BRIEFING_CHANNEL_ID` ≠ `TELEGRAM_OPERATOR_CHAT_ID` 강제.

env validation 시점:
- **(A) main() 시작 직후** — 빠른 실패. 누락/같음이면 즉시 exit 1 + GHA log에 명시. operator alert 못 보냄(token 없을 수 있으므로).
- **(B) run_pipeline 진입 시** — operator alert 시도해볼 수 있음 (token 있으면). 그러나 token 자체가 누락이면 결국 alert 실패.

→ (A)가 단순하고 안전. token 누락은 setup 단계 문제이므로 operator alert 못 가는 것이 정상 (GHA email 알림이 대신 작동).

**[Answer]:** A. 단, alert 가능성을 위한 보강:
- TELEGRAM_BOT_TOKEN + TELEGRAM_OPERATOR_CHAT_ID 두 개만 있으면 alert 한 번 시도 ("config error: missing X")
- 그 외 환경에서는 GHA stderr + exit 1로 종료 (GHA email alert가 fallback)
- chat_id 동일성 체크는 명시적 ConfigError로 raise.

### Q10. NFR acceptance criteria depth (planning input only)

이 NFR Requirements 단계 결과물 (`nfr-requirements.md`)은 다음 단계 (Code Generation) 의 testable AC가 됨. u1과 u2 NFR Requirements는 ~30+ AC를 생성했지만 u5는 통합 unit이라 AC 수가 더 적을 가능성 (대부분 application-design에서 이미 봉인).

예상되는 AC:
- AC-001-1 (≤ 10분 wall-clock; integration test에서 검증 어려움 → soft AC w/ smoke timing)
- AC-001-2 (각 stage 함수가 elapsed time을 PipelineResult에 기록)
- AC-001-3 (entrypoint timeout-minutes: 12 in workflow YAML — u6에서 검증)
- AC-003-1 ~ AC-003-N (Q9=B 표 각 row별 1 AC)
- AC-005-1 (status taxonomy SUCCESS/PARTIAL/FAILED)
- AC-005-2 (date_resolution KST 평일/토요일 분기 계산)
- AC-006-1 (record/replay fixture로 integration test pinning)
- AC-007-1 (env vars validation at main() entry; chat_id 동일성 거부)
- AC-007-2 (구조화 로깅 — INFO/WARNING/ERROR; 토큰 redaction은 u4 내부에서 이미 처리)

이 정도 ~10-15개 AC면 적당한가, 아니면 더 세분?

**[Answer]:** 충분. ~10-15개 정도가 적절. 통합 unit이라 application-design에서 이미 봉인된 부분이 많아 AC가 단위 unit보다 적은 게 자연스러움. 다만 Q9=B 에러 정책 표 7개 row는 각각 1 AC로 펼쳐야 (AC-003-1 ~ AC-003-7). date_resolution 도 평일/토요일/공휴일 = 3 AC 정도로 분할.

---

## How to Approve

이 plan은 u5 NFR Requirements의 단일 출처. 답변 후 `approve` 또는 `changes [Qn]` 으로 응답.

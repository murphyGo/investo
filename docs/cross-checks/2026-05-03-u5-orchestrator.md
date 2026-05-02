# Cross-Check Report: u5 orchestrator

**Scope**: Unit `u5 orchestrator` (pipeline composer + `python -m investo` entrypoint)
**Date**: 2026-05-03
**Checked by**: Codex
**Triggered by**: `dev-investo` health check after all construction stages completed

---

## Inputs

| Document | Role |
|----------|------|
| `docs/requirements.md` | Single-source-of-truth FR/NFR list |
| `aidlc-docs/inception/user-stories/stories.md` | US-005 / US-007 acceptance criteria |
| `aidlc-docs/inception/application-design/unit-of-work-story-map.md` | Story-to-unit ownership |
| `aidlc-docs/construction/u5-orchestrator/nfr-requirements/nfr-requirements.md` | u5 NFR acceptance criteria |
| `aidlc-docs/construction/plans/u5-orchestrator-code-generation-plan.md` | u5 implementation plan |
| `aidlc-docs/construction/u5-orchestrator/code/summary.md` | Code-generation closeout and traceability |
| Implementation: `src/investo/orchestrator/`, `src/investo/__main__.py`, `src/investo/models/results.py`, `tests/unit/orchestrator/`, `tests/integration/test_pipeline.py`, `.github/workflows/daily-briefing.yml` | Artifacts verified |

---

## Scope Filter

Per `unit-of-work-story-map.md`, **u5 orchestrator** is responsible for:

- **Primary story**: US-005 (GitHub Actions cron으로 자동 실행된다)
- **Touched stories**: US-004 public notification trigger, US-007 failure-alert hook
- **FRs**: FR-005 u5 runtime slice, FR-007 u5 failure-routing slice
- **NFRs covered whole or share**: NFR-001 overall runtime budget tracking, NFR-003 stage failure policy, NFR-005 date/logging maintainability, NFR-006 integration testing, NFR-007 env validation and chat-ID disjointness

Out of scope: GitHub Actions schedule declaration, workflow `timeout-minutes`, Pages deployment, and GHA default email/banner behavior. Those are u6 infra/CI responsibilities, though this cross-check read `.github/workflows/daily-briefing.yml` to verify the boundary.

---

## Summary

| Status | Count | Percentage |
|--------|------:|-----------:|
| ✅ Complete | 8 | 67% |
| ⚠️ Partial | 3 | 25% |
| ❌ Gap | 1 | 8% |
| 🔄 Deferred | 0 | 0% |
| ⏳ In Progress | 0 | 0% |
| **Total** | **12** | **100%** |

**Overall compliance for u5 orchestrator**: u5's runtime orchestration contract is implemented and verified. The Partials are expected cross-unit closures with u6. The Gap is a requirements mismatch: FR-007 asks for retry when operator-alert delivery itself fails; u5 logs the failure at WARNING and preserves FAILED status, but does not retry.

---

## Functional Requirements

| ID | Description | Status | Evidence | Notes |
|----|-------------|--------|----------|-------|
| FR-005 | GitHub Actions cron scheduled execution | ⚠️ Partial | `resolve_target_date`, `main`, `run_pipeline`, `.github/workflows/daily-briefing.yml` | u5 implements the runtime entrypoint and date resolution. Actual cron / workflow_dispatch / timeout YAML is u6 scope. |
| FR-007 | Operator failure alert routing | ❌ Gap | `_safe_alert`, `_attempt_boot_alert`, `FailureContext`, tests | u5 routes collect/generate/publish/top-level failures to operator chat and prevents public-channel failure alerts, but alert-send failure is not retried as FR-007 states. |

### FR-005 Acceptance-Criterion Detail

| Criterion | Status | Evidence |
|-----------|--------|----------|
| GitHub Actions `schedule` cron trigger | ⚠️ | Implemented in `.github/workflows/daily-briefing.yml`; u6 owns final infra/CI cross-check |
| 평일 한국시간 오전 7시 / UTC 22:00 | ⚠️ | `daily-briefing.yml` cron + `resolve_target_date`; u6 owns workflow closure |
| 토요일 한국시간 오전 9시 1회 | ⚠️ | `daily-briefing.yml` cron + `resolve_target_date`; u6 owns workflow closure |
| `workflow_dispatch` 수동 트리거 | ⚠️ | `INVESTO_TARGET_DATE` parsing in `__main__.py`; workflow input in YAML; u6 owns workflow closure |
| 단일 job 실행 시간 ≤ 10분 | ⚠️ | u5 records `duration_seconds` / `stage_timings`; `timeout-minutes: 12` is u6 workflow guard |
| 실행 시각/지속시간 로그 확인 가능 | ✅ | `run_pipeline` stage logging and `PipelineResult.stage_timings` tests |

### FR-007 Acceptance-Criterion Detail

| Criterion | Status | Evidence |
|-----------|--------|----------|
| 파이프라인 실패 시 `TELEGRAM_OPERATOR_CHAT_ID`로 알림 발송 | ✅ | `run_pipeline` `_safe_alert`; integration empty-collect alert test |
| GitHub Actions 기본 실패 알림도 함께 활성 | ⚠️ | u5 maps FAILED to exit code 1; u6 owns GHA behavior |
| 실패 단계 + 에러 메시지 / stack trace 요약 포함 | ✅ | `_build_failure_context`; `FailureContext`; run_pipeline/main tests |
| 공개 시황 채널에는 실패 메시지 발송 금지 | ✅ | `BriefingPublisher` and `OperatorAlerter` constructed from disjoint env vars; integration chat isolation test |
| 알림 자체 실패 시 재시도 후 GHA 로그에 명시적 마킹 | ❌ | `_safe_alert` logs WARNING and keeps FAILED; no retry loop exists by design AC-003-11 |

---

## User Stories

| ID | Title | Status | Evidence | Notes |
|----|-------|--------|----------|-------|
| US-005 | GitHub Actions cron으로 자동 실행된다 | ⚠️ Partial | `python -m investo`, `resolve_target_date`, workflow YAML | Runtime side is complete; full story closes after u6 infra/CI cross-check. |
| US-007 | 파이프라인 실패 시 운영자 1:1 chat으로 알림 받는다 | ⚠️ Partial | `_safe_alert`, `_attempt_boot_alert`, integration alert tests | Failure routing and chat isolation are complete. Alert-send retry is missing; GHA default notification is u6 scope. |

---

## Non-Functional Requirements

| ID | Description | Status | Evidence | Notes |
|----|-------------|--------|----------|-------|
| NFR-001 | Overall performance budget and timing visibility | ⚠️ Partial | `PipelineResult.stage_timings`, `duration_seconds`, no `wait_for`, no stage `gather` | u5 records timings and relies on unit-level timeouts. Workflow `timeout-minutes: 12` and first cron runtime are u6/ops closure. |
| NFR-003 | Q9=B reliability / graceful degradation policy | ✅ Complete | `run_pipeline`; unit + integration failure-path tests | Empty collect / generation / publish failures alert and FAILED; notify failure yields PARTIAL without alert; per-source degradation stays SUCCESS. |
| NFR-005 | Date resolution, logging, status taxonomy | ✅ Complete | `resolve_target_date`; stage logs; `PipelineStatus`; tests | No US holiday calendar dependency by design; manual rerun handles holiday misses. |
| NFR-006 | Orchestrator integration tests and DI seams | ✅ Complete | `run_pipeline` injectable `fetch`, `runner`, `git_runner`, `generate`; integration pipeline tests | Existing fake patterns are reused; no live external I/O. |
| NFR-007 | Env validation, secret handling, chat separation | ✅ Complete | `_validate_env`, `ConfigError`, whitespace-trim chat check, tests | 5 required env vars validated; public and operator chat IDs rejected if equal before dispatcher construction. |
| Module boundary | Orchestrator is the only unit importing all work units | ✅ Complete | `pipeline.py` imports u1/u2/u3/u4; prior u1-u4 reports | This is the intended DAG root; other units remain isolated. |

---

## Verification Run

| Command | Result |
|---------|--------|
| `uv run pytest tests/unit/orchestrator tests/integration/test_pipeline.py -q` | ✅ 158 passed |
| `uv run mypy --strict src/investo/orchestrator src/investo/__main__.py src/investo/models/results.py` | ✅ no issues in 6 source files |
| `uv run ruff check src/investo/orchestrator src/investo/__main__.py tests/unit/orchestrator tests/integration/test_pipeline.py` | ✅ all checks passed |
| `rg -n "asyncio\\.wait_for\\(|asyncio\\.gather\\(|for .*range\\(|while .*attempt|...|_redact_bot_token|tenacity|backoff|pandas_market_calendars|..." src/investo/orchestrator src/investo/__main__.py tests/unit/orchestrator tests/integration/test_pipeline.py pyproject.toml` | ✅ expected literals/docs/tests only; no stage `wait_for`, no stage `gather`, no retry loop around stages, no forbidden dependency |

---

## Gaps Analysis

### GAP-001: FR-007 requires retry for operator-alert delivery failure, but u5 logs only

**Requirement**: FR-007 says if the operator alert itself fails, retry and at least explicitly mark it in GitHub Actions logs.

**Status**: ❌ Gap. In `run_pipeline`, `_safe_alert` attempts one alert. If `OperatorAlerter.alert` returns `SendResult(ok=False)` or raises `Exception`, u5 logs a WARNING and preserves the original FAILED pipeline status. There is no retry. This is also deliberate in u5 NFR AC-003-11, which forbids orchestrator-level retry loops around stage calls, but that local design choice conflicts with the product-level FR-007 wording.

**Impact**: Medium-low. The primary pipeline failure still exits 1, so GitHub Actions default failure signaling remains available after u6. The missing part is improved Telegram alert delivery resilience.

**Proposed Action**: Either add a narrow retry inside `_safe_alert` / `_attempt_boot_alert` specifically for operator-alert delivery, or update FR-007 to remove "retry" and require only explicit warning logs plus GHA default notification. If implementing, keep it scoped to alert delivery so stage calls remain non-retried.

### GAP-002: FR-005 / US-005 full cron behavior is split with u6

**Requirement**: FR-005 includes the actual GitHub Actions cron schedule, workflow_dispatch, and job timeout.

**Status**: ⚠️ Partial at full-product level. u5 implements the runtime entrypoint, target-date resolution, exit codes, and timing telemetry. The workflow YAML exists, but final infra/CI ownership is u6.

**Impact**: Low for u5 stage gate. This is an intentional unit boundary.

**Proposed Action**: Verify schedule, workflow_dispatch input, `timeout-minutes: 12`, secrets wiring, and GHA default notification in the u6 infra/CI cross-check.

---

## Open TECH-DEBT in u5 Scope

| ID | Priority | Description | Cross-check status |
|----|----------|-------------|--------------------|
| DEBT-017 | Low | `_TRACEBACK_EXCERPT_MAX_CHARS` duplicated between `pipeline.py` and `models/results.py` | Accepted; not blocking |
| DEBT-018 | Low | AST-grep deny tests use substring matching instead of callable identity | Accepted test-maintainability item |
| DEBT-019 | Low | `resolve_target_date` PBT covers only 2026 | Accepted coverage breadth item |
| DEBT-020 | Low | `_safe_alert` and `_attempt_boot_alert` exception lists are not aligned | Accepted; related to boot alert robustness |
| DEBT-021 | Low | Unused `PublisherError` re-export in `pipeline.__all__` | Accepted dead-code cleanup |

No new TECH-DEBT items were added by this cross-check. GAP-001 should be resolved as either a code change or a requirements clarification.

---

## Sign-Off

⚠️ **u5 orchestrator cross-check PASSED WITH GAP.**

The runtime orchestration contract is complete: stage composition, target-date resolution, env validation, chat-ID disjointness, failure routing, status taxonomy, exit-code mapping, and timing telemetry are all implemented and tested. The remaining product-level work is u6 infra/CI closure plus one FR-007 mismatch around retrying failed operator-alert delivery.

# NFR Requirements — `u5 orchestrator`

**Date**: 2026-04-30
**Source**: `u5-orchestrator-nfr-requirements-plan.md` (proposed answers approved via `/loop` continuation pattern after Q1-Q10 review)

This document fixes measurable, testable acceptance criteria for the NFRs that touch the orchestrator. Anything not listed here is OUT of scope for `u5` (typically owned by u1/u2/u3/u4 internally; u5 only routes between them).

`u5` has no Functional Design artifact (FD = SKIP per execution-plan). The orchestrator's behavior is fully specified by:
- `aidlc-docs/inception/application-design/component-methods.md` C5 (method signatures)
- `aidlc-docs/inception/application-design/application-design.md` Time Budget table + Error Policy (Q9=B) summary
- `aidlc-docs/inception/application-design/unit-of-work.md` u5 module structure + DoD

The AC below convert those design-level decisions into pinning tests.

---

## NFR-001: Performance — orchestrator's wall-clock enforcement (≤ 10 min)

**Owner of overall budget**: u5 orchestrator
**Total budget**: 10 min wall-clock from `main()` entry to exit

The application-design Time Budget allocates: collect ≤ 4 min / generate ≤ 4 min / publish ≤ 1 min / notify ≤ 30 s / GHA overhead ≤ 30 s. Each unit enforces its own slice internally (per Q1=A: trust unit-level timeouts).

### Acceptance criteria

- **AC-001-1** — Each `_stage_*` function records its elapsed wall-clock time on a `StageTiming` dict carried into `PipelineResult`. Pinned by `test_pipeline.py::test_run_pipeline_records_per_stage_elapsed`.
- **AC-001-2** — `run_pipeline` records `total_elapsed_s` on `PipelineResult`. The integration smoke test asserts `total_elapsed_s < 600` (with full mocks; smoke is far below the cap). Pinned by `test_pipeline.py::test_run_pipeline_total_elapsed_under_10min_with_mocks`.
- **AC-001-3** — `run_pipeline` does NOT wrap stage calls in `asyncio.wait_for` (per Q1=A: trust unit-level timeouts; no orchestrator-side mid-stage cancellation). Pinned by an AST-grep test asserting no `wait_for(_stage_` call appears in `pipeline.py`.
- **AC-001-4** — The GitHub Actions workflow YAML (u6) sets `timeout-minutes: 12` on the `daily-briefing` job (10-min design budget + 2-min safety margin per Q1=A). Verified by u6's workflow-YAML test.
- **AC-001-5** — Stages are executed **sequentially** (Q5 confirmed). `run_pipeline` does NOT use `asyncio.gather` to overlap stages. Pinned by an AST-grep test asserting no `asyncio.gather` call appears in `pipeline.py` at the stage level. (u1's `aggregator` is the only `asyncio.gather` call site — for source parallelism, not stage parallelism.)

---

## NFR-003: Reliability — graceful degradation + status taxonomy

**Q9=B Error Policy table** (from `application-design.md`):

| Stage | Failure → Behavior |
|-------|--------------------|
| collect (per-source) | log + empty list, proceed (graceful) |
| collect (total empty) | alert + abort publish |
| generate (LLM) | inner retry → final-fail alert + abort publish |
| publish (disclaimer missing) | alert + abort publish (NFR-004 hard block) |
| publish (git push) | retry → final-fail alert + FAILED |
| notify_briefing | best-effort, fail → PARTIAL (publish still alive) |
| top-level unexpected exception | alert + exit 1 |

### Acceptance criteria

- **AC-003-1** — Per-source failure during collect is silently swallowed (per-source error caught at u1's aggregator boundary; aggregator returns the union of successful sources). `run_pipeline` does not see per-source errors. Pinned by `test_pipeline.py::test_collect_per_source_failure_does_not_affect_pipeline_status` (single-source-fail with other sources succeeding → `status=SUCCESS`).
- **AC-003-2** — Empty collect (every source returned 0 items) → `_stage_collect` returns `[]` → `run_pipeline` raises an internal `EmptyCollectError` → routed to `OperatorAlerter.alert(FailureContext(stage="collect", ...))` → publish + notify SKIPPED → `PipelineResult.status=FAILED`. Pinned by `test_pipeline.py::test_empty_collect_aborts_with_failed_status_and_operator_alert`.
- **AC-003-3** — `BriefingGenerationError` raised from `_stage_generate` → routed to `OperatorAlerter.alert(FailureContext(stage="generate", ...))` → publish + notify SKIPPED → `status=FAILED`. Pinned by `test_pipeline.py::test_generate_failure_aborts_with_failed_status_and_operator_alert`.
- **AC-003-4** — `PublisherDisclaimerError` raised from `_stage_publish` → routed to `OperatorAlerter.alert(FailureContext(stage="publish", ...))` → notify SKIPPED → `status=FAILED`. The disclaimer-missing case is NOT retried. Pinned by `test_pipeline.py::test_publisher_disclaimer_error_aborts_with_failed_status`.
- **AC-003-5** — `PublisherGitError` raised from `_stage_publish` (after u3's internal retry exhausted) → routed to `OperatorAlerter.alert(FailureContext(stage="publish", ...))` → notify SKIPPED → `status=FAILED`. The 1024-byte `last_stderr` is included verbatim in `FailureContext.error_message`. Pinned by `test_pipeline.py::test_publisher_git_error_aborts_with_failed_status_and_includes_stderr`.
- **AC-003-6** — `_stage_notify_briefing` returns `SendResult(ok=False, error=...)` → publish is still considered successful → `status=PARTIAL`. **No** operator alert is sent for notify-briefing failure (per Q2: PARTIAL is the visibility, not an alert event). Pinned by `test_pipeline.py::test_notify_briefing_failure_yields_partial_status_no_operator_alert`.
- **AC-003-7** — Top-level unexpected exception (anything not in the explicit catch list — e.g., `KeyError`, `RuntimeError` from a programmer error) propagates to `main()` → `main()` catches → best-effort `OperatorAlerter.alert(FailureContext(stage="orchestrator", error_type=type(e).__name__, ...))` → exit 1. Pinned by `test_pipeline.py::test_unexpected_exception_caught_in_main_alerts_and_exits_1`.

### PARTIAL status definition (Q2)

- **AC-003-8** — `PipelineResult.status=PARTIAL` if and only if: every stage from collect through publish succeeded AND `_stage_notify_briefing` returned `SendResult(ok=False)`. No other case yields PARTIAL. Pinned by `test_pipeline.py::test_partial_status_only_for_publish_ok_notify_fail`.
- **AC-003-9** — Per-source collect failure (graceful degradation within u1) does NOT downgrade `status` to PARTIAL. As long as ≥ 1 source returned items AND every subsequent stage succeeded, `status=SUCCESS`. Pinned by `test_pipeline.py::test_per_source_failure_does_not_downgrade_to_partial`.
- **AC-003-10** — Operator-alert delivery failure during a FAILED run does NOT change `status` (already FAILED). The alert failure is logged at WARNING level (per AC-005-1) but `main()` still exits 1. Pinned by `test_pipeline.py::test_operator_alert_failure_during_failed_run_does_not_change_status`.

### Orchestrator-level meta-retry (Q4=A)

- **AC-003-11** — `run_pipeline` does NOT wrap stage calls in any retry loop. Each unit owns its own retry policy (u1: per-source backoff; u2: RetryBudget; u3: git-push retry). Pinned by an AST-grep test asserting no `for _ in range(...)` or `while attempts <` loop wraps a `_stage_*` call in `pipeline.py`.

---

## NFR-005: Maintainability — date resolution + structured logging

### Date resolution AC (per Q3=A)

- **AC-005-1** — `resolve_target_date(now_utc, *, weekday_only_us_close=True)` returns the previous KST trading day's date for **KST 평일 cron fires**. KST Tue-Fri 07:00 → preceding KST date (Mon-Thu). KST Mon 07:00 → preceding KST Friday (skip weekend). Pinned by `test_date_resolution.py::test_weekday_kst_morning_returns_previous_us_close_date` (parametrized over Mon-Fri).
- **AC-005-2** — KST 토요일 09:00 cron → preceding KST Friday. Pinned by `test_date_resolution.py::test_saturday_kst_morning_returns_friday`.
- **AC-005-3** — `resolve_target_date` does NOT consult a US trading calendar (per Q3=A: no extra dep for ~10× per year manual handling). On US public holidays (Thanksgiving, July 4, etc.), the function still returns the prior KST date; if the upstream sources have no data, the empty-collect path (AC-003-2) routes to operator alert. Pinned by a test that documents this behavior + a comment explaining the trade-off.

### Logging strategy (per Q6=B)

- **AC-005-4** — `pipeline.py` uses Python stdlib `logging` (no `structlog`, `loguru`, or other external logger). Pinned by AST-grep asserting no `import structlog` / `import loguru` in `pipeline.py`.
- **AC-005-5** — Each stage entry/exit emits an INFO-level log line: `[stage] starting`, `[stage] elapsed=N.NNs ok=true/false`. Pinned by a test using `caplog` (pytest fixture) on a fully-mocked `run_pipeline` invocation.
- **AC-005-6** — Per-source graceful-degradation events (a source returned 0 items) emit a WARNING-level log line. Stage failures emit ERROR. The logger name is `investo.orchestrator.pipeline`. Pinned by `caplog` asserting log levels per scenario.

### Status taxonomy enum (per Q2)

- **AC-005-7** — `PipelineStatus` is a `StrEnum` with three members: `SUCCESS`, `PARTIAL`, `FAILED`. No other status values are added without a corresponding ratified design change. Pinned by an explicit enum-membership test.
- **AC-005-8** — `PipelineResult` is a frozen pydantic v2 model with `target_date: date`, `status: PipelineStatus`, `stage_timings: dict[str, float]`, `total_elapsed_s: float`, `error_summary: str | None` (None on SUCCESS, populated on PARTIAL/FAILED).

---

## NFR-006: Testing — integration test record/replay reuse

### Acceptance criteria

- **AC-006-1** — `tests/integration/test_pipeline.py` exercises `run_pipeline` end-to-end with **all four** existing mock patterns wired simultaneously (per Q8 confirmation):
  - u1 sources: `httpx.MockTransport` (or pre-populated `Aggregator` w/ fake adapters)
  - u2 briefing: `FakeClaudeRunner` (record/replay fixture mechanism)
  - u3 publisher: fake `GitRunner` Protocol implementation
  - u4 notifier: `httpx.MockTransport` shared with u1 OR per-class

  Pinned by `test_pipeline.py::test_run_pipeline_happy_path_full_mocks`.
- **AC-006-2** — `tests/integration/test_pipeline.py` exercises each Q9=B failure-path AC (one integration test per row of AC-003-1 through AC-003-7). Pinned by named tests under `test_pipeline.py::test_failure_*`.
- **AC-006-3** — No new mock infrastructure is introduced for u5 integration testing. The orchestrator exposes dependency-injection seams (constructor params or function args) so tests can substitute the existing fakes without monkeypatching internals. Pinned by reading `pipeline.py` for explicit `runner=` / `http=` / `aggregator=` parameters.
- **AC-006-4** — `tests/unit/orchestrator/test_date_resolution.py` PBT (hypothesis-based) for `resolve_target_date`: any UTC datetime over a 30-day range converted to KST and routed through `resolve_target_date` produces a date that is ≤ the KST date and is a weekday (per Q3=A behavior). ≥ 100 examples per PBT.
- **AC-006-5** — `tests/unit/orchestrator/` has separate happy/failure unit tests for each `_stage_*` function (not just integration). u5 unit-test count target: ≥ 30 tests (date resolution + per-stage + run_pipeline orchestration + main entrypoint).

---

## NFR-007: Security — env var validation + token redaction reuse

### Acceptance criteria (per Q9=A+)

- **AC-007-1** — `main()` validates 5 env vars at entry (per `component-methods.md` C5):
  - `CLAUDE_CODE_OAUTH_TOKEN` (required)
  - `TELEGRAM_BOT_TOKEN` (required)
  - `TELEGRAM_BRIEFING_CHANNEL_ID` (required)
  - `TELEGRAM_OPERATOR_CHAT_ID` (required)
  - `SITE_URL_BASE` (required, must parse as `HttpUrl`)

  Missing any → `ConfigError` raised with the missing var name(s). Pinned by `test_main.py::test_main_raises_config_error_on_missing_*` (5 parametrized cases).
- **AC-007-2** — `TELEGRAM_BRIEFING_CHANNEL_ID == TELEGRAM_OPERATOR_CHAT_ID` → `ConfigError("public channel and operator chat must be disjoint")` raised before any dispatcher is constructed (CLAUDE.md #5 enforcement). Pinned by `test_main.py::test_main_rejects_equal_chat_ids`.
- **AC-007-3** — On `ConfigError` raised by env validation, `main()`:
  - If `TELEGRAM_BOT_TOKEN` AND `TELEGRAM_OPERATOR_CHAT_ID` are present (even if other vars missing), attempts ONE best-effort `OperatorAlerter.alert(FailureContext(stage="config", error_type="ConfigError", ...))` with a 5-s timeout. Result ignored.
  - Logs the ConfigError to stderr (so GHA captures it).
  - Returns exit code 1.

  Pinned by `test_main.py::test_main_config_error_attempts_best_effort_alert_when_possible`.
- **AC-007-4** — `pipeline.py` and `main()` do NOT log any of the 5 env var **values**. Pinned by an AST-grep / source-grep asserting no `logger.*(\".*{TELEGRAM_BOT_TOKEN}\".*)` or `print(token)` patterns appear.
- **AC-007-5** — Bot-token redaction is the responsibility of u4's `_redact_bot_token` (already implemented + tested in u4 Step 7). u5's `pipeline.py` does NOT reimplement redaction; if `pipeline.py` ever needs to format an error message containing a bot token, it MUST route through u4's redaction (e.g., by passing the raw error to `OperatorAlerter.alert` which redacts internally). Pinned by an AST-grep asserting `_redact_bot_token` is NOT imported into `pipeline.py` (proxy: u5 doesn't construct token-bearing strings; it only forwards).

---

## NFR-002 / NFR-004 — owned by other units (not duplicated)

- **NFR-002 (Cost)** is fully pinned by u2's AC-2.1 through AC-2.5 (CI grep `scripts/check_no_anthropic_sdk.py` is repo-wide). u5 does not re-pin.
- **NFR-004 (Disclaimer)** is fully pinned by u2's AC-4.X (idempotent `append_disclaimer`) + u3's `verify_disclaimer` substring-block AC. u5's role is only to NOT bypass either: `_stage_publish` calls `write_briefing(briefing, target_date)` from u3; the verify-first ordering is a u3 invariant. Pinned indirectly by the NFR-003 `PublisherDisclaimerError` integration test (AC-003-4).

---

## Drift guard

- **AC-drift-1** — Any change to `_stage_*` function signatures triggers a `/code-review git` review per `dev-investo` §5.1.
- **AC-drift-2** — Any addition of an external retry library (`tenacity`, `backoff`, etc.) to `pyproject.toml` is forbidden by Q4=A; CI grep asserts neither package appears in `[project.dependencies]` or `[project.optional-dependencies]`.
- **AC-drift-3** — Any addition of `pandas_market_calendars` or `pandas` to dependencies (per Q3=A rejection) is forbidden by the same CI grep extension.
- **AC-drift-4** — Any orchestrator-side `asyncio.wait_for(_stage_*, ...)` wrap is forbidden by AC-001-3 (per Q1=A).
- **AC-drift-5** — `PipelineStatus` enum cannot grow new members without an audit-log entry ratifying the design change (per AC-005-7).

---

## Trace map — NFR ID → AC

| NFR | u5 ACs |
|-----|--------|
| NFR-001 | AC-001-1 ~ AC-001-5 (5 AC) |
| NFR-003 | AC-003-1 ~ AC-003-11 (11 AC) |
| NFR-005 | AC-005-1 ~ AC-005-8 (8 AC) |
| NFR-006 | AC-006-1 ~ AC-006-5 (5 AC) |
| NFR-007 | AC-007-1 ~ AC-007-5 (5 AC) |
| Drift | AC-drift-1 ~ AC-drift-5 (5 AC) |
| **Total** | **39 AC** |

NFR-002 + NFR-004 owned by u2 + u3; not duplicated here.

---

## Summary

u5 orchestrator's NFR Requirements: **39 testable AC** across NFR-001 / NFR-003 / NFR-005 / NFR-006 / NFR-007 + drift guards. The bulk (11 of 39) target NFR-003's Q9=B Error Policy table — each row gets at least one pinning integration test. The orchestrator does not introduce new constraints; it codifies the integration boundary between u1-u4 and the GHA cron entrypoint.

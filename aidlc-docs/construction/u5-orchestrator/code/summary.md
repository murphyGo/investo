# u5 orchestrator — Code Generation Summary

**Date**: 2026-04-30
**Stage**: Code Generation (final stage for u5 orchestrator; FD = SKIP per execution-plan; NFR Requirements ✅ closed 2026-04-30 with 39 testable AC)
**Status**: ✅ COMPLETE
**Stories closed**: US-005 (스케줄 실행)

---

## Files created

### Source code (`src/investo/orchestrator/` + `src/investo/__main__.py`)

| File | LOC | Role |
|------|----:|------|
| `__init__.py` | 89 | Public surface — 4 re-exports + module docstring (`run_pipeline`, `resolve_target_date`, `ConfigError`, `EmptyCollectError`) (Step 11) |
| `errors.py` | 93 | `ConfigError` w/ 2-factory anti-conflation pattern + `EmptyCollectError` internal sentinel (Step 3) |
| `date_resolution.py` | 94 | KST UTC+9 cron-time → US trading-day mapping; no holiday calendar dep per Q3=A (Step 4) |
| `pipeline.py` | 703 | 4 async stage runners + `run_pipeline` Q9=B router + 3 utility helpers (Steps 5, 6, 7, 8, 9, 12) |
| `__main__.py` | 253 | `python -m investo` entrypoint — env validation + best-effort alerts + exit codes (Steps 10, 12) |
| **Subtotal — orchestrator + entrypoint** | **1,232** | 5 source files |
| `models/results.py` (extended) | +60 | Added `stage_timings: dict[str, float]` field + extended `FailureStage` Literal w/ `"orchestrator"` (Steps 2, 10) |
| **Total** | **1,292** | 5 new src files + 1 model extension |

### Tests (`tests/unit/orchestrator/` + `tests/integration/`)

| File | LOC | Tests | Role |
|------|----:|------:|------|
| `__init__.py` | 0 | 0 | Empty marker (Step 1) |
| `conftest.py` | 13 | 0 | Placeholder w/ DEBT-010/013/016 cross-reference (Step 1) |
| `test_errors.py` | 195 | 17 | ConfigError 2-factory contract + factory cross-check + EmptyCollectError (Step 3) |
| `test_date_resolution.py` | 253 | 17 | 5-parametrized weekday + Sat/Sun + AC-005-3 holiday non-consultation pin + UTC + naive rejection + year boundaries + DST guard + `weekday_only_us_close=False` + 2 PBTs at 100 examples each (Step 4) |
| `test_stage_collect.py` | 203 | 9 | Happy + AC-003-2 empty + AC-005-5 logging + default-fetch monkeypatch + propagation (Step 5) |
| `test_stage_generate.py` | 333 | 13 | Happy + 4-stage parametrized BGE propagation + identity-not-wrapped pin + AC-005-5 + default-callable wiring + programmer-error propagation (Step 6) |
| `test_stage_publish.py` | 351 | 9 | Real `write_briefing` + happy + AC-003-4 disclaimer/IO + AC-003-5 push exhaustion via `_FailingGitPushRunner` w/ idempotent-noop retry + commit message format pin + AC-005-5 (Step 7) |
| `test_stage_notify_briefing.py` | 274 | 9 | httpx.MockTransport + happy + AC-003-6/8 SendResult forward + CLAUDE.md #5 stage-layer chat_id pin + programmer-error propagation + AC-005-5/6 (Step 8) |
| `test_run_pipeline.py` | 923 | 32 | All 11 Q9=B AC paths + AC-001-1 stage_timings on success/abort + AC-003-9/10 PARTIAL invariants + 3 AST-grep deny tests (AC-001-3 / AC-001-5 / AC-003-11) + 7 H1 regression + 2 helpers (`_briefing_url_for`, `_build_failure_context`) (Steps 9, 12) |
| `test_main.py` | 477 | 30 | AC-007-1 5-var (3) + AC-007-2 disjointness (1) + 5 H2 whitespace regression + AC-007-3 (3) + URL parsing (2) + parametrized exit-code mapping + AC-003-7 top-level (2) + happy paths (2) + `_missing_env_vars` helper (2) + best-effort robustness (2) + forward-args sanity (1) (Steps 10, 12) |
| `tests/integration/test_pipeline.py` | 496 | 7 | AC-006-1 4-mock end-to-end + AC-003-2 empty collect → operator alert + AC-003-6 PARTIAL + CLAUDE.md #5 chat-ID isolation + 2 public-surface importability + resolve_target_date round-trip via re-export (Step 11) |
| **Total** | **3,518** | **143** | 9 unit test files + 1 integration test |

### Surface area

| Public re-export | Defined in | Consumed by |
|------------------|------------|-------------|
| `run_pipeline(target_date=None, *, publisher, alerter, site_url_base, fetch=None, runner=None, git_runner=None, generate=None) -> PipelineResult` | `pipeline.py` | `__main__.main()`; integration tests; `/cross-check` |
| `resolve_target_date(now_utc, *, weekday_only_us_close=True) -> date` | `date_resolution.py` | `__main__.main()`; integration tests; PBT |
| `ConfigError` | `errors.py` | `__main__.main()` raises; tests |
| `EmptyCollectError` | `errors.py` | `_stage_collect` raises; `run_pipeline` catches; tests |

**`main` is intentionally NOT re-exported** from `investo.orchestrator`. It lives in `investo.__main__` per Python convention so `python -m investo` resolves it; re-exporting from the package would create two import paths for the same symbol. Inline comment in `__init__.py` ratifies the decision.

**Internal helpers NOT re-exported** (private stage runners + composer helpers): `_stage_collect`, `_stage_generate`, `_stage_publish`, `_stage_notify_briefing`, `_default_generate_briefing`, `_briefing_url_for`, `_build_failure_context`, `_safe_alert`, `_build_result`. Individually testable via explicit imports from `investo.orchestrator.pipeline`.

### Cross-unit imports (module-boundary verification — CLAUDE.md #3)

`u5 orchestrator` imports from ALL FOUR work units, plus models + stdlib + httpx:

- `investo.models` — `Briefing`, `BriefingNotification`, `FailureContext`, `NormalizedItem`, `PipelineResult`, `PipelineStatus`, `SendResult`
- `investo.sources` — `fetch_all` (DI default for `_stage_collect`)
- `investo.briefing` — `generate_briefing` (DI default for `_stage_generate`); `BriefingGenerationError` (caught for AC-003-3); `ClaudeRunner` Protocol type
- `investo.publisher` — `write_briefing`, `commit_and_push`, `GitRunner` Protocol; `PublisherDisclaimerError`, `PublisherIOError`, `PublisherGitError`, `PublisherError`
- `investo.notifier` — `BriefingPublisher`, `OperatorAlerter`, `build_summary`
- stdlib — `asyncio`, `logging`, `os`, `sys`, `time`, `traceback`, `datetime` / `zoneinfo`, `pathlib`, `typing.Final`
- already-locked — `pydantic` (HttpUrl, TypeAdapter, ValidationError); `httpx` (AsyncClient, HTTPError)

**u5 is the ONLY unit allowed to import all 4 work units** per CLAUDE.md #3. The other 4 work units do not import each other (verified across u1-u4 reviews).

---

## FR / NFR traceability

### NFR-001 — Performance (orchestrator wall-clock ≤ 10 min)

| AC | Description | Pinned by |
|----|-------------|-----------|
| AC-001-1 | Per-stage `stage_timings: dict[str, float]` field on `PipelineResult` | `test_results.py::test_pipeline_result_*_stage_timings_*` (5 tests) + `test_run_pipeline.py::test_run_pipeline_records_stage_timings_on_success` + `test_run_pipeline_records_failed_stage_timing_even_on_abort` |
| AC-001-2 | `total_elapsed_s` (`duration_seconds`) on `PipelineResult` | `test_run_pipeline.py::test_run_pipeline_duration_seconds_set_on_success` |
| AC-001-3 | NO `asyncio.wait_for(_stage_*` in pipeline.py | `test_run_pipeline.py::test_pipeline_source_has_no_asyncio_wait_for_on_stages` (AST-grep deny) |
| AC-001-4 | GHA workflow YAML `timeout-minutes: 12` | Deferred to u6 infra/CI |
| AC-001-5 | Sequential stages (no stage-level `asyncio.gather`) | `test_run_pipeline.py::test_pipeline_source_has_no_stage_level_asyncio_gather` (AST AST-grep deny) |

### NFR-003 — Reliability (Q9=B Error Policy)

| AC | Description | Pinned by |
|----|-------------|-----------|
| AC-003-1 | Per-source collect failure already swallowed by u1 → SUCCESS (no PARTIAL downgrade) | `test_run_pipeline.py::test_run_pipeline_per_source_partial_collect_yields_success` + `test_run_pipeline_per_source_partial_is_success_not_partial` |
| AC-003-2 | Empty collect → `EmptyCollectError` → operator alert + FAILED | `test_stage_collect.py::test_stage_collect_empty_result_raises_empty_collect_error` + `test_run_pipeline.py::test_run_pipeline_empty_collect_fails_with_alert` + integration `test_pipeline.py::test_pipeline_end_to_end_empty_collect_alerts_operator` |
| AC-003-3 | `BriefingGenerationError` → operator alert + FAILED | `test_stage_generate.py::test_stage_generate_propagates_briefing_generation_error` (4-parametrized) + `test_stage_generate_does_not_swallow_or_wrap_bge` + `test_run_pipeline.py::test_run_pipeline_generate_failure_fails_with_alert` (4-parametrized) |
| AC-003-4 | `PublisherDisclaimerError` / `PublisherIOError` → operator alert + FAILED | `test_stage_publish.py::test_stage_publish_propagates_disclaimer_error_no_write` + `test_stage_publish_propagates_io_error` + `test_run_pipeline.py::test_run_pipeline_publisher_disclaimer_error_fails_with_alert` |
| AC-003-5 | `PublisherGitError` after retry exhaustion → operator alert + FAILED | `test_stage_publish.py::test_stage_publish_propagates_git_error_after_write_succeeded` + `test_run_pipeline.py::test_run_pipeline_git_push_failure_fails_with_alert` |
| AC-003-6 | Notify failure → PARTIAL with NO operator alert | `test_stage_notify_briefing.py::test_stage_notify_briefing_returns_failure_send_result_*` + `test_run_pipeline.py::test_run_pipeline_notify_failure_yields_partial_no_alert` + integration `test_pipeline_end_to_end_notify_failure_yields_partial` |
| AC-003-7 | Top-level unexpected `Exception` in `main()` → best-effort alert(stage="orchestrator") + exit 1 | `test_main.py::test_main_top_level_exception_attempts_alert_and_exits_1` + `test_main_top_level_exception_does_not_mask_failure_when_alert_skipped` |
| AC-003-8 | PARTIAL = exactly publish-ok + notify-fail (taxonomy invariant) | `test_run_pipeline.py::test_run_pipeline_notify_failure_yields_partial_no_alert` |
| AC-003-9 | Per-source collect failure does NOT downgrade to PARTIAL | `test_run_pipeline.py::test_run_pipeline_per_source_partial_is_success_not_partial` |
| AC-003-10 | Alert delivery failure during FAILED run → status STAYS FAILED + WARNING | `test_run_pipeline.py::test_run_pipeline_alert_failure_during_failed_run_keeps_failed` + `test_run_pipeline_alert_raise_during_failed_run_keeps_failed` + 7 H1 regression tests |
| AC-003-11 | NO orchestrator-level retry loops wrapping stage calls | `test_run_pipeline.py::test_pipeline_source_has_no_orchestrator_level_retry_loops` (AST-grep deny) |

### NFR-005 — Maintainability

| AC | Description | Pinned by |
|----|-------------|-----------|
| AC-005-1 | KST 평일 cron → previous US trading day | `test_date_resolution.py::test_resolve_target_date_weekday_kst_morning` (5-parametrized) |
| AC-005-2 | KST Saturday cron → Friday | `test_date_resolution.py::test_resolve_target_date_saturday_kst_morning_returns_friday` |
| AC-005-3 | NO US trading calendar consultation (US holidays surface via empty-collect) | `test_date_resolution.py::test_resolve_target_date_returns_us_holiday_date_unchanged` |
| AC-005-4 | stdlib `logging` only (no `structlog` / `loguru`) | TS-3 enforced by zero-new-dep grep + Step 1.3 deny-list verification |
| AC-005-5 | INFO log on stage entry/exit | All 4 `test_stage_*.py` files have `caplog`-based AC-005-5 tests |
| AC-005-6 | Stage failures → ERROR; per-source degradation → WARNING; logger name `investo.orchestrator.pipeline` | `test_stage_notify_briefing.py::test_stage_notify_briefing_logs_warning_on_failure` (level pin: WARNING not ERROR) |
| AC-005-7 | `PipelineStatus` StrEnum w/ 3 members (no growth without audit) | `test_results.py::test_pipeline_status_values` |
| AC-005-8 | `PipelineResult` frozen pydantic w/ 5+1 fields including `stage_timings` | `test_results.py::test_pipeline_result_frozen` + `test_pipeline_result_default_stage_timings_empty_dict` |

### NFR-006 — Testing

| AC | Description | Pinned by |
|----|-------------|-----------|
| AC-006-1 | Integration test wires all 4 mock patterns simultaneously | `test_pipeline.py::test_pipeline_end_to_end_success` (httpx.MockTransport for u4 + canned `call_claude_code` driving real `generate_briefing` for u2 + real `write_briefing` for u3 + fake `fetch` for u1) |
| AC-006-2 | 1 integration test per Q9=B failure row | `test_pipeline.py::test_pipeline_end_to_end_empty_collect_alerts_operator` + `test_pipeline_end_to_end_notify_failure_yields_partial` (sample of full Q9=B row coverage; remaining rows pinned at unit level via `test_run_pipeline.py`) |
| AC-006-3 | DI seam (constructor params); no monkeypatching of internals | `pipeline.py` exposes `fetch=`, `runner=`, `git_runner=`, `generate=` — used throughout test files |
| AC-006-4 | `resolve_target_date` PBT (≥100 examples) | `test_date_resolution.py::test_resolve_target_date_pbt_post_condition` + `test_resolve_target_date_pbt_raw_yesterday_with_flag_false` (2 PBTs at 100 examples each) |
| AC-006-5 | ≥30 u5 unit tests | **143 u5 tests** (110 unit + 7 integration + 26 from PipelineResult model tests) |

### NFR-007 — Security (env vars + token redaction)

| AC | Description | Pinned by |
|----|-------------|-----------|
| AC-007-1 | 5-var validation at `main()` entry | `test_main.py::test_main_returns_1_when_required_var_missing` (5-parametrized) + `test_main_treats_empty_string_as_missing` |
| AC-007-2 | Chat-ID disjointness ConfigError BEFORE dispatcher construction | `test_main.py::test_main_rejects_equal_channel_and_operator_ids` + 5 H2 whitespace-tolerance regression tests |
| AC-007-3 | Best-effort alert when token + operator-chat-id present | `test_main.py::test_main_attempts_boot_alert_on_config_error_when_alert_prereqs_present` + 2 skip-when-prereq-missing tests |
| AC-007-4 | No env values in log lines | Verified in source; no test (any test would re-read the source — rely on review) |
| AC-007-5 | Redaction proxied through u4's `_redact_bot_token` | u5 does NOT import `_redact_bot_token`; u4 owns redaction. Verified in source. |

### Drift guards

| AC | Description | Pinned by |
|----|-------------|-----------|
| AC-drift-1 | Signature-change → `/code-review git` review | Process — Step 12 sub-agent review demonstrates the convention |
| AC-drift-2 | Deny `tenacity` / `backoff` deps | `pyproject.toml` grep + `scripts/check_no_anthropic_sdk.py` (extended in u2 Step 10.1) |
| AC-drift-3 | Deny `pandas_market_calendars` / `pandas` | Same grep |
| AC-drift-4 | Deny `asyncio.wait_for(_stage_*)` | AC-001-3 AST-grep test |
| AC-drift-5 | `PipelineStatus` enum cannot grow without audit-log entry | Process — DEBT not registered (current 3 members are stable) |

---

## Open TECH-DEBT items

### From u5 (new this stage)

| ID | Priority | Source step | Description |
|----|----------|-------------|-------------|
| DEBT-017 | Low | Step 12 review | `_TRACEBACK_EXCERPT_MAX_CHARS` duplicated between `pipeline.py` and `models/results.py` |
| DEBT-018 | Low | Step 12 review | AST-grep deny tests use substring matching; brittle to `_stage_*` rename |
| DEBT-019 | Low | Step 12 review | `resolve_target_date` PBT covers only 2026; missing leap-year edges |
| DEBT-020 | Low | Step 12 review | post-H1 `_safe_alert` (Exception) and `_attempt_boot_alert` (narrow) exception lists not aligned |
| DEBT-021 | Low | Step 12 review | unused `PublisherError` re-export in `pipeline.__all__` |

### Cross-unit / pre-existing (unchanged)

| ID | Priority | Origin |
|----|----------|--------|
| DEBT-001 / DEBT-002 | Medium | models |
| DEBT-007 / DEBT-012 | Medium | u2 / u3 |
| DEBT-006 / DEBT-008 / DEBT-010 / DEBT-011 | Low | u2 |
| DEBT-013 | Low | u3 |
| DEBT-003 / DEBT-004 / DEBT-005 / DEBT-009 | Low | u1 |
| DEBT-014 / DEBT-015 / DEBT-016 | Low | u4 |

None block u5. 5 of 21 open items originated in u5; all 5 are Low priority.

---

## FD-vs-implementation divergences (ratified in audit log)

Six structural deviations or ratified fixes landed during u5:

1. **Step 5 — `_stage_collect` callable injection vs class injection**. Plan's `aggregator: Aggregator` parameter was speculative; u1's aggregator is module-level `fetch_all` not a class. Replaced with `CollectCallable` injection seam matching AC-006-3 (DI without monkeypatching internals).

2. **Step 6 — direct `await` for `generate_briefing`, NOT `asyncio.to_thread` wrap**. Plan said TS-2 `asyncio.to_thread` per the orchestrator-side wrap convention. But `generate_briefing` is async-native — its sync `subprocess.run` is bridged via `asyncio.to_thread` *inside* `call_claude_code`. The plan's wrap form would be a TypeError. TS-2 still applies — just owned by u2 not duplicated at u5.

3. **Step 6 — `_default_generate_briefing` adapter for keyword-only API bridging**. u2's `generate_briefing` has keyword-only `runner=` / `budget=`. Orchestrator exposes a positional 3-arg `GenerateCallable` shape via a thin module-level adapter. `budget` intentionally NOT plumbed (per Q4=A: orchestrator does not control u2's retry budget).

4. **Step 9 — `run_pipeline` skipped-stage convention**. When an early stage fails, downstream stages get `"skipped"` in the `stages` dict but NO key in `stage_timings`. Operators see "where time went" without confusing zeros for stages that didn't run.

5. **Step 10 — `FailureStage` Literal extended with `"orchestrator"` (5th value)**. `FailureContext.stage` was `Literal["collect", "generate", "publish", "notify_briefing"]`. Boot/top-level failures (env-validation ConfigError + AC-003-7 unexpected-exception path) needed an explicit stage value — semantically clearer than reusing one of the four stage names. Models test parametrizations updated in lockstep.

6. **Step 12 — H1 + H2 fixes from sub-agent review**. (a) `_safe_alert` exception list broadened from `(OSError, RuntimeError, ValueError)` → `Exception` per documented intent (broken alerter must not mask underlying failure; httpx.HTTPError / asyncio.TimeoutError used to leak). KeyboardInterrupt / SystemExit / asyncio.CancelledError still propagate. (b) Chat-ID disjointness whitespace-tolerant via `.strip()` on all 5 env vars during validation — closes a CLAUDE.md #5 bypass where one stray space let operator alerts route to the public channel.

All six ratified in `aidlc-docs/audit.md`. No cross-unit contract was broken.

---

## Story status

- ✅ **US-005** (스케줄 실행) — closed by `python -m investo` entrypoint + `run_pipeline` Q9=B router. KST 평일 / 토요일 cron-time correctly maps to US trading day per `resolve_target_date`. Total wall-clock ≤ 10 min budget enforced by trusting unit-level timeouts (per Q1=A) + GHA `timeout-minutes: 12` safety net (deferred to u6). All 11 Q9=B Error Policy AC paths pinned by integration + unit tests. CLAUDE.md #5 chat-ID disjointness enforced BEFORE either dispatcher is constructed (whitespace-tolerant per H2 fix).

---

## Pre-flight notes for u6 infra/CI

`u6 infra/CI` is the next and final unit (YAML/config only — no FD/NFR per execution-plan):

- **GHA workflow YAML** (`.github/workflows/daily-briefing.yml`):
  - cron schedule: KST 평일 07:00 (UTC 22:00 prev-day) + KST 토요일 09:00 (UTC 토 00:00).
  - Sets `timeout-minutes: 12` on the `daily-briefing` job per AC-001-4 (10-min design budget + 2-min safety margin).
  - Wires the 5 GitHub Secrets: `CLAUDE_CODE_OAUTH_TOKEN`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_BRIEFING_CHANNEL_ID`, `TELEGRAM_OPERATOR_CHAT_ID`, `SITE_URL_BASE` per AC-007-1.
  - Runs `python -m investo` and exits with the entrypoint's exit code. SUCCESS|PARTIAL → green; FAILED → red + GHA's default email alert as fallback.
  - Reads `permissions: contents: write` for the `git push` from inside the runner.

- **GitHub Pages YAML** (`.github/workflows/pages.yml`):
  - Triggers on push to `main` (after the daily-briefing job commits the new markdown).
  - Builds the `mkdocs-material` site and deploys to `gh-pages` branch.

- **CONTRIBUTING.md update**: document the cron schedule, secret names, `timeout-minutes: 12` rationale, and the operator's manual-trigger workflow (`workflow_dispatch`).

- **No new Python source code**. u5 is the entire runtime; u6 is config plumbing.

### Stable surface u6 consumes

| Symbol | What u6 needs it for |
|--------|----------------------|
| `python -m investo` | Cron entrypoint; exit code → workflow status |
| Exit code 0 | SUCCESS \| PARTIAL → workflow green |
| Exit code 1 | FAILED → workflow red + GHA default email alert |
| 5 env vars | Wired from GitHub Secrets to the workflow's `env:` block |

### Failure paths the operator sees in production

| Failure | Where surfaced | Latency |
|---------|----------------|---------|
| Single source down | u1 swallows; pipeline still runs → SUCCESS | None (graceful) |
| Empty collect (all sources down) | OperatorAlerter (Telegram 1:1) + GHA failure | ≤ 1 min |
| LLM failure (Claude CLI down 3× in a row) | OperatorAlerter + GHA failure | ≤ 4 min |
| Disclaimer missing (NFR-004 hard block) | OperatorAlerter + GHA failure | ≤ 4 min |
| Git push failed 3×× | OperatorAlerter + GHA failure | ≤ 5 min |
| Public-channel notify failed | PARTIAL (no alert; GHA shows green) | None — operator checks the channel manually |
| Boot config error | Best-effort OperatorAlerter (when token+operator-id present) + GHA email | ≤ 10 sec |

---

## Quality gate (final, Step 13 closeout)

| Tool | Result |
|------|--------|
| `ruff check .` | ✅ |
| `ruff format --check .` | ✅ (106 files) |
| `mypy --strict src/` | ✅ (37 source files: 7 models + 8 sources + 7 briefing + 6 publisher + 5 notifier + 4 orchestrator + `__main__`) |
| `pytest` | ✅ **705/705** passing (252 baseline + 178 u2 + 70 u3 + 56 u4 + 149 u5 = 705) |

Test breakdown for u5: 17 errors + 17 date_resolution + 9 stage_collect + 13 stage_generate + 9 stage_publish + 9 stage_notify + 32 run_pipeline + 30 main + 7 integration = **143 u5 tests**, plus +6 from `PipelineResult.stage_timings` model tests = **149 tests added by u5**.

---

## Next stage gate

`u5 orchestrator` Code Generation is now CLOSED. The unit becomes eligible for `/cross-check` against requirements. **One stage gate remains**:

1. `u6 infra/CI` (YAML/config only — Code Generation but no FD/NFR)

Then global `Build and Test` after every unit's CG completes.

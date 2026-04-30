# Code Generation Plan: `u5 orchestrator`

**Date**: 2026-04-30
**Unit**: u5 orchestrator — pipeline integration glue (`run_pipeline` + 4 stage runners + date_resolution + entrypoint)
**Stage**: Code Generation (FD = SKIP per execution-plan; NFR Requirements ✅ closed 2026-04-30 with 39 testable AC)

**Plan source**:
- `aidlc-docs/inception/application-design/component-methods.md` — C5 method signatures
- `aidlc-docs/inception/application-design/application-design.md` — Time Budget + Q9=B Error Policy
- `aidlc-docs/inception/application-design/unit-of-work.md` — u5 module structure + DoD
- `aidlc-docs/construction/u5-orchestrator/nfr-requirements/` — 39 AC + tech stack decisions
- `src/investo/models/results.py` — `PipelineStatus`, `PipelineResult`, `FailureContext`, `FailureStage` (already shipped)
- `src/investo/{sources,briefing,publisher,notifier}/__init__.py` — public surfaces u5 consumes
- `CLAUDE.md` — project rule #3 (orchestrator is the only unit allowed to import all 4 work units), #5 (chat_id disjointness)

---

## Unit Context

### Stories closed by this stage
- **US-005 스케줄 실행** (closes when this unit's CG completes) — KST 평일/토요일 cron entrypoint + ≤10분 wall-clock + Q9=B graceful degradation

### Dependencies
- `investo.models` — `NormalizedItem`, `Briefing`, `BriefingNotification`, `SendResult`, `FailureContext`, `FailureStage`, `PipelineStatus`, `PipelineResult`
- `investo.sources` — `Aggregator` (or whatever `fetch_all` exposes), source-fetch errors
- `investo.briefing` — `generate_briefing`, `BriefingGenerationError`
- `investo.publisher` — `write_briefing`, `commit_and_push`, `PublisherDisclaimerError`, `PublisherIOError`, `PublisherGitError`, `archive_path`
- `investo.notifier` — `BriefingPublisher`, `OperatorAlerter`, `build_summary`
- `httpx.AsyncClient` (existing dep) — shared client injected into both notifier dispatchers
- **NEW external deps**: NONE (per `tech-stack-decisions.md`).

### Definition of Done (from unit-of-work)
- [ ] `python -m investo` entrypoint works (env missing → explicit error + exit 1)
- [ ] Q9=B graceful degradation policy fully implemented + tested per AC-003-1 ~ AC-003-11
- [ ] `resolve_target_date` weekday/saturday branches verified
- [ ] integration test exercises the full pipeline with all external calls mocked

### Module boundary recap
- u5 imports from `investo.models / sources / briefing / publisher / notifier` + stdlib + `httpx`. **u5 is the ONLY unit allowed to import all 4 work units** (CLAUDE.md #3).
- u5 enforces CLAUDE.md #5 chat_id disjointness via `ConfigError` BEFORE constructing the dispatchers (per AC-007-2).

### Known FD-vs-existing-model reconciliation

Per AC-001-1 the orchestrator records per-stage elapsed time on `PipelineResult.stage_timings: dict[str, float]`. The existing shipped `PipelineResult` (in `src/investo/models/results.py` from earlier units) has:
- `target_date: date`
- `status: PipelineStatus`
- `stages: dict[str, str]` (free-form diagnostic, default `{}`)
- `duration_seconds: float` (total)
- `briefing_url: HttpUrl | None`

There is no `stage_timings: dict[str, float]` field today. Two options:
- **(A) Extend `PipelineResult`** with `stage_timings: dict[str, float] = Field(default_factory=dict)`. Backward-compatible (default empty, existing tests still pass).
- **(B) Encode per-stage timing into the existing `stages` dict** as strings like `"ok in 12.34s"`.

**Plan recommendation: (A)** — typed float dict is cleaner for tests + future structured-log integration. Step 2 lands the model extension. (B) would conflate two diagnostic surfaces (status + timing) into one untyped string blob.

---

## Steps

### Step 1: Project bootstrap

- [x] **1.1** Created `src/investo/orchestrator/__init__.py` (~80 lines) —
  module docstring describes US-005 contract (single-entry pipeline runner +
  KST schedule), Q9=B graceful degradation policy summary (per-source
  swallow → SUCCESS / empty-collect → FAILED / BriefingGenerationError →
  FAILED / Publisher* → FAILED / SendResult.ok=False from notify → PARTIAL
  no-alert / top-level unexpected → main() best-effort alert), the
  chat_id-disjointness env-var enforcement (CLAUDE.md #5 — orchestrator
  validates BEFORE constructing dispatchers), and the non-raising
  `run_pipeline` contract (returns `PipelineResult` always; only
  programmer errors propagate). Cross-references all design + NFR docs.
  `__all__: list[str] = []` placeholder (public re-exports finalized in
  Step 11).
- [x] **1.2** Created `tests/unit/orchestrator/__init__.py` (empty) and
  `tests/unit/orchestrator/conftest.py` (~14 lines) — placeholder
  docstring noting per-test fixtures land with the stage tests in
  Steps 4-9 + explicit cross-reference to DEBT-010/013/016 (per-unit
  test-helper duplication tracked across u2/u3/u4) so any duplication
  introduced during u5 has a documented destination.
- [x] **1.3** Confirmed `pyproject.toml` deps unchanged (TS-1 ~ TS-9 are
  stdlib + already-locked; no new dep). Repo-wide grep against
  `tech-stack-decisions.md` TS-10 deny-list (anthropic, tenacity,
  backoff, pandas_market_calendars, structlog, loguru, pytz, pendulum,
  pydantic_settings, respx) → all absent.
- [x] **1.4** Quality gate: ruff ✅, ruff format ✅ (94 files), mypy
  --strict ✅ (**34 source files** = 33 prior + `orchestrator/__init__.py`),
  pytest ✅ **556/556** (bootstrap-only step; no new tests yet —
  conftest.py is a fixture stub, no test bodies).

---

### Step 2: Extend `PipelineResult` model — `stage_timings` field

**Refs**: AC-001-1, AC-005-8, FD-vs-existing-model reconciliation (option A).

- [x] **2.1** Edited `src/investo/models/results.py`:
  - Added field `stage_timings: dict[str, float] = Field(default_factory=dict)` to `PipelineResult`.
  - Added `_reject_negative_stage_timings` field validator: rejects negatives AND values exceeding the same `_DURATION_CEILING_SECONDS` (24h) used for `duration_seconds` — no individual stage can outlast the whole pipeline. Each value violation raises with the stage key embedded (`stage_timings['collect'] must be >= 0, got -0.5`) for fast debugging.
  - Updated class docstring documenting the new field — keys are stage names (typically the four `FailureStage` values plus optional synthetic names); values are wall-clock seconds; orchestrator populates this on every `run_pipeline` exit including failure paths; default `{}` is backward-compatible with existing tests.
- [x] **2.2** Extended `tests/unit/models/test_results.py` (+5 tests, +1 over plan target — added the ceiling-guard test alongside the negative-guard):
  - `test_pipeline_result_default_stage_timings_empty_dict` — backward compat ✅
  - `test_pipeline_result_stage_timings_round_trip` — model_dump→model_validate round-trip with all 4 standard stage keys
  - `test_pipeline_result_stage_timings_accepts_zero` — boundary (skipped stages legitimately record 0.0)
  - `test_pipeline_result_stage_timings_rejects_negative_values` — validator pin
  - `test_pipeline_result_stage_timings_rejects_value_over_ceiling` — second validator branch (24h ceiling)
- [x] **2.3** Quality gate: ruff ✅, ruff format ✅ (94 files, 2 auto-formatted), mypy --strict ✅ (34 source files; field addition only), pytest ✅ **561/561** (+5 tests; zero regressions in the prior 556).

---

### Step 3: `errors.py` — `ConfigError` + per-stage exception umbrella

**Refs**: AC-007-1, AC-007-2, AC-003-2.

- [x] **3.1** Created `src/investo/orchestrator/errors.py` (~95 lines):
  - `class ConfigError(RuntimeError)` — raised by env-validation in `main()`. Carries an immutable `missing_vars: tuple[str, ...]` field (empty tuple for the chat-ID-equality variant). Two factory classmethods:
    - `for_missing(missing_vars)` — non-empty input required; builds message `"missing required environment variable(s): {comma-joined names}"`. Empty input raises `ValueError("ConfigError.for_missing requires at least one var name; use ConfigError.for_equal_chat_ids() for the chat-ID-equality case")` so the two failure modes can never be silently conflated.
    - `for_equal_chat_ids()` — explicit factory for the CLAUDE.md #5 disjointness violation. Message names BOTH env vars + cites "CLAUDE.md project rule #5" + uses "disjoint" so the operator alert is actionable without further context.
  - `class EmptyCollectError(RuntimeError)` — internal sentinel raised by `_stage_collect` when aggregator returned 0 items (per AC-003-2). Not exposed publicly; routed by `run_pipeline` to `OperatorAlerter.alert(stage="collect")` + `status=FAILED`.
  - Both inherit from `RuntimeError` (not `Exception`) — they signal runtime preconditions, not programmer logic errors. `main()`'s top-level `except Exception` after `except ConfigError` cleanly separates the two paths.
- [x] **3.2** Created `tests/unit/orchestrator/test_errors.py` (~195 lines, **17 tests** vs plan's 3-test target — effort high; full surface coverage):
  - **Construction (4)**: `inherits_from_runtime_error`, `default_missing_vars_is_empty_tuple`, `missing_vars_is_immutable_tuple`, `str_form_is_the_message`
  - **`for_missing` (4)**: `single_var`, `multiple_vars_join_in_order` (asserts msg index ordering), `all_five_required_vars` (pins the AC-007-1 5-var contract; if env-var list changes, test fails in lockstep), `rejects_empty_tuple`
  - **`for_equal_chat_ids` (3)**: `empty_missing_vars` (the discriminator), `message_names_both_vars`, `cites_claude_md_rule`
  - **Raise+catch round-trip (2)**: `preserves_missing_vars` (main() needs this for AC-007-3 routing), `caught_as_runtime_error`
  - **EmptyCollectError (4)**: `inherits_from_runtime_error`, `default_construction` (no message; pure control-flow signal), `str_with_message`, `distinct_from_config_error` (neither catches the other)
- [x] **3.3** Quality gate: ruff ✅, ruff format ✅ (95 files; 1 auto-formatted), mypy --strict ✅ (**35 source files** = 34 + `orchestrator/errors.py`), pytest ✅ **578/578** (+17 tests; zero regressions in the prior 561).

---

### Step 4: `date_resolution.py` — `resolve_target_date`

**Refs**: AC-005-1 ~ AC-005-3, AC-006-4 (PBT).

- [x] **4.1** Created `src/investo/orchestrator/date_resolution.py` (~75 lines):
  - `def resolve_target_date(now_utc: datetime, *, weekday_only_us_close: bool = True) -> date`
  - Module-level `_KST = ZoneInfo("Asia/Seoul")` bound once at import (Asia/Seoul is fixed UTC+9 since 1988; no DST; rebinding avoids per-call tz lookups).
  - Algorithm: convert UTC → KST → `target = kst_today - 1 day` → if `weekday_only_us_close`, walk back while `target.weekday() >= 5` (bounded ≤ 2 iterations: Sat→Fri or Sun→Fri).
  - Naive `datetime` raises `ValueError("...timezone-aware...")` at boundary (mirrors `models._validators.ensure_tz_aware` shape; not imported to keep `orchestrator` independent of `models` validators outside of schema usage).
  - **Per AC-005-3 / Q3=A**: NO `pandas_market_calendars` consultation — US holidays surface via empty-collect → `EmptyCollectError` → operator alert. Module docstring explicitly documents the trade-off so any future "just add the calendar" PR has visible justification to overrule.
- [x] **4.2** Created `tests/unit/orchestrator/test_date_resolution.py` (~265 lines, **17 tests** vs plan's ~10 target — high effort):
  - **AC-005-1 Weekday morning (5 parametrized)**: Tue→Mon, Wed→Tue, Thu→Wed, Fri→Thu, Mon→Fri (skip weekend).
  - **AC-005-2 Saturday (1)**: Sat→Fri + asserts target weekday=4.
  - **Sunday extension (1)**: Sun→Fri (2 iterations of weekend-skip loop).
  - **AC-005-3 holiday non-consultation (1)**: KST Fri 2026-07-03 (US Independence Day observed) → Thu 2026-07-02 unchanged; pinning test documents that any future calendar-dep PR must delete this test.
  - **UTC input boundary (1)**: explicit UTC datetime input verifies +9 offset conversion.
  - **Naive datetime rejection (1)**: ValueError with "timezone-aware" match.
  - **Year boundary (2)**: 2026-01-01 Thu→Wed 2025-12-31; 2026-01-05 Mon→Fri 2026-01-02.
  - **DST guard (1)**: March 8 + November 1 2026 (US DST transitions) — KST unaffected; both Sundays walk back to Friday correctly.
  - **`weekday_only_us_close=False` (2)**: raw yesterday (Sun→Sat allowed); default flag value pinned to True.
  - **2 PBTs at 100 examples each (per AC-006-4)**:
    - Default-flag post-conditions: target is a weekday + strictly < KST today + at most 3 days back (Mon→prev Fri is the maximum gap).
    - `weekday_only_us_close=False`: target is exactly `kst_today - 1 day` regardless of weekday.
- [x] **4.3** PBT (per AC-006-4): TWO hypothesis strategies covering both flag values, each at 100 examples. Strategy: `st.datetimes(min=2026-01-01, max=2026-12-31 23:59, timezones=st.just(UTC))` — full-year domain (vs plan's 30-day suggestion) since KST conversion + weekday math should be uniformly correct year-round.
- [x] **4.4** Quality gate: ruff ✅, ruff format ✅ (97 files; 1 auto-formatted then re-verified clean), mypy --strict ✅ (**36 source files** = 35 prior + `orchestrator/date_resolution.py`), pytest ✅ **595/595** (+17 tests including 2 100-example PBTs; zero regressions in the prior 578).

---

### Step 5: `_stage_collect` — wraps u1 sources aggregator

**Refs**: AC-001-1, AC-003-1, AC-003-2, AC-005-5.

**Design note**: u1's aggregator is a **module-level function** `investo.sources.fetch_all(target_date) -> list[NormalizedItem]`, not a class. Plan signature `aggregator: Aggregator` was speculative; actual signature uses a `CollectCallable = Callable[[date], Awaitable[list[NormalizedItem]]]` keyword-only `fetch=` parameter that defaults to `_default_fetch_all = investo.sources.fetch_all`. This dependency-injection seam matches AC-006-3 (DI seams; no monkeypatching of internals required for tests, though one test demonstrates monkeypatching the default-binding for the production-wire path).

- [x] **5.1** Created `src/investo/orchestrator/pipeline.py` (~95 lines):
  - Module docstring describes the file's incremental build-up across Steps 5-9 (this commit lands `_stage_collect` only).
  - `CollectCallable` type alias for the injectable aggregator surface.
  - `_default_fetch_all = investo.sources.fetch_all` module-level binding (test seam — `monkeypatch.setattr` redirects this).
  - `_logger = logging.getLogger("investo.orchestrator.pipeline")` per AC-005-4.
  - `async def _stage_collect(target_date, *, fetch=None) -> list[NormalizedItem]`:
    - INFO `[collect] starting target_date=%s` on entry.
    - `items = await runner(target_date)` (runner = injected `fetch` or `_default_fetch_all`).
    - INFO `[collect] returned %d items` on exit (BEFORE the empty-check raise — operators see the count in GHA logs even on failure).
    - Empty result → `raise EmptyCollectError("aggregator returned 0 items for target_date={target_date}")`.
- [x] **5.2** Created `tests/unit/orchestrator/test_stage_collect.py` (~205 lines, **9 tests** vs plan's 4 target — high effort):
  - Happy path (3): items returned, target_date forwarded, partial aggregator (AC-003-1 — non-empty list with degraded sources still proceeds).
  - AC-003-2 (2): empty result → `EmptyCollectError`; error message embeds `target_date`.
  - AC-005-5 (2): INFO logs on entry + exit; INFO emitted even on empty-collect failure path (operators see count before the raise).
  - Default wiring (1): `fetch=None` calls `_default_fetch_all` (verified via `monkeypatch.setattr` of the module-level binding).
  - Propagation (1): non-`SourceFetchError` exceptions from aggregator (programmer errors) propagate without swallowing, ready for AC-003-7 routing in `main()`.
- [x] **5.3** Quality gate: ruff ✅ (initial fail on SIM117 nested-with → fixed via combined-context form), ruff format ✅ (98 files; 2 auto-formatted), mypy --strict ✅ (**37 source files** = 36 prior + `orchestrator/pipeline.py`), pytest ✅ **604/604** (+9 tests; zero regressions in the prior 595).

---

### Step 6: `_stage_generate` — wraps u2 briefing.generate_briefing

**Refs**: AC-001-1, AC-003-3, TS-2 (asyncio.to_thread for sync subprocess wrap).

- [ ] **6.1** In `pipeline.py`, add:
  - `async def _stage_generate(items: list[NormalizedItem], target_date: date, *, runner: ClaudeCodeRunner | None = None) -> Briefing`
  - Logs INFO `[generate] starting`
  - `briefing = await asyncio.to_thread(generate_briefing, items, target_date, runner=runner)` (per TS-2)
  - On `BriefingGenerationError`: re-raise (caller handles routing)
- [ ] **6.2** Tests: `tests/unit/orchestrator/test_stage_generate.py`:
  - happy path with `FakeClaudeRunner` injected → returns `Briefing`
  - `BriefingGenerationError` propagates (different stage values: classification, synthesis, post_validation, budget)
  - asyncio.to_thread wrap doesn't lose context (await completes correctly)
- [ ] **6.3** Quality gate.

---

### Step 7: `_stage_publish` — wraps u3 publisher write_briefing + commit_and_push

**Refs**: AC-001-1, AC-003-4, AC-003-5, TS-2.

- [ ] **7.1** In `pipeline.py`, add:
  - `async def _stage_publish(briefing: Briefing, target_date: date, *, git_runner: GitRunner | None = None) -> Path`
  - Logs INFO `[publish] starting`
  - Path 1: `path = await asyncio.to_thread(write_briefing, briefing, target_date)` — verify-first (u3 enforces disclaimer); raises `PublisherDisclaimerError` or `PublisherIOError` on failure
  - Path 2: `await asyncio.to_thread(commit_and_push, message=f"briefing: {target_date}", files=[path], runner=git_runner)` — raises `PublisherGitError` on exhausted retry
  - Returns the archive path
- [ ] **7.2** Tests: `tests/unit/orchestrator/test_stage_publish.py`:
  - happy path (fake `GitRunner`) → returns archive path; commit_and_push called with correct message + files
  - `PublisherDisclaimerError` from write_briefing → propagates; commit_and_push NOT called
  - `PublisherGitError` from commit_and_push → propagates after write succeeded
  - `PublisherIOError` from write_briefing → propagates
- [ ] **7.3** Quality gate.

---

### Step 8: `_stage_notify_briefing` — wraps u4 BriefingPublisher.send

**Refs**: AC-003-6, AC-005-7 (PARTIAL = exactly publish-ok + notify-fail).

- [ ] **8.1** In `pipeline.py`, add:
  - `async def _stage_notify_briefing(briefing: Briefing, *, publisher: BriefingPublisher, site_url: HttpUrl) -> SendResult`
  - Logs INFO `[notify_briefing] starting`
  - `summary = build_summary(briefing, site_url=str(site_url))`
  - `payload = BriefingNotification(target_date=briefing.target_date, summary_text=summary, site_url=site_url)`
  - `result = await publisher.send(payload)`
  - Returns the `SendResult` (orchestrator decides PARTIAL vs SUCCESS based on `result.ok`)
- [ ] **8.2** Tests: `tests/unit/orchestrator/test_stage_notify_briefing.py`:
  - happy path (`MockTransport` → 200 + ok=true) → `SendResult(ok=True)`
  - Telegram API failure → `SendResult(ok=False)` (non-raising contract — u4's responsibility, but pin)
  - HTTP transport error → `SendResult(ok=False)`
  - request body shape: chat_id matches `publisher._channel_id`; text matches `summary`
- [ ] **8.3** Quality gate.

---

### Step 9: `run_pipeline` composer — applies Q9=B routing + status assembly

**Refs**: AC-001-1, AC-001-3, AC-001-5, AC-003-1 ~ AC-003-11, AC-005-7.

- [ ] **9.1** In `pipeline.py`, add:
  - `async def run_pipeline(target_date: date | None = None, *, aggregator, runner, git_runner, publisher, alerter, site_url) -> PipelineResult`
  - `start = time.monotonic()`; `stage_timings = {}`; `stages_status = {}`
  - **collect**: try `_stage_collect(target_date, aggregator=aggregator)` → on `EmptyCollectError` → alert(FailureStage="collect") → return `PipelineResult(status=FAILED, stages={"collect": "failed: empty"})`
  - **generate**: try `_stage_generate(items, target_date, runner=runner)` → on `BriefingGenerationError` → alert(stage="generate") → return FAILED
  - **publish**: try `_stage_publish(briefing, target_date, git_runner=git_runner)` → on `PublisherDisclaimerError | PublisherIOError | PublisherGitError` → alert(stage="publish") → return FAILED
  - **notify_briefing**: try `_stage_notify_briefing(...)` → if `SendResult.ok=False` → log WARNING, status=PARTIAL (no operator alert per AC-003-6)
  - **success**: status=SUCCESS, briefing_url derived from `archive_path` + `site_url` base
  - All stages: record `stage_timings[stage] = time.monotonic() - stage_start` regardless of outcome
  - Total `duration_seconds = time.monotonic() - start`
- [ ] **9.2** Tests: `tests/unit/orchestrator/test_run_pipeline.py` — Q9=B Error Policy table coverage:
  - happy path → SUCCESS + all 4 stage_timings populated + briefing_url set + 0 alerter calls
  - empty collect → FAILED + stages={"collect": "failed: empty"} + 1 alerter call (stage="collect")
  - generate fail → FAILED + 1 alerter call (stage="generate") + publish/notify SKIPPED
  - publish disclaimer fail → FAILED + 1 alerter call (stage="publish") + notify SKIPPED
  - publish git fail → FAILED + 1 alerter call (stage="publish") + notify SKIPPED
  - notify fail → PARTIAL + 0 alerter calls + briefing_url still set (publish was OK)
  - per-source collect failure (aggregator partial) → SUCCESS (per AC-003-9) + 0 alerter calls
  - alerter failure during FAILED run → status still FAILED (per AC-003-10) + WARNING logged
  - top-level `KeyError` from a stage (programmer error) → propagates from `run_pipeline` (caught by `main()`)
- [ ] **9.3** AST-grep tests (per AC-001-3, AC-001-5, AC-003-11): assert `pipeline.py` does NOT contain `asyncio.wait_for(_stage_*` or stage-level `asyncio.gather(_stage_*` or retry loops wrapping stage calls.
- [ ] **9.4** Quality gate.

---

### Step 10: `main()` entrypoint — env validation + best-effort alert + exit codes

**Refs**: AC-007-1 ~ AC-007-5, US-005 entrypoint contract.

- [ ] **10.1** Replace `src/investo/__main__.py`:
  - `def main() -> int`: read 5 env vars (`CLAUDE_CODE_OAUTH_TOKEN`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_BRIEFING_CHANNEL_ID`, `TELEGRAM_OPERATOR_CHAT_ID`, `SITE_URL_BASE`)
  - Missing var → `ConfigError(missing_vars=(...,))`
  - Equal `TELEGRAM_BRIEFING_CHANNEL_ID == TELEGRAM_OPERATOR_CHAT_ID` → `ConfigError(missing_vars=(), message="...")`
  - On `ConfigError`: if `TELEGRAM_BOT_TOKEN` AND `TELEGRAM_OPERATOR_CHAT_ID` are present, attempt ONE best-effort `OperatorAlerter.alert(FailureContext(stage="orchestrator", error_type="ConfigError", ...))` with 5s timeout (per AC-007-3 — note: `FailureContext.stage` is `Literal["collect", "generate", "publish", "notify_briefing"]`, so we use stage="orchestrator" via "notify_briefing" or extend FailureStage; **plan to use `stage="notify_briefing"` as the closest fit OR extend the literal — Step 10.1 chooses the path during impl**); log to stderr; return 1
  - On success: build shared `httpx.AsyncClient` + construct `BriefingPublisher` + `OperatorAlerter` (kwargs-only, disjoint chat_ids per CLAUDE.md #5); construct `Aggregator` + obtain `runner` + `git_runner`; call `asyncio.run(run_pipeline(...))`
  - Map `PipelineStatus` → exit code: SUCCESS|PARTIAL → 0; FAILED → 1
  - Top-level unexpected `Exception` (not `ConfigError`) → best-effort alert (stage="orchestrator") + log + return 1 (per AC-003-7)
- [ ] **10.2** Tests: `tests/unit/orchestrator/test_main.py`:
  - 5 missing-var parametrized cases → `ConfigError` raised + exit 1 + best-effort alert attempted (when possible)
  - chat_id equality → `ConfigError` raised + exit 1
  - happy SUCCESS → exit 0
  - PARTIAL → exit 0
  - FAILED → exit 1
  - top-level exception → exit 1 + alert attempted (mocked OperatorAlerter)
- [ ] **10.3** Resolve the FailureStage Literal: if needed, add `"orchestrator"` to `FailureStage` literal in `src/investo/models/results.py` (small extension; ratify in Step 10's audit log entry).
- [ ] **10.4** Quality gate.

---

### Step 11: `__init__.py` public surface + integration test

**Refs**: AC-006-1 ~ AC-006-3.

- [ ] **11.1** Replace `src/investo/orchestrator/__init__.py` placeholder:
  - Re-export `run_pipeline`, `main`, `resolve_target_date`, `ConfigError`, `EmptyCollectError`
  - Internal helpers (`_stage_*`) NOT re-exported (private contract)
- [ ] **11.2** Create `tests/integration/test_pipeline.py` (~300 lines):
  - End-to-end happy path: 4 mocks wired (httpx.MockTransport for u1 + u4 / FakeClaudeRunner for u2 / fake GitRunner for u3) → `run_pipeline` → SUCCESS
  - End-to-end empty collect → FAILED + alerter call
  - End-to-end generate fail → FAILED + alerter call
  - End-to-end publish disclaimer fail → FAILED + alerter call
  - End-to-end publish git fail → FAILED + alerter call
  - End-to-end notify fail → PARTIAL + no alerter call
  - End-to-end per-source partial → SUCCESS
  - Public surface importability: `run_pipeline`, `main`, `resolve_target_date`, `ConfigError`, `EmptyCollectError` all resolve from `investo.orchestrator`
- [ ] **11.3** Quality gate.

---

### Step 12: Sub-agent code review (combined u5 review)

Delegate fresh-eyes review per dev-investo skill §5.1. Focus areas:

- **Module boundary**: u5 imports from all 4 work units (allowed) + `investo.models` + stdlib + `httpx`. Verify NO unit-to-unit imports were inadvertently created.
- **Q9=B routing correctness**: every Error Policy table row has the correct routing (FAILED vs PARTIAL vs SUCCESS); every routing has the correct alerter call vs no-alert behavior.
- **Time accounting**: `stage_timings` populated even on stage-FAIL paths (so debugging post-mortem can see which stage was slow before failing).
- **Env validation timing**: `ConfigError` raised BEFORE any `httpx.AsyncClient` is constructed (no resource leak).
- **Best-effort alert robustness**: when `TELEGRAM_BOT_TOKEN` is missing, the best-effort alert is silently skipped (no nested ConfigError).
- **Async-sync interaction**: `asyncio.to_thread` wraps the right sync calls; no accidental blocking inside an `async def` body.
- **Test isolation**: integration tests don't leak files into the real archive/ dir (use tmp_path or `monkeypatch.setattr` for `ARCHIVE_ROOT`).
- **Logging**: logger name follows AC-005-6 convention; no env-var values in log lines (AC-007-4).
- **CLAUDE.md #5 enforcement**: `main()` rejects equal chat_ids BEFORE constructing dispatchers; integration test pins this.

After review: apply Critical / High fixes before commit; triage Medium / Low into TECH-DEBT or apply.

---

### Step 13: Closeout `summary.md` + final quality gate

- [ ] **13.1** `aidlc-docs/construction/u5-orchestrator/code/summary.md`:
  - Files-created table (source + tests)
  - 39 AC traceability table — each AC pinned by named test
  - Story status: US-005 ✅ closed
  - Open TECH-DEBT (any new from u5; carry forward 16 from prior units)
  - Hand-off notes for u6 infra/CI: stable surface = `python -m investo` exit 0/1; integration-tested under all 4 mocks; the GHA workflow YAML wires the cron schedule + env-vars (Secrets) + `timeout-minutes: 12`
- [ ] **13.2** Final quality gate: ruff ✅, ruff format ✅, mypy --strict ✅ (~40 source files: 33 prior + 7 new u5 — `__init__.py`, `errors.py`, `date_resolution.py`, `pipeline.py`, plus model extension; `__main__.py` replaced; counts confirmed at gate run), pytest ✅ (~556 baseline + ~50-60 u5 = ~610-620 tests).

**Exit**: ✅ `u5 orchestrator` Code Generation stage CLOSED. Story US-005 closes. The unit becomes eligible for `/cross-check`. After u5: `u6 infra/CI` (YAML/config only — Code Generation but no FD/NFR), then global `Build and Test`.

---

## Step Dependency Graph

```
1 bootstrap
  └── 2 PipelineResult.stage_timings extension
        └── 3 errors (ConfigError, EmptyCollectError)
              ├── 4 date_resolution
              ├── 5 _stage_collect (depends on 3)
              ├── 6 _stage_generate (depends on 3)
              ├── 7 _stage_publish (depends on 3)
              ├── 8 _stage_notify_briefing (depends on 3)
              └── 9 run_pipeline (depends on 5+6+7+8)
                    └── 10 main entrypoint (depends on 9 + 4)
                          └── 11 __init__ + integration test
                                └── 12 sub-agent review
                                      └── 13 closeout
```

In practice: 1 → 2 → 3 → 4 → 5 → 6 → 7 → 8 → 9 → 10 → 11 → 12 → 13 sequentially.

---

## Estimated Scope

- ~7 source files in `src/investo/orchestrator/` (`__init__.py`, `errors.py`, `date_resolution.py`, `pipeline.py`) + extension to `models/results.py` + replacement of `__main__.py` = effectively 6 src files net
- ~7 test files in `tests/unit/orchestrator/` + 1 integration test (`tests/integration/test_pipeline.py`)
- ~13 plan steps, each yielding 1 commit
- Solo dev: ~1.5-2 days (larger than u3/u4 because of integration test scope)

---

## How to Approve

This plan is the single source of truth for `u5` Code Generation. Reply
**approve** to begin Step 1; **changes [N]** to revise step N.

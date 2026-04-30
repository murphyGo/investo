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

**Refs**: AC-001-1, AC-003-3.

**Design reconciliation (vs plan)**: ``generate_briefing`` is already async-native (its sync ``subprocess.run`` is bridged via ``asyncio.to_thread`` *inside* ``call_claude_code`` per u2 Step 6). The plan's ``await asyncio.to_thread(generate_briefing, ...)`` form would be a TypeError on an async function. ``_stage_generate`` therefore ``await``s directly. TS-2 (asyncio.to_thread for sync subprocess) still applies — it's just owned by u2's ``call_claude_code``, not duplicated at the orchestrator boundary.

**Signature reconciliation**: u2's ``generate_briefing`` has keyword-only ``runner=`` / ``budget=`` parameters. The orchestrator exposes a positional ``GenerateCallable = Callable[[date, Sequence[NormalizedItem], ClaudeRunner | None], Awaitable[Briefing]]`` shape for test convenience and bridges via a thin module-level adapter ``_default_generate_briefing``. ``budget`` is intentionally NOT exposed at the orchestrator boundary (per Q4=A — orchestrator does not control u2's retry budget).

- [x] **6.1** Extended `src/investo/orchestrator/pipeline.py`:
  - Imports: `ClaudeRunner` (Protocol from `briefing.claude_code`), `generate_briefing as _u2_generate_briefing`, `Briefing` model.
  - `GenerateCallable` type alias for the test-seam shape.
  - `_default_generate_briefing(target_date, items, runner) -> Briefing` adapter — thin wrapper that calls `_u2_generate_briefing(target_date, items, runner=runner)` to bridge positional `GenerateCallable` ↔ u2's keyword-only API. Lives as a module-level function (not `functools.partial`) for type-checker clarity.
  - `async def _stage_generate(target_date, items, *, runner=None, generate=None) -> Briefing`:
    - INFO `[generate] starting target_date=%s items=%d` on entry.
    - `runner_callable = generate if generate is not None else _default_generate_briefing` — DI seam.
    - `briefing = await runner_callable(target_date, items, runner)` — direct await; no asyncio.to_thread wrap (already-async).
    - INFO `[generate] briefing built target_date=%s` on success.
    - `BriefingGenerationError` re-raised unchanged (caller routes per AC-003-3).
- [x] **6.2** Created `tests/unit/orchestrator/test_stage_generate.py` (~310 lines, **13 tests** vs plan's 3 target — high effort):
  - **Happy path (4)**: returns Briefing from u2; (target_date, items) forwarded; runner seam forwarded to u2 (critical for integration-test FakeClaudeRunner replay path); default `runner=None` when caller omits.
  - **AC-003-3 BGE propagation (2)**: 4-stage parametrized test (classification/synthesis/post_validation/budget) confirms each propagates with correct `stage` + `attempt_count`; identity test confirms BGE is NOT wrapped (`exc_info.value is original`).
  - **Programmer-error propagation (1)**: KeyError from u2 propagates unwrapped per FD failure contract + AC-003-7 routing.
  - **AC-005-5 INFO logging (2)**: entry + exit log messages with target_date + items count; "starting" emitted BEFORE u2 is invoked even on failure path (no "briefing built" message after raise).
  - **Default-callable wiring (1)**: `generate=None` resolves to `_default_generate_briefing`; verified via `monkeypatch.setattr` of the module-level adapter binding.
- [x] **6.3** Quality gate: ruff ✅, ruff format ✅ (100 files; 1 auto-formatted), mypy --strict ✅ (**37 source files** — pipeline.py extended in place; no new src file), pytest ✅ **617/617** (+13 tests; zero regressions in the prior 604).

---

### Step 7: `_stage_publish` — wraps u3 publisher write_briefing + commit_and_push

**Refs**: AC-001-1, AC-003-4, AC-003-5, TS-2.

- [x] **7.1** Extended `src/investo/orchestrator/pipeline.py`:
  - Added imports: `asyncio`, `Path`, u3's public surface (`GitRunner`, `commit_and_push`, `write_briefing`).
  - `async def _stage_publish(briefing, target_date, *, git_runner=None) -> Path`:
    - INFO `[publish] starting target_date=%s` on entry.
    - Phase 1: `archive_path = await asyncio.to_thread(write_briefing, briefing, target_date)` — sync u3 function bridged off the event loop (TS-2). Raises `PublisherDisclaimerError` (NFR-004 verify-first; nothing on disk) or `PublisherIOError` (atomic write OS error).
    - INFO `[publish] wrote {archive_path}` between phases.
    - Phase 2: `await asyncio.to_thread(commit_and_push, "briefing: {target_date}", [archive_path], runner=git_runner)` — 3-attempt retry (FD R3 backoff 0/2/8 s) with idempotent-commit detection on retry. `PublisherGitError` after exhaustion; `last_stderr` is 1024-byte UTF-8 truncated.
    - INFO `[publish] committed + pushed %s` on success. Returns `archive_path` for `run_pipeline` to derive `briefing_url`.
- [x] **7.2** Created `tests/unit/orchestrator/test_stage_publish.py` (~330 lines, **9 tests** vs plan's 4 target — high effort):
  - **Happy path (3)**: end-to-end write+commit+push (asserts file on disk + add/commit/push call sequence); returns the archive path; commit message format `"briefing: 2026-04-25"` pinned (so u6 / cross-check can grep).
  - **AC-003-4 (2)**: PublisherDisclaimerError propagates with no file on disk + commit_and_push NEVER called; PublisherIOError propagates with git phase skipped.
  - **AC-003-5 (1)**: 3-attempt push exhaustion → PublisherGitError; `last_stderr` propagated; file IS on disk (write succeeded). `_FailingGitPushRunner` simulates the realistic "commit landed, push failed, retry sees clean tree" idempotent-noop case via the `_is_idempotent_commit_noop` detector.
  - **Default git_runner (1)**: `git_runner=None` forwards `None` to `commit_and_push` so u3 uses real subprocess; verified by `monkeypatch.setattr` on the orchestrator's imported binding.
  - **AC-005-5 INFO logging (2)**: 3-line happy log (starting → wrote → committed + pushed); "starting" emitted BEFORE any I/O even on disclaimer-fail (operators see attempt in GHA log).
  - **GitRunner Protocol kwargs reconciliation**: u3's GitRunner uses `(args, *, capture_output, text, check)` — my initial fakes used `timeout` (matching u4's pattern). Fixed mid-step.
  - **PublisherIOError signature reconciliation**: `__init__` uses `path=` (not `target_path=`). Fixed mid-step.
- [x] **7.3** Quality gate: ruff ✅ (initial SIM102 nested-if violation in fake → fixed via `and` combine), ruff format ✅ (101 files; 1 auto-formatted), mypy --strict ✅ (37 source files; pipeline.py extended in place), pytest ✅ **626/626** (+9 tests; zero regressions in the prior 617).

---

### Step 8: `_stage_notify_briefing` — wraps u4 BriefingPublisher.send

**Refs**: AC-003-6, AC-003-8, AC-005-5, AC-005-6.

- [x] **8.1** Extended `src/investo/orchestrator/pipeline.py`:
  - Added imports: `pydantic.HttpUrl`, `BriefingNotification`, `SendResult`, `BriefingPublisher`, `build_summary`.
  - `async def _stage_notify_briefing(briefing, *, publisher, site_url) -> SendResult`:
    - INFO `[notify_briefing] starting target_date=%s` on entry.
    - 3 phases: `build_summary(briefing, site_url=str(site_url))` → `BriefingNotification(target_date, summary_text, site_url)` (model re-validates 4096 UTF-16 cap as defense in depth) → `await publisher.send(payload)`.
    - On `result.ok=True`: INFO `[notify_briefing] ok target_date=%s message_id=%s` (message_id helps diagnose chat-ID misconfig).
    - On `result.ok=False`: WARNING `[notify_briefing] failed target_date=%s error=%s` per AC-005-6 (NOT ERROR — failure here is non-fatal; pipeline marks PARTIAL).
    - **Non-raising contract**: u4's `BriefingPublisher.send` already encodes HTTP failures as `SendResult(ok=False)`; orchestrator forwards verbatim. Programmer errors (test stubs with bugs, etc.) DO propagate per FD failure contract — orchestrator does not swallow.
- [x] **8.2** Created `tests/unit/orchestrator/test_stage_notify_briefing.py` (~290 lines, **9 tests** vs plan's 4 target — high effort):
  - **Happy path (3)**: SendResult(ok=True, message_id) returned; chat_id in request body matches publisher's channel_id (CLAUDE.md #5 stage-layer safety net); text contains date header + market_summary + site_url footer.
  - **AC-003-6 / AC-003-8 (3)**: Telegram API error (`{"ok":false}`) → SendResult(ok=False, error contains "channel not found"); httpx.ConnectError → SendResult(ok=False); programmer error from broken publisher (RuntimeError) propagates unwrapped (orchestrator doesn't blanket-swallow).
  - **AC-005-5 / AC-005-6 logging (2)**: success → INFO with message_id, NO WARNING records; failure → WARNING with error message embedded (NOT ERROR level — failure is non-fatal at this layer).
  - **Site URL flow (1)**: `site_url` flows through both `build_summary` (footer) and `BriefingNotification` (model field); end-to-end pin via request body inspection.
- [x] **8.3** Quality gate: ruff ✅, ruff format ✅ (102 files; 1 auto-formatted), mypy --strict ✅ (37 source files — pipeline.py extended in place), pytest ✅ **635/635** (+9 tests; zero regressions in the prior 626).

---

### Step 9: `run_pipeline` composer — applies Q9=B routing + status assembly

**Refs**: AC-001-1, AC-001-3, AC-001-5, AC-003-1 ~ AC-003-11, AC-005-7.

- [x] **9.1** Extended `src/investo/orchestrator/pipeline.py` with `run_pipeline` composer:
  - Imports added: `asyncio`, `time`, `traceback`, `UTC`/`datetime`, pydantic `TypeAdapter`, `BriefingGenerationError`, models (`FailureContext`, `PipelineResult`, `PipelineStatus`), notifier `OperatorAlerter`, `resolve_target_date`, all 3 publisher errors umbrella + `PublisherError` for re-export.
  - **Signature**: `async def run_pipeline(target_date=None, *, publisher, alerter, site_url_base, fetch=None, runner=None, git_runner=None, generate=None) -> PipelineResult`. DI seams forward to each stage runner. Default `target_date=None` resolves via `resolve_target_date(datetime.now(UTC))`.
  - **Q9=B routing** sequential per Q5 (no `asyncio.gather` of stages):
    - collect → except EmptyCollectError → alert + FAILED + downstream skipped
    - generate → except BriefingGenerationError → alert + FAILED
    - publish → except (PublisherDisclaimerError | PublisherIOError | PublisherGitError) → alert + FAILED
    - notify_briefing → non-raising; SendResult.ok=False → PARTIAL (NO alert per AC-003-6); SendResult.ok=True → SUCCESS
  - **Stage timings** recorded for each executed stage (not for skipped stages — operators see "where time went" without confusing zeros).
  - **Briefing URL**: `_briefing_url_for(target_date, site_url_base)` builds `{base}/{YYYY}/{MM}/{YYYY-MM-DD}/`, threaded into both `_stage_notify_briefing(site_url=...)` and `PipelineResult.briefing_url`.
  - **Best-effort alerter** via `_safe_alert(alerter, stage, exc)` helper:
    - Constructs `FailureContext` via `_build_failure_context` (truncates traceback to ≤2000 chars per the model's own validator; falls back to `type(exc).__name__` when `str(exc)` is empty so `error_message` min_length=1 holds).
    - On alerter SendResult(ok=False) → WARNING log, status stays FAILED (AC-003-10).
    - On alerter raising (programmer error in stub) → catches `OSError | RuntimeError | ValueError`, logs WARNING, status stays FAILED — does NOT mask the underlying stage failure with an unrelated exception.
  - **No retry** at orchestrator boundary (per Q4=A); **no `asyncio.wait_for`** wrap (per Q1=A); **no stage-level `asyncio.gather`** (per Q5).
  - Final `_build_result` helper logs `[pipeline] complete target_date=... status=... duration=...` at INFO + constructs the frozen `PipelineResult`.

- [x] **9.2** Created `tests/unit/orchestrator/test_run_pipeline.py` (~700 lines, **25 tests** vs plan's 9 target — high effort):
  - **Happy path (2)**: SUCCESS with all 4 stage_timings + briefing_url + no alert; target_date=None resolves to a weekday.
  - **AC-003-1 + AC-003-9 (2)**: per-source partial → SUCCESS not PARTIAL; explicit AC-003-9 invariant pin.
  - **AC-003-2 (1)**: empty collect → FAILED + 1 alert(stage="collect", error_type="EmptyCollectError"); downstream skipped; publisher never called.
  - **AC-003-3 (1, parametrized over 4 BGE stages)**: classification/synthesis/post_validation/budget → FAILED + alert(stage="generate", error_type="BriefingGenerationError").
  - **AC-003-4 (1)**: PublisherDisclaimerError → FAILED + alert(stage="publish", error_type="PublisherDisclaimerError"); notify skipped.
  - **AC-003-5 (1)**: PushFailingGitRunner exhausts retries → FAILED + alert(stage="publish", error_type="PublisherGitError"); idempotent-noop on retry handled.
  - **AC-003-6 + AC-003-8 (1)**: notify SendResult(ok=False) → PARTIAL with briefing_url set + NO alert.
  - **AC-003-10 (2)**: alerter ok=False during FAILED → status stays FAILED + WARNING logged; alerter raising → status stays FAILED + WARNING ("alert raised unexpected").
  - **AC-001-1 (2)**: stage_timings populated on success (all 4 keys, all non-negative); on abort, only stages that ran get timings (downstream skipped → no key).
  - **Programmer error propagation (1)**: aggregator RuntimeError → propagates from run_pipeline (orchestrator does NOT catch arbitrary Exception per AC-003-7 routing in main()).
  - **Briefing URL composition (2)**: trailing-slash base normalized; month padded to 2 digits (`/2026/01/2026-01-05/`).
  - **Total duration sanity (1)**: `duration_seconds ≥ sum(stage_timings.values()) - 0.1` (loose bound).
  - **`_build_failure_context` (2)**: traceback truncated to ≤2000 chars; empty `str(exc)` falls back to class name so min_length=1 holds.
- [x] **9.3** AST-grep deny tests (3) — read `pipeline.py` source, parse with `ast`, assert no offending nodes:
  - **AC-001-3** — regex `asyncio\.wait_for\s*\(\s*_stage_` returns no match.
  - **AC-001-5** — walk AST for `asyncio.gather(...)` calls; assert no positional arg contains the substring `_stage_`.
  - **AC-003-11** — walk AST for `For` / `While` nodes whose body contains an `await _stage_*(...)` expression; assert empty.
- [x] **9.4** Quality gate: ruff ✅ (initial F401 unused imports + 2× E501 long-line in fake ctors → fixed via `--fix` + manual line-break), ruff format ✅ (1 file auto-formatted), mypy --strict ✅ (initial unused-`type: ignore` on `FailureContext.stage=stage` — type checker accepted the str narrowing → comment removed), pytest ✅ **660/660** (+25 tests; zero regressions in the prior 635).

---

### Step 10: `main()` entrypoint — env validation + best-effort alert + exit codes

**Refs**: AC-007-1 ~ AC-007-5, US-005 entrypoint contract.

- [x] **10.1** Replaced `src/investo/__main__.py` (~210 lines, NotImplementedError stub → real entrypoint). Module structure: `_REQUIRED_ENV_VARS` Final tuple; `_ALERT_PREREQ_VARS` (token + operator_chat_id) gate for AC-007-3; `_BOOT_ALERT_TIMEOUT_S=5.0`; `_missing_env_vars()` (treats `""` as missing per GHA Secrets behavior); `_validate_env() -> 5-tuple` (ConfigError.for_missing on absence; `for_equal_chat_ids()` on CLAUDE.md #5 violation BEFORE either dispatcher constructed; pydantic ValidationError on bad SITE_URL_BASE wrapped in ConfigError); `_attempt_boot_alert(exc)` (catches construction `ValidationError|ValueError` + dispatch `OSError|RuntimeError|httpx.HTTPError` so alerter never masks the underlying exit code; uses 5-s timeout client); `_async_main()` (1st try ConfigError → alert+1; 2nd try shared `httpx.AsyncClient(timeout=30.0)` + dispatcher construction + `await run_pipeline(...)`; status → 0/0/1; top-level Exception per AC-003-7 → log.exception + alert + 1, never propagates); `main()` sync wrapper sets `logging.basicConfig(INFO)` + `asyncio.run(_async_main())`.

  Original prose (preserved for traceability):
  - `def main() -> int`: read 5 env vars (`CLAUDE_CODE_OAUTH_TOKEN`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_BRIEFING_CHANNEL_ID`, `TELEGRAM_OPERATOR_CHAT_ID`, `SITE_URL_BASE`)
  - Missing var → `ConfigError(missing_vars=(...,))`
  - Equal `TELEGRAM_BRIEFING_CHANNEL_ID == TELEGRAM_OPERATOR_CHAT_ID` → `ConfigError(missing_vars=(), message="...")`
  - On `ConfigError`: if `TELEGRAM_BOT_TOKEN` AND `TELEGRAM_OPERATOR_CHAT_ID` are present, attempt ONE best-effort `OperatorAlerter.alert(FailureContext(stage="orchestrator", error_type="ConfigError", ...))` with 5s timeout (per AC-007-3 — note: `FailureContext.stage` is `Literal["collect", "generate", "publish", "notify_briefing"]`, so we use stage="orchestrator" via "notify_briefing" or extend FailureStage; **plan to use `stage="notify_briefing"` as the closest fit OR extend the literal — Step 10.1 chooses the path during impl**); log to stderr; return 1
  - On success: build shared `httpx.AsyncClient` + construct `BriefingPublisher` + `OperatorAlerter` (kwargs-only, disjoint chat_ids per CLAUDE.md #5); construct `Aggregator` + obtain `runner` + `git_runner`; call `asyncio.run(run_pipeline(...))`
  - Map `PipelineStatus` → exit code: SUCCESS|PARTIAL → 0; FAILED → 1
  - Top-level unexpected `Exception` (not `ConfigError`) → best-effort alert (stage="orchestrator") + log + return 1 (per AC-003-7)
- [x] **10.2** Created `tests/unit/orchestrator/test_main.py` (~360 lines, **25 tests** vs plan's 7 target — high effort): AC-007-1 (3: 5-parametrized missing-var, empty-string, multi-missing); AC-007-2 (1: chat-id equality, pipeline NEVER invoked); AC-007-3 (3: prereqs present → 1 alert with stage="orchestrator"; bot_token missing → no alert; operator_chat_id missing → no alert); site URL parsing (2: malformed → exit 1, happy URL forwarded); exit-code mapping (1 parametrized: SUCCESS|PARTIAL → 0, FAILED → 1); AC-003-7 (2: KeyError → alert(orchestrator, KeyError) + exit 1; RuntimeError without prereqs → exit 1 no alert); happy path (2); _missing_env_vars helper (2: declaration order, empty when all set); best-effort alert robustness (2: FailureContext construction failure silenced, alerter dispatch OSError silenced); forward-args sanity (1: publisher / alerter / site_url_base reach run_pipeline). Uses `_stub_pipeline` + `_capture_alerts` context-manager helpers that monkeypatch the symbols inside `__main__`'s import binding (DI without changing `__main__` signature).
- [x] **10.3** Extended `FailureStage` Literal in `src/investo/models/results.py` to include `"orchestrator"` (5th value). Updated:
  - `tests/unit/models/test_results.py::_FAILURE_STAGES` tuple.
  - `tests/unit/models/test_roundtrip.py::_FAILURE_STAGES` strategy.
  - This is the explicit stage value for boot/top-level failures (env-validation ConfigError + AC-003-7 unexpected-exception path) — semantically clearer than reusing one of the four stage names. Ratified in audit log.
- [x] **10.4** Quality gate: ruff ✅ (3 F401 unused imports auto-fixed: `UTC`/`datetime`/`Iterator`-related leftover from initial draft; 1 unused fixture import), ruff format ✅ (105 files), mypy --strict ✅ (37 source files — `__main__.py` rewritten in place; no new src file), pytest ✅ **686/686** (+25 main tests + 1 from FailureStage extension touching the parametrized models tests; zero regressions in the prior 660).

---

### Step 11: `__init__.py` public surface + integration test

**Refs**: AC-006-1, AC-006-3.

- [x] **11.1** Finalized `src/investo/orchestrator/__init__.py` public surface:
  - Re-exports: `run_pipeline`, `resolve_target_date`, `ConfigError`, `EmptyCollectError` (4 names).
  - **`main` deliberately NOT re-exported** here — it lives in `investo.__main__` per Python convention so `python -m investo` finds it. Re-exporting from `investo.orchestrator` would be redundant + error-prone (two import paths for the same symbol). Inline comment ratifies the decision.
  - Internal stage runners (`_stage_*`) NOT re-exported — they're implementation details of `run_pipeline` and individually testable via explicit imports from `investo.orchestrator.pipeline`.
- [x] **11.2** Created `tests/integration/test_pipeline.py` (~430 lines, **7 tests**):
  - **AC-006-1 happy path (1)**: 4 mocks wired simultaneously — fake `fetch` for u1, real `generate_briefing` driven by canned `call_claude_code` stub for u2 (mirrors `test_briefing_pipeline_poc.py`), real `write_briefing` to `tmp_path` ARCHIVE_ROOT + fake GitRunner for u3, single shared httpx.AsyncClient with MockTransport routing both `BriefingPublisher.send` and any `OperatorAlerter.alert` based on chat_id. Asserts: SUCCESS status, all 4 stage_timings, real file on disk with disclaimer ("투자 자문" or "면책"), git add/commit/push sequence, public-channel send with per-day URL footer, NO operator alert.
  - **AC-003-2 empty collect (1)**: 0-item fetch → FAILED + 1 operator alert (lands at operator chat ID NOT public channel) + u2/u3/public-channel never invoked.
  - **AC-003-6 / AC-003-8 notify failure (1)**: Telegram `{"ok":false,"description":"rate limited"}` for the public-channel call → PARTIAL + briefing_url set + NO operator alert + file still on disk + git lifecycle ran.
  - **CLAUDE.md #5 chat-ID isolation invariant (1)**: empty-collect failure path issues 1 Telegram call → assert `chat_ids_seen == [_OPERATOR_CHAT]`; public channel never receives anything.
  - **Public-surface importability (2)**: 4 names resolve from `investo.orchestrator`; internal `_stage_*` NOT exposed; `main` NOT re-exported (per Step 11.1 design); `__all__` exact set check; types verified (`callable` / `RuntimeError` subclass).
  - **resolve_target_date round-trip (1)**: smoke test that the re-export works the same as the module-level import (catches accidental shadowing).
  - **Test architecture**: `stub_u2_claude` fixture monkeypatches u2's `call_claude_code` with stage1+stage2 stubs and disables `_BACKOFF_SCHEDULE` so retries don't introduce wall-clock delay. `isolated_archive` fixture redirects `ARCHIVE_ROOT` + disables `time.sleep` in u3's git_ops backoff.
- [x] **11.3** Quality gate: ruff ✅ (3 F401 unused imports auto-fixed: `ConfigError`, `EmptyCollectError`, `logging` from initial draft), ruff format ✅ (1 file auto-formatted), mypy --strict ✅ (37 source files; `__init__.py` extended in place — no new src file), pytest ✅ **693/693** (+7 integration tests; zero regressions in the prior 686).

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

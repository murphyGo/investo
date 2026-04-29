# Tech Stack Decisions — `u5 orchestrator`

**Date**: 2026-04-30
**Source**: `u5-orchestrator-nfr-requirements-plan.md` (proposed answers approved via `/loop` continuation pattern)

This locks `u5`-specific library choices. Project-wide stack (Python 3.11+, pydantic v2, ruff, mypy --strict, pytest, hypothesis) is already fixed in `pyproject.toml` and is not re-decided here. Units `u1` (httpx, defusedxml, bleach) and `u4` (httpx) already locked their additions.

**Headline result**: u5 adds **zero** new external dependencies. Every choice below is stdlib or already-locked project core. This matches u2's posture (also zero new deps) and is the strictest possible reading of NFR-002 (월 $0 운영비; 의존성 최소화).

---

## TS-1. Async runtime — stdlib `asyncio`

- **Status**: stdlib, no dep change.
- **Used here**: `pipeline.py::run_pipeline` is `async def`. Every `_stage_*` function is `async def` (per `component-methods.md` C5). `main()` runs `asyncio.run(run_pipeline())`.
- **Why stdlib `asyncio`**: u1's aggregator already uses `asyncio.gather` for source parallelism. Reusing stdlib keeps the runtime model uniform across the whole project.
- **Why not `anyio`**: `anyio` would add a dependency for cross-runtime support (trio + asyncio). u5 has no trio requirement; pure asyncio is simpler.
- **Forbidden**: any third-party event-loop library (`uvloop`, `trio`, `curio`).

---

## TS-2. Subprocess+asyncio bridge — stdlib `asyncio.to_thread` (per Q7=A)

- **Status**: stdlib, no dep change.
- **Used here**: u3's `commit_and_push` and u2's `call_claude_code` are sync `subprocess.run` callers. The orchestrator's `_stage_publish` and `_stage_generate` wrap those with `await asyncio.to_thread(commit_and_push, ...)` / `await asyncio.to_thread(generate_briefing, ...)` to keep the async surface uniform.
- **Why `asyncio.to_thread`**: zero-dependency, stdlib-since-3.9. The CPU work in those subprocess calls is in the child process, not in the Python interpreter — so the sync function blocking the thread is fine. The await point gives the event loop a chance to handle other coroutines (though u5 stages run sequentially per Q5, so there is no concurrent coroutine to handle in practice; the wrap is for **interface uniformity**, not parallelism).
- **Why not run sync functions directly inside async**: blocking the event loop thread is generally bad practice; even though there's nothing else running, future test patterns (e.g., spawning a watchdog coroutine) become viable.
- **Why not `anyio.to_thread.run_sync`**: same as TS-1 (no `anyio` dep).

---

## TS-3. Logging — stdlib `logging` (per Q6=B)

- **Status**: stdlib, no dep change.
- **Used here**: `pipeline.py` declares `logger = logging.getLogger("investo.orchestrator.pipeline")`. INFO for stage entry/exit + elapsed time. WARNING for graceful degradation (single-source failure). ERROR for stage failure paths.
- **Why stdlib `logging`**:
  - GitHub Actions captures stdout/stderr verbatim. The structured-log advantage (machine-parseable JSON) is wasted in a 1-person GHA viewer.
  - stdlib `logging` is universally familiar; no learning curve.
  - Zero dep cost.
- **Why not `structlog`**: needs `structlog` package; JSON output reduces GHA log readability for a 1-person operator. Reject per Q6=B.
- **Why not `loguru`**: same dependency cost; opinionated formatting that conflicts with GHA's expected line-oriented log shape.
- **Log format**: default Python `logging.basicConfig(level=INFO, format='%(asctime)s %(levelname)s %(name)s: %(message)s')` set in `main()` before `run_pipeline`. No file handlers (GHA captures stderr).

---

## TS-4. Date / time — stdlib `datetime` + `zoneinfo` (per Q3=A)

- **Status**: stdlib, no dep change.
- **Used here**: `date_resolution.py::resolve_target_date` accepts a UTC `datetime`, converts via `astimezone(zoneinfo.ZoneInfo("Asia/Seoul"))` to KST, applies the weekday/saturday branch, returns a `date`.
- **Why stdlib `zoneinfo`**: Python 3.9+ ships IANA tz database support directly. No `pytz` needed.
- **Why not `pytz`**: deprecated in favor of `zoneinfo` since 3.9. Reject.
- **Why not `pendulum`**: heavier API surface, dependency cost, no advantage for our 2 timezone conversions (UTC → KST).
- **Why not `pandas_market_calendars`** (rejected per Q3=A): brings transitive `pandas` + `numpy` dependencies (~ tens of MB). For ~10× per year US-holiday handling, the cost-benefit is firmly negative for a 1-person tool. The operator alert path (AC-003-2) covers it.

---

## TS-5. Status enum — stdlib `enum.StrEnum` (per AC-005-7)

- **Status**: stdlib, no dep change.
- **Used here**: `models/results.py` (or `orchestrator/__init__.py`) declares `class PipelineStatus(StrEnum): SUCCESS = "success"; PARTIAL = "partial"; FAILED = "failed"`.
- **Why `StrEnum`**: Python 3.11+ stdlib (project minimum is 3.11). Each member is both a string and an enum value, so `result.status == "success"` and `result.status == PipelineStatus.SUCCESS` both work — useful in JSON serialization (pydantic v2 model_dump) and log messages.
- **Why not pydantic-only constraint** (e.g., `Literal["success", "partial", "failed"]`): no enumerable membership; no `.value` attribute for log lines. StrEnum is strictly better here.

---

## TS-6. PipelineResult — pydantic v2 BaseModel (existing dep)

- **Status**: already locked (pydantic v2 is project core).
- **Used here**: `models/results.py` adds `class PipelineResult(BaseModel)` per AC-005-8: `target_date: date`, `status: PipelineStatus`, `stage_timings: dict[str, float]`, `total_elapsed_s: float`, `error_summary: str | None = None`. Frozen (`model_config = ConfigDict(frozen=True)`).
- **Why frozen**: `PipelineResult` is the orchestrator's return value; downstream test assertions should not see mutated state.
- **Why not a `dataclass`**: pydantic gives free JSON serialization (for future log integration) and validation (e.g., `total_elapsed_s ≥ 0`). Existing project dep.

---

## TS-7. Env var parsing — stdlib `os.environ` + pydantic `HttpUrl` (existing)

- **Status**: stdlib + existing dep.
- **Used here**: `main()` reads via `os.environ["NAME"]` (raises `KeyError` if missing → caught and re-raised as `ConfigError` per AC-007-1). `SITE_URL_BASE` parsed via `pydantic.HttpUrl(value)` for URL validation.
- **Why not `pydantic_settings`**: would tie env-var parsing to a specific pydantic-settings model class. The 5-var schema is small and stable; `os.environ.get()` + manual validation is simpler. `pydantic_settings` adds another package dep without proportional benefit.
- **Why not `python-decouple` / `dotenv`**: dotenv is for local development; production runs in GHA where env vars are injected via Secrets. No dotenv needed.

---

## TS-8. Test mocks — reuse existing patterns (per Q8 confirmation)

- **Status**: no new dep; reuses 4 existing fakes.
- **Used here**:
  - **u1 sources**: `httpx.MockTransport` (already used in u1 unit tests + u2 integration smoke).
  - **u2 briefing**: `FakeClaudeRunner` (record/replay fixture mechanism, FD R9 in u2).
  - **u3 publisher**: fake `GitRunner` Protocol implementation (existing in u3 tests).
  - **u4 notifier**: `httpx.MockTransport` (existing in u4 tests).

  `tests/integration/test_pipeline.py` activates all four simultaneously. The orchestrator exposes constructor params or function args so each fake can be injected without monkeypatching internals (per AC-006-3).
- **Why not introduce a new mock framework** (e.g., `respx`, `pytest-httpx`): we already have working mock patterns shipped + tested; introducing another framework would require migrating existing tests. Reject per Q8 confirmation.

---

## TS-9. Hypothesis PBT — already locked

- **Status**: hypothesis is already in dev-deps (used by u1 / u2).
- **Used here**: `tests/unit/orchestrator/test_date_resolution.py` runs ≥ 100-example PBT for `resolve_target_date` per AC-006-4. Strategy: `from hypothesis import strategies as st` → `st.datetimes(...)` constrained to a 30-day range.
- **Why hypothesis (not random)**: shrinking on failure + minimum-counterexample reporting are essential for date-arithmetic edge cases (DST, year boundaries).

---

## TS-10. Forbidden additions (AC-drift-2 + AC-drift-3)

This section is the explicit **deny-list** for u5. Adding any of these to `pyproject.toml` MUST be rejected by `/code-review git`:

- `tenacity` / `backoff` — orchestrator-level retry libraries (Q4=A: no orchestrator-level retry; trust unit-level)
- `pandas_market_calendars` / `pandas` / `numpy` — US trading calendar (Q3=A: no extra dep; operator alert covers ~10× per year)
- `structlog` / `loguru` — alternative loggers (Q6=B: stdlib `logging` is sufficient)
- `pytz` — superseded by stdlib `zoneinfo` (Python ≥ 3.9)
- `pendulum` / `arrow` — date-time libraries (stdlib `datetime` + `zoneinfo` are sufficient)
- `anyio` / `trio` / `uvloop` / `curio` — alternative async runtimes (stdlib `asyncio` is sufficient)
- `pydantic_settings` — env-var-to-model wrapper (5-var schema doesn't justify it)
- `respx` / `pytest-httpx` — alternative HTTP mock frameworks (existing `httpx.MockTransport` is sufficient)

CI guard: `scripts/check_no_anthropic_sdk.py` (already shipped in u2) extended in u5 Code Generation Step 1 to scan for these deny-list packages in `pyproject.toml`. Same script, additional regex.

---

## Summary

u5 orchestrator adds **0 new external dependencies**. It uses 4 stdlib modules (`asyncio`, `logging`, `datetime`/`zoneinfo`, `enum`) + pydantic v2 (already locked) + reuses 4 existing test mock patterns. The 8-package deny-list (TS-10) hardens the zero-cost invariant against future drift.

This matches u2's posture (also zero new deps) and is the strictest plausible reading of NFR-002. Total project external deps after u5: **3 runtime** (httpx, pydantic, defusedxml + bleach for u1) — same as after u4.

# Session Log: 2026-04-29 - u2 briefing - Code Generation Step 6

## Overview
- **Date**: 2026-04-29
- **Unit**: u2 briefing
- **Stage**: Code Generation
- **Step**: Step 6 — `claude_code.py` (RetryBudget + subprocess wrapper)

## Work Summary

Implemented the LLM-call boundary — the **NFR-002 single LLM call site**.
Module exposes `RetryBudget` (FD L4 cumulative wall-clock counter shared
across stages), `ClaudeRunner` (Protocol — test seam matching
`subprocess.run`'s relevant signature), and `call_claude_code` (async
wrapper that dispatches via `asyncio.to_thread(subprocess.run, ...)` so
the event loop stays responsive while the LLM thinks).

`subprocess.TimeoutExpired` is wrapped into a `SubprocessOutcome` with
`returncode=124` and `stderr="<timeout after Ns>"` — the caller's retry
loop decides whether to retry, no exception-handling discipline needed
in the loop itself.

21 new tests covering RetryBudget arithmetic + boundaries, runner-seam
correctness (passes through args/timeout, surfaces non-zero returncode
without raising), TimeoutExpired wrapping, event-loop non-blocking
under concurrent dispatch, and four AST-based source self-checks
pinning AC-2.5 (no oauth token literal), AC-7.1 (no shell=True / no
string-form subprocess), and the Anthropic SDK ban.

## Files Changed

### Created
- `src/investo/briefing/claude_code.py` (192 lines) — RetryBudget
  dataclass with `record/would_exceed/check_or_raise` + `_default_runner`
  (only call site of `subprocess.run`) + `call_claude_code` async
  wrapper + `ClaudeRunner` Protocol + module docstring documenting
  subprocess hygiene rules.
- `tests/unit/briefing/test_claude_code.py` (294 lines) — 21 tests
  including the AST-based `_executable_source` helper that strips
  docstrings before grep (avoids the docstring's negative-context
  mentions of `CLAUDE_CODE_OAUTH_TOKEN` and `shell=True` causing
  false positives).

### Modified
- `aidlc-docs/construction/plans/u2-briefing-code-generation-plan.md` —
  Step 6 sub-tasks `[x]` with detailed status notes
- `aidlc-docs/aidlc-state.md` — u2 CG progress 5/10 → 6/10
- `aidlc-docs/audit.md` — Step 6 entry prepended
- `docs/TECH-DEBT.md` — DEBT-006 added (cancellation propagation gap,
  Low priority, deferred until u5 orchestrator wait_for pattern is
  finalized)

## Key Decisions

| Decision | Rationale |
|----------|-----------|
| `asyncio.to_thread(subprocess.run, ...)` over `asyncio.create_subprocess_exec` | Simpler — runner seam matches `subprocess.run`'s signature, FakeClaudeRunner (Step 7) just implements `__call__(args, ...)`. Trade-off: cancellation doesn't reach the child process (DEBT-006). Acceptable for v1 since per-call timeout enforces the bound. |
| `SubprocessOutcome` returned for both success AND non-zero returncode | FD R3 — non-zero returncode is one of several retry triggers; the caller's retry loop inspects the outcome. Raising would require try/except in the caller, complicating the retry-budget tracking. |
| `TimeoutExpired` wrapped into outcome (returncode=124) | Same rationale — keep the surface consistent. The retry loop sees `returncode != 0` and decides whether to retry; no exception path. |
| `would_exceed` uses `>=` (inclusive) | FD L4 wording: "if the next attempt would exceed budget, raise immediately". Equality counts as exhausted. Test pins `240 + 60 == 300` returns True. |
| `check_or_raise(*, stage)` parameter unused but kept | API symmetry with caller-context. `del stage` documents intent and silences linters. The BGE always carries `stage="budget"` because budget is its own failure mode. |
| AST-based `_executable_source` test helper | The naive `inspect.getsource(cc)` grep false-positives on the module docstring's negative-context mentions ("the OAuth token env var is consumed by the CLI binary"). AST-strip ensures we grep only executable code. |

## Code Review Results

Sub-agent review (general-purpose): **APPROVE (ship as-is)**.

| Category | Status |
|----------|--------|
| Correctness | ✅ |
| Safety | ✅ |
| Reliability | ⚠️ → ✅ (DEBT-006 registered) |
| Maintainability | ✅ |
| Test Coverage | ✅ |

Findings: 0 Critical / 0 High / 2 Mediums / 3 Lows + 2 TECH-DEBT
candidates.
- **M1** Cancellation propagation gap → DEBT-006 (Low; defer to u5).
- **M2** Test margin too tight (0.18s) → APPLIED, bumped to 0.25s.
- **L1** `del stage` in `check_or_raise` — kept.
- **L2** `stderr=None` coercion — kept (theoretical defensive code).
- **L3** `_executable_source` nested-function recursion — agent's
  concern was incorrect; `ast.walk(tree)` already recurses. No action.

## Quality Gate

- `ruff check .` ✅
- `ruff format --check .` ✅ (52 files already formatted)
- `mypy --strict src/` ✅ (21 source files; +1 from Step 5's 20)
- `pytest -q` ✅ **353/353 passed in 3.90s**
  - +21 new tests in `test_claude_code.py`

## Potential Risks

- **R-Step6-1**: When u5 orchestrator wraps `generate_briefing` in an
  outer `asyncio.wait_for`, a timeout there would cancel the awaiter
  but leave the `claude` child process running until the inner
  `subprocess.run` timeout fires. Up to 120 s of orphan-child
  lifetime. DEBT-006 registered. Acceptable for v1 (single-process
  runner; kernel cleanup is reliable).
- **R-Step6-2**: The `time.monotonic` used for `elapsed_s` measures
  wall-clock between dispatch and return. If the system clock leaps,
  monotonic is immune. ✅
- **R-Step6-3**: `_executable_source` AST strip would miss content in
  string literals at runtime (e.g. `BANNED = "shell=True"`). No such
  patterns exist or are likely to be introduced. Tests would still
  catch the `subprocess.run("...")` form via the executable code grep.

## TECH-DEBT Items

- **DEBT-006** (NEW, Low): Cancellation propagation gap in
  `call_claude_code`'s `asyncio.to_thread` wrapping. Defer until u5
  orchestrator's wait_for wrapping is finalized; if u5 takes the
  simpler "trust the inner timeout" path, DEBT-006 closes without
  action.

## Next Step

**Step 7** — `tests/_helpers/fake_claude_runner.py`: SHA-256 fixture
key + JSON fixture replay + INVESTO_LIVE_LLM record mode + AC-6.5
grep test ensuring no test imports `subprocess` directly to invoke
`claude`.

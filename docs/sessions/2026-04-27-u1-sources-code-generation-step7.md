# Session Log: 2026-04-27 — u1 sources — Code Generation Step 7 (`aggregator.py`)

## Overview
- **Date**: 2026-04-27
- **Unit**: u1 sources
- **Stage**: Code Generation
- **Step**: 7 of 10 — `fetch_all` aggregator

## Work Summary
Implemented `fetch_all(target_date)` per FD L1: open a shared
`httpx.AsyncClient`, build `FetchWindow.from_kst_date`, dispatch every
registered adapter concurrently via `asyncio.gather(...,
return_exceptions=True)`. Per-result classification matches L4 — a
`SourceFetchError` is logged at WARNING and contributes `[]`; any other
`BaseException` (including `CancelledError` / `KeyboardInterrupt` /
`SystemExit`, all of which `gather` catches when
`return_exceptions=True`) is re-raised so the orchestrator's stage
guard sees it. The early `if not adapters: return []` short-circuit
avoids opening an `AsyncClient` when nothing is registered.

13 new tests across two files pin the contract:
`test_aggregator.py` covers AC-3.1–3.5 + programmer-error propagation;
`test_fetch_all_budget.py` covers AC-1.1 (scaled by 100x for test
speed) and adds a separate concurrency-proof test.

The autouse `_isolate_registry` fixture had been duplicated across
three test files; consolidated into `tests/unit/sources/conftest.py`.

**Side-fix**: hypothesis caught a pre-existing bug in `_parse_retry_after`
(Step 3) where `"NaN"` parsed via `float()` returned a NaN value that
silently bypassed `compute_sleep`'s `[0, max_retry_after_s]` bound (NaN
comparisons always return False). Added a `math.isfinite` guard plus 4
regression tests covering NaN/Infinity/-Infinity/inf.

Code review verdict: **APPROVE_WITH_NOTES**. All 5 suggestions applied,
DEBT-005 registered for future structured-logging migration.

## Files Changed
- Created:
  - `src/investo/sources/aggregator.py` — `fetch_all`
  - `tests/unit/sources/test_aggregator.py` — 11 anchor tests
  - `tests/unit/sources/test_fetch_all_budget.py` — 2 timing tests
  - `tests/unit/sources/conftest.py` — `_isolate_registry` autouse fixture
  - `docs/sessions/2026-04-27-u1-sources-code-generation-step7.md` — this file
- Modified:
  - `src/investo/sources/_retry.py` — `math.isfinite` NaN/Inf guard in `_parse_retry_after`
  - `tests/unit/sources/test_retry.py` — 2 new NaN/Inf regression tests
  - `tests/unit/sources/test_registry.py` — dropped local fixture (uses conftest.py)
  - `aidlc-docs/aidlc-state.md` — Step 7/10 ✅
  - `aidlc-docs/audit.md` — Step 7 audit log entry (with side-fix note)
  - `aidlc-docs/construction/plans/u1-sources-code-generation-plan.md` — Step 7 marked complete
  - `docs/TECH-DEBT.md` — added DEBT-005

## Key Decisions
| Decision | Rationale |
|----------|-----------|
| `for result in results` (no `adapter` in unpacking) | The aggregator logs the exception's self-reported `source_name`. If an adapter violates FD R8 by raising `SourceFetchError("typo")` while registered as "fomc-rss", the lie surfaces in the log — that's the desired debugging signal. Inline comment justifies the choice. |
| `BaseException` branch covers `CancelledError` / `KeyboardInterrupt` / `SystemExit` | `gather(return_exceptions=True)` catches all `BaseException` subclasses since 3.8. Re-raising keeps the orchestrator in control of run-level lifecycle. Inline comment confirms the breadth is deliberate. |
| Early `if not adapters: return []` short-circuit | Reads as documentation, not optimization. Saves opening a useless AsyncClient + gathering an empty awaitable list. |
| Conftest extraction for `_isolate_registry` | Three identical copies across test files violated DRY. Conftest scope is `tests/unit/sources/` so it applies to all sibling tests; new test files inherit isolation for free. |
| Bump concurrency-test bound 0.6 → 0.75 s | 3 × 0.3 s sleeps: sequential is 0.9 s, concurrent is ~0.3 s. 0.75 still discriminates concurrent from sequential while leaving 50%+ headroom for slow CI runners. |
| Patch `_parse_retry_after` NaN bug as Step 7 side-fix | The bug was pre-existing (Step 3) and only surfaced now because hypothesis explores randomly. Fixing during the failing quality gate is cheaper than parking the test failure for a separate commit. Audit-log note records the cross-step fix. |

## Code Review Results
Sub-agent (general-purpose) per dev-investo §5.1.

| Category | Status |
|----------|--------|
| Correctness | ✅ — L1/L4 algorithm faithful; AC-3.1–3.5 pinned |
| Safety | ✅ — `async with` closes AsyncClient before re-raise; cancellation propagates correctly |
| Reliability | ✅ — programmer errors propagate, source errors are isolated per FD R6 |
| Maintainability | ✅ — consolidated fixture; documented BaseException + log-name choices inline |
| Test Coverage | ✅ — 13 anchor tests; AC-1.1 budget + concurrency proof |

**Issues addressed in-step**:
- M1 — inline comment confirms BaseException scope
- M2 — inline comment justifies `result.source_name` (vs `adapter.name`) choice
- L3 — concurrency bound bumped 0.6 → 0.75
- L4 — `_isolate_registry` extracted to conftest.py (3 copies → 1)
- DEBT-005 — registered (Low priority — structured-logging migration)

**Side-fix**:
- `_parse_retry_after` NaN bug — patched with `math.isfinite` + 4 regression tests

## Potential Risks
- The conftest extraction means new test files under `tests/unit/sources/` automatically pick up the registry-isolation fixture. A future test that *wants* to inspect post-import registry state (e.g., a smoke test that the FOMC adapter from Step 9 self-registers) will need to override or skip the fixture explicitly — flag in the Step 9 plan.
- The 0.75 s concurrency bound still relies on `asyncio.sleep` being roughly accurate. In an extremely loaded environment (CI runner under heavy memory pressure), event-loop scheduling jitter could push elapsed past 0.75 s. Re-evaluate if the test ever flakes; the next backstop is to assert "elapsed ≤ 1.5 × max(adapter_sleep)" rather than a fixed number.

## TECH-DEBT Items
- DEBT-005 — Aggregator log line is printf-style, not L5-structured (Low; revisit on operations / structured-logging ADR)

## Next Step
Step 8: `src/investo/sources/fomc_rss.py` — first concrete adapter
implementing the FOMC press-release RSS feed. Requires capturing a
recorded fixture (one-off network call), then offline tests via
`httpx.MockTransport` covering AC-7.2/7.3/7.4/7.6.

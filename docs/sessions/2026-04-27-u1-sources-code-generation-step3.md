# Session Log: 2026-04-27 — u1 sources — Code Generation Step 3 (`_retry.py`)

## Overview
- **Date**: 2026-04-27
- **Unit**: u1 sources
- **Stage**: Code Generation
- **Step**: 3 of 10 — shared retry / backoff helper

## Work Summary
Implemented `_retry.py` with three public surfaces: `RetryConfig` (frozen+slots
dataclass with field validation), `compute_sleep` (pure function with
Retry-After precedence), and `async retry_get` (wraps the inner retry loop in
`asyncio.wait_for` to enforce the 60-s outer wall-clock budget). The
`SourceFetchError` exception lives here pending Step 5's relocation to
`protocol.py`. Status classification: 5xx + 429 + transient httpx errors are
retryable; 4xx-not-429 + other httpx errors + oversized body are terminal.

The implementation surface diverges from plan §3.1 by using explicit `url` /
`headers` / `params` kwargs instead of a `request_kwargs` dict. The change is
documented in the module docstring; the FOMC adapter (Step 8) only needs
those three. Future adapters needing `data=` / `json=` will extend the
signature.

Sub-agent code review verdict: **APPROVE** — 0 Critical/High/Medium, 3 Lows,
1 TECH-DEBT. L1 (`last_exc` dead-code) was applied; L2/L3 are cosmetic /
already documented and skipped. DEBT-003 was registered.

## Files Changed
- Created:
  - `src/investo/sources/_retry.py` — `RetryConfig`, `SourceFetchError`, `compute_sleep`, `retry_get`, helpers
  - `tests/unit/sources/test_retry.py` — 38 tests (24 anchor + 2 PBT + 12 mock-transport scenarios)
  - `docs/TECH-DEBT.md` — added DEBT-003 (5 MB body cap is post-hoc)
- Modified:
  - `aidlc-docs/aidlc-state.md` — Step 3/10 ✅
  - `aidlc-docs/audit.md` — Step 3 audit log entry
  - `aidlc-docs/construction/plans/u1-sources-code-generation-plan.md` — Step 3 marked complete

## Key Decisions
| Decision | Rationale |
|----------|-----------|
| `SourceFetchError` lives in `_retry.py` for now (Step 3) | Step 5 builds `protocol.py` and will relocate the class there with a re-export here. Avoids partial Step-5 work in Step 3 while keeping per-step atomicity. |
| Explicit `url` / `headers` / `params` kwargs vs plan's `request_kwargs` dict | mypy strict friendliness; FOMC adapter (Step 8) needs only these. Documented divergence in module docstring. |
| Wrap inner loop in `asyncio.wait_for(timeout=total_budget_s)` | Single source of truth for the 60-s cap. Cancellation is graceful — inner coroutine has no `except CancelledError`, so cancellation propagates cleanly out of `await asyncio.sleep()` or `await client.get()`. |
| Post-hoc 5 MB body cap (vs streaming) | `httpx.AsyncClient.get()` buffers the full body by default. v1 trades streaming complexity for simplicity; FOMC RSS is < 200 KB so the buffer is irrelevant in practice. Streaming added as DEBT-003. |
| `RetryConfig.__post_init__` validates field bounds | Catches misconfigured adapter constructors at instantiation rather than at first failure. Same pattern as `FetchWindow`. |
| `_parse_retry_after` clamps negative + past-date Retry-After to 0.0 | RFC 7231 says clients SHOULD wait at least the indicated time; a past date or negative number means "you're free now." Clamping at 0 preserves the contract. |
| Removed `last_exc` defensive tracker (review L1) | Inside `_retry_get_inner`, the loop body always returns or raises — `last_exc` could only be `None` at the trailer. Replaced trailer with `raise AssertionError(...) # pragma: no cover` for clarity. |

## Code Review Results
Sub-agent (general-purpose) per dev-investo §5.1.

| Category | Status |
|----------|--------|
| Correctness | ✅ — status classification, Retry-After precedence, 60-s outer cap all verified live |
| Safety | ✅ — `wait_for` cancellation graceful; 5 MB cap is post-hoc by design (DEBT-003) |
| Reliability | ✅ — covers `TimeoutException` / `NetworkError` / `RemoteProtocolError`; `retries=0` works |
| Maintainability | ✅ (after L1 fix) — single dataclass, explicit kwargs, clear error contract |
| Test Coverage | ✅ — 38 tests; 2 PBTs at 100 examples each |

**Issues addressed in-step**:
- L1 — dead `last_exc` removed; defensive trailer simplified
- L2 — skipped (cosmetic test-helper `type: ignore`)
- L3 — skipped (surface choice already documented in module docstring)

**Issues registered**:
- DEBT-003 (Low) — post-hoc 5 MB body cap; revisit when a non-RSS adapter lands

## Potential Risks
- The "outer budget" timer test (`test_retry_get_budget_enforced`) uses a 100 ms budget vs 1 s handler sleep. CI hosts under load could conceivably take > 100 ms to schedule the cancellation, but the assertion bound is `< 0.5 s` — generous enough for a 5× safety margin.
- The `SourceFetchError`-lives-in-`_retry.py` arrangement is technically a temporary state. Step 5's plan must remember to relocate the class and add a re-import line here. Tracked in plan §5.1.

## TECH-DEBT Items
- DEBT-003 — `retry_get` 5 MB body cap is post-hoc (Low priority; revisit when a non-RSS adapter lands)

## Next Step
Step 4: `src/investo/sources/_sanitize.py` — `bleach`-based HTML strip helper
for feed-derived titles and summaries (NFR AC-7.2). Small file with ~5 anchor
tests. Likely self-review.

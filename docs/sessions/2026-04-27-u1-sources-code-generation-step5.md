# Session Log: 2026-04-27 — u1 sources — Code Generation Step 5 (`protocol.py`)

## Overview
- **Date**: 2026-04-27
- **Unit**: u1 sources
- **Stage**: Code Generation
- **Step**: 5 of 10 — `SourceAdapter` Protocol + `SourceFetchError` relocation

## Work Summary
Created `src/investo/sources/protocol.py` as the canonical home for the
public adapter contract:

- **`SourceFetchError`** — relocated from `_retry.py`. Same interface
  except `cause` widened from `Exception | None` to `BaseException |
  None` to match FD §E4 exactly.
- **`SourceAdapter` Protocol** — declares `ClassVar[str] name`,
  `ClassVar[Category] category`, and `async def fetch(client, window)
  -> list[NormalizedItem]`. Pinned NOT `@runtime_checkable` —
  registration uses class-attribute inspection at import time, so
  runtime structural checks would only invite false-positive matches.

`_retry.py` updated to `from investo.sources.protocol import
SourceFetchError` with `__all__` re-export, preserving the prior
import path so `tests/unit/sources/test_retry.py` continues to work
unchanged.

## FD-vs-Implementation Divergence (Ratified)
The plan §5.1 and the implementation use `async def fetch(self,
client, window: FetchWindow)`; the FD §E1 / R3 specify
`async def fetch(client, target_date: date)`. Defensible refinement —
the aggregator (Step 7) builds the `FetchWindow` once and dispatches
the prebuilt window to every adapter, avoiding N adapter-side
re-derivations. Window carries `target_date` as a field, so no
information is lost. Recorded canonically in `aidlc-docs/audit.md`.

## Files Changed
- Created:
  - `src/investo/sources/protocol.py` — `SourceFetchError`, `SourceAdapter` Protocol
  - `tests/unit/sources/test_protocol.py` — 13 anchor tests
  - `docs/sessions/2026-04-27-u1-sources-code-generation-step5.md` — this file
- Modified:
  - `src/investo/sources/_retry.py` — dropped local `SourceFetchError` class; imports + re-exports from `protocol.py`
  - `aidlc-docs/aidlc-state.md` — Step 5/10 ✅
  - `aidlc-docs/audit.md` — Step 5 audit log entry (with FD-vs-impl divergence ratification)
  - `aidlc-docs/construction/plans/u1-sources-code-generation-plan.md` — Step 5 marked complete

## Key Decisions
| Decision | Rationale |
|----------|-----------|
| `SourceAdapter` is NOT `@runtime_checkable` | Registry inspects class attributes at import time; isinstance check would only enable accidental duck-typed matches elsewhere. Fail-loud over fail-silently. |
| Pin Protocol introspection via `_is_protocol` and `_is_runtime_protocol` | These are CPython's stable-since-3.8 markers — sharper than walking `__mro__` or relying on `pytest.raises(TypeError)` from a bad isinstance call. |
| Widen `cause: Exception \| None` → `cause: BaseException \| None` | Matches FD §E4 verbatim. Existing callers in `_retry.py` only pass `Exception` subtypes, so the widening is a no-op for them but allows future callers to wrap `KeyboardInterrupt` / `SystemExit` if they ever needed to. |
| Use `ClassVar[str]` / `ClassVar[Category]` on Protocol attributes | Matches FD R2 / §E1 ("class attribute, not instance"). Concrete adapters can declare attributes with or without `ClassVar` and still satisfy the Protocol — mypy strict is satisfied either way. |
| Define `_StubAdapter` at module level (test file) | Underscore prefix tells pytest not to collect it; serves as both mypy-side Protocol-conformance proof and runtime fixture for the async-fetch test. |
| `_retry.py` re-exports `SourceFetchError` via `from … import` + `__all__` | Preserves `tests/unit/sources/test_retry.py` imports unchanged. The `is`-identity test (`test_source_fetch_error_re_exported_from_retry`) pins this. |

## Code Review Results
Sub-agent (general-purpose) per dev-investo §5.1.

| Category | Status |
|----------|--------|
| Correctness | ✅ — `SourceFetchError` matches FD §E4; Protocol matches §E1 (with ratified `window` divergence) |
| Safety | ✅ — no circular imports; `_retry → protocol → _window` is the right layering |
| Reliability | ✅ — re-export identity preserved; existing tests still pass |
| Maintainability | ✅ (after M1 + L1 fixes) — sharper Protocol introspection pins |
| Test Coverage | ✅ — 13 anchor tests; mypy-side Protocol-conformance proof |

**Issues addressed in-step**:
- M1 — replaced weak `pytest.raises(TypeError)` shape-pin with `_is_runtime_protocol` introspection
- L1 — replaced MRO walk with `_is_protocol` introspection
- L3 — skipped (cosmetic; stub-fetch test uses an unused but harmless `httpx.AsyncClient`)
- L4 — confirmed `asyncio_mode = "auto"` is already configured in `pyproject.toml`

**Issues registered**: none. No new TECH-DEBT.

## Potential Risks
- The `_is_protocol` / `_is_runtime_protocol` introspection markers are CPython internals. They have been stable since Python 3.8 and are widely used (mypy itself relies on them), so the risk of a future Python release breaking the pins is low. If the project ever upgrades to a Python version that renames them, the two assertions are easy to update.
- Concrete adapters that declare `name = "fomc-rss"` without a `ClassVar` annotation will still satisfy the Protocol per mypy structural matching. Developers reading the FOMC adapter (Step 8) will see two stylistic options; the Step 8 implementation should pick one and the rest should follow.

## TECH-DEBT Items
None added.

## Next Step
Step 6: `src/investo/sources/_registry.py` — `@register` class
decorator that registers a fresh adapter instance keyed by
`cls.name`, raises `RuntimeError` on duplicate; `list_sources() ->
list[SourceAdapter]` accessor; `_clear_for_test()` private utility for
test isolation.

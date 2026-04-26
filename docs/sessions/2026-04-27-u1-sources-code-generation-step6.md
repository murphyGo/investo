# Session Log: 2026-04-27 — u1 sources — Code Generation Step 6 (`_registry.py`)

## Overview
- **Date**: 2026-04-27
- **Unit**: u1 sources
- **Stage**: Code Generation
- **Step**: 6 of 10 — `@register` decorator + `list_sources()` + `_clear_for_test()`

## Work Summary
Implemented the module-level adapter registry per FD §E2 and L3.
`register` is a TypeVar-bound generic decorator that preserves the
concrete adapter type; the duplicate-name check fires *before* the
dict mutation so a rejected registration never partially mutates
state. `list_sources()` returns a fresh list copy each call —
mutation by callers does not affect the registry. `_clear_for_test`
is a fixture-only utility for resetting the registry between tests.

The registry is populated at import time of `investo.sources/__init__.py`
(Step 9 wires the adapter imports); for now Step 6 just provides the
mechanism, proven independently of any concrete adapter.

Code review: **APPROVE** with 3 Low-severity polish notes. All
skipped — one needs Python 3.12+ syntax (PEP 695), the others are
pure cosmetics. No TECH-DEBT registered.

## Files Changed
- Created:
  - `src/investo/sources/_registry.py` — `_ADAPTERS`, `register`, `list_sources`, `_clear_for_test`
  - `tests/unit/sources/test_registry.py` — 12 tests with autouse snapshot/restore fixture
  - `docs/sessions/2026-04-27-u1-sources-code-generation-step6.md` — this file
- Modified:
  - `aidlc-docs/aidlc-state.md` — Step 6/10 ✅
  - `aidlc-docs/audit.md` — Step 6 audit log entry
  - `aidlc-docs/construction/plans/u1-sources-code-generation-plan.md` — Step 6 marked complete

## Key Decisions
| Decision | Rationale |
|----------|-----------|
| `register(cls: type[_AdapterT]) -> type[_AdapterT]` (TypeVar bound to `SourceAdapter`) | Preserves the precise concrete adapter class type through the decorator. A decorated `class FomcRssAdapter` stays typed as `type[FomcRssAdapter]` rather than widening to `type[SourceAdapter]`. |
| Duplicate-check fires before dict mutation | A failed registration cannot partially mutate the registry — `test_duplicate_does_not_replace_existing_entry` pins this. |
| `_clear_for_test` lives in `_registry.py` (not a separate `testing.py`) | One helper isn't worth a new module. The single-underscore prefix signals "private but accessible from tests"; the docstring caveats that it's for fixtures only. |
| Autouse `_isolate_registry` fixture with snapshot/clear/yield/restore | Today the registry is empty at import time (Step 9 will wire adapters), but the snapshot/restore keeps the test correct *after* adapters land. try/finally ensures restore even if a test raises. |
| Tests use `class Stub(_StubBase)` per case for fresh registry entries | Each subclass is a distinct type with its own `name` ClassVar shadow; using a base class with a placeholder `<override-me>` slug avoids re-declaring `category` and `fetch` in every test. |
| `dict.values()` for `list_sources` (Python 3.7+ stable insertion order) | FD §E2 is silent on order, but stable order makes test assertions concrete (`["a", "b", "c"]`) and matches operator expectations (adapters appear in import order in logs). |

## Code Review Results
Sub-agent (general-purpose) per dev-investo §5.1.

| Category | Status |
|----------|--------|
| Correctness | ✅ — duplicate check before mutation; insertion order preserved |
| Safety | ✅ — module-level dict is import-lock-protected; no concurrency hazard at v1 |
| Reliability | ✅ — `try/finally` in fixture guarantees restore; failed `cls()` raises loudly at import time |
| Maintainability | ✅ — TypeVar pattern preserves concrete type; clean docstrings |
| Test Coverage | ✅ — 12 anchor tests covering happy path, duplicates, mutation safety, fixture utility |

**Issues skipped** (all Low, optional polish):
- L1 — PEP 695 generic syntax `def register[T: SourceAdapter](...)` requires Python 3.12+; project pins 3.11+ so the TypeVar form is correct
- L2 — cosmetic nit on test arg (`"not an adapter"` vs `object()`); current form reads fine
- L3 — docstring could explicitly link FD §E2 post-import-immutability invariant; skipped as cosmetic

**Issues registered**: none. No new TECH-DEBT.

## Potential Risks
- The current registry is single-threaded (populated under Python's import lock). If a future feature ever calls `register` from a worker thread (e.g., dynamic plugin loading at runtime), `dict.__contains__` + `dict.__setitem__` is not atomic and a race could let two adapters with the same name register. FD §E2 explicitly forbids post-import mutation, so this is a non-issue today; flagging only because the reviewer raised it.
- Adapter classes with `__init__(self, foo)` will fail at import time with `TypeError`. Per FD R3 this is the intended failure mode (adapters are stateless), but the error trace points at `_registry.py:47` rather than the offending adapter line. If a future adapter needs constructor args, the `cls()` call will need to be revised — but doing so would also violate R3.

## TECH-DEBT Items
None added.

## Next Step
Step 7: `src/investo/sources/aggregator.py` — `async def fetch_all(target_date)` opening a shared `httpx.AsyncClient`, building `FetchWindow.from_kst_date(target_date)`, dispatching all `list_sources()` adapters concurrently via `asyncio.gather(..., return_exceptions=True)`, catching `SourceFetchError` per-adapter (logged at WARNING + `[]`), re-raising programmer errors. Pins NFR ACs 1.1, 3.1–3.5.

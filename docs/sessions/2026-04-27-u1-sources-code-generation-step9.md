# Session Log: 2026-04-27 — u1 sources — Code Generation Step 9 (`__init__.py` + plugin contract)

## Overview
- **Date**: 2026-04-27
- **Unit**: u1 sources
- **Stage**: Code Generation
- **Step**: 9 of 10 — public surface lock + drift guard

## Work Summary
Locked the public surface of `investo.sources`: populated `__init__.py`
with adapter discovery (`from . import fomc_rss` triggers
`@register` at first package import per FD §E2 / R2), the 5-name
re-export set (`SourceAdapter`, `SourceFetchError`, `list_sources`,
`fetch_all`, `FetchWindow`), and an `__all__` declaration that locks
the surface for `from investo.sources import *` consumers. Module
docstring includes the NFR AC-5.4 4-step procedure for adding a new
adapter, so contributors don't need to track down the procedure
elsewhere.

The plugin-contract test file (`test_plugin_contract.py`) overrides
the conftest autouse `_isolate_registry` fixture with a variant that
re-registers `FomcRssAdapter` after the clear — this lets the
drift-guard tests see the production registry state without
touching any global mutable state outside the snapshot/restore
boundary.

7 new tests pin: AC-5.2 drift guard (count + names sets); a +1 stub
test that proves the guard is meaningful (not tautological); AC-5.3
duplicate-name with the production slug `"fomc-rss"` (strongest
form of the rule); `__all__` content lock; internal-helper non-leak
list; re-export identity via `is`-checks against canonical defining
modules.

Code review: **APPROVE**, 0 Critical/High/Medium, 4 Lows. Applied L3
(bump-comment near `EXPECTED_ADAPTER_COUNT`); skipped L1/L2/L4 as
cosmetic / overlap with NFR phrasing. No new TECH-DEBT.

## Files Changed
- Created:
  - `tests/unit/sources/test_plugin_contract.py` — 7 tests
  - `docs/sessions/2026-04-27-u1-sources-code-generation-step9.md` — this file
- Modified:
  - `src/investo/sources/__init__.py` — was a docstring stub; now contains adapter import + re-exports + `__all__`
  - `aidlc-docs/aidlc-state.md` — Step 9/10 ✅
  - `aidlc-docs/audit.md` — Step 9 audit log entry
  - `aidlc-docs/construction/plans/u1-sources-code-generation-plan.md` — Step 9 marked complete

## Key Decisions
| Decision | Rationale |
|----------|-----------|
| Adapter discovery via `from . import fomc_rss  # noqa: F401` | Standard idiom for plugin-package side-effect imports. The relative form matches the FD §E2 example wording verbatim. `noqa: F401` is the canonical ruff suppression for unused-but-needed imports. |
| Override the conftest autouse fixture in the test file | Other test files exercise stubs in a clean registry; this file alone exercises the production state. Overriding the autouse fixture by name (with snapshot → clear → re-register production → yield → restore) is pytest's documented pattern and keeps state contained to the test boundary. |
| Use `name = "fomc-rss"` (production slug) in the duplicate-name test | Pins R2's "fail loudly, never silently overwrite" against the strongest possible adversary — a future refactor that special-cases distinct classes for the same name would still fail. |
| Document the NFR AC-5.4 4-step procedure in the docstring | Contributors adding a new adapter shouldn't have to chase the procedure across multiple files. The plan's Step 10 will also add it to CONTRIBUTING; this is the in-source canonical location. |
| Test re-export identity via `is` (not `==`) | Strongest possible binding check — catches accidental shadowing or re-creation that string-equality wouldn't. |
| Apply L3 bump-comment near `EXPECTED_ADAPTER_COUNT` | Future contributors adding/removing an adapter will be guided directly to the correct constant rather than hunting through the plan or docstring. Cheap clarity. |

## Code Review Results
Sub-agent (general-purpose) per dev-investo §5.1.

| Category | Status |
|----------|--------|
| Correctness | ✅ — `__init__.py` matches R2 + AC-5.4; `__all__` exactly the 5-name surface |
| Safety | ✅ — module boundary respected; no cross-unit imports |
| Reliability | ✅ — fixture override is symmetric (snapshot → clear → re-register → yield → clear → restore) |
| Maintainability | ✅ — 4-step procedure inline in docstring; bump-comment near `EXPECTED_ADAPTER_COUNT` |
| Test Coverage | ✅ — 7 tests pin every assertion in the plan §9.2 |

**Issues addressed in-step**:
- L3 — added bump-when-adding-or-removing comment above `EXPECTED_ADAPTER_COUNT`

**Issues skipped** (cosmetic / spec-aligned):
- L1 — docstring "4-line procedure" wording (mirrors NFR AC-5.4's phrasing)
- L2 — merge count + names tests (kept split for diagnostic clarity on failure)
- L4 — execute actual `from investo.sources import *` (testing `__all__` directly is the canonical pattern)

## Potential Risks
- The `_isolate_registry` fixture override depends on pytest's name-shadowing semantics. If a future pytest version changes how same-named autouse fixtures interact across conftest and test files, the production-mirror fixture could silently fail to override the conftest one — and the drift-guard test would run against a cleared registry, falsely passing on `len(...) == 0` if `EXPECTED_ADAPTER_COUNT` were ever bumped to 0. Mitigation: the +1 stub test would catch this drift in practice (since `len == 0 + 1 != EXPECTED + 1` for any nonzero EXPECTED). Probability is low but worth flagging.
- `EXPECTED_ADAPTER_COUNT` and the names set must be updated together when adding adapters. The bump-comment makes this clearer, but the system still relies on contributor discipline. The drift-guard's "fails loudly" property catches the omission — but only after the contributor has run the test suite.

## TECH-DEBT Items
None added.

## Next Step
Step 10 (final): CI cost guard + CONTRIBUTING + closeout. Specifically:
- `scripts/check_no_paid_apis.py` — grep blocklist runner
- `tests/unit/sources/test_no_paid_apis.py` — invoke the script as subprocess
- CONTRIBUTING section — 4-line procedure + free-tier declaration + fixture-recording how-to
- `aidlc-docs/construction/u1-sources/code/summary.md` — closeout summary with NFR AC-to-test traceability
- Stories US-001 + US-008 close on Step 10 completion.

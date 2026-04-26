# Code Generation Summary: `models` (foundation)

**Date**: 2026-04-27
**Stage**: Construction · Code Generation
**Status**: ✅ Complete (all 8 plan steps)
**Quality gate**: ruff ✅ · ruff format ✅ · mypy --strict ✅ · pytest 101/101 ✅

---

## What was produced

The foundation library — every other unit imports from here. Final
public surface is locked at `from investo.models import ...` and pinned
by a drift-guard test (`tests/unit/models/test_init.py`).

### Files

| Path | Lines | Role |
|------|------:|------|
| `src/investo/models/__init__.py` | 36 | Public API re-exports + `__all__` |
| `src/investo/models/items.py` | 79 | `Category`, `NormalizedItem` |
| `src/investo/models/briefing.py` | 98 | `Briefing`, `BriefingNotification`, `TELEGRAM_MESSAGE_LIMIT` |
| `src/investo/models/results.py` | 173 | `PipelineStatus`, `SendResult`, `FailureContext`, `PipelineResult`, `FailureStage` |
| `src/investo/models/_validators.py` | 53 | Internal: `reject_blank_strict`, `reject_blank_preserve`, `ensure_tz_aware` |
| `tests/unit/models/test_items.py` | 194 | 26 tests |
| `tests/unit/models/test_briefing.py` | 173 | 31 tests |
| `tests/unit/models/test_results.py` | 258 | 34 tests |
| `tests/unit/models/test_init.py` | 57 | 4 tests (public-API drift guard) |
| `tests/unit/models/test_roundtrip.py` | 252 | 6 PBT × 100 examples |

**Total**: 5 source files (439 LOC), 5 test files (934 LOC), 101 tests.

### Public API (locked)

```python
from investo.models import (
    Category,                    # Literal["news"|"price"|"macro"|"calendar"|"earnings"]
    NormalizedItem,              # Source Adapter output
    Briefing,                    # Briefing Generator output (7 sections)
    BriefingNotification,        # Public Telegram channel payload
    TELEGRAM_MESSAGE_LIMIT,      # int = 4096 (UTF-16 code units)
    PipelineStatus,              # StrEnum {SUCCESS, PARTIAL, FAILED}
    SendResult,                  # Notifier dispatch outcome
    FailureContext,              # Operator alert payload
    FailureStage,                # Literal["collect"|"generate"|"publish"|"notify_briefing"]
    PipelineResult,              # Orchestrator final outcome
)
```

`_validators` and its helper functions (`reject_blank_strict`,
`reject_blank_preserve`, `ensure_tz_aware`) stay private. The drift
guard pins the surface so future model additions force an explicit
update of `__all__`.

---

## Key design decisions (chronological)

| # | Decision | Reason |
|---|----------|--------|
| 1 | `pydantic v2` + `frozen=True` + `extra="forbid"` on every model | Immutable provenance + reject silent ingestion of unknown fields |
| 2 | tz-aware `datetime` enforcement on `published_at` and `occurred_at` | KST/UTC drift in cron-driven pipelines is a real bug class |
| 3 | `StrictStr | StrictInt | StrictFloat` for `raw_metadata` values | Default lax mode coerces `"42" → 42` and accepts `bool` (int subclass) — both corrupt source provenance |
| 4 | `_validators.py` — two flavors of blank rejection | `_strict` strips and reject (identifiers); `_preserve` rejects whitespace-only without modifying (markdown sections) |
| 5 | `BriefingNotification.summary_text` validates length in **UTF-16 code units** | Telegram counts UTF-16; emoji are surrogate pairs (2 units per code point), so a Python `max_length=4096` would let oversized payloads through |
| 6 | Disclaimer auto-append + Publisher pre-publish verify (NFR-004) | Two-layer compliance: code controls insertion, runtime guards leakage |
| 7 | `SendResult` cross-field invariant via `model_validator` | Notifier contract: `ok=True ⇒ error=None`; `ok=False ⇒ message_id=None`. Locks ambiguity at the data layer |
| 8 | `PipelineResult.duration_seconds` bounded `[0, 86400]` | Catches wall-clock arithmetic bugs; NFR-001 caps real runs at 10 minutes |
| 9 | `FailureContext.traceback_excerpt` capped at 2000 chars | Operator chat has Telegram's 4096 UTF-16 limit; 2000 leaves headroom for `error_type`/`error_message`/formatting |
| 10 | `PipelineStatus` as `StrEnum` (Python 3.11+) | More ergonomic than `class PipelineStatus(str, Enum)`; spec said v3.11+ is the target |
| 11 | `__all__` pinned via drift-guard test | mypy doesn't catch a forgotten re-export; the test does |

---

## Code review history

Each step's code (where non-trivial) was reviewed by a separate
sub-agent (`general-purpose`) per `dev-investo` §5.1. All findings
were either fixed in-step or registered as TECH-DEBT.

| Step | Severity counts | Action |
|------|-----------------|--------|
| 2 (`items.py`) | 0 high, 2 medium, 4 low | M1/M2 fixed in-step (strict union, whitespace) |
| 3 (`briefing.py`) | 1 high, 2 medium, 3 low | H1/L1/L2 fixed; M1/M2 → DEBT-001/002 |
| 4 (`results.py`) | 2 high, 3 medium, 3 low | All 8 fixed in-step |
| 5 (`__init__.py`) | self-check (re-export module) | n/a |
| 6 (unit tests) | self-check | n/a |
| 7 (PBT) | self-check | n/a |

### TECH-DEBT items deferred from this stage

| ID | Priority | Description | Owner stage |
|----|----------|-------------|-------------|
| DEBT-001 | Medium | `Briefing` model invariant `disclaimer ∈ rendered_markdown` (defense-in-depth alongside Publisher's runtime check) | Future hardening |
| DEBT-002 | Medium | Date sanity bounds on `target_date` / `published_at` (`2024-01-01 ≤ d ≤ today+1`) — apply at orchestrator boundary, not model | u5 orchestrator |

---

## Verification matrix (by NFR)

| NFR | How verified for this unit |
|-----|----------------------------|
| NFR-002 (Cost / no Anthropic SDK) | `models/` imports pydantic only; no `anthropic`. Will be re-verified in `briefing.py` (u2) by lint check |
| NFR-003 (Reliability) | Validators reject ambiguous inputs at the boundary. `SendResult` non-raising contract pinned by tests |
| NFR-004 (Disclaimer) | `Briefing.disclaimer` is required + non-empty. Publisher (u3) will perform substring verify pre-publish |
| NFR-006 (PBT partial) | 6 round-trip tests × 100 examples on every public model. Strategies cover ASCII, BMP, surrogate-pair emoji, zoneinfo timezones, bounded floats, optional fields |
| NFR-007 (Security baseline) | No secrets in `models`; `extra="forbid"` blocks silent ingestion of attacker-supplied fields from external API responses |

---

## Pre-flight for u1 sources

When the next unit (`u1 sources`) starts implementing Source Adapters,
it will consume from `investo.models`:

| u1 needs | From `models` |
|----------|---------------|
| Output type for `SourceAdapter.fetch` | `list[NormalizedItem]` |
| Allowed category values | `Category` |
| Provenance-bag value typing | Implicit via `NormalizedItem.raw_metadata` (Strict union) |

`u1` should NOT import from `investo.models._validators` directly. If
a similar blank-rejection helper is needed, prefer adding to
`_validators.py` and re-using rather than duplicating.

---

## Story status

`models` is the foundation — no stories close out at this stage. Each
of US-001~US-009 is "in progress" on the consumer side and will be
ticked complete by the unit that owns the story (US-001 closes when
`u1 sources` finishes Code Generation, etc.).

| Story | Foundation provides | Closes when |
|-------|---------------------|-------------|
| US-001 | `NormalizedItem` | u1 sources Code Gen complete |
| US-002 | `Briefing` | u2 briefing Code Gen complete |
| US-003 | (no model) | u3 publisher Code Gen complete |
| US-004 | `BriefingNotification` | u4 notifier Code Gen complete |
| US-005 | `PipelineResult`, `PipelineStatus` | u5 orchestrator Code Gen complete |
| US-006 | (no model) | u3 publisher Code Gen complete |
| US-007 | `FailureContext` | u4 notifier Code Gen complete |
| US-008 | `Category`, `NormalizedItem` | u1 sources Code Gen complete |
| US-009 | (constraint, not type) | u2 briefing Code Gen (no Anthropic SDK) |

---

## Next target

Per delivery order from `unit-of-work-dependency.md`:

1. **`u1 sources`** — Functional Design (per execution-plan.md selective per-unit policy)
   - Plugin registry contract
   - Async `SourceAdapter` Protocol
   - Per-source timeout/retry policy
   - At least 1 reference adapter PoC plan

After `u1` Functional Design + NFR Requirements + Code Generation,
move to `u2 briefing`, then the rest of the order.

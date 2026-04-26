# Code Generation Plan: `models` (foundation)

**Date**: 2026-04-27
**Unit**: `models` — foundation library (not a unit per se; prerequisite for all units)
**Stage**: Code Generation
**Source artifacts**:
- `aidlc-docs/inception/application-design/components.md` — `models` module description
- `aidlc-docs/inception/application-design/component-methods.md` — pydantic v2 type definitions (lines under "## models — Common Types")
- `aidlc-docs/inception/application-design/unit-of-work.md` — Definition of Done for models foundation
- `docs/requirements.md` — NFR-006 (PBT for serialization round-trip)

---

## Unit Context

### Purpose
Pydantic v2 type library shared across all units. Acts as the single import surface for all data shapes that cross unit boundaries.

### Stories Implemented
None directly. Foundation supports all stories indirectly:
- US-001 / US-008: NormalizedItem
- US-002 / US-009: Briefing
- US-004: BriefingNotification
- US-007: FailureContext
- US-005: PipelineResult, PipelineStatus
- US-004 / US-007: SendResult

### Dependencies
- **External**: `pydantic>=2.0`
- **Internal**: none (leaf node in DAG)

### Interfaces / Contracts
- `Category` — `Literal["news", "price", "macro", "calendar", "earnings"]`
- `NormalizedItem` — Source Adapter output
- `Briefing` — Briefing Generator output (7 sections + rendered markdown)
- `BriefingNotification` — Public channel payload
- `FailureContext` — Operator alert payload
- `SendResult` — Notifier dispatch result (non-raising)
- `PipelineStatus` — enum (`SUCCESS`/`PARTIAL`/`FAILED`)
- `PipelineResult` — orchestrator final output

### Module Location (per Q3 src layout)
- Code: `src/investo/models/`
- Tests: `tests/unit/models/`

### Acceptance Criteria
- All types defined per `component-methods.md` signatures
- Public API explicit via `models/__init__.py` `__all__`
- All types hold under `mypy --strict`
- Property-based round-trip test passes for every model (NFR-006, PBT extension partial)
- `ruff check .` and `ruff format --check .` clean

---

## Steps

### Step 1: Project bootstrap (one-time, occurs alongside models) ✅

- [x] **1.1** `pyproject.toml` (PEP 621, hatchling build, src layout, ruff+mypy+pytest config, `aidlc-workflows`/`aidlc-docs`/`archive` excluded from ruff scope)
- [x] **1.2** Package skeleton: `src/investo/__init__.py` (`__version__ = "0.1.0"`), `src/investo/__main__.py` (placeholder raising NotImplementedError)
- [x] **1.3** Test scaffolding: `tests/__init__.py`, `tests/unit/__init__.py`, `tests/unit/models/__init__.py` (all empty)
- [x] **1.4** Install verified: `python3 -m venv .venv && source .venv/bin/activate && pip install -e ".[dev]"` succeeded (Python 3.14.3, pydantic 2.13.3, pytest 9.0.3, ruff 0.15.12, mypy 1.20.2, hypothesis 6.152.2)

**Quality gate**: `ruff check .` ✅ · `ruff format --check .` ✅ · `mypy --strict src/` ✅ · `pytest` ✅ (0 tests yet) · `python -m investo` → expected `NotImplementedError` ✅

### Step 2: Implement `models/items.py` ✅

- [x] **2.1** `Category` Literal type
- [x] **2.2** `NormalizedItem` pydantic v2 BaseModel with all 7 fields, `frozen=True`, `extra="forbid"`
- [x] **2.3** Validators: tz-aware `published_at`, strip+reject blank for `source_name`/`title`, normalize empty/whitespace `summary` → `None` (M2)
- [x] **2.4** Strict union for `raw_metadata` values (`StrictStr | StrictInt | StrictFloat`) to block silent coercion incl. `bool` (M1)
- [x] **2.5** `models/__init__.py` placeholder (full re-exports land in Step 5)

**Code review** (sub-agent): no Critical/High; M1 (raw_metadata strict union) + M2 (whitespace normalization) fixed in same step. Low cosmetic suggestions deferred.
**Quality gate**: ruff ✅ · mypy strict ✅ · runtime smoke + validator tests ✅

### Step 3: Implement `models/briefing.py` ✅

- [x] **3.1** `Briefing` pydantic v2 BaseModel: 7 sections + `rendered_markdown` + `disclaimer` + `target_date`, `frozen=True`, `extra="forbid"`. Markdown-preserving blank-rejection validator.
- [x] **3.2** `BriefingNotification` pydantic v2 BaseModel: `target_date`, `summary_text`, `site_url`, `frozen=True`, `extra="forbid"`.
- [x] **3.3** **H1 fix**: `summary_text` length validated in **UTF-16 code units** (Telegram's actual measurement) instead of Python char count, so emoji-heavy summaries can't sneak past the 4096-unit cap.
- [x] **3.4** **L1/L2 refactor**: Extracted `reject_blank_strict` / `reject_blank_preserve` to `models/_validators.py`; `items.py` and `briefing.py` both use it.

**Code review** (sub-agent): no Critical; H1 (High UTF-16 limit) + L1/L2 fixed in-step. M1 (disclaimer-in-markdown invariant) and M2 (date sanity bounds) registered as DEBT-001 and DEBT-002 in `docs/TECH-DEBT.md`.
**Quality gate**: ruff ✅ · mypy strict ✅ · UTF-16 boundary tests (4096 ASCII / 4097 ASCII / 2048 emoji / 2049 emoji / mixed / Korean BMP) ✅ · Step 2 regression ✅

### Step 4: Implement `models/results.py` ✅

- [x] **4.1** `PipelineStatus(StrEnum)` with `SUCCESS`/`PARTIAL`/`FAILED` + member docstrings (L2 cosmetic also addressed)
- [x] **4.2** `SendResult` BaseModel (`frozen`, `extra="forbid"`) + cross-field `model_validator` enforcing `ok=True ⇒ error=None` and `ok=False ⇒ message_id=None` (M1)
- [x] **4.3** `FailureContext` BaseModel with `FailureStage` Literal, `traceback_excerpt` capped at 2000 chars (L3), `occurred_at` tz-aware via shared helper (L1)
- [x] **4.4** `PipelineResult` BaseModel **frozen** (H1), `stages` dict free-form (H2 — documented in docstring), `duration_seconds` bounded `[0, 24h]` (M2), `briefing_url` HttpUrl serialization caveat documented (M3)
- [x] **4.5** Promoted `ensure_tz_aware` to `models/_validators.py`; refactored `items.py` to use it (L1)

**Code review** (sub-agent): 2 High + 3 Medium + 3 Low — all 8 fixed in-step or via shared helper extraction. Quality gate clean. Step 2 / Step 3 regression OK.

### Step 5: Models package `__init__.py` (public API) ✅

- [x] **5.1** Updated `src/investo/models/__init__.py`:
  - Re-exports `Category`, `NormalizedItem`, `Briefing`, `BriefingNotification`, `TELEGRAM_MESSAGE_LIMIT`, `PipelineStatus`, `SendResult`, `FailureContext`, `PipelineResult`, `FailureStage`
  - `__all__` lists all 10 names alphabetized
  - Internal `_validators` helpers stay private (verified via star-import isolation test)

**Verification**: `from investo.models import *` brings exactly the 10 public names — `_validators`, `reject_blank_strict`, `ensure_tz_aware`, etc. are confirmed absent. All 6 model classes construct successfully via top-level import. Quality gate clean.

**Self-check** (no full sub-agent review for this trivial re-export module): public API matches `__all__`; star import isolation OK; direct imports OK; type-checker (`mypy --strict`) green.

### Step 6: Unit tests (basic construction + validation)

- [ ] **6.1** `tests/unit/models/test_items.py`:
  - Valid `NormalizedItem` construction
  - Empty title raises ValidationError
  - Naive `published_at` raises ValidationError
  - Invalid `category` literal raises ValidationError
  - Extra field raises ValidationError (extra="forbid")
- [ ] **6.2** `tests/unit/models/test_briefing.py`:
  - Valid `Briefing` construction (all 7 sections present)
  - Valid `BriefingNotification` construction
  - `summary_text > 4096` raises ValidationError
  - Invalid `site_url` raises ValidationError
- [ ] **6.3** `tests/unit/models/test_results.py`:
  - Valid `SendResult` (success, failure variants)
  - Valid `FailureContext` for each stage literal
  - Valid `PipelineResult` with each `PipelineStatus`
  - Invalid stage literal raises ValidationError

### Step 7: Property-based round-trip tests (NFR-006 PBT partial)

- [ ] **7.1** `tests/unit/models/test_roundtrip.py` using `hypothesis`:
  - Strategy for `NormalizedItem` → `model_dump_json()` → `model_validate_json()` → equality
  - Same for `Briefing`, `BriefingNotification`, `SendResult`, `FailureContext`, `PipelineResult`
  - Use `hypothesis` `from_type()` if pydantic strategy is sufficient; otherwise hand-write `@composite` strategies for complex fields (datetimes with tz, URLs)
  - `@settings(max_examples=100)` per model

### Step 8: Quality gate + summary

- [ ] **8.1** Run `ruff check .` — fix any issues
- [ ] **8.2** Run `ruff format .` — auto-format
- [ ] **8.3** Run `mypy --strict src/` — fix any type issues
- [ ] **8.4** Run `pytest tests/unit/models/` — all tests pass
- [ ] **8.5** Write `aidlc-docs/construction/models/code/summary.md`:
  - Files created (paths)
  - Public API surface (re-exports)
  - Test coverage summary
  - Any deviations from `component-methods.md` and rationale
  - Pre-flight for next unit (u1 sources): which models will be consumed where
- [ ] **8.6** Mark all unit stories as ⏳→ in-progress for consumer units (no story is fully [x] yet — models is foundation).

---

## Story Traceability

| Story | Foundation provides |
|-------|---------------------|
| US-001 | `NormalizedItem` |
| US-002 | `Briefing` |
| US-004 | `BriefingNotification` |
| US-005 | `PipelineResult`, `PipelineStatus` |
| US-007 | `FailureContext` |
| US-004, US-007 | `SendResult` |
| US-008 | `Category`, `NormalizedItem` |
| US-009 | (no direct type) |

---

## Out of Scope for This Stage

- HTTP client (`httpx`) — added in u1 scope
- Telegram payload helpers — added in u4 scope
- Workflow YAML / mkdocs config — u6 scope
- Logging / config infrastructure — TBD; for now, models do not depend on config
- ADR — no architectural decision needed beyond what Application Design captured

---

## Estimated Scope

- ~7 source files
- ~5 test files
- ~9 plan steps
- Solo dev: ~half-day (mostly mechanical, plus hypothesis strategy fine-tuning)

---

## Single Source of Truth

This plan is the **single source of truth** for `models` Code Generation. Any deviation must update this plan first. After all `[ ]` become `[x]`, present 2-option completion (Request Changes / Continue to Next Stage = u1 sources).

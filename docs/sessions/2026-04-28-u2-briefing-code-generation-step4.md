# Session Log: 2026-04-28 - u2 briefing - Code Generation Step 4

## Overview
- **Date**: 2026-04-28
- **Unit**: u2 briefing
- **Stage**: Code Generation
- **Step**: Step 4 — `errors.py` (BriefingGenerationError + SubprocessOutcome
  + AC-7.4 stderr byte cap)

## Work Summary

Implemented the error-types module — the **u2 error contract layer**.
Two public types: `BriefingGenerationError` (E4, an `Exception` subclass
that wraps LLM-traceable failures with stage / attempt_count /
last_stderr / cause attributes) and `SubprocessOutcome` (E5, a frozen
slotted dataclass holding stdout / stderr / returncode / elapsed_s for
the retry helper). Plus a `BriefingStage` Literal alias for the four
stage names.

The non-trivial bit is `_truncate_stderr`: it caps `last_stderr` at
**1024 UTF-8 bytes** (NFR AC-7.4), with multi-byte boundary safety via
`bytes[:cap].decode("utf-8", errors="ignore")`. A 10 KB stderr ends up
at ≤1024 bytes; a Korean text whose byte length lands the cap mid-codepoint
decodes cleanly without `UnicodeDecodeError`.

20 new tests across one file. All passing.

## Files Changed

### Created
- `src/investo/briefing/errors.py` (122 lines) — `BriefingStage` Literal +
  `SubprocessOutcome` (frozen+slots dataclass) + `_truncate_stderr` helper +
  `BriefingGenerationError` Exception subclass with keyword-only `__init__`
  + module docstring documenting the error contract (BGE for LLM-traceable
  failures, programmer errors propagate as-is).
- `tests/unit/briefing/test_errors.py` (244 lines) — 20 tests:
  BGE class shape (Exception not RuntimeError), 4-stage parametrize,
  message format, attribute round-trip, `from`-chain preservation, AC-7.4
  byte-cap with at-cap/just-over/far-over/multi-byte-boundary cases,
  None-stderr passthrough, SubprocessOutcome construction + frozen +
  slots+frozen-attr-injection, 4 E4 construction-example replications.

### Modified
- `aidlc-docs/construction/plans/u2-briefing-code-generation-plan.md` —
  Step 4 sub-tasks `[x]`
- `aidlc-docs/aidlc-state.md` — u2 CG progress 3/10 → 4/10
- `aidlc-docs/audit.md` — Step 4 entry prepended

## Key Decisions

| Decision | Rationale |
|----------|-----------|
| `BriefingGenerationError` extends `Exception`, not `RuntimeError` | Matches u1's `SourceFetchError` decision. Lets `pytest.raises(BriefingGenerationError)` not accidentally catch programmer-error `RuntimeError`s (per FD L5 / R4). |
| Keyword-only `__init__` (`*,`) | Forces explicit naming at every call site — operator alerts in u4 use these field names directly; positional args would obscure intent. |
| `last_stderr` byte cap, not codepoint cap | The semantic constraint (alert payload size) is bytes, not characters. UTF-8 multi-byte characters means a 1024-codepoint cap could be 4096 bytes. |
| `bytes[:cap].decode("utf-8", errors="ignore")` for multi-byte safety | Drops the partial trailing codepoint cleanly. UTF-8's self-synchronizing property means valid prefix bytes always decode to a valid string after dropping invalid trailing bytes. Tested at the `한 × 342 + "x"` boundary case. |
| `SubprocessOutcome` is `slots=True` + `frozen=True` | Slots prevent accidental attribute injection (typo in retry-loop code). Frozen prevents mutation in retry helpers that share the value. |
| BGE attributes are mutable post-construction | Python `Exception` subclasses can't easily be frozen (pickle / chained-exception machinery breaks). Matches u1's pragmatic choice; documented. |

## Code Review Results

Sub-agent review (general-purpose): **APPROVE**.

| Category | Status |
|----------|--------|
| Correctness | ✅ |
| Safety | ✅ |
| Reliability | ✅ |
| Maintainability | ✅ |
| Test Coverage | ✅ |

Findings: 0 Critical / 0 High / 0 Medium / 2 Lows.
- **L1** Stale `__dict__` / "logical immutability" comment in
  `BGE.__init__` — REMOVED (Python Exception subclasses can't be easily
  frozen anyway).
- **L2** `BriefingStage` Literal alias re-declaration — kept (correctly
  re-exported in `__all__`).

## Quality Gate

- `ruff check .` ✅
- `ruff format --check .` ✅ (48 files already formatted)
- `mypy --strict src/` ✅ (19 source files; +1 from Step 3's 18)
- `pytest -q` ✅ **314/314 passed in 3.36s**
  - +20 new tests (errors module fully covered)

## Potential Risks

- **R-Step4-1**: BGE attributes are mutable; downstream code could
  accidentally mutate `bge.last_stderr` after construction. Acceptable
  per u1 precedent; mitigated by mypy strict catching most accidental
  mutations and code review for the rest.

## TECH-DEBT Items

None added. None resolved.

## Next Step

**Step 5** — `prompts.py`: 4 `Final[str]` constants
(`STAGE1_SYSTEM`, `STAGE1_USER_TEMPLATE`, `STAGE2_SYSTEM`,
`STAGE2_USER_TEMPLATE`) + `str.format` substitution convention +
sentinel-grep test scaffolding for AC-5.1.

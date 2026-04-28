# Session Log: 2026-04-28 - u2 briefing - Code Generation Step 2

## Overview
- **Date**: 2026-04-28
- **Unit**: u2 briefing
- **Stage**: Code Generation
- **Step**: Step 2 — `disclaimer.py` (DISCLAIMER constant + idempotent
  `append_disclaimer` + PBT)

## Work Summary

Implemented the disclaimer module — the **NFR-004 compliance core** of u2.
Module exports two names: `DISCLAIMER` (the canonical Korean text constant)
and `append_disclaimer(markdown)` (a pure idempotent function). Idempotence
is anchored on the literal section header `## ⑦ 면책조항` per FD R5; body
text drift detection is u3 publisher's job (`verify_disclaimer`,
defense-in-depth per NFR-004).

13 new tests across 2 files. 3 PBTs run 100 examples each.

## Files Changed

### Created
- `src/investo/briefing/disclaimer.py` (62 lines) — `DISCLAIMER: Final[str]`
  + private `_ANCHOR` + `append_disclaimer(markdown)` + module docstring
  documenting the cross-unit boundary.
- `tests/unit/briefing/test_disclaimer.py` (101 lines) — 9 anchor tests
  covering DISCLAIMER shape, AC-4.2 (substring), AC-4.3 (last-section
  anchor), AC-4.5 (Final[str]), and idempotence example cases including
  the LLM-hallucination drift case.
- `tests/unit/briefing/test_disclaimer_pbt.py` (51 lines) — 3 PBTs:
  unconditional idempotence, conditional presence (anchor-less inputs),
  and an unconditional anchor-always canary.

### Modified
- `aidlc-docs/construction/plans/u2-briefing-code-generation-plan.md` —
  Step 2 sub-tasks `[x]` with detailed status notes
- `aidlc-docs/aidlc-state.md` — u2 CG progress 1/10 → 2/10
- `aidlc-docs/audit.md` — Step 2 entry prepended

## Key Decisions

| Decision | Rationale |
|----------|-----------|
| Anchor on `## ⑦ 면책조항` (header), not full DISCLAIMER body | FD R5 explicit choice. Body wording is allowed to drift via future ADR; section header is the canonical idempotence detect. Drifted-body case caught by u3's `verify_disclaimer` (defense-in-depth). |
| "Presence" PBT conditioned on `_ANCHOR not in input` | Unconditional `DISCLAIMER in append_disclaimer(x)` doesn't hold when input contains only the anchor (no body), per the chosen idempotence semantics. The conditional form pins the meaningful invariant: for anchor-less input, the full DISCLAIMER appears. The unconditional anchor-always invariant is pinned by a third PBT as a regression canary. |
| Two-newline separator in append path | Guarantees the disclaimer header is rendered as a top-level markdown section even when input ends without trailing newline. |
| `DISCLAIMER` and `_ANCHOR` are separate constants | Sub-agent suggested deriving `_ANCHOR = DISCLAIMER.split("\n", 1)[0]` for single-source-of-truth. Skipped per FD R5 explicit decoupling rationale (anchor is intentionally fixed even if body wording changes). |

## Code Review Results

Sub-agent review (general-purpose): **APPROVE**.

| Category | Status |
|----------|--------|
| Correctness | ✅ |
| Safety | ✅ (pure function, no I/O, no globals) |
| Reliability | ✅ (no error paths) |
| Maintainability | ✅ |
| Test Coverage | ✅ |

Findings: 0 Critical / 0 High / 0 Medium / 4 Lows + 1 verification.
- **L1** DEBT-001 docstring reference: verified registered in
  `docs/TECH-DEBT.md` ✅ (no action needed)
- **L2** derive `_ANCHOR` from `DISCLAIMER`: skipped (R5 explicit decouple)
- **L3** test-side `ANCHOR` literal duplication: skipped (black-box virtue)
- **L4** regex intent comment in `test_disclaimer.py`: applied

## Quality Gate

- `ruff check .` ✅
- `ruff format --check .` ✅ (44 files already formatted)
- `mypy --strict src/` ✅ (17 source files; +1 from Step 1's 16)
- `pytest -q` ✅ **265/265 passed in 3.03s**
  - +13 new tests: 9 anchor + 3 PBT + 1 type check
  - 3 PBTs each ran 100 examples

## Potential Risks

- **R-Step2-1**: If the FD R5 wording is changed in a future ADR, the
  Korean string in `disclaimer.py` AND any test fixtures referencing
  the exact body must be updated together. The anchor-on-header
  semantics protect u2 itself but not u3, where `verify_disclaimer`
  byte-checks the full constant. Mitigation: AC-D.4 process — wording
  changes require an audit-log entry, which forces both sites to be
  reviewed.

## TECH-DEBT Items

None added. None resolved.

## Next Step

**Step 3** — `leak_guard.py`: R6 PII/secret regex blocklist (GitHub PAT,
AWS access key, JWT, generic long base64 with URL-context exclusion,
email, Korean phone) + `scan(markdown) -> LeakGuardHit | None`
+ example-based hit/miss tests for AC-6.4, AC-7.3.

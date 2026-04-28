# Session Log: 2026-04-28 - u2 briefing - Code Generation Step 3

## Overview
- **Date**: 2026-04-28
- **Unit**: u2 briefing
- **Stage**: Code Generation
- **Step**: Step 3 — `leak_guard.py` (R6 PII/secret regex blocklist + scan)

## Work Summary

Implemented the leak-guard module — the **NFR-007 PII boundary** for u2.
The module exposes `LeakGuardHit` (a NamedTuple with `pattern_name` and a
truncated `match_text`) and `scan(markdown) -> LeakGuardHit | None`.
Six R6 patterns are checked in deterministic priority order; the generic
long-base64 pattern is filtered through `_is_in_url_context` to avoid
false positives on URL paths.

29 new tests across one file. The Step 3 sub-agent review surfaced a real
ReDoS risk in FD R6's literal email regex (`\S+@\S+\.\S+`), which has
overlapping `\S+` quantifiers. Tightened to `[^\s@]+@[^\s@]+\.[^\s@]+`
— same matches in practice, no overlap, linear backtracking. Audit-log
entry per AC-D.4 documents this regex amendment.

## Files Changed

### Created
- `src/investo/briefing/leak_guard.py` (115 lines) — closed `_PATTERNS`
  tuple + `_URL_CONTEXT_FILTERED` frozenset + `_is_in_url_context` helper
  + `scan()` + `LeakGuardHit` NamedTuple. Module docstring documents the
  3-step change discipline (code + test + audit) per AC-D.4.
- `tests/unit/briefing/test_leak_guard.py` (220 lines) — 29 tests:
  hit cases (one canonical example per R6 pattern, parameterized for
  PAT prefixes and Korean phone formats) + miss cases (clean Korean and
  English text, URL-contained base64, room-number-not-phone, sub-threshold
  base64) + URL-context boundary tests + Step 3 review-driven regression
  pins (ReDoS, autolink, mailto).

### Modified
- `aidlc-docs/construction/plans/u2-briefing-code-generation-plan.md` —
  Step 3 sub-tasks `[x]` with detailed status notes (review verdicts,
  AC-D.4 amendment record)
- `aidlc-docs/aidlc-state.md` — u2 CG progress 2/10 → 3/10
- `aidlc-docs/audit.md` — Step 3 entry prepended

## Key Decisions

| Decision | Rationale |
|----------|-----------|
| Email regex refinement to `[^\s@]+@[^\s@]+\.[^\s@]+` | Step 3 sub-agent H1: original `\S+@\S+\.\S+` has overlapping quantifiers → quadratic backtracking on adversarial LLM output. Refinement is semantically equivalent for valid email matches (an `@` in the local part is theoretically valid syntax but never seen in practice). Audit entry per AC-D.4 (this is a closed-list change). |
| Pattern priority (`github_pat` first, `oauth_long_base64` last) | Specific credential patterns must win over the generic base64 pattern. A `ghp_...`-shaped string should be reported as `github_pat`, not `oauth_long_base64`. Test `test_first_pattern_wins` pins this. |
| URL-context exclusion only on `oauth_long_base64` | Other R6 patterns are specific enough that URL-embedded matches are still meaningful leaks (a real `AKIA...` in a URL path IS still a leak). Only the generic base64 pattern needs URL filtering. |
| `_is_in_url_context` walks back 200 chars | Enough to catch typical markdown link forms `[text](https://...)` and inline `https://...`; bounded enough that scan stays linear in markdown length. Boundary tested at 250-char filler in `test_long_base64_with_url_outside_lookback_window_is_flagged`. |
| `match_text[:64]` codepoint slice (not byte) | All R6 patterns match ASCII-alphabet content (PAT, AWS key, JWT, base64, email local-part, phone digits). Codepoint count is byte count for these. Safe for the use case. |
| Skip `oauth_long_base64` URL-safe alphabet expansion (TD-leak-guard-2) | Defer per AC-D.5 "wait for ops evidence" pattern; matches u1's deferral of runtime metrics. Re-evaluate when a real false-negative is observed. |

## Code Review Results

Sub-agent review (general-purpose): **APPROVE_WITH_FIXES**.

| Category | Status |
|----------|--------|
| Correctness | ✅ |
| Safety / Security | ⚠️ → ✅ (H1 fixed: email ReDoS) |
| Reliability (FP control) | ⚠️ → ✅ (H2/M2 tests added) |
| Maintainability | ✅ |
| Test Coverage | ✅ |

Findings: 0 Critical / 2 Highs / 1 Medium / 3 Lows + 2 TECH-DEBT candidates.
- **H1** Email regex ReDoS — APPLIED (tightened regex + regression test).
- **H2** Autolink markdown `<https://...>` form — APPLIED (regression
  test pins current correct exclusion).
- **M1** Email match-text trailing punctuation — implicitly resolved by
  H1 (the `[^\s@]` class trims punctuation cleanly).
- **M2** `mailto:` test — APPLIED (regression test documents that
  mailto links in public archive are flagged as email leaks).
- **L1** URL-safe base64 alphabet (`-_`) — design observation; matches
  FD R6 verbatim; skipped.
- **L2** 199/200-char boundary test — cosmetic; skipped.
- **L3** Codepoint vs byte slice — sound for use case.
- **TD-leak-guard-1** — applied as part of H1.
- **TD-leak-guard-2** (URL-safe base64) — deferred.

## Quality Gate

- `ruff check .` ✅
- `ruff format --check .` ✅ (46 files already formatted)
- `mypy --strict src/` ✅ (18 source files; +1 from Step 2's 17)
- `pytest -q` ✅ **294/294 passed in 3.26s**
  - +29 new tests in `test_leak_guard.py`
  - Includes ReDoS regression test (timing assertion < 1.0s — actual ~ms)

## Potential Risks

- **R-Step3-1**: A future LLM update could emit OAuth tokens in URL-safe
  base64 format (`-_` instead of `+/`). The current regex would not
  catch them (TD-leak-guard-2 / L1). Mitigation: u3 publisher's
  pre-publish review window is the human safety net; track via DEBT
  registry if/when seen.
- **R-Step3-2**: The `_is_in_url_context` 200-char lookback could miss a
  legitimate URL exclusion if the URL starts more than 200 chars before
  the candidate. Acceptable: a base64 blob 200+ chars after a URL is
  unlikely to be the URL's own content.

## TECH-DEBT Items

None added. None resolved. (TD-leak-guard-1 was identified but applied
inline as H1 fix; TD-leak-guard-2 is deferred per AC-D.5 pattern but
not formally registered in `docs/TECH-DEBT.md` until evidence emerges.)

## Next Step

**Step 4** — `errors.py`: `BriefingGenerationError` (E4) +
`SubprocessOutcome` (E5) + 1024-byte stderr cap test for AC-7.4.

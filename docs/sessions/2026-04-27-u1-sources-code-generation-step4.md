# Session Log: 2026-04-27 — u1 sources — Code Generation Step 4 (`_sanitize.py`)

## Overview
- **Date**: 2026-04-27
- **Unit**: u1 sources
- **Stage**: Code Generation
- **Step**: 4 of 10 — HTML strip helper

## Work Summary
Implemented `_sanitize.py` with a single public function `strip_html` that
reduces feed-derived HTML to plain text. Pipeline: `bleach.clean(tags=[],
strip=True, strip_comments=True)` → `html.unescape` → Unicode-aware
whitespace collapse via `re.compile(r"\s+")`. The whitespace regex matches
Unicode whitespace (U+00A0 NBSP, U+3000 ideographic space) which is the
right default for CJK feeds.

Before writing tests I probed the actual bleach behavior on edge cases
(`<script>`, `<br/>`, lone `<`, `&amp;amp;`, etc.) so test expectations
match observed library output rather than wishful behavior. The
`<script>alert(1)</script>` case: bleach strips the wrapper but keeps the
inner text — XSS-safe because the result contains no `<` / `>` and so
cannot be re-parsed as HTML downstream.

`mypy --strict` initially failed because `bleach` lacks bundled type
stubs; added `types-bleach>=6` to dev dependencies and reran.

Sub-agent code review: **APPROVE_WITH_NOTES** — 0 Critical/High/Medium, 4
Lows, 1 TECH-DEBT. L2/L3/L4 applied; L1 (redundant explicit kwarg) is
defensible and kept. DEBT-004 registered for the long-term bleach→nh3
migration.

## Files Changed
- Created:
  - `src/investo/sources/_sanitize.py` — `strip_html` pipeline
  - `tests/unit/sources/test_sanitize.py` — 25 anchor tests
  - `docs/sessions/2026-04-27-u1-sources-code-generation-step4.md` — this file
- Modified:
  - `pyproject.toml` — added `types-bleach>=6` to dev deps
  - `docs/TECH-DEBT.md` — added DEBT-004
  - `aidlc-docs/aidlc-state.md` — Step 4/10 ✅
  - `aidlc-docs/audit.md` — Step 4 audit log entry
  - `aidlc-docs/construction/plans/u1-sources-code-generation-plan.md` — Step 4 marked complete

## Key Decisions
| Decision | Rationale |
|----------|-----------|
| Probe bleach behavior empirically before writing tests | Bleach's exact handling of `<script>`, `<br/>`, lone `<`, etc. is library-version-specific. Pinning observed behavior produces sharper assertions and avoids "wishful" tests that paper over a future-incompatible upgrade. |
| Use `bleach.clean(tags=[], strip=True, strip_comments=True)` then `html.unescape` (not the reverse order) | The output is plain text consumed by markdown rendering. There is no second HTML parse pass, so `&lt;script&gt;` → literal `<script>` in the output is safe (text, never re-parsed). Reverse order would let entities reintroduce angle brackets *before* the tag stripper sees them — strictly worse. |
| Use `re.compile(r"\s+")` (matches Unicode whitespace) | CJK feeds use U+3000 ideographic space; the default Unicode-matching `\s` collapses it like ASCII whitespace, which is what readers expect. Documented inline. |
| Add `types-bleach>=6` to dev deps rather than `# type: ignore[import-untyped]` | mypy strict is the project standard; an explicit stub install scales better than per-import ignores and gives mypy the actual API surface. |
| Keep the explicit `strip_comments=True` kwarg (review L1) | Defaults to `True` in bleach 6, but the explicit kwarg documents intent in case bleach ever flips the default. Cosmetic. |

## Code Review Results
Sub-agent (general-purpose) per dev-investo §5.1.

| Category | Status |
|----------|--------|
| Correctness | ✅ — `bleach.clean` → `html.unescape` order is safe; XSS test pins no `<`/`>` in output |
| Safety | ✅ — script/style content survives as plain text only; comparison expressions like `"price < 100"` round-trip cleanly |
| Reliability | ✅ — empty/whitespace input handled; idempotence verified |
| Maintainability | ✅ (after L2/L4) — Unicode-whitespace behavior documented inline; test comments reworded to be local |
| Test Coverage | ✅ — 25 anchor tests, all paths exercised |

**Issues addressed in-step**:
- L2 — added Unicode-whitespace inline comment in `_sanitize.py`
- L3 — added `test_comparison_expression_preserved` for `"price < 100"` / `"a < b > c"`
- L4 — reworded `test_script_tag_content_neutralized` comment to keep the assertion local

**Issues skipped** (with rationale):
- L1 — `strip_comments=True` is the bleach 6 default but explicit kwarg documents intent and survives any future default flip. Defensible.

**Issues registered**:
- DEBT-004 (Low) — bleach is in maintenance-only mode; `nh3` (Rust-based, active) is the recommended successor. Single-function module makes migration trivial when needed.

## Potential Risks
- Bleach version drift: a future bleach upgrade could change `<script>` content handling. The `test_script_tag_content_neutralized` test asserts `result == "alert(1)"`; if a future version drops the content, this test will fail loudly with a clear signal — that's the desired behavior.
- `types-bleach` version may lag behind `bleach` releases. If bleach gets a 7.x release before types-bleach catches up, dev install will need a `--ignore-installed` workaround. Not actionable until it happens.

## TECH-DEBT Items
- DEBT-004 — `_sanitize.py` depends on `bleach` (maintenance-mode); `nh3` is the recommended successor (Low; revisit on bleach EOL)

## Next Step
Step 5: `src/investo/sources/protocol.py` — `SourceFetchError` (relocated
from `_retry.py`) + `SourceAdapter` Protocol with class-level `name` /
`category` and `async fetch(client, window)`. Tests pin the contract.

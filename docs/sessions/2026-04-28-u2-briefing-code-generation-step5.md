# Session Log: 2026-04-28 - u2 briefing - Code Generation Step 5

## Overview
- **Date**: 2026-04-28
- **Unit**: u2 briefing
- **Stage**: Code Generation
- **Step**: Step 5 — `prompts.py` (4 Final[str] constants + AC-5.1 + AC-5.2/5.3
  sentinel-grep test + str.format convention)

## Work Summary

Implemented the prompt-template module — the **NFR-005 prompt code
separation core**. Four `Final[str]` constants (`STAGE1_SYSTEM`,
`STAGE1_USER_TEMPLATE`, `STAGE2_SYSTEM`, `STAGE2_USER_TEMPLATE`) hold
the Stage 1 / Stage 2 prompt skeletons per FD L2 / L3. SYSTEM constants
are concatenated as literals (never `.format()`-ed); USER templates use
`str.format(**kwargs)` with documented placeholders.

The AC-5.2 / AC-5.3 sentinel-grep test enforces the NFR-005 module
boundary: prompt body strings appear only in `prompts.py`. The test
will continue to enforce as Steps 6 (`claude_code.py`) and 8
(`pipeline.py`) land — those modules MUST import the constants, not
inline them.

18 new tests across one file. All passing.

## Files Changed

### Created
- `src/investo/briefing/prompts.py` (140 lines) — 4 Final[str] prompt
  constants + module docstring documenting (a) the substitution
  convention, (b) the SYSTEM-never-formatted invariant, (c) the
  caller's brace-escaping obligation for `grouped_sections`, (d) the
  defense-in-depth layering with `leak_guard.scan`.
- `tests/unit/briefing/test_prompts.py` (200 lines) — 18 tests covering
  AC-5.1 (Final[str] populated), Stage 1 anchors (role + JSON schema +
  section ID legend + section IDs 2-5; explicit absence of ⑦), Stage 2
  anchors (six fixed Korean section headers + R5 disclaimer exclusion +
  R8 Korean+ticker rule + PII-emission prohibition), placeholder
  substitution round-trip, format-idempotence-under-repeat,
  AC-5.2/5.3 sentinel-grep with anti-tautology check, SYSTEM-never-formatted
  convention pinned via `pytest.raises(KeyError, IndexError, ValueError)`,
  cross-module collision check (`## ① 요약` not in DISCLAIMER).

### Modified
- `aidlc-docs/construction/plans/u2-briefing-code-generation-plan.md` —
  Step 5 sub-tasks `[x]`
- `aidlc-docs/aidlc-state.md` — u2 CG progress 4/10 → 5/10
- `aidlc-docs/audit.md` — Step 5 entry prepended

## Key Decisions

| Decision | Rationale |
|----------|-----------|
| SYSTEM constants are NEVER `.format()`-ed | Stage 1 system prompt contains literal `{` / `}` in the JSON schema example. Calling `.format()` would raise. Convention locked by `test_stage1_system_format_call_raises_key_error`. Caller code (pipeline.py, Step 8) merges via `f"{SYSTEM}\n\n{USER_TEMPLATE.format(...)}"` — concatenation, not formatting. |
| 3 placeholders in `STAGE2_USER_TEMPLATE` (not 6) | The FD L3 user prompt has per-section bullet lists that vary per run. Two designs: (a) 5 per-section placeholders + unassigned + target_date = 7; (b) 1 grouped blob + unassigned + target_date = 3. Chose (b) — the rendering helper in pipeline.py builds the grouped blob, the prompt template stays simple and review-friendly. |
| Sentinel-grep test runs from Step 5 | The grep iterates every `*.py` under `src/investo/briefing/` except `prompts.py`. Currently catches accidental inlining in `disclaimer.py`, `leak_guard.py`, `errors.py`. When Steps 6 and 8 land, the same test continues to enforce. Anti-tautology test (`test_prompts_file_actually_contains_the_sentinels`) ensures the sentinels are in `prompts.py` itself. |
| `STAGE2_SYSTEM` includes concrete English-token examples (AAPL, MSFT, S&P 500, $, ¥, €) | Gives the LLM anchors for the R8 "Korean prose with English tickers/index/currency preserved" rule. Without examples the LLM may hallucinate Korean transliterations like `에스피500`. |
| Caller's brace-escaping obligation documented in module docstring (M-1 fix) | When `pipeline.py` builds `grouped_sections` from item titles/summaries that may legitimately contain `{` / `}`, it must escape them as `{{` / `}}` before substitution. Documented at the contract surface so Step 8 implementer doesn't miss it. |

## Code Review Results

Sub-agent review (general-purpose): **APPROVE (ship-ready for Step 5)**.

| Category | Status |
|----------|--------|
| Correctness | ✅ |
| str.format Safety | ✅ |
| Reliability | ⚠️ → ✅ (M-1 documented; Step 8 owns the implementation) |
| Maintainability | ✅ |
| Test Coverage | ✅ |

Findings: 0 Critical / 0 High / 2 Mediums / 3 Lows + 2 TECH-DEBT
candidates.
- **M-1** Brace contamination in `grouped_sections` payload —
  forward-looking concern; APPLIED as caller-obligation docstring
  section. Step 8's `build_section_plan` rendering will own the actual
  escaping.
- **M-2** Defense-in-depth not documented in code — APPLIED as
  "Defense in depth (NFR-007 R6)" docstring section linking
  prompt-side hint + leak_guard.scan post-validation safety net.
- **L-1** Sentinel rephrase ("Section ID legend" too generic) — skipped.
  Current sentinel set is unique enough.
- **L-2** `pytest.raises(KeyError)` test for SYSTEM-never-formatted —
  APPLIED.
- **L-3** Disclaimer collision check (`## ① 요약` not in DISCLAIMER) —
  APPLIED.
- **TD-prompts-001** locked via L-2 fix.
- **TD-prompts-002** (brace escaping in `build_section_plan`) deferred
  to Step 8 plan as explicit caller obligation.

## Quality Gate

- `ruff check .` ✅
- `ruff format --check .` ✅ (50 files already formatted)
- `mypy --strict src/` ✅ (20 source files; +1 from Step 4's 19)
- `pytest -q` ✅ **332/332 passed in 3.45s**
  - +18 new tests in `test_prompts.py`

## Potential Risks

- **R-Step5-1**: Future contributor adds `jinja2` or `pyyaml` to
  prompts.py for "richer templating". Mitigated by AC-5.5 + Step 10
  CI grep; for now the convention lives in the module docstring.
- **R-Step5-2**: Stage 2 prompt asks the LLM to write Korean prose;
  output variance is real (FD R11). The leak_guard is the safety net,
  but a particularly creative LLM could still embed PII patterns
  (e.g. fictitious phone numbers in narrative). Test fixture-based
  determinism (R9 / Step 7 FakeClaudeRunner) keeps CI stable.

## TECH-DEBT Items

None added to registry. TD-prompts-001 and TD-prompts-002 were
identified by the agent and resolved inline (TD-001 → L-2 test;
TD-002 → docstring caller-obligation, full implementation in Step 8).

## Next Step

**Step 6** — `claude_code.py`: `RetryBudget` (FD L4) +
`call_claude_code` subprocess wrapper (asyncio.to_thread, list-form
only) + token-not-in-code self-check for AC-2.5/7.2.

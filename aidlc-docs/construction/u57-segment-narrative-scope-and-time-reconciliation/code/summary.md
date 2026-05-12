# u57 Segment Narrative Scope + Time-State Reconciliation — Code Generation Summary

**Date**: 2026-05-13
**Unit**: u57 segment-narrative-scope-and-time-reconciliation
**Status**: Complete (8/8 steps, 45/45 checkboxes)
**FR**: FR-013

## Goal

End 4 cross-segment narrative defects from `archive/.../2026-05-11.md`:
1. Time-state contradictions (domestic cited "US 하락 출발" while US closed +0.5% same day).
2. Cross-market over-promotion (Iran/oil in domestic §② core).
3. Foreign tickers in domestic watchlist without 국내 linkage.
4. Shared macro (UST/oil/Fed) duplicated across us-equity + crypto §② with no segment-specific reinterpretation.

Solution: (a) BundleContext pre-computation, (b) time-state regex catalogue, (c) deterministic cross-segment linkage lint, (d) `CROSS_MARKET_CORE_ALLOWED` allow-list, (e) shared-macro `## ⓪` H2 surface.

## Quality Gate

| Gate | Result |
|------|--------|
| `ruff check .` | clean (322 files) |
| `ruff format --check` | clean (323 files) |
| `mypy --strict src/` | 126 source files, 0 issues |
| `pytest -q` | **2297 passed** (2206 → +91, plan est. +52-70) |
| `mkdocs build --strict` | clean |

## Key Deliverables

- **`briefing/time_state.py`** — `TimeState` Literal[6] + `TIME_STATE_PATTERNS` regex catalogue (`pre-market/open/intraday/close/post-close/scheduled`). `close` wins on conflict.
- **`models/bundle_context.py`** — `MarketStateSummary` + `BundleContext` + `CROSS_MARKET_CORE_ALLOWED = {"geopolitical_oil_macro","fed_policy_event","global_systemic_risk"}`.
- **`orchestrator/bundle_context.py::compute_bundle_context`** — Pre-Stage-2 reducer derives each segment's `close_state` from latest-time-stated routed item. Shared macro themes hit by ≥2 segments surface in `shared_macro_block`.
- **`publisher/cross_segment_lint.py`** — three deterministic lints:
  - `lint_domestic_foreign_linkage` (AC1, REJECT-tier): foreign ticker in domestic paragraph requires `\d{6}` or linkage keyword `{국내 영향, 환율 경로, 코스피 연관, 수급 영향, 외국인 매매, 환율, 원/달러}` in same `\n\n` block.
  - `lint_native_fact_priority` (AC2, WARN-tier): segment §② first H3 primary noun must match segment-native allowlist.
  - `lint_time_state_consistency` (AC1.5, REJECT-tier): if any segment's `close_state == close`, sibling segments must not cite that market as `출발/장중/개장`.
- **`publisher/shared_macro.py::inject_shared_macro_block`** — idempotent `## ⓪ 오늘의 매크로` H2 above `## 한눈에 보기` (u51 TL;DR).
- Stage-2 prompt: BC-1~BC-4 rule block + `{bundle_context}` JSON placeholder; self-slot = `pending` (anti-self-assert).

## Untestable AC → Measurable Proxy

Plan's 3 untestable DoD items rewritten:
- AC1 "cross-market downgrade unless link explicit" → linkage lint regex (5+ test cases pinned).
- AC2 "native facts ranked above cross-market" → §② first-H3 primary-noun allowlist match.
- AC3 "domestic watchlist no unrelated global tickers" → AC1 mechanism + watchlist strict mode.

All 3 are deterministic regex lints — quality gate passes.

## Key Decisions

- **Option B (pre-comp)** over `SEGMENT_ORDER` reordering. Domestic prompt no longer waits on US generation.
- **Strict-mode default = log-only**. WARN/REJECT structured records emitted; paragraph rewrite reserved for D57-C.
- **Korean word-boundary**: Python `\b` treats Hangul as word char → `\bAAPL\b` fails in `AAPL이`. Switched to `(?<![A-Za-z])` / `(?![A-Za-z])` anchors.
- **R3 module boundary**: `BundleContext` in `models/` so all three sibling units may import.
- **R13 hygiene**: lint extras carry segment / kind / severity / numeric lengths only (pinned by `test_cross_segment_lint_logging.py`).

## Files

**New (12)**:
- `src/investo/briefing/time_state.py`
- `src/investo/models/bundle_context.py`
- `src/investo/orchestrator/bundle_context.py`
- `src/investo/publisher/cross_segment_lint.py`
- `src/investo/publisher/shared_macro.py`
- 7 new test files (+91 tests)

**Modified (8)**:
- `src/investo/briefing/{prompts,pipeline}.py`
- `src/investo/orchestrator/pipeline.py`
- `tests/unit/briefing/test_prompts.py`
- `tests/unit/orchestrator/test_run_pipeline.py`
- `docs/requirements.md` (FR-013)
- `aidlc-docs/aidlc-state.md`
- `aidlc-docs/audit.md`

## TECH-DEBT Candidates

- **D57-A** `FOREIGN_TICKER_PATTERN` static allowlist — auto-sync vs `sources/` ticker registry.
- **D57-B** `lint_native_fact_priority` Korean morphology (KoNLPy) — reduce subject-trailing false-negatives.
- **D57-C** Strict-mode auto-demote rewrite path (currently log-only); `INVESTO_LINT_STRICT` env-var hook reserved.
- **D57-D** Shared-macro auto-strip vs WARN-only — false-positive risk on segment-specific reinterpretation.
